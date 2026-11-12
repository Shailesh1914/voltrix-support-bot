"""Where the secrets come from (spec 08 section 5). No AWS: Parameter
Store is a fake client that records its calls."""

import pytest

from query.config import ConfigError
from web.secret_source import Secrets, load_secrets
from web_testkit import CODE, KEY

PS_KEY = "sk-ant-test-FROM-PARAMETER-STORE-0000"
PS_CODE = "code-FROM-parameter-store-99"


class FakeSSM:
    def __init__(self, values=None, error=None):
        self.values = {"/voltrix/anthropic-key": PS_KEY, "/voltrix/access-code": PS_CODE} if values is None else values
        self.error = error
        self.calls = []

    def get_parameter(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"Parameter": {"Name": kwargs["Name"], "Type": "SecureString", "Value": self.values[kwargs["Name"]]}}


class Factory:
    def __init__(self, client=None):
        self.client = client or FakeSSM()
        self.made = 0

    def __call__(self):
        self.made += 1
        return self.client


def no_ssm():
    raise AssertionError("Parameter Store used in file mode")


@pytest.fixture
def secrets_file(tmp_path):
    def _write(key=KEY, code=CODE):
        path = tmp_path / "home" / ".config" / "voltrix" / "secrets.env"
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = ([f"VOLTRIX_ANTHROPIC_API_KEY={key}"] if key is not None else []) + (
            [f"VOLTRIX_ACCESS_CODE={code}"] if code is not None else []
        )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return path

    return _write


def assert_names_setting_not_value(error, setting, *values):
    message = str(error.value)
    assert setting in message
    for value in values:
        assert value not in message


# --- file mode -------------------------------------------------------------------------------


@pytest.mark.parametrize("environ", [{}, {"VOLTRIX_SECRETS_SOURCE": "file"}], ids=["not set", "file"])
def test_file_mode_reads_both_from_the_secrets_file(secrets_file, environ):
    secrets = load_secrets(environ, secrets_file(), no_ssm)
    assert (secrets.anthropic_key, secrets.access_code) == (KEY, CODE)


def test_file_mode_missing_access_code(secrets_file):
    with pytest.raises(ConfigError) as error:
        load_secrets({}, secrets_file(code=None), no_ssm)
    assert_names_setting_not_value(error, "VOLTRIX_ACCESS_CODE", KEY)


def test_file_mode_missing_key(secrets_file):
    with pytest.raises(ConfigError) as error:
        load_secrets({}, secrets_file(key=None), no_ssm)
    assert_names_setting_not_value(error, "VOLTRIX_ANTHROPIC_API_KEY", CODE)


def test_file_mode_no_file(tmp_path):
    with pytest.raises(ConfigError, match="VOLTRIX_ANTHROPIC_API_KEY"):
        load_secrets({}, tmp_path / "missing.env", no_ssm)


def test_secrets_file_inside_the_project_is_refused(tmp_path):
    from query.config import REPO_ROOT

    with pytest.raises(ConfigError, match="outside the project"):
        load_secrets({"VOLTRIX_ANTHROPIC_API_KEY": KEY}, REPO_ROOT / "secrets.env", no_ssm)


# --- VOLTRIX_SECRETS_SOURCE ------------------------------------------------------------------


@pytest.mark.parametrize("value", ["", "File", "ssm", "parameter-store", "parameter_store ", "env"])
def test_any_other_source_stops_the_start_up(secrets_file, value):
    with pytest.raises(ConfigError) as error:
        load_secrets({"VOLTRIX_SECRETS_SOURCE": value}, secrets_file(), no_ssm)
    assert "VOLTRIX_SECRETS_SOURCE" in str(error.value)
    if value.strip():
        assert repr(value) not in str(error.value)


# --- parameter_store mode ----------------------------------------------------------------------

PS_ENV = {"VOLTRIX_SECRETS_SOURCE": "parameter_store"}


