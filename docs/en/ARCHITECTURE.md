# Architecture

[中文](../zh/ARCHITECTURE.md)

## Module layout

```
src/doppelvoice/
├── cli.py                  # entry, argument parsing, subcommands
├── config.py               # frozen sub-configs + AppConfig container + snapshot()
├── audio/
│   ├── devices.py          # enumerate + dedupe by physical device (handles MME 31-char truncation)
│   ├── capture.py          # mic → asyncio queue + exposes peak_level
│   ├── playback.py         # asyncio queue → virtual mic
│   ├── opus_decoder.py     # ogg/opus per-sentence decoder
│   └── resample.py         # int16 resampling (soxr → linear fallback), shared by 3 callers
├── engine/
│   ├── protocol.py         # protobuf bridge (absolute imports, no sys.path hack)
│   ├── doubao.py           # WebSocket client: session lifecycle + URL allowlist + frame guard
│   ├── protos/             # official .proto sources
│   └── _pb/                # generated protobuf bindings (absolute imports rewritten)
├── pipeline/
│   └── orchestrator.py     # asyncio fan-out: sender / receiver / metrics + _ReceiverContext
├── gui/                    # PySide6 + qasync
│   ├── app.py
│   ├── main_window.py      # toolbar / 9-language dropdown / device dropdown / subtitles / status bar
│   ├── settings_dialog.py  # 3 tabs: API / Audio / Advanced (with denoise toggle)
│   ├── subtitle_view.py    # QTextEdit + MAX_BLOCKS=2000 memory cap
│   ├── i18n.py             # zh/en UI text + 9-language display names
│   ├── theme.py / bus.py / env_io.py  # styling / signal bus / atomic .env I/O
│   └── widgets/            # status badge / level meter
└── utils/
    └── log.py              # loguru config + global secret-redaction patcher
```

## Concurrency model

```
[ sounddevice mic callback (audio thread) ]
        │ thread-safe queue.Queue.put_nowait
        ▼
   thread Queue (capture-side, maxsize=50)
        │ run_in_executor pulls
        ▼
   asyncio.Queue (capture_q, maxsize=50)
        │ async for chunk
        ▼
[ sender coroutine ] ── ws.send ──► Doubao
                                       │
                          ws.recv      ▼
[ receiver coroutine ] ◄───────────────┘
        │ parse → _ReceiverContext + 4 _handle_* helpers
        │ kind == "audio"        → push opus decoder
        │ kind == "sentence_end" → drain decoder → push playback
        │ kind == "target_text"  → emit GuiEventBus
        │ kind == "error"        → classify fatal/transient
        ▼
[ playback buffer (jitter buf) ]
        │
        │ sounddevice playback callback (audio thread)
        ▼
[ CABLE Input device ]
```

- All coroutines run on a single asyncio event loop (qasync shares with Qt).
- Audio callback threads only touch thread-safe primitives (`queue.Queue`,
  `threading.Event`, atomic `_peak_level: float`); a bridge coroutine moves
  data into asyncio land. They never touch the loop directly, ensuring safe
  shutdown.
- Capture queue full → drop the oldest chunk (real-time priority).
- Playback callback underrun → emit silence rather than block.
- **GUI level meter reuses capture's RMS** — the second `sd.InputStream` from
  v0.1 is gone.

## Configuration data flow

```
.env / env vars ──► AppConfig.load()
                    │ ┌─ Credentials (mutable, supports key rotation)
                    │ └─ AudioConfig (frozen) / TranslationConfig (frozen) / NetworkConfig (frozen)
                    ▼
                 main_window.cfg
                    │
       ┌────────────┴────────────┐
       ▼                         ▼
  SettingsDialog mutates    orchestrator = Orchestrator(cfg)
  cfg.audio = replace(...)        │
       │                          ▼
       │           self.cfg = cfg.snapshot()  ← shallow copy
       │                          │
       │           snapshot stays stable for the running session
       ▼
  next session sees the new value;
  current running session is unaffected
```

Sub-configs use `@dataclass(frozen=True)`; mutation goes through
`dataclasses.replace(cfg.audio, …)` and assignment back to `cfg.audio`.
`Orchestrator.__init__` calls `cfg.snapshot()` to take a shallow copy so that
in-flight session state cannot be corrupted by a mid-run device or sample-rate
change in the GUI.

