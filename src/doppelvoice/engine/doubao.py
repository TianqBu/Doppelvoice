"""豆包 AST 2.0 同声传译 WebSocket 客户端（纯 protobuf）。"""
from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from typing import AsyncIterator, Optional
from urllib.parse import urlparse

import websockets
from loguru import logger

from doppelvoice.engine.protocol import ast_pb, events_pb, STATUS_SUCCESS, EventType
from doppelvoice.config import AppConfig

# 单帧上限：正常 TTSResponse 一般 1-50KB，4MB 留足余量。
# 帮 ParseFromString 抵御恶意服务端构造的超大 protobuf。
_MAX_FRAME_BYTES = 4 * 1024 * 1024

# 允许的 WS hostname 白名单：防止 .env 注入恶意 URL 把凭据发到攻击者。
_ALLOWED_WS_HOSTS = {
    "openspeech.bytedance.com",
}


def _validate_ws_url(url: str) -> None:
    """拒绝 wss 之外的 scheme 和白名单外的 hostname。"""
    parsed = urlparse(url)
    if parsed.scheme != "wss":
        raise ValueError(f"WS URL must use wss://, got scheme={parsed.scheme!r}")
    host = parsed.hostname or ""
    if host not in _ALLOWED_WS_HOSTS and not any(
        host.endswith("." + h) for h in _ALLOWED_WS_HOSTS
    ):
        raise ValueError(
            f"WS hostname {host!r} not in allowed list "
            f"(set: {sorted(_ALLOWED_WS_HOSTS)})"
        )


@dataclass(frozen=True)
class TranslationEvent:
    """对上层暴露的事件。frozen=True：跨线程/跨协程的值对象，禁止变更。"""
    kind: str                            # "audio" | "source_text" | "target_text"
                                         # | "session_started" | "session_finished"
                                         # | "error" | "usage" | "raw"
    audio: Optional[bytes] = None
    text: Optional[str] = None
    raw_event: Optional[int] = None
    status_code: Optional[int] = None
    message: Optional[str] = None
    is_definite: bool = False            # 句子终态（SourceSubtitleEnd / TranslationSubtitleEnd）


