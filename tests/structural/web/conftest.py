"""Fixtures for the web structural tests: they live in web_testkit.py
(a uniquely named module, so test files can import its helpers too)."""

from web_testkit import (  # noqa: F401  (fixtures are found by name)
    all_logs,
    clean_environment,
    make_bot,
    no_network,
    no_real_kb_version_file,
    no_real_secrets_file,
    no_retry_sleep,
    production_logs,
    spec_08,
)
