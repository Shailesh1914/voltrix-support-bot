"""Tests of the Stage B scripts that use AWS (stage_b.py, push_image.py,
point_lambda.py, check_stage_b.py, measure_cold_start.py), against the fake
account in stage_b_fakes.py. No AWS, no Docker, no network."""

import json

import pytest

import check_stage_b as csb
import measure_cold_start as mcs
import point_lambda as pl
import push_image as pi
import stage_b as sb
from stage_b_fakes import (ACCOUNT, FUNCTION_URL, NEW_DIGEST, NEW_TAG, OLD_DIGEST, OLD_TAG, REGISTRY, TOKEN,
                           FakeCloud)


@pytest.fixture
def cloud():
    return FakeCloud()


# --- stage_b.py -------------------------------------------------------------------


@pytest.mark.parametrize("tag", ["v2-20261113-406e022", "v12-20270101-0123abc"])
def test_release_tags_have_the_d8_format(tag):
    assert sb.check_release_tag(tag) == tag


@pytest.mark.parametrize("tag", ["v2-20261112-d98f7e5-local", "latest", "v2-2026111-406e022", "v2-20261113-406E022",
                                 "2-20261113-406e022", "v2-20261113-406e0221"])
def test_local_latest_and_malformed_tags_are_refused(tag):
    with pytest.raises(sb.DeployError):
        sb.check_release_tag(tag)


def test_the_names_and_region_are_those_of_round_2():
    assert (sb.REGION, sb.FUNCTION, sb.REPOSITORY, sb.PROFILE) == \
        ("ap-south-1", "voltrix-support-bot", "voltrix-support-bot", "voltrix-deploy")
    assert sb.LOG_GROUP == "/aws/lambda/voltrix-support-bot"
    assert sb.LAMBDA_SETTINGS == {"PackageType": "Image", "Architectures": ["x86_64"], "MemorySize": 2048, "Timeout": 60}


def test_child_processes_never_get_aws_credentials_or_anthropic_variables():
    env = sb.child_env({"AWS_ACCESS_KEY_ID": "AKIAX", "AWS_SECRET_ACCESS_KEY": "s", "AWS_SESSION_TOKEN": "t",
                        "AWS_PROFILE": "admin", "AWS_REGION": "us-east-1", "AWS_DEFAULT_REGION": "eu-west-1",
                        "ANTHROPIC_API_KEY": "k", "PATH": "/bin", "HOME": "/h"})
    assert env == {"PATH": "/bin", "HOME": "/h"}


def test_every_aws_call_names_the_profile_and_region(cloud):
    aws = sb.Aws(cloud)
    aws.identity()
    aws.function()
    assert all(args[-6:-1] == ["--profile", "voltrix-deploy", "--region", "ap-south-1", "--output"]
               for args in cloud.commands("aws"))


@pytest.mark.parametrize("arn", [f"arn:aws:iam::{ACCOUNT}:root", f"arn:aws:iam::{ACCOUNT}:user/admin",
                                 f"arn:aws:sts::{ACCOUNT}:assumed-role/Admin/me", "arn:aws:iam::999999999999:user/voltrix-deploy"])
def test_only_the_deployment_user_may_run_the_scripts(cloud, arn):
    cloud.arn = arn
    with pytest.raises(sb.DeployError, match="only as the IAM user voltrix-deploy"):
        sb.Aws(cloud).identity()


def test_an_aws_failure_carries_its_error_code(cloud):
    aws = sb.Aws(cloud)
    aws.identity()
    assert aws.ecr_image("v2-20990101-0000000") is None  # ImageNotFoundException means "absent"
    cloud.images = None  # anything else is an error, not "absent"
    with pytest.raises(Exception):
        aws.ecr_image("v2-20990101-0000000")


def test_the_spec_function_has_no_problems(cloud):
    assert sb.lambda_problems(cloud.configuration) == []


@pytest.mark.parametrize("change, expected", [
    (lambda c: c.update(MemorySize=1024), "MemorySize"),
    (lambda c: c.update(Timeout=30), "Timeout"),
    (lambda c: c.update(Architectures=["arm64"]), "Architectures"),
    (lambda c: c.update(PackageType="Zip"), "PackageType"),
    (lambda c: c.update(Role=f"arn:aws:iam::{ACCOUNT}:role/other"), "execution role"),
    (lambda c: c.update(VpcConfig={"SubnetIds": ["subnet-1"]}), "VPC"),
    (lambda c: c["Environment"]["Variables"].update(VOLTRIX_SECRETS_SOURCE="file"), "VOLTRIX_SECRETS_SOURCE"),
    (lambda c: c["Environment"]["Variables"].pop("HANDOFF_DIR"), "HANDOFF_DIR"),
])
def test_differences_from_spec_08_section_7_are_found(cloud, change, expected):
    change(cloud.configuration)
    assert any(expected in p for p in sb.lambda_problems(cloud.configuration))