class DoubaoClient:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.session_id: str = ""
        self.connection_id: str = ""
        self._sequence: int = 0
        # send_audio 模板：会话开始后构建一次，每次只改 binary_data 再 SerializeToString
        self._audio_req: Optional[ast_pb.TranslateRequest] = None

    # ── 连接 ──
    async def connect(self) -> None:
        # 关键：连接前校验 URL，防止 .env 注入把密钥发到攻击者
        _validate_ws_url(self.cfg.network.ws_url)
        cred = self.cfg.credentials
        self.connection_id = str(uuid.uuid4())
        headers = [
            ("X-Api-App-Key", cred.app_key),
            ("X-Api-Access-Key", cred.access_key),
            ("X-Api-Resource-Id", cred.resource_id),
            ("X-Api-Connect-Id", self.connection_id),
        ]
        # 日志只记 hostname，不记完整 URL（已校验过；规避未来 query string 漏洗）
        host = urlparse(self.cfg.network.ws_url).hostname
        logger.info("connecting to ws://{}…", host)
        self.ws = await asyncio.wait_for(
            websockets.connect(
                self.cfg.network.ws_url,
                additional_headers=headers,
                max_size=_MAX_FRAME_BYTES,
                ping_interval=20,
                ping_timeout=30,
                close_timeout=5,
            ),
            timeout=self.cfg.network.connect_timeout_s,
        )
        logger.info("✓ ws open connection_id={}", self.connection_id)

    def _next_seq(self) -> int:
        self._sequence += 1
        return self._sequence

    def _fill_request_meta(self, meta) -> None:
        """RequestMeta 只填 SessionID（和官方 demo 对齐；网关层已用 header 鉴权）。"""
        meta.SessionID = self.session_id

    # ── 会话 ──
    async def start_session(self) -> None:
        assert self.ws is not None
        self.session_id = str(uuid.uuid4())
        self._sequence = 0
        req = self._build_start_session()
        await self.ws.send(req.SerializeToString())
        logger.debug("sent StartSession session_id={}", self.session_id)

        raw = await asyncio.wait_for(
            self.ws.recv(), timeout=self.cfg.network.session_timeout_s + 5
        )
        resp = ast_pb.TranslateResponse()
        resp.ParseFromString(raw)
        evt_name = EventType.Name(resp.event) if resp.event else "None"
        logger.debug(
            "first response: event={}({}) status={} msg={!r}",
            evt_name, resp.event,
            resp.response_meta.StatusCode if resp.HasField("response_meta") else None,
            resp.response_meta.Message if resp.HasField("response_meta") else "",
        )

        if resp.event == EventType.SessionStarted:
            logger.info("✓ SessionStarted id={}", self.session_id)
            # 会话建立后，预构 send_audio 模板：4 个 source_audio 元数据字段全程不变
            self._audio_req = self._build_audio_template()
            return
        if resp.event == EventType.SessionFailed:
            raise RuntimeError(
                f"SESSION_FAILED: code={resp.response_meta.StatusCode} "
                f"msg={resp.response_meta.Message!r}"
            )
        raise RuntimeError(
            f"unexpected first event={evt_name}({resp.event}) "
            f"status={resp.response_meta.StatusCode if resp.HasField('response_meta') else None}"
        )

    def _build_start_session(self) -> ast_pb.TranslateRequest:
        """对齐官方 ast_demo.py：format=wav, uid=did, 不设 platform。
        denoise 显式发送：默认 false 保留说话人音色细节供零样本克隆。
        """
        a = self.cfg.audio
        t = self.cfg.translation

        req = ast_pb.TranslateRequest()
        self._fill_request_meta(req.request_meta)
        req.event = EventType.StartSession

        req.user.uid = "ast_py_client"
        req.user.did = "ast_py_client"

        req.source_audio.format = "wav"  # 官方 demo 用 "wav"，不是 "pcm"
        req.source_audio.rate = a.input_sample_rate
        req.source_audio.bits = a.bits
        req.source_audio.channel = a.channels

        req.request.mode = t.mode
        req.request.source_language = t.source_language
        req.request.target_language = t.target_language
        if t.speaker_id:
            req.request.speaker_id = t.speaker_id

        # optional bool denoise = 7：显式发送，避免服务端默认（推测 true）磨平音色
        req.denoise = t.denoise

        if t.mode == "s2s":
            req.target_audio.format = a.output_format  # "ogg_opus"
            req.target_audio.rate = a.output_sample_rate
        return req

    def _build_audio_template(self) -> ast_pb.TranslateRequest:
        """预构 TaskRequest 模板：4 个静态字段一次填好，send_audio 只改 binary_data。"""
        a = self.cfg.audio
        req = ast_pb.TranslateRequest()
        self._fill_request_meta(req.request_meta)
        req.event = EventType.TaskRequest
        req.source_audio.format = "wav"
        req.source_audio.rate = a.input_sample_rate
        req.source_audio.bits = a.bits
        req.source_audio.channel = a.channels
        return req

    # ── 发送音频 ──
    async def send_audio(self, pcm_bytes: bytes) -> None:
        """TaskRequest 每包都带完整 source_audio 元数据（官方 demo 做法）。

        复用 _audio_req 模板：每秒 12-13 次调用，省掉每次 protobuf 对象重建。
        """
        assert self.ws is not None
        if self._audio_req is None:
            # 极少分支：start_session 之前就发音频；按老路径建包以保持鲁棒性
            self._audio_req = self._build_audio_template()
        self._audio_req.source_audio.binary_data = pcm_bytes
        await self.ws.send(self._audio_req.SerializeToString())

    async def finish_session(self) -> None:
        if self.ws is None or not self.session_id:
            return
        req = ast_pb.TranslateRequest()
        self._fill_request_meta(req.request_meta)
        req.event = EventType.FinishSession
        try:
            await self.ws.send(req.SerializeToString())
            logger.debug("sent FinishSession")
        except Exception as e:
            logger.warning(f"finish_session send failed: {e}")

    async def close(self) -> None:
        if self.ws is None:
            return
        try:
            await self.ws.close()
        except Exception as e:
            logger.debug(f"ws close: {e}")
        self.ws = None

    # ── 接收事件流 ──
    async def iter_events(self) -> AsyncIterator[TranslationEvent]:
        """
        正常结束：收到 SessionFinished/SessionFailed 或调用方 break。
        异常断链：重新抛出 ConnectionClosedError 让上层决定是否重连（区别于正常退出）。
        """
        assert self.ws is not None
        try:
            async for raw in self.ws:
                # 帧大小防御：max_size 已经是网络层兜底，这里再加显式校验
                if isinstance(raw, (bytes, bytearray)) and len(raw) > _MAX_FRAME_BYTES:
                    logger.warning(
                        "oversized frame {} bytes (limit {}), dropping",
                        len(raw), _MAX_FRAME_BYTES,
                    )
                    continue
                try:
                    resp = ast_pb.TranslateResponse()
                    resp.ParseFromString(raw)
                except Exception as e:
                    logger.warning(f"protobuf decode failed: {e}")
                    continue
                ev = self._classify(resp)
                if ev is not None:
                    yield ev
        except websockets.ConnectionClosedOK as e:
            # 干净关闭（服务端主动 1000）也视为异常：我们期望 FinishSession 后再关
            logger.warning(f"ws closed cleanly (code={e.code}) — 视为断链触发重连")
            raise
        except websockets.ConnectionClosedError as e:
            logger.warning(f"ws closed with error: code={e.code} reason={e.reason!r}")
            raise

    def _classify(self, resp: "ast_pb.TranslateResponse") -> Optional[TranslationEvent]:
        status = resp.response_meta.StatusCode if resp.HasField("response_meta") else 0
        message = resp.response_meta.Message if resp.HasField("response_meta") else ""
        e = resp.event

        # 错误码（非 0 / 非 20000000）
        if status and status != STATUS_SUCCESS:
            return TranslationEvent(
                kind="error", raw_event=e, status_code=status, message=message
            )

        if e == EventType.SessionStarted:
            return TranslationEvent(kind="session_started", raw_event=e)
        if e == EventType.SessionFinished:
            return TranslationEvent(kind="session_finished", raw_event=e)
        if e == EventType.SessionFailed:
            return TranslationEvent(
                kind="error", raw_event=e, status_code=status, message=message or "SessionFailed"
            )
        if e == EventType.SessionCanceled:
            # 官方 demo 把 SessionCanceled 也当终态失败处理
            return TranslationEvent(
                kind="error", raw_event=e, status_code=status, message=message or "SessionCanceled"
            )

        # 源语字幕
        if e in (EventType.SourceSubtitleStart, EventType.SourceSubtitleResponse, EventType.SourceSubtitleEnd):
            return TranslationEvent(
                kind="source_text",
                text=resp.text,
                raw_event=e,
                is_definite=(e == EventType.SourceSubtitleEnd),
            )
        # 译文字幕
        if e in (EventType.TranslationSubtitleStart, EventType.TranslationSubtitleResponse, EventType.TranslationSubtitleEnd):
            return TranslationEvent(
                kind="target_text",
                text=resp.text,
                raw_event=e,
                is_definite=(e == EventType.TranslationSubtitleEnd),
            )

        # TTS 音频
        if e == EventType.TTSResponse and resp.data:
            return TranslationEvent(kind="audio", audio=resp.data, raw_event=e)

        # TTS 句子边界（需要用于 ogg_opus 累积解码）
        if e == EventType.TTSSentenceStart:
            return TranslationEvent(kind="sentence_start", raw_event=e)
        if e == EventType.TTSSentenceEnd:
            return TranslationEvent(kind="sentence_end", raw_event=e)
        if e == EventType.TTSEnded:
            return TranslationEvent(kind="tts_ended", raw_event=e)
        if e == EventType.UsageResponse:
            # 计费信息在 ResponseMeta.Billing，转 dict 方便日志/GUI 展示
            extra: dict = {}
            try:
                from google.protobuf.json_format import MessageToDict
                extra = MessageToDict(resp.response_meta, preserving_proto_field_name=True)
            except Exception:
                pass
            summary = message or str(extra.get("billing") or extra)
            return TranslationEvent(kind="usage", raw_event=e, message=summary)
        if e == EventType.AudioMuted:
            return TranslationEvent(kind="raw", raw_event=e)

        logger.debug(f"unhandled event={EventType.Name(e) if e else 'None'}({e})")
        return None
