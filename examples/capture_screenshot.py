"""自动截图：构造主窗口 + 预填示例数据 → 渲染为 PNG。"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import QApplication

from doppelvoice.config import AppConfig, Credentials
from doppelvoice.gui.i18n import I18n
from doppelvoice.gui.main_window import MainWindow
from doppelvoice.gui.theme import stylesheet


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyleSheet(stylesheet("dark"))

    cfg = AppConfig(credentials=Credentials(
        app_key="(redacted)", access_key="(redacted)",
        resource_id="volc.service_type.10053",
    ))
    i18n = I18n("zh")  # 截中文版
    win = MainWindow(cfg, i18n, theme="dark")
    win.resize(960, 760)

    # 预填示例字幕，让截图有内容
    samples_zh = [
        "大家好，欢迎来到今天的会议。",
        "我们今天要讨论的是新一代实时语音同传技术。",
        "这个系统不仅能翻译你的语言，还能保留你独特的音色。",
    ]
    samples_en = [
        "Hello everyone, welcome to today's meeting.",
        "Today we'll be discussing next-generation real-time speech interpretation.",
        "This system not only translates your language but also preserves your unique voice.",
    ]
    for s in samples_zh:
        win.src_view.feed(s, True)
    for s in samples_en:
        win.tgt_view.feed(s, True)

    # 设状态为运行中
    win.status_badge.set_state("running", i18n.t("status.running"))

    # 设置一些指标
    win._sentence_count = 12
    win._audio_bytes = 145600
    win._tick_metrics()

    # 模拟麦克风电平
    win.audio_meter.set_level(0.65)

    win.show()

    out_path = Path(__file__).resolve().parents[1] / "docs" / "images" / "screenshot.png"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _grab():
        # 等渲染完成
        pixmap = win.grab()
        pixmap.save(str(out_path), "PNG")
        print(f"saved: {out_path}  ({pixmap.size().width()}x{pixmap.size().height()})")
        win._stop_mic_meter()  # 释放音频流
        QApplication.quit()

    QTimer.singleShot(800, _grab)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
