"""字幕显示组件：支持"进行中"句子实时更新。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor, QColor
from PySide6.QtWidgets import QTextEdit


class SubtitleView(QTextEdit):
    """
    每新 is_definite=True 的文本 → 新起一行（确定）
    每 is_definite=False 的文本 → 替换当前"进行中"那行
    """

    # 字幕历史 paragraph 上限：长跑会话防 QTextDocument 无界增长。
    # 一句字幕 = 一个 block；2000 句 ~= 几小时使用，超出从头 FIFO 丢弃。
    MAX_BLOCKS = 2000

    def __init__(self, title_color: str = "#1e90ff"):
        super().__init__()
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        f = QFont("Microsoft YaHei", 14)
        self.setFont(f)
        # Qt 原生上限：超出 MAX_BLOCKS 自动从开头删 block，无需手动维护
        self.document().setMaximumBlockCount(self.MAX_BLOCKS)
        self.setStyleSheet(
            "QTextEdit { background:#1e1e1e; color:#e0e0e0; border:1px solid #333; "
            "padding:8px; border-radius:6px; }"
        )
        self._title_color = title_color
        self._has_inprogress = False

    def append_definite(self, text: str) -> None:
        if not text.strip():
            return
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if self._has_inprogress:
            # 把"进行中"那行原位置替换为最终文本
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
            self._has_inprogress = False
        if cursor.position() > 0:
            cursor.insertBlock()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#e0e0e0"))
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def update_inprogress(self, text: str) -> None:
        if not text.strip():
            return
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        if self._has_inprogress:
            cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
            cursor.removeSelectedText()
        if cursor.position() > 0:
            cursor.insertBlock()
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#888888"))
        fmt.setFontItalic(True)
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        self._has_inprogress = True
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def feed(self, text: str, is_definite: bool) -> None:
        if is_definite:
            self.append_definite(text)
        else:
            self.update_inprogress(text)

    def clear_all(self) -> None:
        self.clear()
        self._has_inprogress = False
