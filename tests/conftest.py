import pytest

from controlplane.config import Config
from controlplane.sandbox.policy import AuditLog, Sandbox
from controlplane.sandbox.toy_repo import build_toy_repo


@pytest.fixture()
def test_config(tmp_path) -> Config:
    """Function-scoped and rebuilt fresh per test -- this is a security
    test suite, so each test gets a clean, isolated sandbox root rather
    than sharing mutable state across tests."""
    sandbox_root = tmp_path / "toy_repo"
    config = Config(gemini_api_key="unused-in-tests", sandbox_root=sandbox_root)
    build_toy_repo(config)
    return config


@pytest.fixture()
def audit_log() -> AuditLog:
    return AuditLog()


@pytest.fixture()
def sandbox(test_config, audit_log) -> Sandbox:
    return Sandbox(test_config, audit_log)
