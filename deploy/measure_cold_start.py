"""Measure Lambda cold starts with AWS_LWA_ASYNC_INIT false and true
(spec 08 section 7: the adapter's start-up setting is decided at the start
of Stage B, based on a measurement there; Stage B Round 1 section 3).

    .venv/bin/python deploy/measure_cold_start.py            # plan only: no AWS call
    .venv/bin/python deploy/measure_cold_start.py --confirm  # measure

Free: only GET /health, no Claude call. As the IAM user voltrix-deploy.

1. One warm-up GET /health (the first start after a new image also pulls
   the image; it is shown but not counted).
2. --runs times each setting, alternating, starting with the opposite of
   the current value, so every update really changes the configuration.
   Each update starts fresh execution environments, so the next request
   is a cold start.
3. For each: the time until the first /health 200 through the Function URL,
   and from CloudWatch the REPORT line (Duration, Init Duration, Max Memory
   Used) and any INIT_REPORT line (an Init timeout shows "Status: timeout").
4. At the end AWS_LWA_ASYNC_INIT is put back to its value before the run.
   The owner decides the final value and records it in spec 08.

Exit 0 measured, 1 failed, 5 plan only.
"""

import argparse
import re
import sys
import time
from dataclasses import dataclass, field

from stage_b import (ASYNC_INIT, EXIT_DRY_RUN, EXIT_FAILED, EXIT_OK, FUNCTION, Aws, DeployError,
                     concurrency_note, environment_of, http, join_url, lambda_problems, run_process)

REPORT_RE = re.compile(r"REPORT RequestId: \S+\s+Duration: ([\d.]+) ms\s+Billed Duration: (\d+) ms\s+"
                       r"Memory Size: \d+ MB\s+Max Memory Used: (\d+) MB(?:\s+Init Duration: ([\d.]+) ms)?")
INIT_REPORT_RE = re.compile(r"INIT_REPORT Init Duration: ([\d.]+) ms\s+Phase: (\w+)\s+Status: (\w+)")
HEALTH_DEADLINE_S = 180
LOG_WAIT_S = 90


@dataclass
class Run:
    setting: str
    first_status: int = 0
    seconds: float | None = None
    duration_ms: float | None = None
    billed_ms: int | None = None
    init_ms: float | None = None
    memory_mb: int | None = None
    init_reports: list[str] = field(default_factory=list)

    @property
    def init_timeout(self) -> bool:
        return any("timeout" in r for r in self.init_reports)


def settings_order(current: str, runs: int) -> list[str]:
    first = "true" if current != "true" else "false"
    second = "false" if first == "true" else "true"
    return [first, second] * runs


def time_health(url: str, fetch=http, clock=time.monotonic, pause=time.sleep,
                deadline: float = HEALTH_DEADLINE_S) -> tuple[int, float | None]:
    """(status of the first answer, seconds until a 200 or None)."""
    started = clock()
    first_status = None
    while clock() - started < deadline:
        status, _, _ = fetch("GET", join_url(url, "/health"))
        if first_status is None:
            first_status = status
        if status == 200:
            return first_status, clock() - started
        pause(1.0)
    return first_status or 0, None


def read_reports(run: Run, events: list[dict]) -> bool:
    """Fills run from the log lines; True when a REPORT line was found."""
    found = False
    for event in events:
        message = event.get("message", "")
        match = INIT_REPORT_RE.search(message)
        if match:
            run.init_reports.append(f"{float(match.group(1)):.0f} ms {match.group(2)} {match.group(3)}")
        match = REPORT_RE.search(message)
        if match and not found:
            found = True
            run.duration_ms, run.billed_ms = float(match.group(1)), int(match.group(2))
            run.memory_mb = int(match.group(3))
            run.init_ms = float(match.group(4)) if match.group(4) else None
    return found


