"""验证 protobuf 消息能正确编解码。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def test_translate_request_roundtrip():
    from doppelvoice.engine.protocol import ast_pb, EventType

    req = ast_pb.TranslateRequest()
    req.request_meta.SessionID = "sid"
    req.request_meta.ConnectionID = "cid"
    req.request_meta.AppKey = "ak"
    req.request_meta.Sequence = 1
    req.event = EventType.StartSession
    req.user.uid = "u"
    req.source_audio.format = "pcm"
    req.source_audio.rate = 16000
    req.source_audio.bits = 16
    req.source_audio.channel = 1
    req.request.mode = "s2s"
    req.request.source_language = "zh"
    req.request.target_language = "en"

    buf = req.SerializeToString()
    assert len(buf) > 10

    back = ast_pb.TranslateRequest()
    back.ParseFromString(buf)
    assert back.event == EventType.StartSession
    assert back.request_meta.SessionID == "sid"
    assert back.source_audio.rate == 16000
    assert back.request.mode == "s2s"


def test_task_request_carries_audio():
    from doppelvoice.engine.protocol import ast_pb, EventType

    audio = b"\x00\x01" * 1280
    req = ast_pb.TranslateRequest()
    req.request_meta.SessionID = "s"
    req.event = EventType.TaskRequest
    req.source_audio.binary_data = audio
    buf = req.SerializeToString()

    back = ast_pb.TranslateRequest()
    back.ParseFromString(buf)
    assert back.event == EventType.TaskRequest
    assert back.source_audio.binary_data == audio


def test_event_constants():
    from doppelvoice.engine.protocol import EventType

    assert EventType.StartSession == 100
    assert EventType.SessionStarted == 150
    assert EventType.TaskRequest == 200
    assert EventType.TTSResponse == 352
    assert EventType.SourceSubtitleEnd == 652
    assert EventType.TranslationSubtitleEnd == 655