## Doubao AST 2.0 protocol (pure protobuf)

**Critical facts** (verified against sokuji reverse-engineering + official
`ast_demo.py` + official `.proto` + official PDF spec 1756902):

- Doubao 同传 2.0 does **not** use a V3 binary frame wrapper. Each WebSocket
  message is a raw protobuf payload.
- No `START_CONNECTION` event: send `StartSession` (event=100) immediately
  after the WS handshake.
- All requests are `TranslateRequest`; all responses are `TranslateResponse`.
- `denoise` is an `optional bool` field (proto field number 7). We send
  `false` explicitly to retain speaker characteristics for zero-shot voice
  cloning, rather than rely on the server default.

### Authentication headers (WebSocket upgrade)

```
X-Api-App-Key:     <APP_KEY>
X-Api-Access-Key:  <ACCESS_KEY>
X-Api-Resource-Id: volc.service_type.10053
X-Api-Connect-Id:  <uuid4>
```

`DoubaoClient.connect()` validates the URL before handshake: scheme must be
`wss://` and hostname must be in the allowlist `{openspeech.bytedance.com}`.
This guards against `.env` injection redirecting credentials to an attacker.

### Protobuf schema (excerpt; full sources in `engine/protos/`)

```proto
message TranslateRequest {
  common.RequestMeta request_meta = 1;
  event.Type event = 2;                  // 100=StartSession / 200=TaskRequest / 102=FinishSession
  User user = 3;
  Audio source_audio = 4;                // format/rate/bits/channel + binary_data
  Audio target_audio = 5;                // only set on StartSession
  ReqParams request = 6;                 // mode/source_language/target_language/speaker_id/corpus
  optional bool denoise = 7;             // explicit false retains voice clone detail
}

message TranslateResponse {
  common.ResponseMeta response_meta = 1;
  event.Type event = 2;                  // 150/152/153/350-352/650-655
  bytes data = 3;                        // TTS audio
  string text = 4;                       // subtitle text
}
```

### Event codes (selected)

```
# upstream
StartSession              = 100
FinishSession             = 102
TaskRequest               = 200    # audio chunks (80ms PCM 16kHz mono each)

# downstream
SessionStarted            = 150
SessionCanceled           = 151
SessionFinished           = 152
SessionFailed             = 153
UsageResponse             = 154    # billing
AudioMuted                = 250    # server detected 2s of silence
TTSSentenceStart          = 350
TTSSentenceEnd            = 351
TTSResponse               = 352    # translated audio (pcm or ogg_opus)
SourceSubtitleStart       = 650
SourceSubtitleResponse    = 651
SourceSubtitleEnd         = 652
TranslationSubtitleStart  = 653
TranslationSubtitleResponse = 654
TranslationSubtitleEnd    = 655
```

### Status codes

- Success: `StatusCode == 20000000`
- Anything non-zero and non-`20000000` is an error.
- Full error code list in `engine/protos/products/understanding/base/au_base.proto`
  (`Code` enum).

### Supported languages

9 codes: `zh / en / ja / id / es / pt / de / fr / zhen`.
`zhen` is the bilingual ZH⇄EN auto mode — set **both** `source_language` and
`target_language` to `zhen`. Any other language code is unidirectional
(e.g. `source_language=ja, target_language=en`).

## Session lifecycle

```
Client → WS handshake (X-Api-* headers; URL validated)
Server → 101 Switching Protocols

Client → StartSession (event=100)
         body has source_audio + target_audio + request + denoise=false
Server → SessionStarted (event=150, status=20000000)

per-session loop:
  Client → TaskRequest (event=200)
           reuses _audio_req template, only updates binary_data
  Server → SourceSubtitleStart/Response/End  (650/651/652)
  Server → TranslationSubtitleStart/Response/End  (653/654/655)
  Server → TTSSentenceStart (350) → TTSResponse×N (352) → TTSSentenceEnd (351)
  Server → AudioMuted (250) when user is silent
  Server → UsageResponse (154) for billing

Client → FinishSession (event=102)
Server → SessionFinished (event=152)
```

### Keep-alive

When the mic is silent, the client sends a 1280-sample silence frame every
~80 ms (`Orchestrator._sender_loop` keepalive path); otherwise the server
times the session out.