def test_parameter_store_reads_both_once_with_decryption(secrets_file, spec_08):
    factory = Factory()
    secrets = load_secrets(PS_ENV, secrets_file(), factory)
    assert (secrets.anthropic_key, secrets.access_code) == (PS_KEY, PS_CODE)
    assert factory.made == 1
    assert sorted(c["Name"] for c in factory.client.calls) == sorted([spec_08.key_parameter, spec_08.code_parameter])
    assert all(c["WithDecryption"] is True for c in factory.client.calls)
    assert len(factory.client.calls) == 2


@pytest.mark.parametrize("name, value", [("VOLTRIX_ANTHROPIC_API_KEY", KEY), ("VOLTRIX_ACCESS_CODE", CODE)])
def test_parameter_store_refuses_secrets_in_the_environment(name, value):
    factory = Factory()
    with pytest.raises(ConfigError) as error:
        load_secrets({**PS_ENV, name: value}, ssm_client_factory=factory)
    assert_names_setting_not_value(error, name, value)
    assert factory.client.calls == []


def test_parameter_store_error_names_the_parameter_only():
    factory = Factory(FakeSSM(error=RuntimeError("AccessDenied for value sk-ant-LEAK")))
    with pytest.raises(ConfigError) as error:
        load_secrets(PS_ENV, ssm_client_factory=factory)
    assert "/voltrix/anthropic-key" in str(error.value)
    assert "sk-ant-LEAK" not in str(error.value)


@pytest.mark.parametrize("parameter", ["/voltrix/anthropic-key", "/voltrix/access-code"])
def test_empty_parameter_stops_the_start_up(parameter):
    values = {"/voltrix/anthropic-key": PS_KEY, "/voltrix/access-code": PS_CODE, parameter: "  "}
    with pytest.raises(ConfigError, match=parameter):
        load_secrets(PS_ENV, ssm_client_factory=Factory(FakeSSM(values)))


# --- both modes ---------------------------------------------------------------------------------

ANTHROPIC_NAMES = [
    "ANTHROPIC_API_KEY",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_CUSTOM_HEADERS",
    "ANTHROPIC_LOG",
    "ANTHROPIC_ANYTHING_ELSE",
]


@pytest.mark.parametrize("source", ["file", "parameter_store"])
@pytest.mark.parametrize("name", ANTHROPIC_NAMES)
def test_anthropic_variables_refused_in_both_modes(secrets_file, source, name):
    factory = Factory()
    with pytest.raises(ConfigError) as error:
        load_secrets({"VOLTRIX_SECRETS_SOURCE": source, name: "value-SENTINEL-1234"}, secrets_file(), factory)
    assert_names_setting_not_value(error, name, "value-SENTINEL-1234")
    assert factory.client.calls == []


@pytest.mark.parametrize("length, ok", [(11, False), (12, True), (40, True)])
def test_code_length_file_mode(secrets_file, spec_08, length, ok):
    assert spec_08.min_code_length == 12
    code = "c" * length
    if ok:
        assert load_secrets({}, secrets_file(code=code), no_ssm).access_code == code
    else:
        with pytest.raises(ConfigError) as error:
            load_secrets({}, secrets_file(code=code), no_ssm)
        assert_names_setting_not_value(error, "VOLTRIX_ACCESS_CODE", code)


@pytest.mark.parametrize("length, ok", [(11, False), (12, True)])
def test_code_length_parameter_store_mode(length, ok):
    code = "p" * length
    values = {"/voltrix/anthropic-key": PS_KEY, "/voltrix/access-code": code}
    factory = Factory(FakeSSM(values))
    if ok:
        assert load_secrets(PS_ENV, ssm_client_factory=factory).access_code == code
    else:
        with pytest.raises(ConfigError) as error:
            load_secrets(PS_ENV, ssm_client_factory=factory)
        assert_names_setting_not_value(error, "/voltrix/access-code", code)


def test_secrets_repr_hides_values():
    secrets = Secrets(KEY, CODE)
    assert KEY not in repr(secrets) and CODE not in repr(secrets) and CODE not in str(secrets)
