"""Tests of check_secrets_stage_b.py (AC-D9) with fakes: an in-memory image
tar, a fake account, fake prompts. The secret values must never be printed
and never be put on a command line."""

import io
import json
import subprocess
import tarfile

import pytest

import check_secrets_stage_b as cs
import stage_b as sb
from stage_b_fakes import NEW_TAG, FakeCloud, cp

CODE = "the-real-access-code-42"
KEY = "sk-ant-api03-" + "Q" * 40


def scanner():
    return cs.Scanner({"the access code": CODE.encode(), "the Anthropic key": KEY.encode()})


def test_values_and_patterns_are_found_by_name_only():
    s = scanner()
    s.scan_bytes("a", f"x {CODE} y".encode())
    s.scan_bytes("b", b"key=sk-ant-admin01-" + b"z" * 30)
    s.scan_bytes("c", b"AKIA" + b"ABCDEFGHIJKLMNOP")
    s.scan_bytes("d", b"aws_secret_access_key = " + b"A" * 40)
    s.scan_bytes("e", b"nothing here")
    assert s.hits == [("the access code", "a"), ("Anthropic API key pattern", "b"),
                      ("AWS access key id pattern", "c"), ("AWS secret key setting", "d")]


def test_the_repository_test_sentinels_are_not_key_shaped():
    s = cs.Scanner({})
    for sentinel in (b"sk-ant-test-SENTINEL-KEY-0123456789", b"sk-ant-LEAK", b"sk-ant-api",
                     b'"AWS_SECRET_ACCESS_KEY": "secret"', b"AKIAEXAMPLE"):
        s.scan_bytes("t", sentinel)
    assert s.hits == []


def test_the_allow_list_is_exactly_the_four_aws_example_key_ids():
    assert cs.KNOWN_AWS_EXAMPLE_KEY_IDS == {
        b"AKIAIOSFODNN7EXAMPLE", b"AKIAI44QH8DHBEXAMPLE", b"AKIA111111111EXAMPLE", b"AKIA222222222EXAMPLE"}
    assert all(cs.PATTERNS[cs.AWS_KEY_ID].fullmatch(v) for v in cs.KNOWN_AWS_EXAMPLE_KEY_IDS)


def test_known_aws_examples_are_reported_as_examples_not_findings():
    """The three files the Round 3 AC-D9 run flagged, with their real shapes."""
    s = scanner()
    s.scan_bytes("image:/x/boto3/examples/cloudfront.rst", b"key_id='AKIAIOSFODNN7EXAMPLE'")
    s.scan_stream("image:/x/botocore/data/sts/2011-06-15/examples-1.json",
                  io.BytesIO(b'{"AccessKeyId": "AKIAIOSFODNN7EXAMPLE"}, {"AccessKeyId": "AKIAI44QH8DHBEXAMPLE"}'))
    s.scan_bytes("image:/x/botocore/data/iam/2010-05-08/examples-1.json",
                 b'"AKIA111111111EXAMPLE" "AKIA222222222EXAMPLE" "AKIAIOSFODNN7EXAMPLE"')
    assert s.hits == []
    assert [v for v, _ in s.examples] == ["AKIAIOSFODNN7EXAMPLE", "AKIAI44QH8DHBEXAMPLE", "AKIAIOSFODNN7EXAMPLE",
                                          "AKIA111111111EXAMPLE", "AKIA222222222EXAMPLE", "AKIAIOSFODNN7EXAMPLE"]


@pytest.mark.parametrize("value", [
    b"AKIA" + b"IOSFODNN7EXAMPLF",   # one character off
    b"ASIA" + b"IOSFODNN7EXAMPLE",   # the temporary-key prefix is not on the list
    b"AKIA" + b"IOSFODNN8EXAMPLE",
    b"AKIA" + b"ABCDEFGHIJKLMNOP",   # a real-looking id
])
def test_anything_else_key_shaped_still_fails_even_next_to_an_example(value):
    s = scanner()
    s.scan_bytes("image:/x/botocore/data/iam/2010-05-08/examples-1.json", b"AKIAIOSFODNN7EXAMPLE " + value)
    assert s.hits == [("AWS access key id pattern", "image:/x/botocore/data/iam/2010-05-08/examples-1.json")]
    assert [v for v, _ in s.examples] == ["AKIAIOSFODNN7EXAMPLE"]


def test_the_examples_are_printed_and_do_not_fail_ac_d9(capsys):
    cloud = FakeCloud()
    cloud.events = [{"timestamp": 1, "logStreamName": "s", "message": "doc AKIAIOSFODNN7EXAMPLE"}]
    answers = iter([CODE, ""])
    assert cs.main(["--only", "logs"], runner=cloud, prompt=lambda p: next(answers)) == 0
    out = capsys.readouterr().out
    assert "[known documentation example] AKIAIOSFODNN7EXAMPLE" in out
    assert "1 known AWS documentation example key id(s), not secrets" in out


def test_a_value_split_across_chunks_is_found(monkeypatch):
    monkeypatch.setattr(cs, "CHUNK", 8)
    s = scanner()
    s.scan_stream("f", io.BytesIO(b"0123456789" * 3 + CODE.encode() + b"tail"))
    assert ("the access code", "f") in s.hits


