"""Ogg/Opus 流解码器。

豆包 TTS s2s 会返回 ogg_opus 分片：TTSSentenceStart 后会陆续到来 TTSResponse（每个携带
ogg chunk），TTSSentenceEnd 标记整句结束。单个 TTSResponse 通常不是完整 OGG 文件，需要
累积到句末一次性交给 soundfile 解码。
"""
from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import soundfile as sf
from loguru import logger


class OggOpusDecoder:
    """累积一句内的 ogg_opus 分片，在 finalize 时解码为 int16 PCM。"""

    def __init__(self) -> None:
        self._chunks: list[bytes] = []

    def feed(self, chunk: bytes) -> None:
        if chunk:
            self._chunks.append(chunk)

    def has_data(self) -> bool:
        return bool(self._chunks)

    def size(self) -> int:
        return sum(len(c) for c in self._chunks)

    def drain(self, target_sr: int, dump_path: "Path | None" = None) -> bytes:
        """解码累积数据到 int16 mono PCM bytes。调用后内部清空。"""
        if not self._chunks:
            return b""
        blob = b"".join(self._chunks)
        self._chunks = []

        # 可选：落盘便于离线分析
        if dump_path is not None:
            try:
                dump_path.parent.mkdir(parents=True, exist_ok=True)
                dump_path.write_bytes(blob)
            except Exception as e:
                logger.debug(f"sentence dump failed: {e}")

        try:
            data, sr = sf.read(io.BytesIO(blob), dtype="float32")
        except Exception as e:
            logger.warning(
                f"opus decode FAILED: {e}; blob_len={len(blob)} "
                f"head_hex={blob[:32].hex()}"
            )
            return b""

        if data.ndim > 1:
            data = data.mean(axis=1)

        native_duration = len(data) / sr
        logger.info(
            f"opus decoded: blob={len(blob)}B → {len(data)} samples @ {sr}Hz "
            f"→ target {target_sr}Hz, duration={native_duration:.2f}s"
        )

        pcm16 = np.clip(data * 32767.0, -32768, 32767).astype(np.int16)
        if sr != target_sr:
            from doppelvoice.audio.resample import resample_int16
            pcm16 = resample_int16(pcm16, sr, target_sr)

        # 验证时长一致（重采样后 duration 应保持不变）
        out_duration = len(pcm16) / target_sr
        if abs(out_duration - native_duration) > 0.05:  # 50ms 容差
            logger.warning(
                f"⚠️ 重采样 duration 不一致: 源 {native_duration:.3f}s → 输出 {out_duration:.3f}s"
            )

        return pcm16.tobytes()

    def reset(self) -> None:
        self._chunks = []
