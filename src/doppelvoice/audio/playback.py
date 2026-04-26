"""虚拟麦克风播放：jitter buffer + 自动重采样。"""
from __future__ import annotations

import asyncio
import collections
import threading
from typing import Optional

import numpy as np
import sounddevice as sd
from loguru import logger

from doppelvoice.audio.devices import find_device
from doppelvoice.audio.resample import resample_int16 as _resample
from doppelvoice.config import AudioConfig


class VirtualMicPlayback:
    """把译音 PCM 连续写入虚拟麦设备。

    关键设计：运行时把设备原生 sr 暴露给外部（例如 opus decoder），
    让上游直接 resample 到设备率，避免双重重采样引入速度/失真问题。
    """

    def __init__(self, cfg: AudioConfig):
        self.cfg = cfg
        # 兼容两种推送：若上游按 output_sample_rate 推，playback 再重采样到 dst_sr
        self.src_sr = cfg.output_sample_rate
        self.dst_sr: int = cfg.output_sample_rate
        self.stream: Optional[sd.RawOutputStream] = None

        # Jitter buffer：环形累积 int16 样本，回调时按需取
        self._lock = threading.Lock()
        self._buf = bytearray()
        self._started = False
        self._min_start_bytes = 0    # 首次蓄能阈值（默认 jitter_buffer_ms）
        self._restart_bytes = 0      # 下溢后重启阈值（缩短为 1/3 jitter_buffer_ms）
        self._max_buf_bytes = 0      # 上限：超过即丢弃最早音频防止漂移
        self._silence_chunk: bytes = b""
        self._underruns = 0
        self._bytes_written = 0
        self._bytes_dropped = 0

    def start(self) -> None:
        dev = find_device(self.cfg.output_device, need_output=True)
        if dev is None:
            raise RuntimeError(
                f"找不到输出虚拟麦 '{self.cfg.output_device}'。请先装 VB-Audio Virtual Cable。"
            )
        # 用设备原生采样率，避免 Windows 软重采样失真
        self.dst_sr = int(dev.default_samplerate)
        frames_per_chunk = int(self.dst_sr * self.cfg.chunk_ms / 1000)

        # jitter 目标字节数 = jitter_ms * dst_sr * 2(bytes/sample)
        bytes_per_ms = self.dst_sr * 2 // 1000  # int16 mono
        self._min_start_bytes = self.cfg.jitter_buffer_ms * bytes_per_ms
        self._restart_bytes = max(self._min_start_bytes // 3, 80 * bytes_per_ms)  # ≥80ms
        # 缓冲上限：opus 模式按整句推入（一句可达 5+ 秒），需留足空间
        # PCM 流模式按 chunk 推入（每次 <100ms），可以更紧封顶避免漂移
        if self.cfg.output_format == "ogg_opus":
            # 30 秒上限，足够装下任何合理的译音句子
            self._max_buf_bytes = 30_000 * bytes_per_ms
        else:
            # PCM 流模式：3× jitter_buffer（~360ms）就够了
            self._max_buf_bytes = self._min_start_bytes * 3
        self._silence_chunk = b"\x00" * (frames_per_chunk * 2)
        logger.debug(
            f"playback cap: jitter={self.cfg.jitter_buffer_ms}ms restart={self._restart_bytes // bytes_per_ms}ms "
            f"max_buf={self._max_buf_bytes // bytes_per_ms}ms (format={self.cfg.output_format})"
        )

        logger.info(
            f"opening virtual mic: device={dev.name} sr={self.dst_sr}Hz jitter={self.cfg.jitter_buffer_ms}ms "
            f"chunk={frames_per_chunk} frames"
        )
        self.stream = sd.RawOutputStream(
            samplerate=self.dst_sr,
            blocksize=frames_per_chunk,
            device=dev.index,
            channels=self.cfg.channels,
            dtype="int16",
            latency="low",
            callback=self._callback,
        )
        self.stream.start()

    def _callback(self, outdata, frames, time_info, status):  # noqa: D401
        if status:
            logger.debug(f"playback status: {status}")
        need = frames * 2  # int16 mono
        threshold = self._min_start_bytes if self._underruns == 0 else self._restart_bytes
        with self._lock:
            if not self._started:
                if len(self._buf) >= threshold:
                    self._started = True
                else:
                    outdata[:] = self._silence_chunk[:need]
                    return
            if len(self._buf) >= need:
                # 直接 slice 写 ctypes buffer，省一次中间 bytes() 拷贝
                outdata[:] = self._buf[:need]
                del self._buf[:need]
            else:
                # underrun：能吐多少吐多少，其余静音
                have_len = len(self._buf)
                outdata[:have_len] = self._buf[:have_len]
                outdata[have_len:] = self._silence_chunk[:need - have_len]
                self._buf.clear()
                self._underruns += 1
                self._started = False  # 重新进入蓄能阶段（阈值会降到 _restart_bytes）

    def push_pcm(self, pcm_bytes: bytes) -> None:
        """接收豆包返回的 PCM，必要时重采样后进 buffer。超限时丢最早防漂移。"""
        if not pcm_bytes:
            return
        if self.src_sr != self.dst_sr:
            arr = np.frombuffer(pcm_bytes, dtype=np.int16)
            arr = _resample(arr, self.src_sr, self.dst_sr)
            pcm_bytes = arr.tobytes()
        with self._lock:
            self._buf.extend(pcm_bytes)
            self._bytes_written += len(pcm_bytes)
            if self._max_buf_bytes and len(self._buf) > self._max_buf_bytes:
                excess = len(self._buf) - self._max_buf_bytes
                del self._buf[:excess]
                self._bytes_dropped += excess

    def buffer_depth_ms(self) -> int:
        with self._lock:
            return int(len(self._buf) / 2 / self.dst_sr * 1000)

    @property
    def device_sample_rate(self) -> int:
        """设备原生采样率（start() 后才有效）。供上游直接 resample 避免双重重采样。"""
        return self.dst_sr

    def push_pcm_at_device_rate(self, pcm_bytes: bytes) -> None:
        """接收已经按设备原生 sr 重采样好的 PCM，直接进 buffer 不再 resample。"""
        if not pcm_bytes:
            return
        with self._lock:
            self._buf.extend(pcm_bytes)
            self._bytes_written += len(pcm_bytes)
            if self._max_buf_bytes and len(self._buf) > self._max_buf_bytes:
                excess = len(self._buf) - self._max_buf_bytes
                del self._buf[:excess]
                self._bytes_dropped += excess

    def flush(self) -> None:
        """清空缓冲（用于重连时丢弃旧会话残留）。"""
        with self._lock:
            self._buf.clear()
            self._started = False

    def stop(self) -> None:
        if self.stream is not None:
            try:
                self.stream.stop()
                self.stream.close()
            except Exception as e:
                logger.warning(f"stop playback: {e}")
            self.stream = None
        logger.info(
            f"playback stopped, underruns={self._underruns}, "
            f"bytes={self._bytes_written}, dropped={self._bytes_dropped}"
        )
