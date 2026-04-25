"""配置：.env + 环境变量 + CLI 参数。"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Credentials:
    app_key: str
    access_key: str
    resource_id: str = "volc.service_type.10053"

    @staticmethod
    def from_env() -> "Credentials":
        load_dotenv(PROJECT_ROOT / ".env")
        app_key = os.getenv("DOUBAO_APP_KEY", "").strip()
        access_key = os.getenv("DOUBAO_ACCESS_KEY", "").strip()
        resource_id = os.getenv("DOUBAO_RESOURCE_ID", "volc.service_type.10053").strip()
        if not app_key or not access_key:
            raise RuntimeError(
                "缺少豆包同传密钥。请在 .env 中设置 DOUBAO_APP_KEY 和 DOUBAO_ACCESS_KEY。"
                "参考 .env.example。"
            )
        return Credentials(app_key=app_key, access_key=access_key, resource_id=resource_id)


@dataclass
class AudioConfig:
    input_device: Optional[str] = None          # 采集设备名子串匹配，None 用默认
    output_device: Optional[str] = "CABLE Input"  # 虚拟麦名子串匹配
    input_sample_rate: int = 16000
    output_sample_rate: int = 48000               # 48kHz fullband opus（官方 demo 用 24000 但听感闷；48kHz 高频保留更好）
    channels: int = 1
    bits: int = 16
    chunk_ms: int = 80                            # 每包音频时长（与 sokuji/豆包参考值一致）
    jitter_buffer_ms: int = 120                   # 播放侧 jitter buffer（越小越快）
    silence_rms_threshold: float = 0.010          # RMS 静音阈值(0-1)，过滤背景噪音 / 回声
    output_format: str = "ogg_opus"               # 豆包 target_audio.format: 默认 ogg_opus（pcm 实测未响应）
    keepalive_ms: int = 80                        # 无人声时发送静音包维持会话


@dataclass
class TranslationConfig:
    source_language: str = "zh"
    target_language: str = "en"
    mode: str = "s2s"                             # "s2s" 语音到语音 / "s2t" 语音到文本
    voice_clone: bool = True
    speaker_id: str = ""                          # 豆包 AST proto 字段；空=默认克隆模式
                                                  # 可试 "clone" / "0" / "auto" / UUID 等


@dataclass
class NetworkConfig:
    ws_url: str = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
    connect_timeout_s: float = 10.0
    session_timeout_s: float = 5.0
    reconnect_base_s: float = 1.0
    reconnect_max_s: float = 30.0
    reconnect_max_retries: int = 0                # 0 = 无限


@dataclass
class AppConfig:
    credentials: Credentials
    audio: AudioConfig = field(default_factory=AudioConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    network: NetworkConfig = field(default_factory=NetworkConfig)
    log_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")
    log_level: str = "INFO"
    # 隐私敏感：默认关闭，开启后译音原始 ogg / 字幕文本会落盘
    dump_audio_to_disk: bool = False
    log_subtitle_text: bool = False

    @staticmethod
    def load() -> "AppConfig":
        load_dotenv(PROJECT_ROOT / ".env")
        cfg = AppConfig(credentials=Credentials.from_env())
        # 选择性读环境变量覆盖默认
        if src := os.getenv("SOURCE_LANG"):
            cfg.translation.source_language = src
        if tgt := os.getenv("TARGET_LANG"):
            cfg.translation.target_language = tgt
        if mode := os.getenv("MODE"):
            cfg.translation.mode = mode
        if sp := os.getenv("SPEAKER_ID"):
            cfg.translation.speaker_id = sp
        if dev_in := os.getenv("INPUT_DEVICE"):
            cfg.audio.input_device = dev_in
        if dev_out := os.getenv("OUTPUT_DEVICE"):
            cfg.audio.output_device = dev_out
        if level := os.getenv("LOG_LEVEL"):
            cfg.log_level = level
        if os.getenv("DUMP_AUDIO", "").lower() in ("1", "true", "yes"):
            cfg.dump_audio_to_disk = True
        if os.getenv("LOG_SUBTITLE", "").lower() in ("1", "true", "yes"):
            cfg.log_subtitle_text = True
        return cfg
