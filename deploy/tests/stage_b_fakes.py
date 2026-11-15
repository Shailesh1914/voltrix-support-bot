"""A fake AWS account and Docker for the Stage B script tests. It answers
the AWS CLI and docker commands the scripts run, from in-memory state. No
AWS, no Docker, no network."""

import json
import subprocess

ACCOUNT = "123456789012"
REGISTRY = f"{ACCOUNT}.dkr.ecr.ap-south-1.amazonaws.com"
TOKEN = "ECR-LOGIN-TOKEN-must-never-be-printed-0123456789"
OLD_TAG, NEW_TAG = "v2-20261113-406e022", "v2-20261114-abcdef1"
OLD_DIGEST, NEW_DIGEST = "sha256:" + "a" * 64, "sha256:" + "b" * 64
FUNCTION_URL = "https://abc123.lambda-url.ap-south-1.on.aws/"
SINGLE = "application/vnd.docker.distribution.manifest.v2+json"


def cp(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


def aws_error(code):
    return cp(returncode=254, stderr=f"\nAn error occurred ({code}) when calling the X operation: something\n")


class FakeCloud:
    def __init__(self):
        self.arn = f"arn:aws:iam::{ACCOUNT}:user/voltrix-deploy"
        self.mutability = "IMMUTABLE"
        self.images = {OLD_TAG: {"imageDigest": OLD_DIGEST, "imageManifestMediaType": SINGLE,
                                 "imageSizeInBytes": 900_000_000, "imageTags": [OLD_TAG]}}
        self.local = {NEW_TAG: {"Os": "linux", "Architecture": "amd64",
                                "Config": {"Labels": {"org.opencontainers.image.revision": "abcdef1" + "0" * 33}}}}
        self.push_media_type = SINGLE
        self.push_digest = NEW_DIGEST
        self.configuration = {
            "FunctionName": "voltrix-support-bot", "PackageType": "Image", "Architectures": ["x86_64"],
            "MemorySize": 2048, "Timeout": 60, "Role": f"arn:aws:iam::{ACCOUNT}:role/voltrix-support-bot-lambda",
            "State": "Active", "LastUpdateStatus": "Successful",
            "Environment": {"Variables": {"VOLTRIX_SECRETS_SOURCE": "parameter_store", "HANDOFF_DIR": "/tmp/handoffs",
                                          "IMAGE_TAG": OLD_TAG, "AWS_LWA_ASYNC_INIT": "false"}},
        }
        self.code = {"ImageUri": f"{REGISTRY}/voltrix-support-bot:{OLD_TAG}",
                     "ResolvedImageUri": f"{REGISTRY}/voltrix-support-bot@{OLD_DIGEST}"}
        self.concurrency = None  # Round 3: no reserved concurrency
        self.events = []
        self.calls = []  # (args, input)
        self.logged_in = False

    # -- the runner ----------------------------------------------------------

    def __call__(self, args, input=None, timeout=None):
        self.calls.append((list(args), input))
        if args[0] == "aws":
            assert args[-6:] == ["--profile", "voltrix-deploy", "--region", "ap-south-1", "--output", args[-1]], args
            return self.aws(args[1:-6])
        if args[0] == "docker":
            return self.docker(args[1:], input)
        raise AssertionError(f"unexpected command {args}")

    def aws(self, a):
        key = tuple(a[:2])
        if key == ("sts", "get-caller-identity"):
            return cp(json.dumps({"Account": ACCOUNT, "Arn": self.arn, "UserId": "AIDAEXAMPLE"}))
        if key == ("ecr", "describe-repositories"):
            return cp(json.dumps({"repositories": [{"repositoryName": "voltrix-support-bot", "imageTagMutability": self.mutability}]}))
        if key == ("ecr", "describe-images"):
            tag = a[a.index("--image-ids") + 1].split("=", 1)[1]
            if tag not in self.images:
                return aws_error("ImageNotFoundException")
            return cp(json.dumps({"imageDetails": [self.images[tag]]}))
        if key == ("ecr", "get-login-password"):
            return cp(TOKEN + "\n")
        if key == ("lambda", "get-function"):
            return cp(json.dumps({"Configuration": self.configuration, "Code": self.code}))
        if key == ("lambda", "get-function-url-config"):
            return cp(json.dumps({"FunctionUrl": FUNCTION_URL, "AuthType": "NONE"}))
        if key == ("lambda", "get-function-concurrency"):
            return cp(json.dumps({} if self.concurrency is None else {"ReservedConcurrentExecutions": self.concurrency}))
        if key == ("lambda", "wait"):
            return cp("")
        if key == ("lambda", "update-function-code"):
            uri = a[a.index("--image-uri") + 1]
            tag = uri.rsplit(":", 1)[1]
            self.code = {"ImageUri": uri, "ResolvedImageUri": f"{REGISTRY}/voltrix-support-bot@{self.images[tag]['imageDigest']}"}
            return cp(json.dumps(self.configuration))
        if key == ("lambda", "update-function-configuration"):
            self.configuration["Environment"] = json.loads(a[a.index("--environment") + 1])
            return cp(json.dumps(self.configuration))
        if key == ("logs", "filter-log-events"):
            start = int(a[a.index("--start-time") + 1])
            return cp(json.dumps({"events": [e for e in self.events if e["timestamp"] >= start]}))
        raise AssertionError(f"unexpected aws command {a}")

    def docker(self, a, input):
        if a[:2] == ["image", "inspect"]:
            tag = a[2].split(":", 1)[1]
            return cp(json.dumps([self.local[tag]])) if tag in self.local else cp(returncode=1, stderr="No such image")
        if a[0] == "login":
            assert input == TOKEN and TOKEN not in " ".join(a)
            self.logged_in = True
            return cp("Login Succeeded")
        if a[0] == "tag":
            return cp()
        if a[0] == "push":
            tag = a[1].rsplit(":", 1)[1]
            self.images[tag] = {"imageDigest": self.push_digest, "imageManifestMediaType": self.push_media_type,
                                "imageSizeInBytes": 950_000_000, "imageTags": [tag]}
            return cp(f"{tag}: digest: {NEW_DIGEST} size: 4321\n")
        if a[0] == "logout":
            self.logged_in = False
            return cp()
        if a[:2] == ["image", "rm"]:
            return cp()
        raise AssertionError(f"unexpected docker command {a}")

    # -- helpers for assertions ---------------------------------------------

    def commands(self, *prefix):
        return [args for args, _ in self.calls if args[:len(prefix)] == list(prefix)]

    def changes(self):
        mutating = {"update-function-code", "update-function-configuration", "push", "login", "tag"}
        return [args for args, _ in self.calls if len(args) > 2 and (args[2] in mutating or args[1] in mutating)]
