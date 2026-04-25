# Setup & Usage

[中文](../zh/SETUP.md)

## 1. Install Python 3.10+

Download from https://www.python.org/downloads/. Tick **Add to PATH** during install.

Verify:
```cmd
python --version
```

## 2. Install VB-Audio Virtual Cable (required)

1. Download: https://vb-audio.com/Cable/ → click **Download** → unzip
2. **Right-click** `VBCABLE_Setup_x64.exe` → **Run as administrator** → click **Install Driver**
3. **Reboot** (required)
4. After reboot, verify in Windows Sound settings:
   - Output: `CABLE Input (VB-Audio Virtual Cable)`
   - Input: `CABLE Output (VB-Audio Virtual Cable)`

## 3. Install project dependencies

```cmd
cd C:\path\to\Doppelvoice
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 4. Configure credentials

Copy `.env.example` to `.env` and fill in your Doubao 同传 2.0 credentials:

```env
DOUBAO_APP_KEY=your_app_id
DOUBAO_ACCESS_KEY=your_access_token
DOUBAO_RESOURCE_ID=volc.service_type.10053
```

Where to find them: Volcengine Console → Speech Tech → 同声传译 2.0 → Application Management.

## 5. Self-check first

```cmd
.venv\Scripts\activate
python -m doppelvoice --check
```

Expected:
- A list of audio devices, including `CABLE Input`
- API connectivity: PASS
- Mic capture: PASS

## 6. Launch

```cmd
python -m doppelvoice          # CLI mode
python -m doppelvoice --gui    # GUI mode
```

Or just double-click `gui.bat`.

When the log shows `✓ SessionStarted`, you can start speaking.

## 7. Use it inside meeting apps

### Zoom
1. Settings → Audio → Microphone → pick `CABLE Output (VB-Audio Virtual Cable)`
2. Uncheck "Automatically adjust microphone volume"
3. Test call: speak Chinese, peer hears English

### 腾讯会议 / 飞书 / Microsoft Teams / Google Meet (Chrome)
Same pattern: Audio settings → Microphone → `CABLE Output`.

### OBS livestream
Add an "Audio Input Capture" source → pick `CABLE Output`.

## 8. Recommended hardware

- Wear a **wired or Bluetooth headset** so the mic doesn't pick up the speaker output (would cause an echo loop).
- Or: speakers and mic on **physically separate devices** (headset mic + main speakers).
- Windows Sound Control Panel → Microphone properties → Levels = 80; **disable** noise suppression enhancements (Doubao does its own).

## 9. FAQ

**Q: "Cannot find CABLE Input device"**
A: VB-Cable not installed or system not rebooted. Open `Control Panel → Sound → Playback` and check that `CABLE Input` is listed.

**Q: Peer says "your voice is choppy"**
A: Increase `--jitter-ms` to 300–500; or check your network; or reduce `--chunk-ms` to 60.

**Q: Latency feels >5 s**
A: Look at the log's `[metrics]` line. Two metrics:
- High network latency → connectivity to ByteDance's data centre is slow; try a different network.
- Playback queue depth growing → consumer is slower than producer; reduce `--jitter-ms`.

**Q: How do I switch to en→zh?**
A: Set `SOURCE_LANG=en` and `TARGET_LANG=zh` in `.env`.

**Q: Voice cloning doesn't sound like me**
A: Speak continuously for the first 10–15 s after starting; the model needs time to capture your voice. Also ensure you're using a wideband mic — Bluetooth HFP (AirPods used as a phone mic) only delivers 8 kHz narrowband and gives poor results.

**Q: Stream drops mid-call**
A: The orchestrator auto-reconnects with exponential backoff. Check the log for `reconnecting in Xs`. Frequent drops usually mean an API quota/QPS limit; check your Volcengine usage page.
