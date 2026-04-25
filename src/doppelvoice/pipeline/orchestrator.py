"""
流水线编排：采集 → WebSocket 发送；WebSocket 接收 → 播放 + 字幕打印。
具备：优雅退出、指数退避重连、指标周期打印。
"""
from __future__ import annotations

import asyncio
import signal
from typing import Callable, Optional, Protocol

from loguru import logger

from doppelvoice.audio.capture import MicCapture
from doppelvoice.audio.opus_decoder import OggOpusDecoder
from doppelvoice.audio.playback import VirtualMicPlayback
from doppelvoice.engine.doubao import DoubaoClient, TranslationEvent
from doppelvoice.config import AppConfig


class _FatalRemote(Exception):
    """服务端致命错误（鉴权/参数/权限/音频格式）——不重连，直接退出。"""
    def __init__(self, code: Optional[int], message: Optional[str]):
        super().__init__(f"FATAL remote code={code} msg={message}")
        self.code = code
        self.message = message


# 只对"瞬时"错误重连（对应 au_base.proto Code 枚举）
_TRANSIENT_CODES = {
    0,         # 未填
    11301,     # LIMIT_QPS
    11303,     # SERVER_BUSY
    21100,     # ERROR_PROCESSING
    21200,     # TIMEOUT_WAITING
    21201,     # TIMEOUT_PROCESSING
    21300,     # INTERRUPTED
    21701,     # AUDIO_DOWNLOAD_FAIL
    29900,     # ERROR_UNKNOWN（可能是瞬时）
}


class EventBus(Protocol):
    """供 GUI 订阅事件。"""
    def emit(self, ev: TranslationEvent) -> None: ...


def _drain_queue(q: asyncio.Queue) -> int:
    """清空队列，返回丢弃的元素数。"""
    n = 0
    while True:
        try:
            q.get_nowait()
            n += 1
        except asyncio.QueueEmpty:
            break
    return n


