"""Tests de la garde SD_SECRET_KEY (jetons JWT forgeables si absente)."""

import pytest

from app.core import config
from app.core.config import Settings, assert_secret_key_is_set


def _fake_settings(key: str):
    config.get_settings = lambda: Settings(secret_key=key)


def test_guard_refuses_example_key():
    _fake_settings("change-me-in-production")
    with pytest.raises(RuntimeError, match="SD_SECRET_KEY"):
        assert_secret_key_is_set()


def test_guard_refuses_old_default_key():
    _fake_settings("change-me-in-production-use-openssl-rand-hex-32")
    with pytest.raises(RuntimeError, match="SD_SECRET_KEY"):
        assert_secret_key_is_set()


def test_guard_refuses_short_key():
    _fake_settings("short")
    with pytest.raises(RuntimeError, match="SD_SECRET_KEY"):
        assert_secret_key_is_set()


def test_guard_accepts_strong_key():
    _fake_settings("a" * 32)
    assert_secret_key_is_set()  # ne doit pas lever
