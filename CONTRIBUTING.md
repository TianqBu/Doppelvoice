# Contributing

Thanks for considering a contribution!

## Setup

```cmd
git clone https://github.com/<your-username>/tongchuan.git
cd tongchuan
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\pip install pytest
```

Copy `.env.example` to `.env` and fill in your Doubao credentials.

## Run tests

```cmd
.venv\Scripts\python.exe -m pytest tests/test_protocol.py -v
```

The other `tests/probe_*.py` scripts are interactive E2E probes that hit the live API and need a working microphone (and credentials).

## Coding style

- Python 3.10+
- Type hints on public APIs
- Docstrings only when behaviour isn't obvious; comments only when WHY isn't obvious
- Keep modules under ~400 lines

## Pull requests

1. Open an issue first if it's a non-trivial change
2. Branch off `master`
3. Keep commits focused; bundle related changes
4. Make sure `pytest` passes
5. For protocol changes: regenerate the protobuf bindings (see `protos/build_python.sh`)

## Reporting issues

Please include:
- Windows version
- Python version
- Audio device names (output of `run.bat --list-devices`)
- Relevant log excerpt from `logs/tongchuan_*.log` (with credentials redacted)

## Areas open for contribution

- macOS / Linux ports (replace VB-Cable with BlackHole / PipeWire)
- Additional translation backends (OpenAI Realtime, ElevenLabs cascade)
- Subtitle overlay window (always-on-top transparent)
- System tray controls
- Reverse direction (English → Chinese) parallel session
