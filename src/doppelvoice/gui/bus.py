"""Qt 信号总线：pipeline 事件 → GUI。"""
from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from doppelvoice.engine.doubao import TranslationEvent


class GuiEventBus(QObject):
    # (text, is_definite)
    source_text = Signal(str, bool)
    target_text = Signal(str, bool)
    # audio bytes length
    audio_received = Signal(int)
    # status: "idle" | "connecting" | "running" | "error" | "stopped"
    status = Signal(str, str)  # status_key, human message
    # arbitrary error
    error = Signal(str)
    # metrics: capture_q, buffer_ms, drops
    metrics = Signal(dict)
    # usage info
    usage = Signal(str)

    def emit_event(self, ev: TranslationEvent) -> None:
        """Orchestrator 调用：把 TranslationEvent 分发到对应 signal。"""
        if ev.kind == "source_text" and ev.text:
            self.source_text.emit(ev.text, ev.is_definite)
        elif ev.kind == "target_text" and ev.text:
            self.target_text.emit(ev.text, ev.is_definite)
        elif ev.kind == "audio" and ev.audio:
            self.audio_received.emit(len(ev.audio))
        elif ev.kind == "error":
            self.error.emit(f"code={ev.status_code} msg={ev.message}")
        elif ev.kind == "usage":
            self.usage.emit(str(ev.message or ""))

    # 兼容 EventBus Protocol
    def emit(self, ev: TranslationEvent) -> None:
        self.emit_event(ev)