def test_a_secret_variable_on_the_function_is_named_but_its_value_never_shown(cloud):
    cloud.configuration["Environment"]["Variables"]["VOLTRIX_ACCESS_CODE"] = "real-code-value-123"
    cloud.configuration["Environment"]["Variables"]["ANTHROPIC_API_KEY"] = "sk-ant-api03-value"
    problems = " ".join(sb.lambda_problems(cloud.configuration))
    assert "VOLTRIX_ACCESS_CODE" in problems and "ANTHROPIC_API_KEY" in problems
    assert "real-code-value-123" not in problems and "sk-ant-api03-value" not in problems


def test_join_url_handles_the_function_url_slash():
    assert sb.join_url(FUNCTION_URL, "/health") == "https://abc123.lambda-url.ap-south-1.on.aws/health"
    assert sb.join_url("http://127.0.0.1:8080", "/ask") == "http://127.0.0.1:8080/ask"


# --- push_image.py ----------------------------------------------------------------


def test_push_without_confirm_makes_no_aws_call(cloud, capsys):
    assert pi.main([NEW_TAG], runner=cloud) == sb.EXIT_DRY_RUN
    assert cloud.commands("aws") == [] and cloud.changes() == []
    assert "No AWS call made" in capsys.readouterr().out


def test_push_logs_in_with_stdin_pushes_verifies_and_logs_out(cloud, capsys):
    assert pi.main([NEW_TAG, "--confirm"], runner=cloud) == sb.EXIT_OK
    remote = f"{REGISTRY}/voltrix-support-bot:{NEW_TAG}"
    docker = [args[1:] for args in cloud.commands("docker")]
    assert ["login", "--username", "AWS", "--password-stdin", REGISTRY] in docker
    assert ["tag", f"voltrix-support-bot:{NEW_TAG}", remote] in docker
    assert ["push", remote] in docker
    assert docker[-2:] == [["logout", REGISTRY], ["image", "rm", remote]]
    assert not cloud.logged_in
    out = capsys.readouterr()
    assert NEW_DIGEST in out.out
    assert TOKEN not in out.out + out.err
    assert all(TOKEN not in " ".join(args) for args, _ in cloud.calls)  # only ever on stdin


def test_push_logs_out_even_when_the_push_fails(cloud):
    original = cloud.docker

    def failing(a, input):
        return pi_fail() if a[0] == "push" else original(a, input)

    def pi_fail():
        from stage_b_fakes import cp
        return cp(returncode=1, stderr="denied")

    cloud.docker = failing
    assert pi.main([NEW_TAG, "--confirm"], runner=cloud) == sb.EXIT_FAILED
    assert cloud.commands("docker", "logout") and not cloud.logged_in


@pytest.mark.parametrize("setup, message", [
    (lambda c: setattr(c, "mutability", "MUTABLE"), "Immutable"),
    (lambda c: c.images.__setitem__(NEW_TAG, {"imageDigest": "sha256:" + "c" * 64}), "already in ECR"),
    (lambda c: setattr(c, "arn", f"arn:aws:iam::{ACCOUNT}:user/admin"), "voltrix-deploy"),
])
def test_push_refuses_before_logging_in(cloud, capsys, setup, message):
    setup(cloud)
    assert pi.main([NEW_TAG, "--confirm"], runner=cloud) == sb.EXIT_FAILED
    assert message in capsys.readouterr().err
    assert not cloud.commands("docker", "login") and not cloud.commands("docker", "push")


def test_push_refuses_a_local_tag_a_missing_image_or_the_wrong_platform(cloud, capsys):
    assert pi.main(["v2-20261112-d98f7e5-local", "--confirm"], runner=cloud) == sb.EXIT_FAILED
    assert pi.main(["v2-20261114-0000000", "--confirm"], runner=cloud) == sb.EXIT_FAILED
    cloud.local[NEW_TAG]["Architecture"] = "arm64"
    assert pi.main([NEW_TAG, "--confirm"], runner=cloud) == sb.EXIT_FAILED
    assert "linux/amd64" in capsys.readouterr().err
    assert cloud.commands("aws") == []


