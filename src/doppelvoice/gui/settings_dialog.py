"""设置对话框：API 凭据 / 音频 / 高级 三个 tab，可测试连接，写回 .env。"""
from __future__ import annotations

import asyncio
from typing import Optional

from loguru import logger
from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from doppelvoice.config import AppConfig, Credentials
from doppelvoice.gui.env_io import read_env, write_env
from doppelvoice.gui.i18n import I18n


class _SecretInput(QWidget):
    """密钥输入框 + 显示/隐藏切换。"""
    def __init__(self, placeholder: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setPlaceholderText(placeholder)
        self.toggle = QPushButton("👁")
        self.toggle.setCheckable(True)
        self.toggle.setFixedWidth(36)
        self.toggle.toggled.connect(self._on_toggle)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.toggle)

    def _on_toggle(self, checked: bool) -> None:
        self.edit.setEchoMode(
            QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        )

    def text(self) -> str:
        return self.edit.text()

    def setText(self, t: str) -> None:  # noqa: N802
        self.edit.setText(t)


class SettingsDialog(QDialog):
    """完整设置面板。点保存后写 .env 并 emit settings_saved。"""

    settings_saved = Signal()

    def __init__(self, cfg: AppConfig, i18n: I18n, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.i18n = i18n
        self.setWindowTitle(i18n.t("settings.title"))
        self.resize(560, 500)
        self.setModal(True)

        self._build_ui()
        self._load_from_env()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 20, 20, 20)
        outer.setSpacing(12)

        title = QLabel(self.i18n.t("settings.title"))
        title.setObjectName("title")
        outer.addWidget(title)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_api_tab(), self.i18n.t("settings.tab.api"))
        self.tabs.addTab(self._build_audio_tab(), self.i18n.t("settings.tab.audio"))
        self.tabs.addTab(self._build_advanced_tab(), self.i18n.t("settings.tab.advanced"))
        outer.addWidget(self.tabs, 1)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = bbox.button(QDialogButtonBox.StandardButton.Save)
        save_btn.setObjectName("primary")
        save_btn.setText(self.i18n.t("settings.save"))
        cancel_btn = bbox.button(QDialogButtonBox.StandardButton.Cancel)
        cancel_btn.setText(self.i18n.t("settings.cancel"))
        bbox.accepted.connect(self._on_save)
        bbox.rejected.connect(self.reject)
        outer.addWidget(bbox)

    def _build_api_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # 帮助文字 + 链接
        help_label = QLabel(self.i18n.t("settings.api.help"))
        help_label.setObjectName("muted")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        link_btn = QPushButton(self.i18n.t("settings.api.console_link"))
        link_btn.clicked.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://console.volcengine.com/speech/app")
        ))
        link_btn.setFixedWidth(140)
        layout.addWidget(link_btn)

        layout.addSpacing(8)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setSpacing(10)

        self.app_key = _SecretInput("App Key (numeric, ~10 digits)")
        self.access_key = _SecretInput("Access Token")
        self.resource_id = QLineEdit()
        self.resource_id.setPlaceholderText("volc.service_type.10053")

        form.addRow(self.i18n.t("settings.api.app_key"), self.app_key)
        form.addRow(self.i18n.t("settings.api.access_key"), self.access_key)
        form.addRow(self.i18n.t("settings.api.resource_id"), self.resource_id)
        layout.addLayout(form)

        layout.addSpacing(6)

        # 测试连接
        test_row = QHBoxLayout()
        self.test_btn = QPushButton(self.i18n.t("settings.api.test"))
        self.test_btn.clicked.connect(self._on_test_connection)
        self.test_result = QLabel("")
        self.test_result.setObjectName("muted")
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_result, 1)
        layout.addLayout(test_row)

        layout.addStretch(1)
        return w

    def _build_audio_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(16, 16, 16, 16)
        form.setSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.chunk_ms = QSpinBox()
        self.chunk_ms.setRange(20, 200)
        self.chunk_ms.setSingleStep(20)
        self.chunk_ms.setSuffix(" ms")

        self.jitter_ms = QSpinBox()
        self.jitter_ms.setRange(60, 800)
        self.jitter_ms.setSingleStep(20)
        self.jitter_ms.setSuffix(" ms")

        self.rms_gate = QDoubleSpinBox()
        self.rms_gate.setRange(0.0, 0.2)
        self.rms_gate.setSingleStep(0.005)
        self.rms_gate.setDecimals(3)

        self.input_sr = QSpinBox()
        self.input_sr.setRange(8000, 48000)
        self.input_sr.setSingleStep(8000)
        self.input_sr.setSuffix(" Hz")
        self.input_sr.setReadOnly(True)
        self.input_sr.setEnabled(False)  # 当前固定 16k

        self.output_sr = QSpinBox()
        self.output_sr.setRange(16000, 48000)
        self.output_sr.setSingleStep(8000)
        self.output_sr.setSuffix(" Hz")

        form.addRow(self.i18n.t("settings.audio.chunk_ms"), self.chunk_ms)
        form.addRow(self.i18n.t("settings.audio.jitter_ms"), self.jitter_ms)
        form.addRow(self.i18n.t("settings.audio.rms_gate"), self.rms_gate)
        form.addRow(self.i18n.t("settings.audio.input_sr"), self.input_sr)
        form.addRow(self.i18n.t("settings.audio.output_sr"), self.output_sr)

        return w

    def _build_advanced_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.speaker_id = QLineEdit()
        self.speaker_id.setPlaceholderText("(blank)")
        form.addRow(self.i18n.t("settings.advanced.speaker_id"), self.speaker_id)

        layout.addLayout(form)

        warn = QLabel(self.i18n.t("settings.advanced.warning"))
        warn.setObjectName("muted")
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #ffd93d;")
        layout.addWidget(warn)

        self.dump_audio = QCheckBox(self.i18n.t("settings.advanced.dump_audio"))
        self.log_subtitle = QCheckBox(self.i18n.t("settings.advanced.log_subtitle"))
        layout.addWidget(self.dump_audio)
        layout.addWidget(self.log_subtitle)

        layout.addStretch(1)
        return w

    def _load_from_env(self) -> None:
        env = read_env()
        self.app_key.setText(env.get("DOUBAO_APP_KEY", ""))
        self.access_key.setText(env.get("DOUBAO_ACCESS_KEY", ""))
        self.resource_id.setText(env.get("DOUBAO_RESOURCE_ID", "volc.service_type.10053"))
        self.speaker_id.setText(env.get("SPEAKER_ID", ""))
        self.dump_audio.setChecked(env.get("DUMP_AUDIO", "").lower() in ("1", "true", "yes"))
        self.log_subtitle.setChecked(env.get("LOG_SUBTITLE", "").lower() in ("1", "true", "yes"))

        a = self.cfg.audio
        self.chunk_ms.setValue(a.chunk_ms)
        self.jitter_ms.setValue(a.jitter_buffer_ms)
        self.rms_gate.setValue(a.silence_rms_threshold)
        self.input_sr.setValue(a.input_sample_rate)
        self.output_sr.setValue(a.output_sample_rate)

    def _on_test_connection(self) -> None:
        app_key = self.app_key.text().strip()
        access_key = self.access_key.text().strip()
        if not app_key or not access_key:
            self.test_result.setText(self.i18n.t("settings.api.test.fail", error="empty"))
            self.test_result.setStyleSheet("color: #ff6b6b;")
            return
        self.test_btn.setEnabled(False)
        self.test_result.setText(self.i18n.t("settings.api.test.testing"))
        self.test_result.setStyleSheet("color: #ffd93d;")

        # 异步在 qasync loop 上执行
        loop = asyncio.get_event_loop()
        loop.create_task(self._do_test(app_key, access_key))

    async def _do_test(self, app_key: str, access_key: str) -> None:
        from doppelvoice.engine.doubao import DoubaoClient
        # 临时 cfg 副本（不污染主配置）
        cfg = AppConfig(credentials=Credentials(
            app_key=app_key,
            access_key=access_key,
            resource_id=self.resource_id.text().strip() or "volc.service_type.10053",
        ))
        client = DoubaoClient(cfg)
        try:
            await client.connect()
            await client.start_session()
            self.test_result.setText(self.i18n.t("settings.api.test.ok"))
            self.test_result.setStyleSheet("color: #00d4aa;")
        except Exception as e:
            logger.exception("test connection failed")
            self.test_result.setText(self.i18n.t("settings.api.test.fail", error=str(e)[:80]))
            self.test_result.setStyleSheet("color: #ff6b6b;")
        finally:
            await client.finish_session()
            await client.close()
            self.test_btn.setEnabled(True)

    def _on_save(self) -> None:
        updates = {
            "DOUBAO_APP_KEY": self.app_key.text().strip(),
            "DOUBAO_ACCESS_KEY": self.access_key.text().strip(),
            "DOUBAO_RESOURCE_ID": self.resource_id.text().strip() or "volc.service_type.10053",
        }
        sp = self.speaker_id.text().strip()
        if sp:
            updates["SPEAKER_ID"] = sp
        if self.dump_audio.isChecked():
            updates["DUMP_AUDIO"] = "1"
        if self.log_subtitle.isChecked():
            updates["LOG_SUBTITLE"] = "1"
        write_env(updates)

        # 同时把音频参数应用到当前 cfg（不持久化采样块/jitter 等到 .env，运行时调）
        self.cfg.audio.chunk_ms = self.chunk_ms.value()
        self.cfg.audio.jitter_buffer_ms = self.jitter_ms.value()
        self.cfg.audio.silence_rms_threshold = self.rms_gate.value()
        self.cfg.audio.output_sample_rate = self.output_sr.value()

        # 把新密钥写回 cfg.credentials，避免重启
        self.cfg.credentials.app_key = updates["DOUBAO_APP_KEY"]
        self.cfg.credentials.access_key = updates["DOUBAO_ACCESS_KEY"]
        self.cfg.credentials.resource_id = updates["DOUBAO_RESOURCE_ID"]

        self.settings_saved.emit()
        QMessageBox.information(self, self.i18n.t("settings.title"), self.i18n.t("settings.saved"))
        self.accept()
