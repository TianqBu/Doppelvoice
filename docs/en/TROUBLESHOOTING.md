# Troubleshooting

[中文](../zh/TROUBLESHOOTING.md)

## Connection / API

### "API connectivity failed: code=11200"
Authentication failed. Re-check `.env`:
- `DOUBAO_APP_KEY` should be the AppID (numeric, ~10 digits)
- `DOUBAO_ACCESS_KEY` should be the Access Token (alphanumeric)
- Service must be enabled in Volcengine Console

### "API connectivity failed: code=11500"
Invalid request parameters. Most likely `source_language` / `target_language` is set to an unsupported value.
Per the official spec (doc 1756902), valid codes are: `zh / en / ja / id / es / pt / de / fr / zhen`.
`zhen` is the bidirectional ZH⇄EN auto mode — both source and target must be set to `zhen`.

### Hangs forever on "建立会话…"
1. Network can't reach `openspeech.bytedance.com`. Check firewall.
2. Run `examples/probe_api.py` to isolate.
3. If WS opens but StartSession never returns, check Volcengine Console for service status.

## Audio capture

### "PortAudioError: Invalid sample rate (-9997)"
The selected microphone's host API doesn't support 16 kHz. Doppelvoice now retries automatically; if it still fails, run `examples/probe_mic.py` to find a working device.

WASAPI in shared mode rejects sample rates other than the device native rate. Try MME or DirectSound variants of the same device.

### Mic captures nothing (no transcript)
1. Windows Settings → Privacy → Microphone → "Allow apps to access microphone" must be ON.
2. Make sure the mic isn't muted in the Windows volume mixer.
3. Try a different mic from the dropdown — built-in laptop mic is usually safe.

## Playback / virtual mic

### Peer hears nothing
1. Look at the GUI status bar — "译音累计" should be > 0 KB. If it's 0, the API isn't sending audio (likely a config issue).
2. Verify Zoom/Teams microphone is set to `CABLE Output (VB-Audio Virtual Cable)`.
3. Test directly: open Voice Recorder app, set its mic to `CABLE Output`, run Doppelvoice and speak — Voice Recorder should pick up the translated audio.

### Audio is choppy / breaks up
- Increase the GUI's `jitter` slider to 300+ ms.
- Increase `chunk` to 100 ms.
- If you hear repeated fragments, set `RMS gate` (静音门限) to 0.015–0.020 to filter background noise.

### Audio plays at wrong speed (slow / fast)
This used to be a sample-rate mismatch bug; v0.2+ fixes it by routing audio at the device's native sample rate. If you still hit it, capture the log line starting with `opus decoded:` and `[sent #N]` — both should report the same Hz value as the device's native rate.

### "对方听到的声音是死人在说话"
- Switch `output_sample_rate` to **48000** (fullband) instead of 24000 — this is the default since v0.2 but check `.env` overrides.
- The voice cloning quality depends on input mic. AirPods over Bluetooth HFP (phone-call mode, 8 kHz narrowband) gives poor cloning; switch to a wired mic or laptop built-in mic.

## Voice cloning quality

### Cloned voice is monotone / mechanical
1. The public AST API is good but lags behind the Volcengine Console demo (which uses a different BFF endpoint with extra prosody processing). This is a hard ceiling.
2. Speak continuously for 15+ seconds at the start of a session — the model needs that time to sample your voice.
3. Use a wideband mic (≥48 kHz native).
4. Try non-empty `SPEAKER_ID` values in `.env` (experimental — proto field exists but undocumented).

## GUI / Windows

### GUI window doesn't appear after `gui.bat`
Old `gui.bat` used `pythonw` which silently ate errors. Latest uses regular `python` — re-pull and try again. If still no window, run from cmd to see the traceback:

```cmd
set PYTHONPATH=src
.venv\Scripts\python.exe -m doppelvoice --gui
```

### `gui.bat` shows garbled `'te.bat' is not recognized`
Your `gui.bat` was edited and now contains non-ASCII characters that confused `cmd.exe`. Re-pull from the repo or recreate it from scratch (see the master copy in this repo — pure ASCII).

### "RuntimeError: Event loop is closed" on quit
Latest version uses `_closing` flag in audio callbacks plus async cleanup in `closeEvent`. If you still see it, please file an issue with the full traceback.

## Privacy / data

### Where are my translated subtitles / audio stored?
By default, **nowhere**. Subtitle text and per-sentence ogg blobs are not persisted.

To enable for debugging only:
```env
DUMP_AUDIO=1
LOG_SUBTITLE=1
```
Files go to `logs/sentences/<timestamp>/NNN.ogg` and `logs/doppelvoice_*.log`. Delete after debugging.

## Reporting bugs

Please include:
- Windows version (`winver`)
- Python version (`python --version`)
- VB-Cable version (Sound Settings → click `CABLE Input` → Properties → Driver)
- Selected mic and host API (`run.bat --list-devices`)
- Relevant log excerpt from `logs/doppelvoice_*.log` — **redact API keys before sharing**
- Steps to reproduce