def test_push_refuses_an_image_not_built_from_the_commit_in_its_tag(cloud, capsys):
    cloud.local[NEW_TAG]["Config"]["Labels"]["org.opencontainers.image.revision"] = "unknown"
    assert pi.main([NEW_TAG], runner=cloud) == sb.EXIT_FAILED
    assert "commit in its tag" in capsys.readouterr().err


def test_push_fails_when_ecr_holds_an_index_lambda_cannot_run(cloud, capsys):
    cloud.push_media_type = "application/vnd.oci.image.index.v1+json"
    assert pi.main([NEW_TAG, "--confirm"], runner=cloud) == sb.EXIT_FAILED
    assert "provenance" in capsys.readouterr().err


def test_push_fails_when_the_ecr_digest_differs(cloud, capsys):
    cloud.push_digest = "sha256:" + "d" * 64
    assert pi.main([NEW_TAG, "--confirm"], runner=cloud) == sb.EXIT_FAILED
    assert "differs" in capsys.readouterr().err


# --- point_lambda.py --------------------------------------------------------------


def pushed(cloud, tag=NEW_TAG, digest=NEW_DIGEST):
    from stage_b_fakes import SINGLE
    cloud.images[tag] = {"imageDigest": digest, "imageManifestMediaType": SINGLE, "imageTags": [tag]}


def test_point_without_confirm_only_reads(cloud, capsys):
    pushed(cloud)
    assert pl.main([NEW_TAG], runner=cloud) == sb.EXIT_DRY_RUN
    assert not cloud.commands("aws", "lambda", "update-function-code")
    assert not cloud.commands("aws", "lambda", "update-function-configuration")
    out = capsys.readouterr().out
    assert f"Rollback afterwards: .venv/bin/python deploy/point_lambda.py {OLD_TAG} --confirm" in out


def test_point_updates_the_image_then_only_image_tag(cloud):
    pushed(cloud)
    before = dict(cloud.configuration["Environment"]["Variables"])
    assert pl.main([NEW_TAG, "--confirm"], runner=cloud) == sb.EXIT_OK
    lam = [args[2] for args in cloud.commands("aws", "lambda")]
    code_at, config_at = lam.index("update-function-code"), lam.index("update-function-configuration")
    assert code_at < config_at
    assert lam[code_at + 1] == "wait" and lam[config_at + 1] == "wait" and lam[code_at - 1] == "wait"
    (update,) = cloud.commands("aws", "lambda", "update-function-code")
    assert update[update.index("--image-uri") + 1] == f"{REGISTRY}/voltrix-support-bot:{NEW_TAG}"
    assert cloud.configuration["Environment"]["Variables"] == {**before, "IMAGE_TAG": NEW_TAG}
    assert cloud.code["ResolvedImageUri"] == f"{REGISTRY}/voltrix-support-bot@{NEW_DIGEST}"


def test_rollback_is_the_same_command_with_the_previous_tag(cloud):
    pushed(cloud)
    assert pl.main([NEW_TAG, "--confirm"], runner=cloud) == sb.EXIT_OK
    assert pl.main([OLD_TAG, "--confirm"], runner=cloud) == sb.EXIT_OK
    assert cloud.code["ResolvedImageUri"] == f"{REGISTRY}/voltrix-support-bot@{OLD_DIGEST}"
    assert cloud.configuration["Environment"]["Variables"]["IMAGE_TAG"] == OLD_TAG


def test_point_does_nothing_when_the_tag_is_already_live(cloud, capsys):
    assert pl.main([OLD_TAG, "--confirm"], runner=cloud) == sb.EXIT_OK
    assert "Nothing to do" in capsys.readouterr().out
    assert not cloud.commands("aws", "lambda", "update-function-code")


@pytest.mark.parametrize("setup, message", [
    (lambda c: None, "not in ECR"),  # NEW_TAG not pushed
    (lambda c: (pushed(c), c.configuration.update(MemorySize=512)), "MemorySize"),
    (lambda c: (pushed(c), c.configuration["Environment"]["Variables"].update(VOLTRIX_ANTHROPIC_API_KEY="x")),
     "VOLTRIX_ANTHROPIC_API_KEY"),
])
def test_point_refuses_without_changing_anything(cloud, capsys, setup, message):
    setup(cloud)
    assert pl.main([NEW_TAG, "--confirm"], runner=cloud) == sb.EXIT_FAILED
    assert message in capsys.readouterr().err
    assert not cloud.commands("aws", "lambda", "update-function-code")
    assert not cloud.commands("aws", "lambda", "update-function-configuration")


