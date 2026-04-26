"""国际化 / Internationalization."""
from __future__ import annotations

import locale
from typing import Callable, Literal

from PySide6.QtCore import QObject, Signal

Language = Literal["zh", "en"]

TRANSLATIONS: dict[Language, dict[str, str]] = {
    "zh": {
        "app.title": "Doppelvoice",
        "app.subtitle": "端到端实时语音翻译 + 0样本音色克隆",
        # menu
        "menu.file": "文件",
        "menu.file.settings": "设置…",
        "menu.file.exit": "退出",
        "menu.view": "视图",
        "menu.view.theme.dark": "深色主题",
        "menu.view.theme.light": "浅色主题",
        "menu.lang": "语言",
        "menu.lang.zh": "简体中文",
        "menu.lang.en": "English",
        "menu.help": "帮助",
        "menu.help.about": "关于",
        "menu.help.docs": "文档",
        # toolbar / actions
        "action.start": "开始同传",
        "action.stop": "停止",
        "action.settings": "设置",
        "action.refresh_devices": "刷新设备",
        "action.clear_subtitles": "清空字幕",
        # status pill
        "status.idle": "空闲",
        "status.opening_audio": "打开音频设备",
        "status.audio_ready": "音频就绪",
        "status.connecting": "连接服务",
        "status.session_starting": "建立会话",
        "status.running": "运行中",
        "status.stopped": "已停止",
        "status.error": "错误",
        # config row
        "config.input_device": "麦克风",
        "config.output_device": "虚拟麦输出",
        "config.source_lang": "源语言",
        "config.target_lang": "目标语言",
        "config.mode": "模式",
        "config.lang.zh": "中文",
        "config.lang.en": "英文",
        "config.lang.ja": "日语",
        "config.lang.id": "印尼语",
        "config.lang.es": "西班牙语",
        "config.lang.pt": "葡萄牙语",
        "config.lang.de": "德语",
        "config.lang.fr": "法语",
        "config.lang.zhen": "中英互译",
        # subtitles
        "subtitle.source": "原文",
        "subtitle.target": "译文",
        # stats
        "stats.latency": "延迟",
        "stats.buffer": "缓冲",
        "stats.sentences": "句",
        "stats.audio_received": "译音",
        "stats.audio_level": "输入电平",
        # settings dialog
        "settings.title": "设置",
        "settings.tab.api": "API 凭据",
        "settings.tab.audio": "音频",
        "settings.tab.advanced": "高级",
        "settings.api.app_key": "App Key",
        "settings.api.access_key": "Access Key",
        "settings.api.resource_id": "Resource ID",
        "settings.api.help": "在火山引擎控制台 → 豆包语音 → 同声传译 2.0 → 应用管理获取",
        "settings.api.console_link": "打开控制台",
        "settings.api.test": "测试连接",
        "settings.api.test.testing": "测试中…",
        "settings.api.test.ok": "✓ 连接成功，鉴权通过",
        "settings.api.test.fail": "✗ 失败：{error}",
        "settings.api.show_secret": "显示密钥",
        "settings.audio.chunk_ms": "每包大小 (ms)",
        "settings.audio.jitter_ms": "Jitter buffer (ms)",
        "settings.audio.rms_gate": "静音门限",
        "settings.audio.input_sr": "输入采样率",
        "settings.audio.output_sr": "输出采样率",
        "settings.advanced.speaker_id": "Speaker ID（实验性，留空使用默认）",
        "settings.advanced.denoise": "服务端降噪（关闭可保留更多音色细节，克隆更像本人）",
        "settings.advanced.denoise.tip": "默认关闭。开启后服务端会在送入克隆模型前清理输入，"
                                         "听起来更干净但会磨平气声/共鸣等独特特征。",
        "settings.advanced.dump_audio": "调试：译音原始 ogg 落盘",
        "settings.advanced.log_subtitle": "调试：字幕文本写入日志",
        "settings.advanced.warning": "⚠ 启用调试落盘会把语音内容明文存到磁盘，仅用于排查问题",
        "settings.save": "保存",
        "settings.cancel": "取消",
        "settings.saved": "设置已保存到 .env",
        # wizard
        "wizard.title": "首次启动配置",
        "wizard.heading": "欢迎使用 Doppelvoice",
        "wizard.body": (
            "Doppelvoice 需要豆包同声传译 2.0 的 API 密钥才能工作。\n\n"
            "1. 访问火山引擎控制台 (console.volcengine.com)\n"
            "2. 豆包语音 → 同声传译 2.0 → 开通服务\n"
            "3. 应用管理页面复制 App Key 和 Access Key"
        ),
        "wizard.next": "下一步",
        "wizard.back": "上一步",
        "wizard.finish": "完成",
        "wizard.skip": "暂时跳过",
        # error / dialog
        "dialog.confirm_quit": "正在同传中，确认退出？",
        "dialog.error.title": "错误",
        "dialog.error.no_credentials": "未配置 API 密钥，请打开设置填写。",
        "dialog.error.cable_missing.title": "缺少虚拟音频设备",
        "dialog.error.cable_missing.body": (
            "找不到 CABLE Input 输出设备。\n\n"
            "请安装 VB-Audio Virtual Cable 并重启电脑：\n"
            "https://vb-audio.com/Cable/"
        ),
        "dialog.about.title": "关于 Doppelvoice",
        "dialog.about.body": (
            "Doppelvoice v0.1\n\n"
            "你的声音，跨越语言。\n"
            "端到端实时语音翻译 + 0 样本音色克隆\n\n"
            "基于字节豆包同声传译 2.0 (Seed LiveInterpret 2.0)\n"
            "MIT License"
        ),
    },
    "en": {
        "app.title": "Doppelvoice",
        "app.subtitle": "End-to-end speech translation with voice cloning",
        # menu
        "menu.file": "File",
        "menu.file.settings": "Settings…",
        "menu.file.exit": "Exit",
        "menu.view": "View",
        "menu.view.theme.dark": "Dark theme",
        "menu.view.theme.light": "Light theme",
        "menu.lang": "Language",
        "menu.lang.zh": "简体中文",
        "menu.lang.en": "English",
        "menu.help": "Help",
        "menu.help.about": "About",
        "menu.help.docs": "Documentation",
        # toolbar / actions
        "action.start": "Start",
        "action.stop": "Stop",
        "action.settings": "Settings",
        "action.refresh_devices": "Refresh devices",
        "action.clear_subtitles": "Clear",
        # status pill
        "status.idle": "Idle",
        "status.opening_audio": "Opening audio",
        "status.audio_ready": "Audio ready",
        "status.connecting": "Connecting",
        "status.session_starting": "Starting session",
        "status.running": "Running",
        "status.stopped": "Stopped",
        "status.error": "Error",
        # config row
        "config.input_device": "Microphone",
        "config.output_device": "Virtual mic output",
        "config.source_lang": "Source",
        "config.target_lang": "Target",
        "config.mode": "Mode",
        "config.lang.zh": "Chinese",
        "config.lang.en": "English",
        "config.lang.ja": "Japanese",
        "config.lang.id": "Indonesian",
        "config.lang.es": "Spanish",
        "config.lang.pt": "Portuguese",
        "config.lang.de": "German",
        "config.lang.fr": "French",
        "config.lang.zhen": "ZH ⇄ EN auto",
        # subtitles
        "subtitle.source": "Source",
        "subtitle.target": "Translation",
        # stats
        "stats.latency": "Latency",
        "stats.buffer": "Buffer",
        "stats.sentences": "sent.",
        "stats.audio_received": "Audio",
        "stats.audio_level": "Input level",
        # settings
        "settings.title": "Settings",
        "settings.tab.api": "API credentials",
        "settings.tab.audio": "Audio",
        "settings.tab.advanced": "Advanced",
        "settings.api.app_key": "App Key",
        "settings.api.access_key": "Access Key",
        "settings.api.resource_id": "Resource ID",
        "settings.api.help": "Get from Volcengine Console → Doubao Voice → Simultaneous Interpretation 2.0 → App Management",
        "settings.api.console_link": "Open Console",
        "settings.api.test": "Test connection",
        "settings.api.test.testing": "Testing…",
        "settings.api.test.ok": "✓ Connected — authentication OK",
        "settings.api.test.fail": "✗ Failed: {error}",
        "settings.api.show_secret": "Show secret",
        "settings.audio.chunk_ms": "Chunk size (ms)",
        "settings.audio.jitter_ms": "Jitter buffer (ms)",
        "settings.audio.rms_gate": "RMS silence gate",
        "settings.audio.input_sr": "Input sample rate",
        "settings.audio.output_sr": "Output sample rate",
        "settings.advanced.speaker_id": "Speaker ID (experimental, blank = default)",
        "settings.advanced.denoise": "Server-side denoise (off = keep voice-clone details)",
        "settings.advanced.denoise.tip": "Off by default. When on, the server cleans the input before "
                                         "the cloning model — sounds cleaner but flattens breath, resonance "
                                         "and other unique characteristics.",
        "settings.advanced.dump_audio": "Debug: dump translated audio (ogg) to disk",
        "settings.advanced.log_subtitle": "Debug: write subtitle text to log files",
        "settings.advanced.warning": "⚠ Debug persistence stores raw speech content on disk; for troubleshooting only.",
        "settings.save": "Save",
        "settings.cancel": "Cancel",
        "settings.saved": "Settings saved to .env",
        # wizard
        "wizard.title": "First-time setup",
        "wizard.heading": "Welcome to Doppelvoice",
        "wizard.body": (
            "Doppelvoice needs Doubao Simultaneous Interpretation 2.0 credentials to work.\n\n"
            "1. Sign in at Volcengine Console (console.volcengine.com)\n"
            "2. Doubao Voice → Simultaneous Interpretation 2.0 → activate service\n"
            "3. Copy App Key and Access Key from App Management"
        ),
        "wizard.next": "Next",
        "wizard.back": "Back",
        "wizard.finish": "Finish",
        "wizard.skip": "Skip for now",
        # dialog
        "dialog.confirm_quit": "A session is running. Quit anyway?",
        "dialog.error.title": "Error",
        "dialog.error.no_credentials": "API credentials not configured. Open Settings to enter them.",
        "dialog.error.cable_missing.title": "Virtual audio device missing",
        "dialog.error.cable_missing.body": (
            "Cannot find CABLE Input output device.\n\n"
            "Install VB-Audio Virtual Cable and reboot:\n"
            "https://vb-audio.com/Cable/"
        ),
        "dialog.about.title": "About Doppelvoice",
        "dialog.about.body": (
            "Doppelvoice v0.1\n\n"
            "Your voice, in any language.\n"
            "End-to-end speech-to-speech translation with zero-shot voice cloning.\n\n"
            "Powered by ByteDance Doubao Simultaneous Interpretation 2.0\n"
            "MIT License"
        ),
    },
}


def detect_system_language() -> Language:
    """跳系统语言：中文系统返回 'zh'，其余返回 'en'。

    Python 3.11+ 标记 locale.getdefaultlocale() 为 deprecated，改用 getlocale()。
    """
    try:
        loc = locale.getlocale()[0] or ""
    except Exception:
        loc = ""
    return "zh" if loc.lower().startswith("zh") else "en"


class I18n(QObject):
    """全局翻译表，发 Signal 通知 GUI 重绘文案。"""
    language_changed = Signal(str)

    def __init__(self, lang: Language | None = None):
        super().__init__()
        self._lang: Language = lang or detect_system_language()

    @property
    def lang(self) -> Language:
        return self._lang

    def set_language(self, lang: Language) -> None:
        if lang == self._lang:
            return
        self._lang = lang
        self.language_changed.emit(lang)

    def t(self, key: str, **kwargs: str) -> str:
        text = TRANSLATIONS[self._lang].get(key) or TRANSLATIONS["en"].get(key) or key
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                return text
        return text


# 全局单例（模块加载时初始化为系统语言）
i18n = I18n()


def t(key: str, **kwargs: str) -> str:
    """便捷函数。"""
    return i18n.t(key, **kwargs)
