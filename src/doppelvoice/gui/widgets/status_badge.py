"""状态徽章（圆角药丸状指示器）。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class StatusBadge(QLabel):
    """通过 QSS 的 dynamic property 切换样式。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("statusBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._state = "idle"

    def set_state(self, state: str, text: str) -> None:
        """state: idle / busy / running / error"""
        self.setProperty("state", state)
        # 触发 QSS 重新评估
        self.style().unpolish(self)
        self.style().polish(self)
        self.setText(f"●  {text}")
