"""实时音频电平表（VU meter）。"""
from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPaintEvent
from PySide6.QtWidgets import QWidget


class AudioLevelMeter(QWidget):
    """显示输入音频 RMS 电平。0..1 范围；自带衰减动画。"""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._target = 0.0
        self._displayed = 0.0
        self._peak = 0.0
        self._peak_hold_ticks = 0
        self.setMinimumHeight(8)
        self.setMaximumHeight(10)

        # 60Hz 衰减动画
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._timer.start()

    def set_level(self, level: float) -> None:
        self._target = max(0.0, min(1.0, level))
        if self._target > self._peak:
            self._peak = self._target
            self._peak_hold_ticks = 30  # ~0.5s

    def _tick(self) -> None:
        # 平滑追上目标值
        diff = self._target - self._displayed
        self._displayed += diff * 0.3
        if abs(diff) < 0.001:
            self._displayed = self._target
        # peak 衰减
        if self._peak_hold_ticks > 0:
            self._peak_hold_ticks -= 1
        else:
            self._peak *= 0.95
            if self._peak < 0.01:
                self._peak = 0.0
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        radius = rect.height() // 2

        # 背景轨道
        painter.setBrush(QColor("#16162a"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, radius, radius)

        # 填充条 - 渐变绿→黄→红
        if self._displayed > 0:
            fill_w = max(1, int(rect.width() * self._displayed))
            grad = QLinearGradient(0, 0, rect.width(), 0)
            grad.setColorAt(0.0, QColor("#00d4aa"))
            grad.setColorAt(0.7, QColor("#ffd93d"))
            grad.setColorAt(1.0, QColor("#ff6b6b"))
            painter.setBrush(grad)
            painter.drawRoundedRect(QRect(0, 0, fill_w, rect.height()), radius, radius)

        # peak 标记
        if self._peak > 0.05:
            peak_x = int(rect.width() * self._peak)
            painter.setBrush(QColor("#ffffff"))
            painter.drawRect(peak_x - 1, 0, 2, rect.height())
