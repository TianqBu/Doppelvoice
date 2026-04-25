"""麦克风采集 → asyncio 队列。

设计要点：
- sounddevice 音频回调在独立线程，**不能**依赖 asyncio loop 存活。
- 回调只写入有界 thread-safe `queue.Queue`（满则丢最早），零 asyncio 交互。
- 一个独立 asyncio 任务 `_bridge()` 从 thread queue 搬运到 asyncio queue。
- 停机时设 `_closing` 标志，回调立即 short-circuit，避免往已销毁 loop 发送。
"""
from __future__ import annotations

import asyncio
import queue
import threading
from typing import Optional

import numpy as np
import sounddevice as sd
from loguru import logger

from doppelvoice.audio.devices import find_device
from doppelvoice.config import AudioConfig

try:
    import soxr  # type: ignore
    _HAS_SOXR = True
except ImportError:
    _HAS_SOXR = False


def _resample(pcm_int16: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
    """int16 → int16 重采样。优先 soxr（高质量），兜底线性插值。"""
    if src_sr == dst_sr or len(pcm_int16) == 0:
        return pcm_int16
    if _HAS_SOXR:
        out = soxr.resample(pcm_int16.astype(np.float32) / 32768.0, src_sr, dst_sr)
        return np.clip(out * 32768.0, -32768, 32767).astype(np.int16)
    n_out = int(len(pcm_int16) * dst_sr / src_sr)
    if n_out <= 0:
        return pcm_int16
    x = np.linspace(0, len(pcm_int16) - 1, n_out)
    return np.interp(x, np.arange(len(pcm_int16)), pcm_int16).astype(np.int16)


class MicCapture:
    """把麦克风 16kHz mono int16 PCM 以 chunk_ms 为粒度推入 asyncio 队列。"""

    def __init__(
        self,
        cfg: AudioConfig,
        out_queue: asyncio.Queue[bytes],
        loop: asyncio.AbstractEventLoop,
    ):
        self.cfg = cfg
        self.out_q = out_queue
        self.loop = loop
        self.stream: Optional[sd.RawInputStream] = None
        self.frames_per_chunk = int(cfg.input_sample_rate * cfg.chunk_ms / 1000)

        # 线程边界：回调只碰 thread_q + _closing（两者都线程安全）
        self._thread_q: "queue.Queue[bytes]" = queue.Queue(maxsize=50)
        self._closing = threading.Event()
        self._bridge_task: Optional[asyncio.Task] = None
        self._drops = 0

        # 采集时的实际采样率（可能 != cfg.input_sample_rate，需软件重采样）
        self._capture_sr: int = cfg.input_sample_rate
        self._capture_frames_per_chunk: int = self.frames_per_chunk

    def _callback(self, indata, frames, time_info, status):  # noqa: D401
        if self._closing.is_set():
            return
        if status:
            logger.debug(f"capture status: {status}")

        # 取 int16 mono 样本
        samples = np.frombuffer(bytes(indata), dtype=np.int16)

        # 如果多通道，取第一通道（理论上我们开的 channels=1，不会进这里）
        if self.cfg.channels == 1 and samples.ndim == 1 and len(samples) > frames:
            samples = samples[::len(samples) // frames]

        # 设备原生率 != 目标率时，软件重采样到目标率（16kHz）
        if self._capture_sr != self.cfg.input_sample_rate:
            samples = _resample(samples, self._capture_sr, self.cfg.input_sample_rate)

        if self.cfg.silence_rms_threshold > 0:
            rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2))) / 32768.0
            if rms < self.cfg.silence_rms_threshold:
                return

        data = samples.astype(np.int16).tobytes()

        try:
            self._thread_q.put_nowait(data)
        except queue.Full:
            try:
                self._thread_q.get_nowait()
                self._drops += 1
            except queue.Empty:
                pass
            try:
                self._thread_q.put_nowait(data)
            except queue.Full:
                self._drops += 1

    async def _bridge(self) -> None:
        """在 asyncio 侧拉 thread_q → out_q（out_q 已是 asyncio.Queue）。"""
        while not self._closing.is_set():
            try:
                chunk = await asyncio.get_running_loop().run_in_executor(
                    None, self._thread_q.get, True, 0.2
                )
            except queue.Empty:
                continue
            except Exception:
                if self._closing.is_set():
                    return
                raise
            if self.out_q.full():
                try:
                    self.out_q.get_nowait()
                    self._drops += 1
                except asyncio.QueueEmpty:
                    pass
            try:
                self.out_q.put_nowait(chunk)
            except asyncio.QueueFull:
                self._drops += 1

    def start(self) -> None:
        dev = find_device(self.cfg.input_device, need_input=True) if self.cfg.input_device else None
        device_idx = dev.index if dev else None
        target_sr = self.cfg.input_sample_rate

        # 优先尝试目标采样率，失败则回退到设备原生率（软件重采样）
        candidate_rates: list[int] = [target_sr]
        if dev is not None:
            native = int(dev.default_samplerate)
            if native != target_sr and native > 0:
                candidate_rates.append(native)
        # 常见兜底率
        for sr in (48000, 44100):
            if sr not in candidate_rates:
                candidate_rates.append(sr)

        self._closing.clear()
        last_err: Optional[Exception] = None
        for sr in candidate_rates:
            blocksize = int(sr * self.cfg.chunk_ms / 1000)
            try:
                self.stream = sd.RawInputStream(
                    samplerate=sr,
                    blocksize=blocksize,
                    device=device_idx,
                    channels=self.cfg.channels,
                    dtype="int16",
                    latency="low",
                    callback=self._callback,
                )
                self.stream.start()
                self._capture_sr = sr
                self._capture_frames_per_chunk = blocksize
                if sr != target_sr:
                    logger.info(
                        f"mic 原生率 {sr}Hz，将软件重采样到 {target_sr}Hz "
                        f"(soxr={'yes' if _HAS_SOXR else 'no'})"
                    )
                break
            except Exception as e:
                last_err = e
                logger.debug(f"open mic @ {sr}Hz failed: {e}")
        else:
            raise RuntimeError(
                f"无法打开麦克风（尝试了 {candidate_rates}Hz）: {last_err}"
            )

        logger.info(
            f"opening mic: device={dev.name if dev else '默认'} "
            f"capture_sr={self._capture_sr}Hz → target={target_sr}Hz "
            f"block={self._capture_frames_per_chunk} samples({self.cfg.chunk_ms}ms)"
        )
        self._bridge_task = self.loop.create_task(self._bridge())

    def stop(self) -> None:
        # 关键：先置 flag，再关 PortAudio 流，避免回调在 loop 销毁后继续跑
        self._closing.set()
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.warning(f"stop capture: {e}")
            self.stream = None
        if self._bridge_task is not None:
            self._bridge_task.cancel()
            self._bridge_task = None
        # 清空剩余 thread queue
        while True:
            try:
                self._thread_q.get_nowait()
            except queue.Empty:
                break
        logger.info(f"capture stopped, total_drops={self._drops}")