class Orchestrator:
    def __init__(self, cfg: AppConfig, event_bus: Optional[EventBus] = None):
        self.cfg = cfg
        self.event_bus = event_bus
        self._stop = asyncio.Event()
        self._metrics_task: Optional[asyncio.Task] = None

    def stop(self) -> None:
        """线程安全：供 GUI / 外部代码触发优雅停机。"""
        self._stop.set()

    def _emit_status(self, key: str, msg: str) -> None:
        if self.event_bus is not None and hasattr(self.event_bus, "status"):
            try:
                self.event_bus.status.emit(key, msg)
            except Exception:
                pass

    async def run(self) -> None:
        loop = asyncio.get_running_loop()

        for sig_name in ("SIGINT", "SIGTERM"):
            if hasattr(signal, sig_name):
                try:
                    loop.add_signal_handler(getattr(signal, sig_name), self._stop.set)
                except NotImplementedError:
                    pass

        self._emit_status("opening_audio", "打开音频设备…")
        playback = VirtualMicPlayback(self.cfg.audio)
        playback.start()

        capture_q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=50)
        capture = MicCapture(self.cfg.audio, capture_q, loop)
        capture.start()
        self._emit_status("audio_ready", "音频就绪")

        self._metrics_task = asyncio.create_task(self._metrics_loop(playback, capture_q))

        try:
            attempt = 0
            while not self._stop.is_set():
                try:
                    await self._one_session(capture_q, playback)
                    attempt = 0  # 成功完整跑完重置退避
                except _FatalRemote as e:
                    logger.error(f"致命错误，不重连：{e}")
                    break
                except Exception as e:
                    attempt += 1
                    if self.cfg.network.reconnect_max_retries and attempt > self.cfg.network.reconnect_max_retries:
                        logger.error(f"超过最大重连次数 {self.cfg.network.reconnect_max_retries}，退出")
                        break
                    delay = min(
                        self.cfg.network.reconnect_base_s * (2 ** (attempt - 1)),
                        self.cfg.network.reconnect_max_s,
                    )
                    logger.error(f"会话异常: {e!r}；{delay:.1f}s 后重连 (#{attempt})")
                    try:
                        await asyncio.wait_for(self._stop.wait(), timeout=delay)
                        break
                    except asyncio.TimeoutError:
                        continue
        finally:
            if self._metrics_task:
                self._metrics_task.cancel()
            capture.stop()
            playback.stop()
            logger.info("已退出")

    async def _one_session(self, capture_q: asyncio.Queue[bytes], playback: VirtualMicPlayback) -> None:
        _drain_queue(capture_q)
        playback.flush()

        client = DoubaoClient(self.cfg)
        try:
            self._emit_status("ws_connecting", "连接豆包服务…")
            await client.connect()
            self._emit_status("session_starting", "建立会话…")
            await client.start_session()
            self._emit_status("running", "运行中")

            sender = asyncio.create_task(self._sender_loop(client, capture_q), name="sender")
            receiver = asyncio.create_task(self._receiver_loop(client, playback), name="receiver")
            stopper = asyncio.create_task(self._stop.wait(), name="stopper")

            done, pending = await asyncio.wait(
                {sender, receiver, stopper},
                return_when=asyncio.FIRST_COMPLETED,
            )

            # 竞争处理：sender 先失败时，服务端的 SessionFailed/SessionCanceled/error
            # 可能还在接收缓冲里没被读取。给 receiver 一个短窗口读完终态帧再取消，
            # 避免 fatal 分类被 sender 的普通异常吞掉（致错误码变成瞬时重连）
            if sender in done and receiver not in done and not self._stop.is_set():
                try:
                    await asyncio.wait_for(asyncio.shield(receiver), timeout=1.5)
                except asyncio.TimeoutError:
                    pass
                except Exception:
                    pass  # receiver 抛异常不在这层处理，交给后面统一 raise

            # 取消剩余 task 并收尾
            for t in (sender, receiver, stopper):
                if not t.done():
                    t.cancel()
            results = await asyncio.gather(sender, receiver, stopper, return_exceptions=True)

            # 优先抛 receiver 的异常（服务端 fatal 经这里），其次 sender
            for task, res in zip((receiver, sender), (results[1], results[0])):
                if isinstance(res, BaseException) and not isinstance(res, asyncio.CancelledError):
                    raise res

            await client.finish_session()
        finally:
            await client.close()

    async def _sender_loop(self, client: DoubaoClient, capture_q: asyncio.Queue[bytes]) -> None:
        """发送音频：有数据发数据，无数据定时发送静音帧维持会话。"""
        chunk_samples = int(self.cfg.audio.input_sample_rate * self.cfg.audio.chunk_ms / 1000)
        silence = b"\x00\x00" * chunk_samples
        keepalive_s = self.cfg.audio.keepalive_ms / 1000
        while not self._stop.is_set():
            try:
                chunk = await asyncio.wait_for(capture_q.get(), timeout=keepalive_s)
                await client.send_audio(chunk)
            except asyncio.TimeoutError:
                # 没采到音频：发静音保活，避免服务端超时
                await client.send_audio(silence)

    async def _receiver_loop(self, client: DoubaoClient, playback: VirtualMicPlayback) -> None:
        import time
        is_opus = self.cfg.audio.output_format == "ogg_opus"
        decoder = OggOpusDecoder() if is_opus else None
        logged_first_audio = False
        dump_root = (
            self.cfg.log_dir / "sentences" / time.strftime("%Y%m%d_%H%M%S")
            if self.cfg.dump_audio_to_disk else None
        )
        sentence_idx = 0
        in_sentence = False
        chunk_count_this_sentence = 0

        # 关键：让 decoder 直接 resample 到设备原生率，避免双重重采样引起的速度偏差
        playback_sr = playback.device_sample_rate
        logger.info(
            f"receiver pipeline: opus → decoder(target {playback_sr}Hz) → playback device {playback_sr}Hz"
        )

        def _dump_path(suffix: str = "") -> "Path | None":
            if dump_root is None:
                return None
            return dump_root / f"{sentence_idx:03d}{suffix}.ogg"

        async for ev in client.iter_events():
            if ev.kind == "audio" and ev.audio:
                if not logged_first_audio:
                    logger.info(
                        f"首个译音 chunk: {len(ev.audio)} bytes, "
                        f"magic={ev.audio[:4]!r}, format={self.cfg.audio.output_format}"
                    )
                    logged_first_audio = True
                if self.event_bus is not None:
                    self.event_bus.emit(ev)
                if decoder is not None:
                    decoder.feed(ev.audio)
                    chunk_count_this_sentence += 1
                else:
                    playback.push_pcm(ev.audio)
            elif ev.kind == "sentence_start" and decoder is not None:
                decoder.reset()
                in_sentence = True
                chunk_count_this_sentence = 0
                logger.debug("sentence_start")
            elif ev.kind == "sentence_end" and decoder is not None:
                in_sentence = False
                if decoder.has_data():
                    sentence_idx += 1
                    blob_size = decoder.size()
                    # 直接输出设备原生率，playback 不再 resample
                    pcm = decoder.drain(playback_sr, dump_path=_dump_path())
                    if pcm:
                        playback.push_pcm_at_device_rate(pcm)
                        logger.info(
                            f"[sent #{sentence_idx}] {chunk_count_this_sentence} chunks / "
                            f"{blob_size} B ogg → {len(pcm)} B PCM @ {playback_sr}Hz "
                            f"({len(pcm) // 2 / playback_sr:.2f}s)"
                        )
                    else:
                        logger.warning(
                            f"[sent #{sentence_idx}] 解码失败 "
                            f"({chunk_count_this_sentence} chunks / {blob_size} B)"
                        )
                else:
                    logger.debug(f"sentence_end 但无数据（chunks={chunk_count_this_sentence}）")
            elif ev.kind == "tts_ended" and decoder is not None and decoder.has_data():
                sentence_idx += 1
                blob_size = decoder.size()
                pcm = decoder.drain(playback_sr, dump_path=_dump_path("_endflush"))
                if pcm:
                    playback.push_pcm_at_device_rate(pcm)
                    logger.info(f"[tts_ended flush #{sentence_idx}] {blob_size}B ogg → {len(pcm)}B PCM")
            elif ev.kind == "target_text":
                # 跳过空文本（服务端 VAD 误触发会发空 start/end 对）
                if not (ev.text or "").strip():
                    continue
                if self.cfg.log_subtitle_text:
                    tag = "译文" if ev.is_definite else "译文·"
                    logger.info(f"[{tag}] {ev.text}")
                else:
                    logger.info(
                        f"[译文{'·终' if ev.is_definite else '·'}] ({len(ev.text)} chars)"
                    )
                if self.event_bus is not None:
                    self.event_bus.emit(ev)
            elif ev.kind == "source_text":
                if not (ev.text or "").strip():
                    continue
                if self.cfg.log_subtitle_text:
                    tag = "原文" if ev.is_definite else "原文·"
                    logger.debug(f"[{tag}] {ev.text}")
                if self.event_bus is not None:
                    self.event_bus.emit(ev)
            elif ev.kind == "error":
                logger.error(
                    f"服务端错误 event={ev.raw_event} code={ev.status_code} msg={ev.message!r}"
                )
                # 只白名单里的瞬时错误重连；其它（鉴权/参数/格式）全部 fatal
                if ev.status_code in _TRANSIENT_CODES:
                    raise RuntimeError(f"remote transient code={ev.status_code} msg={ev.message}")
                raise _FatalRemote(ev.status_code, ev.message)
            elif ev.kind == "session_finished":
                logger.info("会话结束")
                return
            elif ev.kind == "usage":
                logger.info(f"计费: {ev.message}")

    async def _metrics_loop(self, playback: VirtualMicPlayback, cap_q: asyncio.Queue[bytes]) -> None:
        try:
            while not self._stop.is_set():
                await asyncio.sleep(5)
                logger.info(
                    f"[metrics] capture_q={cap_q.qsize()}/{cap_q.maxsize} "
                    f"playback_buf={playback.buffer_depth_ms()}ms"
                )
        except asyncio.CancelledError:
            pass
