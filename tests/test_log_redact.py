"""日志脱敏 _redact + setup_logging 单元测试。"""
from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

from doppelvoice.utils.log import _redact, _SENTINEL, safe_error_message, setup_logging


# 合成的虚拟 token：只用于验证脱敏行为，不是任何真实凭据。
_FAKE_APPKEY = "1234567890"
_FAKE_ACCESS = "fakeAccTok-1234567890_AbCdEfGh"
_FAKE_BEARER = "fakeBearer1234abcdef5678ghijkl"


def test_redacts_app_key_assignment():
    out = _redact(f"app_key={_FAKE_APPKEY}")
    assert _FAKE_APPKEY not in out
    assert _SENTINEL in out


def test_redacts_access_key_with_quotes():
    out = _redact(f'"access_key": "{_FAKE_ACCESS}"')
    assert _FAKE_ACCESS not in out
    assert _SENTINEL in out


def test_redacts_authorization_bearer():
    out = _redact(f"Authorization: Bearer {_FAKE_BEARER}")
    assert _FAKE_BEARER not in out


def test_redacts_x_api_header():
    out = _redact(f"X-Api-Access-Key: {_FAKE_ACCESS}")
    assert _FAKE_ACCESS not in out


def test_long_token_pattern_catches_orphan_token():
    """裸出现的长 base64 token（如 traceback 里）也应脱敏。"""
    long_token = "fakeOrphan_1234567890abcdef_GhIjKlMnOp_QrStUv"
    out = _redact(f"invalid token {long_token}")
    assert long_token not in out


def test_normal_short_message_unchanged():
    msg = "connecting to server"
    assert _redact(msg) == msg


def test_safe_error_message_truncates_long_sentence():
    """普通句子（多个空格分隔的短词）不会被脱敏，应该走截断分支。"""
    msg = " ".join(["foo"] * 60)  # 60 个 'foo'，远超 50 字符
    e = Exception(msg)
    out = safe_error_message(e, max_len=50)
    assert len(out) <= 51  # 50 + 省略号
    assert out.endswith("…")


def test_safe_error_message_redacts():
    e = Exception("failed: app_key=secretvalue123abcdef")
    out = safe_error_message(e)
    assert "secretvalue123" not in out


# ── setup_logging robustness (regression test for v0.3.1 → v0.3.2) ──────────

def test_setup_logging_with_none_stderr(tmp_path, monkeypatch):
    """PyInstaller windowed bundle (onefile + console=False) detaches stdio
    so sys.stderr / sys.stdout are None. loguru.add(None, ...) raises
    `TypeError: Cannot log to objects of type 'NoneType'` on every launch.
    setup_logging must skip the stderr sink when sys.stderr is None and
    still set up the file sink successfully.
    """
    monkeypatch.setattr(sys, "stderr", None)
    monkeypatch.setattr(sys, "stdout", None)
    # Should NOT raise
    setup_logging(tmp_path, level="INFO")
    # File sink should still produce a log file under tmp_path
    from loguru import logger
    logger.info("smoke test entry")
    log_files = list(tmp_path.glob("doppelvoice_*.log"))
    assert log_files, "file sink should still create a log file"


def test_sentinel_not_re_matched():
    """脱敏哨兵自身不应被二次匹配（防止反复替换）。"""
    once = _redact("app_key=verysecretvalue1234")
    twice = _redact(once)
    assert once == twice
