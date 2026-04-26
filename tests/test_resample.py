"""resample_int16 单元测试。"""
from __future__ import annotations

import numpy as np
import pytest

from doppelvoice.audio.resample import resample_int16


def test_same_rate_returns_input():
    x = np.array([1, 2, 3, 4, 5], dtype=np.int16)
    out = resample_int16(x, 16000, 16000)
    np.testing.assert_array_equal(out, x)


def test_empty_input():
    x = np.array([], dtype=np.int16)
    out = resample_int16(x, 16000, 48000)
    assert len(out) == 0


def test_upsample_2x_doubles_length():
    x = (np.sin(np.linspace(0, 2 * np.pi, 1000)) * 10000).astype(np.int16)
    out = resample_int16(x, 16000, 32000)
    # 允许 ±1 sample 的舍入误差
    assert abs(len(out) - 2000) <= 1


def test_downsample_3x_thirds_length():
    x = (np.sin(np.linspace(0, 2 * np.pi, 9000)) * 10000).astype(np.int16)
    out = resample_int16(x, 48000, 16000)
    assert abs(len(out) - 3000) <= 1


def test_dtype_int16_preserved():
    x = (np.random.uniform(-10000, 10000, 1000)).astype(np.int16)
    out = resample_int16(x, 16000, 24000)
    assert out.dtype == np.int16


def test_clipping_no_overflow():
    """边界值不应该 wrap-around。"""
    x = np.full(1000, 32000, dtype=np.int16)  # 接近 int16 上限
    out = resample_int16(x, 16000, 48000)
    assert out.max() <= 32767
    assert out.min() >= -32768
