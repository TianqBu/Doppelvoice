# Changelog

All notable changes to Doppelvoice will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-04-26

Major code-review sweep: 4 parallel agent reviews (architecture / Python /
security / performance) drove a 24-file overhaul. Tests grew 3 → 46.

### Added
- **9-language translation support** per official Doubao spec (doc 1756902):
  `zh / en / ja / id / es / pt / de / fr / zhen`. `zhen` is the bilingual
  ZH⇄EN auto mode (source and target both set to `zhen`).
- **Voice clone tuning**: explicit `denoise=false` in `TranslateRequest` (proto
  field 7) to retain breath / resonance details that the server's default
  denoise pass would otherwise flatten. Tunable via `DENOISE` env var or the
  Settings dialog Advanced tab.
- **Audio device deduplication**: `list_unique_devices()` collapses one
  physical device's MME / DirectSound / WASAPI / WDM-KS duplicates into a
  single entry, with MME's 31-character name truncation handled. Best host
  API is chosen automatically (input → MME / DirectSound for sample-rate
  flexibility; output → WASAPI for low latency).
- **Subtitle memory cap** (`MAX_BLOCKS=2000`) so long sessions don't grow the
  `QTextDocument` unbounded.
- **Atomic `.env` write**: `tempfile.mkstemp` + `os.fsync` + `os.replace`
  prevents credential loss if the process crashes mid-write.
- **Log redaction patcher** (`utils/log.py`): every record passes through a
  3-stage scrubber (KV pairs / `Bearer` tokens / orphan high-entropy strings)
  before reaching stderr or files. Plus `safe_error_message()` for UI use.
- **WebSocket URL allowlist** + 64 MB → 4 MB frame size guard +
  `ParseFromString` length check before deserialization.
- **AppConfig snapshot** isolation: `Orchestrator` takes `cfg.snapshot()` at
  construction; `SettingsDialog` mutations only affect the next session.
- **Tests** (3 → 46): `test_resample`, `test_devices` (with mock host APIs),
  `test_doubao_classify` (every event branch), `test_log_redact`,
  `test_config` (frozen + snapshot semantics).

### Changed
- `AudioConfig` / `TranslationConfig` / `NetworkConfig` now `@dataclass(frozen=True)`.
  External writes go through `dataclasses.replace(cfg.audio, …)` and assignment
  back to `cfg.audio`.
- `silence_rms_threshold` default `0.010` → **`0.0`**. The old default was
  silently dropping the first 80 ms of quiet speech onsets, adding 300–500 ms
  to first-word latency; the server has its own VAD anyway.
- Mic level meter is no longer a second `sd.InputStream`. `MicCapture` now
  exposes `peak_level` from inside its existing audio callback; the GUI polls
  it from the metrics timer. One physical mic = one PortAudio stream.
- `_receiver_loop` split into `_handle_audio` / `_handle_sentence` /
  `_handle_subtitle` / `_handle_error` plus a `_ReceiverContext` dataclass
  for state. The 80-line nested `if/elif` is gone.
- `_resample` extracted to `audio/resample.py` (was duplicated across
  `capture.py` / `playback.py`, with `opus_decoder.py` doing a circular
  `from doppelvoice.audio.capture import _resample`).
- `send_audio()` reuses a cached `TranslateRequest` template (12 protobuf
  object allocations per second saved).
- `playback._callback` writes directly into the ctypes `outdata` buffer
  instead of constructing an intermediate `bytes(...)` copy under the lock.
- `closeEvent` guards against double-confirm via `_quitting` flag and uses
  `asyncio.get_running_loop()` instead of the deprecated `get_event_loop()`.
- `i18n.detect_system_language()` migrated from deprecated
  `locale.getdefaultlocale()` to `locale.getlocale()`.

### Fixed
- **Generated protobuf imports rewritten to absolute paths**
  (`from doppelvoice.engine._pb.common import …`). The `sys.path.insert(_pb)`
  hack in `protocol.py` is gone, eliminating a PyInstaller-onefile blocker
  and avoiding `sys.modules` pollution under top-level names `common` /
  `products`.
- Several `except Exception: pass` swallows replaced with
  `logger.debug(..., exc_info=True)` so audio / WebSocket failures stop being
  invisible.
- `settings_dialog._on_test_connection` no longer leaks raw exception
  tracebacks (which can carry server-echoed credentials) to log files; the
  message is funneled through `safe_error_message`.
- `closeEvent` no longer prompts twice if the user clicks ✕ a second time
  while graceful shutdown is in progress.

### Documented
- README + docs updated for 9 languages and `DENOISE` env var.
- `docs/zh/ARCHITECTURE.md` rewritten (was still describing the pre-rename
  `client/` layout and the 24 kHz / `pcm` settings that no longer apply).
- `TROUBLESHOOTING.md` (zh + en) updated with the acoustic-feedback-loop
  diagnosis (speakers → mic re-capture → re-translation back to the peer)
  and the cure (use headphones).

## [0.1.1] - 2026-04-25

### Changed
- Project renamed from `tongchuan` to `Doppelvoice`
- Package directory restructured: `client/` → `engine/`, `pb/` → `_pb/`
- Examples (`probe_*.py`) moved to `examples/`
- Documentation split into `docs/zh/` and `docs/en/`

### Added
- Bilingual README (English + 简体中文)
- `docs/en/`: full English translation of PRD, ARCHITECTURE, SETUP, TROUBLESHOOTING
- `docs/zh/TROUBLESHOOTING.md`
- `CHANGELOG.md`, `CODE_OF_CONDUCT.md`

## [0.1.0] - 2026-04-22

First working release.

### Added
- End-to-end Chinese → English real-time translation via Doubao Seed AST 2.0
- Zero-shot voice cloning (per-session, model-driven)
- PySide6 GUI with live bilingual subtitles, device picker, jitter / RMS controls
- CLI mode (`--check`, `--list-devices`, `--gui`)
- Automatic reconnect with exponential backoff
- Fatal-vs-transient error classification
- Multi-rate audio capture fallback (WASAPI 16 kHz issue workaround)
- ogg_opus per-sentence decoder (libsndfile-backed)
- Privacy-by-default: no audio or subtitle persistence unless `DUMP_AUDIO=1`
- GitHub Actions CI (Windows, Python 3.10/3.11/3.12)

### Fixed
- 4 HIGH and 3 MEDIUM issues from external code review:
  - `SessionCanceled(151)` event handling
  - sender/receiver task cancellation race
  - close-window cleanup not awaiting `run_task`
  - `Billing` field parsing in `UsageResponse`
- 8 HIGH and 2 MEDIUM issues from earlier review:
  - `iter_events` swallowing `ConnectionClosed`
  - capture queue not draining across reconnects
  - playback state not flushing across reconnects
  - audio callback thread → asyncio loop boundary safety
  - PortAudio stream lifecycle on shutdown
  - request_meta required-field gaps in `TaskRequest` / `FinishSession`
- Audio playback bug: `_max_buf_bytes` cap was too small for sentence-mode opus, truncating long sentences to ~360 ms

### Tuned
- `output_sample_rate` default 24 kHz → 48 kHz (fullband, more natural prosody)
- `format` field aligned with official `ast_demo.py`: `"pcm"` → `"wav"`
- Removed denoise / platform fields that were dead options
- chunk size 60 ms → 80 ms (matches Doubao recommendation)
- jitter buffer 240 ms → 120 ms (lower latency)
- `find_device` for input prefers MME / DirectSound (16 kHz support); WASAPI for output (low latency)
