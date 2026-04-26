# Doppelvoice

> **Your voice, in any language.**
> Real-time speech-to-speech translation with zero-shot voice cloning. The other party hears **English in your own voice** through any meeting app — Zoom, Teams, Google Meet, OBS, anything that takes a microphone.
>
> _Powered by ByteDance Doubao Seed LiveInterpret 2.0._

[中文](README.zh-CN.md) · [Architecture](docs/en/ARCHITECTURE.md) · [Setup](docs/en/SETUP.md) · [Troubleshooting](docs/en/TROUBLESHOOTING.md)

[![Tests](https://img.shields.io/badge/tests-46%20passed-brightgreen.svg)]()
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-lightgrey.svg)]()

---

## What it does

```
You speak Chinese  ─►  Doppelvoice  ─►  Peer hears English (in your voice)
   ┌──────────┐         ┌─────────┐        ┌──────────────────────────────┐
   │ your mic │  ──►    │ Doubao  │  ──►   │ virtual mic → Zoom / Teams … │
   └──────────┘         │ AST 2.0 │        └──────────────────────────────┘
                        └─────────┘
```

End-to-end latency ≈ 2.5–3 s. Subtitles stream token-by-token; voice is cloned zero-shot from your speech as you talk.

## Features

- 🎙 **End-to-end speech-to-speech** — no separate STT / MT / TTS plumbing
- 🗣 **Zero-shot voice cloning** — model captures your voice on the fly; explicit
  `denoise=false` to retain breath / resonance details
- 🌐 **9 languages** — `zh / en / ja / id / es / pt / de / fr / zhen` (the
  last one is the bilingual ZH⇄EN auto mode)
- ⚡ **~2.5 s latency** — production-grade real-time
- 🪟 **Native Windows GUI** (PySide6) with live bilingual subtitles
- 🔌 **Universal compatibility** — anything that accepts a microphone works
- 🔁 **Automatic reconnect** with exponential backoff and fatal-error classification
- 🔒 **Privacy-first defaults** — translated audio and subtitles never persist
  to disk unless you opt in; logs auto-redact API keys and bearer tokens
- 🧹 **Clean device picker** — one entry per physical device (host-API
  duplicates collapsed; MME 31-char name truncation handled)
- 🛠 **Configurable** — sample rate, jitter buffer, RMS gate, denoise toggle,
  speaker_id, all tweakable

## Demo

![Doppelvoice GUI](docs/images/screenshot.png)

## Quick start

### 1. Install [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) (required, free)

Download → **right-click `VBCABLE_Setup_x64.exe`** → run as administrator → click **Install Driver** → **reboot**.

### 2. Get Doubao API credentials

