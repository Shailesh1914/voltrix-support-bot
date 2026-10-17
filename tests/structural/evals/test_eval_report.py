"""Report files and the Markdown the human reads."""

import pytest

from evals.eval_report import ReportExists, fmt_rate, histogram, sweep_markdown, write_report


def test_write_report_names_and_refuses_overwrite(tmp_path):
    paths = write_report(tmp_path, "2026-10-16", "part-a-retrieval", {"a": 1}, "# A\n")
    assert [p.name for p in paths] == ["2026-10-16-part-a-retrieval.json", "2026-10-16-part-a-retrieval.md"]
    with pytest.raises(ReportExists):
        write_report(tmp_path, "2026-10-16", "part-a-retrieval", {"a": 2}, "# B\n")
    write_report(tmp_path, "2026-10-16", "part-a-retrieval", {"a": 2}, "# B\n", overwrite=True)
    assert paths[1].read_text(encoding="utf-8") == "# B\n"


def test_histogram_counts_every_score():
    scores = [0.10, 0.31, 0.62, 0.64, 0.99, 1.0]
    lines = histogram(scores)
    total = sum(int(line.split()[-1]) for line in lines if line.split()[-1].isdigit())
    assert total == len(scores)
    assert len(lines) == 20


def test_fmt_rate():
    assert fmt_rate({"passed": 21, "total": 24, "rate": 21 / 24}) == "21/24 (87.5%)"
    assert fmt_rate({"passed": 0, "total": 0, "rate": None}) == "– (0 tickets)"


def sweep_data(meeting):
    rate = {"passed": 1, "total": 1, "rate": 1.0}
    return {
        "date": "2026-10-16",
        "git_commit": "abc",
        "git_dirty": False,
        "ticket_file_sha256": "0" * 64,
        "n_tickets": 1,
        "n_answer": 1,
        "n_escalate": 0,
        "runs": [{"file": "r1.json", "sha256": "f" * 64}],
        "thresholds_meeting_targets": meeting,
        "rows": [
            {
                "threshold": 0.5,
                "worst": {"ac1": rate, "ac2": rate, "wrong_escalation": rate},
                "meets_targets": bool(meeting),
                "tickets_passed_in_all_runs": 1,
            }
        ],
    }


def test_sweep_markdown_never_chooses():
    md = sweep_markdown(sweep_data([0.5]))
    assert "does NOT choose the threshold" in md
    assert "0.50" in md
    assert "**None** of 0.50–0.90" in sweep_markdown(sweep_data([]))
