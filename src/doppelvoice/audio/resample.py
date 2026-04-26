"""共享的 int16 重采样实现。

提取出来的目的：
- 之前 capture.py 和 playback.py 各有一份 _resample，opus_decoder.py 还反向 import
  capture._resample —— 形成 audio.opus_decoder → audio.capture 的循环依赖味。
- 把 _resample 抽到中立模块 doppelvoice.audio.resample，三家都依赖它，无循环。
"""
from __future__ import annotations

import numpy as np

try:
    import soxr  # type: ignore
    _HAS_SOXR = True
except ImportError:  # soxr 可选；缺了用线性插值兜底
    _HAS_SOXR = False


def resample_int16(pcm_int16: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
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


__all__ = ["resample_int16"]
