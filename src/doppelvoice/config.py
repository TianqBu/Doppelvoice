"""配置：.env + 环境变量 + CLI 参数。

设计：
- AudioConfig / TranslationConfig / NetworkConfig 都是 `frozen=True`
  → 单一一份子 config 一旦创建就不能就地修改，避免"Orchestrator 跑着会话时
  SettingsDialog 偷偷改了 chunk_ms"这种数据竞争。
- 想"修改"一个子 config，必须用 `dataclasses.replace(cfg.audio, chunk_ms=80)`
  返回新副本，再把新副本赋回 `app_cfg.audio`。
- AppConfig 本身是可变容器（持有子 config 的引用），上层可以原子地换整个子 config。
- Credentials 仍可变（密钥轮换 / 启动时回灌支持）。
- Orchestrator 在 __init__ 用 `dataclasses.replace(cfg)` 做浅拷贝快照，
  之后 GUI 再换 cfg.audio 不会影响正在跑的会话。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
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


@dataclass(frozen=True)
class AudioConfig:
    input_device: Optional[str] = None          # 采集设备名子串匹配，None 用默认
    output_device: Optional[str] = "CABLE Input"  # 虚拟麦名子串匹配
    input_sample_rate: int = 16000
    output_sample_rate: int = 48000               # 48kHz fullband opus（官方 demo 用 24000 但听感闷；48kHz 高频保留更好）
    channels: int = 1
    bits: int = 16
    chunk_ms: int = 80                            # 每包音频时长（与 sokuji/豆包参考值一致）
    jitter_buffer_ms: int = 120                   # 播放侧 jitter buffer（越小越快）
    # 0 = 关闭客户端 VAD（推荐，豆包服务端有自己的 VAD）。
    # 之前默认 0.010 会把首字辅音/气声当成静音过滤掉，每句首字延迟 +300-500ms。
    # 仅在嘈杂环境下用户主动调高时启用。
    silence_rms_threshold: float = 0.0
    output_format: str = "ogg_opus"               # 豆包 target_audio.format: 默认 ogg_opus（pcm 实测未响应）
    keepalive_ms: int = 80                        # 无人声时发送静音包维持会话


@dataclass(frozen=True)
class TranslationConfig:
    source_language: str = "zh"
    target_language: str = "en"
    mode: str = "s2s"                             # "s2s" 语音到语音 / "s2t" 语音到文本
    voice_clone: bool = True
    speaker_id: str = ""                          # 豆包 AST proto 字段；空=默认克隆模式
                                                  # 可试 "clone" / "0" / "auto" / UUID 等
    # 关键：影响零样本音色克隆的还原度。
    #   true  → 服务端先降噪再喂模型，输入听起来更干净，但会磨平气声/共鸣等独特音色细节
    #   false → 输入原样喂模型，保留更多说话人特征，克隆更像本人（默认）
    # proto 字段为 optional bool，不显式发送时使用服务端默认值（推测为 true）
    denoise: bool = False


@dataclass(frozen=True)
class NetworkConfig:
    ws_url: str = "wss://openspeech.bytedance.com/api/v4/ast/v2/translate"
    connect_timeout_s: float = 10.0
    session_timeout_s: float = 5.0
    reconnect_base_s: float = 1.0
    reconnect_max_s: float = 30.0
    reconnect_max_retries: int = 0                # 0 = 无限


@dataclass
class AppConfig:
    """可变容器：持有 frozen 子 config 的引用。要更改子配置走 replace() 路径。"""
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
        # 选择性读环境变量覆盖默认；frozen 子 config 用 replace 重建
        translation_overrides: dict[str, object] = {}
        if src := os.getenv("SOURCE_LANG"):
            translation_overrides["source_language"] = src
        if tgt := os.getenv("TARGET_LANG"):
            translation_overrides["target_language"] = tgt
        if mode := os.getenv("MODE"):
            translation_overrides["mode"] = mode
        if sp := os.getenv("SPEAKER_ID"):
            translation_overrides["speaker_id"] = sp
        if dn := os.getenv("DENOISE"):
            translation_overrides["denoise"] = dn.lower() in ("1", "true", "yes")
        if translation_overrides:
            cfg.translation = replace(cfg.translation, **translation_overrides)

        audio_overrides: dict[str, object] = {}
        if dev_in := os.getenv("INPUT_DEVICE"):
            audio_overrides["input_device"] = dev_in
        if dev_out := os.getenv("OUTPUT_DEVICE"):
            audio_overrides["output_device"] = dev_out
        if audio_overrides:
            cfg.audio = replace(cfg.audio, **audio_overrides)

        if level := os.getenv("LOG_LEVEL"):
            cfg.log_level = level
        if os.getenv("DUMP_AUDIO", "").lower() in ("1", "true", "yes"):
            cfg.dump_audio_to_disk = True
        if os.getenv("LOG_SUBTITLE", "").lower() in ("1", "true", "yes"):
            cfg.log_subtitle_text = True
        return cfg

    def snapshot(self) -> "AppConfig":
        """浅拷贝整个 AppConfig（子 config 是 frozen，引用即不可变）。
        Orchestrator 在 __init__ 用它隔离自己看到的 cfg 与 GUI 后续的修改。
        """
        return replace(self)
