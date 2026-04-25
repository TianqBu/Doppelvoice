"""主窗口：现代化布局，菜单栏 + 工具栏 + 状态徽章 + 输入电平 + 双字幕 + 状态栏。"""
from __future__ import annotations

import asyncio
import threading
from typing import Optional

import numpy as np
import sounddevice as sd
from loguru import logger
from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QStatusBar,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from doppelvoice.audio import devices as audio_devices
from doppelvoice.config import AppConfig
from doppelvoice.gui.bus import GuiEventBus
from doppelvoice.gui.env_io import has_credentials
from doppelvoice.gui.i18n import I18n
from doppelvoice.gui.settings_dialog import SettingsDialog
from doppelvoice.gui.subtitle_view import SubtitleView
from doppelvoice.gui.theme import ThemeName, stylesheet
from doppelvoice.gui.widgets.audio_meter import AudioLevelMeter
from doppelvoice.gui.widgets.status_badge import StatusBadge
from doppelvoice.pipeline.orchestrator import Orchestrator


class MainWindow(QMainWindow):
    def __init__(self, cfg: AppConfig, i18n: I18n, theme: ThemeName = "dark"):
        super().__init__()
        self.cfg = cfg
        self.i18n = i18n
        self._theme = theme
        self.bus = GuiEventBus()
        self.orchestrator: Optional[Orchestrator] = None
        self.run_task: Optional[asyncio.Task] = None
        self._sentence_count = 0
        self._audio_bytes = 0
        self._mic_meter_stream: Optional[sd.InputStream] = None
        self._mic_meter_lock = threading.Lock()
        self._mic_level = 0.0

        self.setWindowTitle("Doppelvoice")
        self.resize(960, 760)

        self._build_ui()
        self._wire_signals()
        self._refresh_device_lists()
        self._apply_translations()
        self.i18n.language_changed.connect(self._apply_translations)

        self._metrics_timer = QTimer(self)
        self._metrics_timer.setInterval(500)
        self._metrics_timer.timeout.connect(self._tick_metrics)
        self._metrics_timer.start()

        self._start_mic_meter()

    # ── UI ──
    def _build_ui(self) -> None:
        self._build_menubar()
        self._build_toolbar()

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 14, 20, 14)
        outer.setSpacing(14)

        # 头部：标题 + 状态徽章
        header = QHBoxLayout()
        title = QLabel("Doppelvoice")
        title.setObjectName("title")
        self.subtitle_label = QLabel("")
        self.subtitle_label.setObjectName("muted")
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.addWidget(title)
        title_box.addWidget(self.subtitle_label)
        header.addLayout(title_box)
        header.addStretch(1)
        self.status_badge = StatusBadge()
        self.status_badge.set_state("idle", self.i18n.t("status.idle"))
        header.addWidget(self.status_badge)
        outer.addLayout(header)

        # 设备配置行
        cfg_row = QHBoxLayout()
        cfg_row.setSpacing(10)
        self.input_label = QLabel()
        self.output_label = QLabel()
        self.input_dev = QComboBox()
        self.output_dev = QComboBox()
        self.refresh_btn = QPushButton()
        cfg_row.addWidget(self.input_label)
        cfg_row.addWidget(self.input_dev, 1)
        cfg_row.addWidget(self.output_label)
        cfg_row.addWidget(self.output_dev, 1)
        cfg_row.addWidget(self.refresh_btn)
        outer.addLayout(cfg_row)

        # 语种行
        lang_row = QHBoxLayout()
        self.src_lang_label = QLabel()
        self.src_lang = QComboBox()
        self.src_lang.addItem("中文", "zh")
        self.src_lang.addItem("English", "en")
        self.src_lang.setCurrentIndex(0 if self.cfg.translation.source_language == "zh" else 1)
        self.arrow_label = QLabel("→")
        self.arrow_label.setStyleSheet("font-size: 16px; padding: 0 6px;")
        self.tgt_lang_label = QLabel()
        self.tgt_lang = QComboBox()
        self.tgt_lang.addItem("English", "en")
        self.tgt_lang.addItem("中文", "zh")
        self.tgt_lang.setCurrentIndex(0 if self.cfg.translation.target_language == "en" else 1)
        lang_row.addWidget(self.src_lang_label)
        lang_row.addWidget(self.src_lang)
        lang_row.addWidget(self.arrow_label)
        lang_row.addWidget(self.tgt_lang_label)
        lang_row.addWidget(self.tgt_lang)
        lang_row.addStretch(1)
        outer.addLayout(lang_row)

        # 输入电平
        meter_row = QHBoxLayout()
        self.meter_label = QLabel()
        self.meter_label.setObjectName("muted")
        self.meter_label.setMinimumWidth(80)
        self.audio_meter = AudioLevelMeter()
        meter_row.addWidget(self.meter_label)
        meter_row.addWidget(self.audio_meter, 1)
        outer.addLayout(meter_row)

        # 双字幕
        split = QSplitter(Qt.Orientation.Vertical)
        self.src_view = SubtitleView()
        self.tgt_view = SubtitleView()
        src_wrap = self._wrap_titled(self.src_view, "subtitle.source")
        tgt_wrap = self._wrap_titled(self.tgt_view, "subtitle.target")
        self.src_wrap_label = src_wrap.findChild(QLabel)
        self.tgt_wrap_label = tgt_wrap.findChild(QLabel)
        split.addWidget(src_wrap)
        split.addWidget(tgt_wrap)
        split.setSizes([300, 380])
        outer.addWidget(split, 1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.metric_label = QLabel("")
        self.status_bar.addPermanentWidget(self.metric_label)

    def _wrap_titled(self, view: QWidget, _key: str) -> QWidget:
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        label = QLabel()
        label.setObjectName("h2")
        v.addWidget(label)
        v.addWidget(view, 1)
        return w

    def _build_menubar(self) -> None:
        mb = self.menuBar()
        mb.clear()

        self.menu_file = mb.addMenu("")
        self.act_settings = QAction(self)
        self.act_settings.setShortcut(QKeySequence("Ctrl+,"))
        self.act_settings.triggered.connect(self._open_settings)
        self.menu_file.addAction(self.act_settings)
        self.menu_file.addSeparator()
        self.act_exit = QAction(self)
        self.act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        self.act_exit.triggered.connect(self.close)
        self.menu_file.addAction(self.act_exit)

        self.menu_view = mb.addMenu("")
        self.act_theme_dark = QAction(self, checkable=True)
        self.act_theme_light = QAction(self, checkable=True)
        theme_group = QActionGroup(self)
        theme_group.addAction(self.act_theme_dark)
        theme_group.addAction(self.act_theme_light)
        self.act_theme_dark.setChecked(self._theme == "dark")
        self.act_theme_light.setChecked(self._theme == "light")
        self.act_theme_dark.triggered.connect(lambda: self._set_theme("dark"))
        self.act_theme_light.triggered.connect(lambda: self._set_theme("light"))
        self.menu_view.addAction(self.act_theme_dark)
        self.menu_view.addAction(self.act_theme_light)

        self.menu_lang = mb.addMenu("")
        self.act_lang_zh = QAction(self, checkable=True)
        self.act_lang_en = QAction(self, checkable=True)
        lang_group = QActionGroup(self)
        lang_group.addAction(self.act_lang_zh)
        lang_group.addAction(self.act_lang_en)
        self.act_lang_zh.setChecked(self.i18n.lang == "zh")
        self.act_lang_en.setChecked(self.i18n.lang == "en")
        self.act_lang_zh.triggered.connect(lambda: self.i18n.set_language("zh"))
        self.act_lang_en.triggered.connect(lambda: self.i18n.set_language("en"))
        self.menu_lang.addAction(self.act_lang_zh)
        self.menu_lang.addAction(self.act_lang_en)

        self.menu_help = mb.addMenu("")
        self.act_about = QAction(self)
        self.act_about.triggered.connect(self._show_about)
        self.act_docs = QAction(self)
        self.act_docs.triggered.connect(lambda: QDesktopServices.openUrl(
            QUrl("https://github.com/")
        ))
        self.menu_help.addAction(self.act_docs)
        self.menu_help.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        tb = QToolBar()
        tb.setMovable(False)
        tb.setFloatable(False)
        self.addToolBar(tb)

        self.start_btn = QPushButton()
        self.start_btn.setObjectName("primary")
        self.start_btn.setMinimumWidth(140)
        self.stop_btn = QPushButton()
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setMinimumWidth(120)
        self.stop_btn.setEnabled(False)
        self.settings_btn = QPushButton()
        self.clear_btn = QPushButton()

        tb.addWidget(self.start_btn)
        tb.addWidget(self.stop_btn)
        tb.addSeparator()
        tb.addWidget(self.clear_btn)
        spacer = QWidget()
        spacer.setSizePolicy(QWidget().sizePolicy())
        tb.addWidget(spacer)
        tb.addWidget(self.settings_btn)

    def _wire_signals(self) -> None:
        self.start_btn.clicked.connect(self._on_start)
        self.stop_btn.clicked.connect(self._on_stop)
        self.clear_btn.clicked.connect(self._clear_subtitles)
        self.refresh_btn.clicked.connect(self._refresh_device_lists)
        self.settings_btn.clicked.connect(self._open_settings)

        self.bus.source_text.connect(self.src_view.feed)
        self.bus.target_text.connect(self.tgt_view.feed)
        self.bus.target_text.connect(self._count_sentence)
        self.bus.audio_received.connect(self._on_audio)
        self.bus.error.connect(self._on_error)
        self.bus.status.connect(self._on_status)

    def _apply_translations(self) -> None:
        i = self.i18n
        self.subtitle_label.setText(i.t("app.subtitle"))
        self.menu_file.setTitle(i.t("menu.file"))
        self.act_settings.setText(i.t("menu.file.settings"))
        self.act_exit.setText(i.t("menu.file.exit"))
        self.menu_view.setTitle(i.t("menu.view"))
        self.act_theme_dark.setText(i.t("menu.view.theme.dark"))
        self.act_theme_light.setText(i.t("menu.view.theme.light"))
        self.menu_lang.setTitle(i.t("menu.lang"))
        self.act_lang_zh.setText(i.t("menu.lang.zh"))
        self.act_lang_en.setText(i.t("menu.lang.en"))
        self.menu_help.setTitle(i.t("menu.help"))
        self.act_about.setText(i.t("menu.help.about"))
        self.act_docs.setText(i.t("menu.help.docs"))
        self.start_btn.setText("▶  " + i.t("action.start"))
        self.stop_btn.setText("■  " + i.t("action.stop"))
        self.clear_btn.setText(i.t("action.clear_subtitles"))
        self.settings_btn.setText(i.t("action.settings"))
        self.input_label.setText(i.t("config.input_device"))
        self.output_label.setText(i.t("config.output_device"))
        self.refresh_btn.setText("↻  " + i.t("action.refresh_devices"))
        self.src_lang_label.setText(i.t("config.source_lang"))
        self.tgt_lang_label.setText(i.t("config.target_lang"))
        self.meter_label.setText(i.t("stats.audio_level"))
        if self.src_wrap_label is not None:
            self.src_wrap_label.setText(i.t("subtitle.source"))
        if self.tgt_wrap_label is not None:
            self.tgt_wrap_label.setText(i.t("subtitle.target"))
        cur_state = str(self.status_badge.property("state") or "idle")
        self.status_badge.set_state(cur_state, i.t(f"status.{cur_state}"))

    # ── 设备列表 ──
    def _refresh_device_lists(self) -> None:
        self.input_dev.clear()
        self.output_dev.clear()
        devs = audio_devices.list_devices()
        def in_pri(d):
            return {"MME": 0, "Windows DirectSound": 1, "Windows WASAPI": 2}.get(d.hostapi_name, 9)
        def out_pri(d):
            return {"Windows WASAPI": 0, "MME": 1, "Windows DirectSound": 2}.get(d.hostapi_name, 9)
        for d in sorted(devs, key=in_pri):
            if d.max_input_channels > 0:
                self.input_dev.addItem(
                    f"[{d.hostapi_name[:5]}] {d.name} ({int(d.default_samplerate)}Hz)", d.name
                )
        for d in sorted(devs, key=out_pri):
            if d.max_output_channels > 0:
                self.output_dev.addItem(
                    f"[{d.hostapi_name[:5]}] {d.name} ({int(d.default_samplerate)}Hz)", d.name
                )
        if self.cfg.audio.input_device:
            self._select_by_substring(self.input_dev, self.cfg.audio.input_device)
        if self.cfg.audio.output_device:
            self._select_by_substring(self.output_dev, self.cfg.audio.output_device)

    @staticmethod
    def _select_by_substring(combo: QComboBox, hint: str) -> None:
        h = hint.lower()
        for i in range(combo.count()):
            name = (combo.itemData(i) or combo.itemText(i)).lower()
            if h in name:
                combo.setCurrentIndex(i)
                return

    # ── 麦克风电平监控（独立流，仅做可视化）──
    def _start_mic_meter(self) -> None:
        try:
            self._mic_meter_stream = sd.InputStream(
                samplerate=44100, channels=1, dtype="float32",
                blocksize=2048, callback=self._mic_meter_cb, latency="low",
            )
            self._mic_meter_stream.start()
        except Exception as e:
            logger.debug(f"mic meter unavailable: {e}")

    def _mic_meter_cb(self, indata, frames, time_info, status):
        if status:
            return
        try:
            arr = np.array(indata, dtype=np.float32).flatten()
            rms = float(np.sqrt(np.mean(arr ** 2)))
            level = min(1.0, rms * 6)
            with self._mic_meter_lock:
                self._mic_level = level
        except Exception:
            pass

    def _stop_mic_meter(self) -> None:
        if self._mic_meter_stream is not None:
            try:
                self._mic_meter_stream.stop()
                self._mic_meter_stream.close()
            except Exception:
                pass
            self._mic_meter_stream = None

    # ── 启停 ──
    def _pull_config(self) -> None:
        self.cfg.translation.source_language = self.src_lang.currentData()
        self.cfg.translation.target_language = self.tgt_lang.currentData()
        in_name = self.input_dev.currentData()
        out_name = self.output_dev.currentData()
        if in_name:
            self.cfg.audio.input_device = in_name
        if out_name:
            self.cfg.audio.output_device = out_name

    def _on_start(self) -> None:
        if self.run_task is not None:
            return
        if not has_credentials():
            QMessageBox.warning(
                self, self.i18n.t("dialog.error.title"),
                self.i18n.t("dialog.error.no_credentials"),
            )
            self._open_settings()
            return
        self._pull_config()
        # 同步 .env 里的密钥到 cfg（用户可能在设置对话框里改过）
        from doppelvoice.gui.env_io import read_env
        env = read_env()
        self.cfg.credentials.app_key = env.get("DOUBAO_APP_KEY", self.cfg.credentials.app_key)
        self.cfg.credentials.access_key = env.get("DOUBAO_ACCESS_KEY", self.cfg.credentials.access_key)
        self.cfg.credentials.resource_id = env.get("DOUBAO_RESOURCE_ID", self.cfg.credentials.resource_id)

        self.orchestrator = Orchestrator(self.cfg, event_bus=self.bus)
        self._set_running_state(True)
        self._sentence_count = 0
        self._audio_bytes = 0
        self.bus.status.emit("connecting", self.i18n.t("status.connecting"))

        loop = asyncio.get_event_loop()
        self.run_task = loop.create_task(self._run_orch())

    async def _run_orch(self) -> None:
        try:
            await self.orchestrator.run()
            self.bus.status.emit("stopped", self.i18n.t("status.stopped"))
        except Exception as e:
            logger.exception("orchestrator crash")
            self.bus.error.emit(repr(e))
            self.bus.status.emit("error", self.i18n.t("status.error"))
        finally:
            self.run_task = None
            self._set_running_state(False)

    def _on_stop(self) -> None:
        if self.orchestrator is not None:
            self.orchestrator.stop()

    def _set_running_state(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        for w in (self.src_lang, self.tgt_lang, self.input_dev, self.output_dev,
                  self.refresh_btn, self.settings_btn):
            w.setEnabled(not running)

    # ── Bus 回调 ──
    def _count_sentence(self, text: str, is_definite: bool) -> None:
        if is_definite and text.strip():
            self._sentence_count += 1

    def _on_audio(self, n: int) -> None:
        self._audio_bytes += n

    def _on_error(self, msg: str) -> None:
        self.status_bar.showMessage(f"{self.i18n.t('status.error')}: {msg}", 8000)

    def _on_status(self, key: str, msg: str) -> None:
        state_map = {
            "idle": "idle", "stopped": "idle",
            "running": "running",
            "error": "error",
            "connecting": "busy", "opening_audio": "busy",
            "audio_ready": "busy", "session_starting": "busy",
        }
        state = state_map.get(key, "busy")
        display = msg or self.i18n.t(f"status.{key}")
        self.status_badge.set_state(state, display)

    def _tick_metrics(self) -> None:
        with self._mic_meter_lock:
            self.audio_meter.set_level(self._mic_level)
        kb = self._audio_bytes / 1024
        self.metric_label.setText(
            f"{self.i18n.t('stats.audio_received')}: {kb:.1f} KB · "
            f"{self._sentence_count} {self.i18n.t('stats.sentences')}"
        )

    # ── 菜单 actions ──
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.cfg, self.i18n, self)
        dlg.settings_saved.connect(self._on_settings_saved)
        dlg.exec()

    def _on_settings_saved(self) -> None:
        self.status_bar.showMessage(self.i18n.t("settings.saved"), 3000)

    def _set_theme(self, theme: ThemeName) -> None:
        self._theme = theme
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet(theme))

    def _show_about(self) -> None:
        QMessageBox.about(self, self.i18n.t("dialog.about.title"),
                          self.i18n.t("dialog.about.body"))

    def _clear_subtitles(self) -> None:
        self.src_view.clear_all()
        self.tgt_view.clear_all()
        self._sentence_count = 0
        self._audio_bytes = 0

    # ── 关闭 ──
    def closeEvent(self, event):  # noqa: N802
        if self.run_task is not None:
            ret = QMessageBox.question(
                self, self.i18n.t("app.title"), self.i18n.t("dialog.confirm_quit"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if ret != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        if self.orchestrator is not None:
            self.orchestrator.stop()
        self._stop_mic_meter()
        if self.run_task is not None and not self.run_task.done():
            event.ignore()
            asyncio.get_event_loop().create_task(self._graceful_quit())
        else:
            event.accept()

    async def _graceful_quit(self) -> None:
        if self.run_task is not None:
            try:
                await asyncio.wait_for(self.run_task, timeout=5.0)
            except asyncio.TimeoutError:
                self.run_task.cancel()
                try:
                    await asyncio.wait_for(self.run_task, timeout=3.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass
            except Exception:
                pass
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is not None:
            app.quit()