@pytest.mark.parametrize("concurrency, shown, flagged", [
    (None, "no reserved concurrency (the account limit of 10 is the cap)", False),
    (0, "THROTTLED", False),
    (2, "2 reserved, but the decision is no reserved concurrency", True),
])
def test_point_shows_the_concurrency_setting(cloud, capsys, concurrency, shown, flagged):
    pushed(cloud)
    cloud.concurrency = concurrency
    assert pl.main([NEW_TAG], runner=cloud) == sb.EXIT_DRY_RUN  # never refused for this
    out = capsys.readouterr().out
    assert shown in out
    assert ("<- check in the Lambda console" in out) == flagged


def test_nothing_expects_reserved_concurrency_2():
    assert sb.concurrency_note(None)[1] and sb.concurrency_note(0)[1]
    assert not sb.concurrency_note(2)[1]


def test_a_throttled_function_can_still_be_deployed(cloud):
    pushed(cloud)
    cloud.concurrency = 0
    assert pl.main([NEW_TAG, "--confirm"], runner=cloud) == sb.EXIT_OK


def test_point_fails_when_the_function_does_not_run_the_tag_afterwards(cloud, capsys):
    pushed(cloud)
    real = cloud.aws

    def stale(a):
        result = real(a)
        if a[:2] == ["lambda", "update-function-code"]:
            cloud.code = {"ResolvedImageUri": f"{REGISTRY}/voltrix-support-bot@{OLD_DIGEST}"}
        return result

    cloud.aws = stale
    assert pl.main([NEW_TAG, "--confirm"], runner=cloud) == sb.EXIT_FAILED
    assert "not the digest" in capsys.readouterr().err


# --- check_stage_b.py -------------------------------------------------------------


GOOD_HEADERS = {"x-request-id": "1b4e28ba-2fa1-4d2b-883f-0016d3cca427"}


def fake_bot(health=None, ask=(401, '{"error": "access denied"}'), page=None, docs=404, headers=GOOD_HEADERS):
    calls = []

    def fetch(method, url, headers_in=None, body=None, timeout=None):
        calls.append((method, url, headers_in, body))
        path = "/" + url.split(".on.aws/", 1)[1]
        if path == "/health":
            return 200, {}, json.dumps(health or {"status": "ok", "kb_version": "v2", "image_tag": NEW_TAG, "model_id": "m"})
        if path == "/ask":
            return ask[0], dict(headers), ask[1]
        if path == "/":
            return page or (200, {"content-security-policy": "default-src 'none'"}, "<p>Synthetic data only.</p>")
        return docs, {}, '{"detail":"Not Found"}'
    return fetch, calls


def test_check_stage_b_passes_against_a_correct_bot():
    fetch, calls = fake_bot()
    report = csb.run(FUNCTION_URL, NEW_TAG, "v2", fetch=fetch)
    assert report.ok, report.rows
    asks = [c for c in calls if c[1].endswith("/ask")]
    assert len(asks) == 3
    assert all(c[2].get("X-Access-Code") in (None, csb.WRONG_CODE) for c in asks)  # never a real code: no paid call


@pytest.mark.parametrize("bot, failing", [
    (dict(health={"status": "ok", "kb_version": "v1", "image_tag": NEW_TAG}), "AC-D2"),
    (dict(health={"status": "ok", "kb_version": "v2", "image_tag": OLD_TAG}), "image_tag"),
    (dict(ask=(200, '{"status": "answered"}')), "AC-D3"),
    (dict(headers={}), "X-Request-Id"),
    (dict(page=(200, {}, "<p>Synthetic data only.</p>")), "Content-Security-Policy"),
    (dict(docs=200), "/docs"),
    (dict(ask=(401, '{"error": "access denied", "k": "sk-ant-api03-x"}')), "key prefix"),
])
def test_check_stage_b_finds_each_problem(bot, failing):
    fetch, _ = fake_bot(**bot)
    report = csb.run(FUNCTION_URL, NEW_TAG, "v2", fetch=fetch)
    assert any(failing in name for name, passed, _ in report.rows if not passed), report.rows


def test_check_stage_b_reads_url_and_tag_from_aws_as_the_deploy_user(cloud):
    assert csb.target_from_aws(sb.Aws(cloud)) == (FUNCTION_URL, OLD_TAG)
    assert cloud.commands("aws", "sts") and cloud.changes() == []


def test_check_stage_b_stops_when_the_function_is_throttled(cloud):
    cloud.concurrency = 0
    with pytest.raises(sb.DeployError, match="THROTTLED"):
        csb.target_from_aws(sb.Aws(cloud))