def wait_for_reports(run: Run, aws: Aws, start_ms: int, clock=time.monotonic, pause=time.sleep) -> None:
    started = clock()
    while clock() - started < LOG_WAIT_S:
        events = aws.log_events(start_ms, "?REPORT ?INIT_REPORT")
        probe = Run(run.setting)
        if read_reports(probe, events):
            pause(5.0)  # let a late INIT_REPORT line arrive too
            read_reports(run, aws.log_events(start_ms, "?REPORT ?INIT_REPORT"))
            return
        pause(5.0)


def set_async_init(aws: Aws, env: dict[str, str], value: str | None) -> dict[str, str]:
    new_env = {k: v for k, v in env.items() if k != ASYNC_INIT}
    if value is not None:
        new_env[ASYNC_INIT] = value
    aws.update_environment(new_env)
    aws.wait_updated()
    return new_env


def measure(aws: Aws, runs: int, fetch=http, clock=time.monotonic, wall=time.time, pause=time.sleep) -> list[Run]:
    aws.identity()
    configuration = aws.function()["Configuration"]
    problems = lambda_problems(configuration)
    if problems:
        raise DeployError("the function does not match spec 08: " + "; ".join(problems))
    if aws.reserved_concurrency() == 0:
        raise DeployError(f"the function is {concurrency_note(0)[0]}; unthrottle it in the Lambda console first")
    url = aws.function_url()
    env = environment_of(configuration)
    original = env.get(ASYNC_INIT)

    warm = Run("warm-up")
    warm.first_status, warm.seconds = time_health(url, fetch, clock, pause)
    results = [warm]
    try:
        for setting in settings_order(original or "false", runs):
            env = set_async_init(aws, env, setting)
            run = Run(setting)
            start_ms = int(wall() * 1000) - 2000
            run.first_status, run.seconds = time_health(url, fetch, clock, pause)
            wait_for_reports(run, aws, start_ms, clock, pause)
            print(f"  {ASYNC_INIT}={setting}: {fmt(run.seconds, 's')} to /health 200, Init {fmt_ms(run.init_ms)}, "
                  f"Duration {fmt_ms(run.duration_ms)}{', INIT TIMEOUT' if run.init_timeout else ''}", flush=True)
            results.append(run)
    finally:
        set_async_init(aws, env, original)
    return results


def fmt(value, unit):
    return "-" if value is None else f"{value:.1f} {unit}"


def fmt_ms(value):
    return "-" if value is None else f"{value / 1000:.1f} s"


def table(results: list[Run]) -> str:
    lines = [f"| Run | {ASYNC_INIT} | First answer | To /health 200 | Init Duration | Duration | Billed | Max memory | INIT_REPORT |",
             "|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(results):
        lines.append(f"| {'warm-up' if i == 0 else i} | {r.setting if i else '(current)'} | HTTP {r.first_status} | "
                     f"{fmt(r.seconds, 's')} | {fmt_ms(r.init_ms)} | {fmt_ms(r.duration_ms)} | "
                     f"{fmt_ms(r.billed_ms)} | {'-' if r.memory_mb is None else f'{r.memory_mb} MB'} | "
                     f"{'; '.join(r.init_reports) or '-'} |")
    return "\n".join(lines)


def main(argv: list[str] | None = None, runner=run_process) -> int:
    parser = argparse.ArgumentParser(prog="deploy/measure_cold_start.py", description="Lambda cold starts, async init off and on.")
    parser.add_argument("--runs", type=int, default=3, help="cold starts per setting (default 3)")
    parser.add_argument("--confirm", action="store_true", help="really change AWS_LWA_ASYNC_INIT and measure")
    args = parser.parse_args(argv)
    if not args.confirm:
        print(f"Plan: {2 * args.runs} configuration updates of {FUNCTION} ({ASYNC_INIT} alternating), one cold "
              "/health each, then the old value back. Free (no Claude call). No AWS call made. Add --confirm.")
        return EXIT_DRY_RUN
    try:
        results = measure(Aws(runner), args.runs)
    except DeployError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_FAILED
    print()
    print(table(results))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
