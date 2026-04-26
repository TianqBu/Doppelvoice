"""配置 frozen + snapshot 行为单元测试。"""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace

import pytest

from doppelvoice.config import (
    AppConfig,
    AudioConfig,
    Credentials,
    NetworkConfig,
    TranslationConfig,
)


def test_audio_config_is_frozen():
    a = AudioConfig()
    with pytest.raises(FrozenInstanceError):
        a.chunk_ms = 100  # type: ignore[misc]


def test_translation_config_is_frozen():
    t = TranslationConfig()
    with pytest.raises(FrozenInstanceError):
        t.source_language = "ja"  # type: ignore[misc]


def test_network_config_is_frozen():
    n = NetworkConfig()
    with pytest.raises(FrozenInstanceError):
        n.connect_timeout_s = 5.0  # type: ignore[misc]


def test_replace_returns_independent_copy():
    a = AudioConfig(chunk_ms=80)
    b = replace(a, chunk_ms=160)
    assert a.chunk_ms == 80
    assert b.chunk_ms == 160


def test_appconfig_audio_swap():
    """AppConfig 仍可变 → 可以原子换整个 audio 引用。"""
    cfg = AppConfig(credentials=Credentials("k", "s"))
    old = cfg.audio
    cfg.audio = replace(cfg.audio, chunk_ms=200)
    assert old.chunk_ms == 80  # 原引用未变
    assert cfg.audio.chunk_ms == 200


def test_snapshot_isolates_subsequent_swaps():
    """snapshot() 拿到副本后，原 cfg 的 audio swap 不应污染快照。"""
    cfg = AppConfig(credentials=Credentials("k", "s"))
    snap = cfg.snapshot()
    cfg.audio = replace(cfg.audio, chunk_ms=999)
    assert snap.audio.chunk_ms == 80  # 快照保持
    assert cfg.audio.chunk_ms == 999


def test_credentials_still_mutable():
    """Credentials 还是可变的（运行时回灌密钥）。"""
    c = Credentials(app_key="x", access_key="y")
    c.app_key = "z"
    assert c.app_key == "z"


def test_default_denoise_is_false():
    """B-perf #denoise：克隆音色保留默认行为。"""
    t = TranslationConfig()
    assert t.denoise is False


def test_default_silence_threshold_is_zero():
    """B-perf #silence：默认关闭客户端 VAD。"""
    a = AudioConfig()
    assert a.silence_rms_threshold == 0.0
