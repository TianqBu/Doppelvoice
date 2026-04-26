"""DoubaoClient._classify 事件分类逻辑单元测试。"""
from __future__ import annotations

import pytest

from doppelvoice.config import AppConfig, Credentials
from doppelvoice.engine.doubao import DoubaoClient
from doppelvoice.engine.protocol import ast_pb, EventType, STATUS_SUCCESS


@pytest.fixture
def client():
    cfg = AppConfig(credentials=Credentials(app_key="x", access_key="y"))
    return DoubaoClient(cfg)


def _make_resp(event: int, *, status: int = 0, message: str = "", text: str = "", data: bytes = b""):
    resp = ast_pb.TranslateResponse()
    resp.event = event
    if status or message:
        resp.response_meta.StatusCode = status
        resp.response_meta.Message = message
    if text:
        resp.text = text
    if data:
        resp.data = data
    return resp


def test_classify_session_started(client):
    ev = client._classify(_make_resp(EventType.SessionStarted))
    assert ev.kind == "session_started"


def test_classify_session_finished(client):
    ev = client._classify(_make_resp(EventType.SessionFinished))
    assert ev.kind == "session_finished"


def test_classify_source_subtitle_response_not_definite(client):
    ev = client._classify(_make_resp(EventType.SourceSubtitleResponse, text="hello"))
    assert ev.kind == "source_text"
    assert ev.text == "hello"
    assert ev.is_definite is False


def test_classify_source_subtitle_end_is_definite(client):
    ev = client._classify(_make_resp(EventType.SourceSubtitleEnd, text="final"))
    assert ev.kind == "source_text"
    assert ev.is_definite is True


def test_classify_translation_subtitle_response(client):
    ev = client._classify(_make_resp(EventType.TranslationSubtitleResponse, text="bonjour"))
    assert ev.kind == "target_text"
    assert ev.text == "bonjour"
    assert ev.is_definite is False


def test_classify_translation_subtitle_end_is_definite(client):
    ev = client._classify(_make_resp(EventType.TranslationSubtitleEnd, text="终态"))
    assert ev.kind == "target_text"
    assert ev.is_definite is True


def test_classify_tts_response_with_audio(client):
    ev = client._classify(_make_resp(EventType.TTSResponse, data=b"\x01\x02\x03"))
    assert ev.kind == "audio"
    assert ev.audio == b"\x01\x02\x03"


def test_classify_sentence_start_end(client):
    s = client._classify(_make_resp(EventType.TTSSentenceStart))
    assert s.kind == "sentence_start"
    e = client._classify(_make_resp(EventType.TTSSentenceEnd))
    assert e.kind == "sentence_end"


def test_classify_session_failed_is_error(client):
    ev = client._classify(_make_resp(EventType.SessionFailed, status=11500, message="bad params"))
    assert ev.kind == "error"
    assert ev.status_code == 11500
    assert ev.message == "bad params"


def test_classify_session_canceled_is_error(client):
    ev = client._classify(_make_resp(EventType.SessionCanceled, message="user cancel"))
    assert ev.kind == "error"


def test_classify_non_zero_non_success_status_is_error(client):
    """非 0 且非 SUCCESS 的状态码 → 直接归为 error。"""
    ev = client._classify(_make_resp(EventType.TTSResponse, status=21300, message="interrupted"))
    assert ev.kind == "error"
    assert ev.status_code == 21300


def test_classify_success_status_not_error(client):
    """STATUS_SUCCESS（20000000）不应归为 error。"""
    ev = client._classify(_make_resp(EventType.SessionStarted, status=STATUS_SUCCESS))
    assert ev.kind == "session_started"


def test_classify_unknown_event_returns_none(client):
    """完全没识别的 event type 返回 None。"""
    # 用一个我们没有处理的合法 event 值（如 UpdateConfig 201 不在 _classify 分支里）
    ev = client._classify(_make_resp(EventType.UpdateConfig))
    assert ev is None
