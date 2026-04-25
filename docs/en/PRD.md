# Doppelvoice — Product Requirements

Version: v0.1
Date: 2026-04-21
Platform: Windows 10/11 (x64)

[中文](../zh/PRD.md)

---

## 1. Goals

In any video conferencing, livestream or call app (Zoom, Teams, 腾讯会议, 飞书, Google Meet, Discord, OBS, …):

- User speaks **Chinese** naturally into the mic.
- The other party hears **English** in **the user's own voice**, in real time.
- End-to-end latency ≤ 3 s (capture + network + synthesis + virtual-mic injection).
- Zero-touch for the meeting app — no plugin, no patch.

Later: en → zh, Japanese, Korean, live caption overlay, dual-track recording.

## 2. Users & Scenarios

| Scenario | Usage |
|---|---|
| Cross-border video meetings | Speak Chinese, peers hear English |
| Overseas livestream | Audience on the stream hears English |
| Interviews / pitch demos | Speak Chinese for fluency, judges hear English |
| Hybrid lecture | Speak Chinese on stage; remote Zoom audience hears English |

## 3. Functional Requirements (MVP)

### 3.1 Required
- **F1**: Capture audio from default mic (or a user-chosen device).
- **F2**: Stream-translate via Doubao Seed LiveInterpret 2.0 (`ast/v2/translate`) WebSocket in S2S mode.
- **F3**: Receive English PCM/Opus audio that retains the user's voice.
- **F4**: Write audio to a Windows virtual sound device (VB-Audio Virtual Cable's `CABLE Input`) so any meeting app can pick it as a microphone.
- **F5**: CLI launcher; one-click `gui.bat`.
- **F6**: Live metrics: latency, bytes sent/received, session state, errors.
- **F7**: All settings via config file: API keys, devices, language pair, audio format.

### 3.2 Important
- **F8**: Auto-reconnect on network drops with exponential backoff.
- **F9**: Per-session zero-shot voice cloning (built into Doubao; no pre-recording).
- **F10**: Ctrl+C clean exit (proper FinishSession + FinishConnection).
- **F11**: `--check` mode that lists devices, tests mic, verifies API connectivity.
- **F12**: Optional silence gating (RMS threshold) to skip empty frames.

### 3.3 Future
- **F13**: Live subtitle GUI (PyQt / web overlay).
- **F14**: Reverse direction (en → zh) on a parallel session.
- **F15**: Hot-word / glossary injection (Doubao `UpdateConfig` supported).
- **F16**: Recording: source + translated tracks to wav.
- **F17**: System tray controls (start/stop, language, device).

## 4. Non-Functional Requirements

| Metric | Target |
|---|---|
| End-to-end latency | ≤ 3 s (Doubao reports 2.21 s s2t / 2.53 s s2s) |
| Audio jitter | Playback jitter buffer ≥ 200 ms |
| CPU | <2% idle, <10% under load (i5-class) |
| Memory | <300 MB |
| Long-session stability | 2 h continuous, no drift, no crash |
| Startup | <3 s |

## 5. Dependencies

### 5.1 User machine
- Windows 10 / 11 64-bit
- Python 3.10+
- Microphone (a noise-cancelling headset is recommended)
- **Virtual audio cable**: [VB-Audio Virtual Cable](https://vb-audio.com/Cable/) (free, required)
- Optional: [VoiceMeeter Banana](https://vb-audio.com/Voicemeeter/banana.htm) for multi-route mixing

### 5.2 Volcengine account
- Activate **Doubao 同声传译 2.0** (`volc.service_type.10053`)
- Three credentials: `APP_KEY` (AppID), `ACCESS_KEY` (Access Token), `RESOURCE_ID = volc.service_type.10053`

## 6. Pipeline Flow

```
[Microphone] ──(16kHz/16bit/mono PCM, 80ms chunks)──► [Capture thread]
                                                            │
                                                            ▼
                                                    [asyncio send queue]
                                                            │
                                                            ▼
                       [WebSocket sender] ──► wss://openspeech.bytedance.com/api/v4/ast/v2/translate
                                                            │
                                          (Doubao end-to-end interpretation + voice cloning)
                                                            │
                                ◄──────────── [TTSResponse English ogg/opus stream]
                                                            │
                                                            ▼
                                                    [asyncio recv queue]
                                                            │
                                                            ▼
                                                    [Jitter buffer ~200ms]
                                                            │
                                                            ▼
                                                  [Write to CABLE Input]
                                                            │
                                                            ▼
                              Zoom/Teams/etc. select "CABLE Output" as microphone
                                                            │
                                                            ▼
                                                       Peer hears English
```

## 7. Key Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Capture lib | `sounddevice` | newer than pyaudio, cleaner API, good WASAPI support |
| Async runtime | `asyncio` + `websockets` | first-class coroutines, low overhead |
| Audio format | 16 kHz/16-bit/mono PCM | Doubao recommended |
| Chunk size | 80 ms = 1280 samples | balance of latency and packet rate |
| Jitter buffer | 120 ms (default) | empirically smooth |
| Config | `.env` + CLI flags | secrets out of repo |
| Logging | `loguru` | colourful, easy config |
| Virtual mic | VB-Cable | most widespread, free, stable driver |

## 8. Acceptance

- [ ] `python -m doppelvoice --check` lists CABLE Input and passes its tests.
- [ ] Run `gui.bat`, speak Chinese, peer in Zoom hears English.
- [ ] After 10 minutes of continuous chat, latency stays ≤ 3 s.
- [ ] Disconnecting the network for 10 s and reconnecting recovers automatically.
- [ ] Ctrl+C cleanly tears everything down.

## 9. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Field names drift from official demo | All payload fields isolated in `engine/doubao.py::_build_start_session`; one-line edits |
| Network jitter | Jitter buffer + adaptive playback |
| Short-utterance voice clone instability | Encourage continuous 10+ s of speech to seed the model |
| VB-Cable sample-rate mismatch | Query device native rate at runtime, resample on the fly |
| Long-session latency drift | Monitor playback queue depth; drop oldest if over cap |

## 10. Roadmap

- **v0.1 (current)**: zh → en S2S CLI/GUI working end-to-end
- **v0.2**: latency tuning, smarter reconnect, self-check
- **v0.3**: GUI polish (tray icon, subtitle overlay)
- **v0.4**: bidirectional translation, hot-word injection
- **v0.5**: dual-track recording and transcript export