1. Sign up at the [Volcengine Console](https://console.volcengine.com/speech/app)
2. Enable **同声传译 2.0** (Simultaneous Interpretation 2.0) — paid service
3. Copy `APP_KEY` and `ACCESS_KEY` from the credentials page

### 3. Clone & install

```cmd
git clone https://github.com/<your-username>/Doppelvoice.git
cd Doppelvoice
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### 4. Configure

```cmd
copy .env.example .env
notepad .env
```

```dotenv
DOUBAO_APP_KEY=your_app_key
DOUBAO_ACCESS_KEY=your_access_key
DOUBAO_RESOURCE_ID=volc.service_type.10053
```

### 5. Self-check & launch

```cmd
check.bat        :: verifies devices + API connectivity + StartSession
gui.bat          :: launches the GUI
run.bat          :: CLI mode
```

In your meeting app: pick **`CABLE Output (VB-Audio Virtual Cable)`** as the microphone.

## CLI

```cmd
run.bat                              :: start translation (CLI)
run.bat --gui                        :: launch GUI
run.bat --check                      :: self-check
run.bat --list-devices               :: list audio devices
run.bat --source en --target zh      :: reverse direction
run.bat --jitter-ms 80               :: lower latency (more underrun risk)
run.bat --log-level DEBUG            :: verbose logs
```

## Configuration

All settings have sensible defaults. Override via `.env` or CLI flags.

| Variable | Default | Notes |
|---|---|---|
| `DOUBAO_APP_KEY` / `DOUBAO_ACCESS_KEY` | _required_ | from Volcengine console |
| `DOUBAO_RESOURCE_ID` | `volc.service_type.10053` | AST 2.0 resource ID |
| `SOURCE_LANG` / `TARGET_LANG` | `zh` / `en` | one of `zh / en / ja / id / es / pt / de / fr / zhen`. Use `zhen` on **both** sides for bilingual ZH⇄EN auto mode. |
| `MODE` | `s2s` | `s2s` (speech→speech) or `s2t` (speech→text) |
| `DENOISE` | `0` | `1` = server-side denoise on (cleaner input but flatter voice clone). `0` keeps breath / resonance for better cloning. |
| `SPEAKER_ID` | _empty_ | Doubao `ReqParams.speaker_id` — empty = clone the speaker; set to a preset like `zh_female_vv_uranus_bigtts` to use a stock voice instead |
| `INPUT_DEVICE` / `OUTPUT_DEVICE` | _auto_ | substring of device name (host API hidden; one entry per physical device) |
| `LOG_LEVEL` | `INFO` | `DEBUG` for verbose |
| `DUMP_AUDIO` | `false` | persist per-sentence ogg blobs (debug only) |
| `LOG_SUBTITLE` | `false` | persist subtitle text in logs (debug only) |

## Architecture

```
src/doppelvoice/
├── engine/        # Doubao AST 2.0 protobuf WebSocket client
├── audio/         # PortAudio (sounddevice) capture + playback + ogg/opus decoder
├── pipeline/      # asyncio orchestration: capture → ws → decode → playback
├── gui/           # PySide6 + qasync
├── cli.py
└── config.py
```

See [docs/en/ARCHITECTURE.md](docs/en/ARCHITECTURE.md) for the full protocol details.

## Tested with

- Windows 10 / 11 x64
- Python 3.10–3.12
- VB-Audio Virtual Cable 1.0.4 (Driver Pack 43)
- Zoom, 腾讯会议, 微信电话, Google Meet (Chrome), OBS

## Known limitations

1. **Voice cloning quality varies** with mic and clarity. AirPods over Bluetooth
   HFP (16 kHz narrowband phone mode) gives mediocre results — a wired/USB mic
   or laptop built-in mic is recommended. The default `denoise=false` already
   tells the server to keep your voice's unique characteristics; toggling it
   on in Settings would flatten the clone further.
2. **End-to-end latency floor ≈ 2.5 s** is the model's hard limit per the
   [Seed LiveInterpret 2.0 paper](https://arxiv.org/abs/2507.17527); local
   processing adds <500 ms.
3. **Voice expressiveness** of the public AST API is good but not as lively
   as the Volcengine Console demo (which goes through a different BFF endpoint).
4. **Per-sentence audio decoding** (ogg_opus) adds ~500 ms latency vs raw
   PCM (which the API does not currently honor).
5. **Use headphones, not speakers.** With external speakers the meeting
   audio gets re-captured by your mic, re-translated, and sent back to the
   peer as their own translated voice — a textbook acoustic feedback loop.
   See [Troubleshooting](docs/en/TROUBLESHOOTING.md#feedback-loop-when-using-speakers).

## Privacy

- API keys live only in `.env` (gitignored).
- Translated audio and subtitle text are **not persisted** to disk by default.
- Set `DUMP_AUDIO=1` / `LOG_SUBTITLE=1` for debugging only.
- All audio is sent through ByteDance's Doubao API. Review their [Terms of Service](https://www.volcengine.com/docs/82379/1394617) before use with sensitive content.

## Contributing

PRs welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE).

## Acknowledgements

- [ByteDance Seed LiveInterpret 2.0](https://seed.bytedance.com/en/seed_liveinterpret) — the underlying translation model
- [kizuna-ai-lab/sokuji](https://github.com/kizuna-ai-lab/sokuji) — protobuf reverse-engineering reference
- [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) — virtual audio routing on Windows