## StartSession TranslateRequest fields

Aligned with the official `ast_demo.py`:

```python
req.request_meta.SessionID    = <uuid4>     # only field; gateway already authenticated by header
req.event                     = 100         # StartSession

req.user.uid                  = "ast_py_client"
req.user.did                  = "ast_py_client"

req.source_audio.format       = "wav"       # NOT "pcm" — server processes "wav" through the right pipeline
req.source_audio.rate         = 16000
req.source_audio.bits         = 16
req.source_audio.channel      = 1

req.target_audio.format       = "ogg_opus"
req.target_audio.rate         = 48000       # 48 kHz fullband; better-sounding than 24 kHz wideband

req.request.mode              = "s2s"       # or "s2t"
req.request.source_language   = "zh"        # one of 9 codes
req.request.target_language   = "en"
req.request.speaker_id        = ""          # empty = clone mode

req.denoise                   = False       # explicit; avoids server default (assumed true) flattening voice
```

## Error recovery

| Event | Action |
|---|---|
| WebSocket dropped | Exponential backoff: 1 s → 2 s → 4 s → 8 s → … capped at 30 s |
| `SessionFailed` / `SessionCanceled` | Retry only `_TRANSIENT_CODES`; auth/format codes → fatal exit |
| Frame > 4 MB | Drop + log warning (defends against malicious-server OOM) |
| Capture / playback queue overflow | Drop oldest audio chunk |

## Security hardening

- **WS URL validation**: hostname allowlist + `wss://` scheme check before connect
- **Frame size**: `max_size=4 MB` (down from 64 MB) + length check before
  `ParseFromString`
- **Atomic `.env` write**: `tempfile.mkstemp` + `os.fsync` + `os.replace` so
  a crash mid-write cannot truncate credentials
- **Global log redaction**: loguru patcher with 3 stages (KV pairs / Bearer
  tokens / orphan high-entropy strings) replaces matches with `***REDACTED***`
- **`logger.exception` replaced with `logger.warning(type(e).__name__)`** so
  tracebacks (which may contain server-echoed credentials) don't land on disk
- **Privacy by default**: `dump_audio_to_disk=False` /
  `log_subtitle_text=False`; user must opt in

## Performance optimizations

| Change | Win |
|---|---|
| send_audio reuses `_audio_req` template | Saves 12-13 protobuf object allocations per second |
| Capture callback uses `np.dot` for RMS | ~4× faster than `np.sqrt(np.mean(x**2))` |
| playback `_callback` writes ctypes outdata directly | Eliminates one intermediate `bytes()` copy |
| opus_decoder resamples to device native rate | Avoids second resample in playback |
| Removed second mic InputStream | One physical mic = one PortAudio stream |
| `silence_rms_threshold=0.0` (default) | No more first-syllable consonant clipping; -300-500 ms first-word latency |

## Known design limits

| Limit | Impact | Mitigation |
|---|---|---|
| Sentence-end ogg/opus batch decode | Output side waits for the full sentence (3-5s) before first sample plays | Switch to streaming opus (`opuslib`) or re-test `format=pcm` |
| Reconnect = new session | Voice clone re-samples zero-shot; long sessions audibly shift timbre on each retry | Investigate whether `speaker_id` supports reuse; surface in UI |
| Hardcoded `CABLE Input` | Won't run outside Windows | Abstract a `VirtualMicResolver` Protocol (v0.5 plan) |
| User uses external speakers | Acoustic feedback loop → peer hears their own voice translated | Wear headphones; future push-to-talk |

## Tests

| File | Coverage |
|---|---|
| `tests/test_protocol.py` | protobuf round-trip + event constants |
| `tests/test_resample.py` | resample: same rate / empty / up / down / clipping |
| `tests/test_devices.py` | dedup: MME 31-char truncation / input/output filter / host API priority |
| `tests/test_doubao_classify.py` | `_classify` for every event branch (10+ cases) |
| `tests/test_log_redact.py` | 3-stage redaction + sentinel non-rematching |
| `tests/test_config.py` | frozen behavior + snapshot isolation + AppConfig swap |
| `examples/probe_*.py` | interactive: API connectivity / end-to-end / mic device probe |

Run: `pytest tests/ -q` (46 total).