def test_check_stage_b_with_url_and_tag_makes_no_aws_call(cloud, capsys):
    fetch, _ = fake_bot(health={"status": "ok", "kb_version": sb.kb_version(), "image_tag": NEW_TAG})
    assert csb.main(["--url", FUNCTION_URL, "--tag", NEW_TAG], runner=cloud, fetch=fetch) == 0
    assert cloud.calls == []


# --- measure_cold_start.py --------------------------------------------------------


def test_settings_alternate_starting_with_a_real_change():
    assert mcs.settings_order("false", 2) == ["true", "false", "true", "false"]
    assert mcs.settings_order("true", 1) == ["false", "true"]


def test_report_lines_are_parsed():
    run = mcs.Run("false")
    events = [
        {"message": "INIT_REPORT Init Duration: 9999.71 ms\tPhase: init\tStatus: timeout\n"},
        {"message": "REPORT RequestId: 1-2-3\tDuration: 14230.55 ms\tBilled Duration: 24231 ms\tMemory Size: 2048 MB"
                    "\tMax Memory Used: 811 MB\tInit Duration: 10001.02 ms\t\n"},
    ]
    assert mcs.read_reports(run, events)
    assert (run.duration_ms, run.billed_ms, run.memory_mb, run.init_ms) == (14230.55, 24231, 811, 10001.02)
    assert run.init_timeout and run.init_reports == ["10000 ms init timeout"]
    warm = mcs.Run("x")
    assert mcs.read_reports(warm, [{"message": "REPORT RequestId: 9\tDuration: 3.1 ms\tBilled Duration: 4 ms\t"
                                               "Memory Size: 2048 MB\tMax Memory Used: 800 MB\t"}])
    assert warm.init_ms is None and not warm.init_timeout


def test_time_health_waits_for_the_first_200():
    now = [0.0]
    answers = iter([(502, {}, ""), (200, {}, "{}")])

    def fetch(method, url, *a, **k):
        now[0] += 6.0
        return next(answers)

    status, seconds = mcs.time_health(FUNCTION_URL, fetch, clock=lambda: now[0], pause=lambda s: now.__setitem__(0, now[0] + s))
    assert status == 502 and seconds == pytest.approx(13.0)


def test_measure_without_confirm_makes_no_aws_call(cloud, capsys):
    assert mcs.main([], runner=cloud) == sb.EXIT_DRY_RUN
    assert cloud.calls == []


def test_measure_alternates_and_restores_the_original_value(cloud, capsys):
    clock = [0.0]

    def fetch(method, url, *a, **k):
        clock[0] += 11.0
        cloud.events.append({"timestamp": 10**13, "message": "REPORT RequestId: r\tDuration: 1500.0 ms\tBilled Duration: "
                             "12000 ms\tMemory Size: 2048 MB\tMax Memory Used: 800 MB\tInit Duration: 9800.0 ms\t"})
        return 200, {}, "{}"

    results = mcs.measure(sb.Aws(cloud), 2, fetch=fetch, clock=lambda: clock[0], wall=lambda: 1.0,
                          pause=lambda s: None)
    sets = [json.loads(args[args.index("--environment") + 1])["Variables"].get("AWS_LWA_ASYNC_INIT")
            for args in cloud.commands("aws", "lambda", "update-function-configuration")]
    assert sets == ["true", "false", "true", "false", "false"]  # the last one puts the original back
    assert [r.setting for r in results] == ["warm-up", "true", "false", "true", "false"]
    assert all(r.init_ms == 9800.0 for r in results[1:])
    env = cloud.configuration["Environment"]["Variables"]
    assert env["AWS_LWA_ASYNC_INIT"] == "false" and env["IMAGE_TAG"] == OLD_TAG
    assert "| 1 | true |" in mcs.table(results)


def test_measure_stops_before_any_change_when_the_function_is_throttled(cloud):
    cloud.concurrency = 0
    with pytest.raises(sb.DeployError, match="THROTTLED"):
        mcs.measure(sb.Aws(cloud), 1, fetch=lambda *a, **k: pytest.fail("fetched"))
    assert not cloud.commands("aws", "lambda", "update-function-configuration")


def test_measure_restores_the_value_even_after_a_failure(cloud):
    def fetch(method, url, *a, **k):
        if cloud.configuration["Environment"]["Variables"].get("AWS_LWA_ASYNC_INIT") == "true":
            raise sb.DeployError("network down")
        return 200, {}, "{}"

    with pytest.raises(sb.DeployError):
        mcs.measure(sb.Aws(cloud), 1, fetch=fetch, clock=lambda: 0.0, wall=lambda: 1.0, pause=lambda s: None)
    assert cloud.configuration["Environment"]["Variables"]["AWS_LWA_ASYNC_INIT"] == "false"