def make_tar(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name, data in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    buffer.seek(0)
    return buffer


def test_every_file_of_the_image_is_searched():
    s = scanner()
    count = cs.scan_tar(s, make_tar({"app/BUILD_INFO.txt": b"ok", "opt/venv/x.py": f"k='{KEY}'".encode()}), "image")
    assert count == 2
    assert sorted(s.hits) == [("Anthropic API key pattern", "image:/opt/venv/x.py"), ("the Anthropic key", "image:/opt/venv/x.py")]


def test_history_hits_name_the_commit_and_file():
    log = "\n".join([
        "commit " + "1" * 40, "Add file", "", "diff --git a/a.txt b/a.txt", "+clean",
        "commit " + "2" * 40, "Oops", "", "diff --git a/notes/x.md b/notes/x.md", f"+code {CODE}",
    ])
    s = scanner()
    cs.scan_history(s, log)
    assert s.hits == [("the access code", "commit 2222222 notes/x.md")]


def test_the_image_target_exports_the_container_and_removes_it():
    calls = []

    def runner(args, input=None, timeout=None):
        calls.append(args)
        if args[1] == "create":
            return cp("container123\n")
        return cp("[]")

    class Popen:
        def __init__(self, args, stdout, env):
            calls.append(args)
            assert "AWS_ACCESS_KEY_ID" not in env
            self.stdout = make_tar({"etc/x": b"clean"})

        def wait(self):
            return 0

    s = scanner()
    assert "1 files" in cs.scan_image(s, NEW_TAG, runner=runner, popen=Popen)
    assert ["docker", "export", "container123"] in calls and calls[-1] == ["docker", "rm", "container123"]
    assert s.hits == []


def test_logs_are_downloaded_and_searched_on_the_laptop():
    cloud = FakeCloud()
    cloud.events = [
        {"timestamp": 1, "logStreamName": "s1", "message": "request a1 answered 3500 ms 200"},
        {"timestamp": 2, "logStreamName": "s2", "message": f"debug {CODE}"},
    ]
    aws = sb.Aws(cloud)
    aws.identity()
    s = scanner()
    summary = cs.scan_logs(s, aws, {"question text of T-001": b"How do I reset"})
    assert summary == "2 log events in 2 streams"
    assert [h[0] for h in s.hits] == ["the access code"] and "s2" in s.hits[0][1]
    (call,) = cloud.commands("aws", "logs")
    assert "--filter-pattern" not in call and CODE not in " ".join(call)


def test_a_logged_ticket_question_is_found():
    cloud = FakeCloud()
    questions = cs.ticket_questions()
    text = next(iter(questions.values())).decode()
    cloud.events = [{"timestamp": 1, "logStreamName": "s", "message": f"q={text}"}]
    aws = sb.Aws(cloud)
    aws.identity()
    s = cs.Scanner({})
    cs.scan_logs(s, aws, questions)
    assert s.hits and s.hits[0][0].startswith("question text of T-")
    assert set(questions) == {"question text of T-001", "question text of T-002", "question text of T-043"}


def test_the_values_never_reach_output_or_any_command(monkeypatch, capsys):
    cloud = FakeCloud()
    cloud.events = [{"timestamp": 1, "logStreamName": "s", "message": f"{CODE} and {KEY}"}]
    cloud.configuration["Environment"]["Variables"]["IMAGE_TAG"] = NEW_TAG
    answers = iter([CODE, KEY])
    code = cs.main(["--only", "lambda,logs"], runner=cloud, prompt=lambda p: next(answers))
    out = capsys.readouterr()
    assert code == 1
    assert "[FOUND] the access code in log s" in out.out and "[FOUND] the Anthropic key in log s" in out.out
    assert CODE not in out.out + out.err and KEY not in out.out + out.err
    assert all(CODE not in " ".join(a) and KEY not in " ".join(a) for a, _ in cloud.calls)
    assert all(i is None for _, i in cloud.calls)


def test_clean_targets_pass(capsys):
    cloud = FakeCloud()
    cloud.events = [{"timestamp": 1, "logStreamName": "s", "message": "request 1 escalated 1200 ms 200"}]
    answers = iter([CODE, ""])  # the key prompt may be skipped
    assert cs.main(["--only", "lambda,logs"], runner=cloud, prompt=lambda p: next(answers)) == 0
    assert "AC-D9 passed" in capsys.readouterr().out


def test_a_short_access_code_or_bad_arguments_stop_early():
    assert cs.main(["--only", "logs"], runner=lambda *a, **k: pytest.fail("ran"), prompt=lambda p: "short") == 1
    assert cs.main(["--only", "image"], prompt=lambda p: pytest.fail("asked")) == 2
    assert cs.main(["--only", "disk"], prompt=lambda p: pytest.fail("asked")) == 2


def test_a_target_that_cannot_be_searched_fails_ac_d9(capsys):
    cloud = FakeCloud()
    cloud.arn = "arn:aws:iam::123456789012:user/admin"
    answers = iter([CODE, ""])
    assert cs.main(["--only", "logs"], runner=cloud, prompt=lambda p: next(answers)) == 1
    assert "NOT SEARCHED" in capsys.readouterr().err


def test_the_real_repository_has_no_secret_shapes():
    """The repo target on this checkout, with dummy values: the pattern
    search must come back clean (the test sentinels are not key-shaped)."""
    s = cs.Scanner({"dummy": b"dummy-value-not-in-the-repo-8f3a"})
    summary = cs.scan_repo(s)
    assert "tracked files" in summary
    assert s.hits == []
