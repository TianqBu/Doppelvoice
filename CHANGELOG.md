# Changelog

All notable changes to Doppelvoice will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
