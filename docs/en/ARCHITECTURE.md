# Architecture

[中文](../zh/ARCHITECTURE.md)

## Module layout

```
src/doppelvoice/
├── cli.py                  # entry, argument parsing, subcommands
├── config.py               # config dataclasses, .env loading
├── audio/
│   ├── devices.py          # enumerate / pick sound cards
│   ├── capture.py          # mic → asyncio queue
│   ├── playback.py         # queue → virtual mic
│   └── opus_decoder.py     # ogg/opus per-sentence decoder
├── engine/
│   ├── protocol.py         # protobuf import bridge
│   ├── doubao.py           # WebSocket client (stateful, session lifecycle)
│   ├── protos/             # official .proto sources
│   └── _pb/                # generated Python protobuf bindings (do not edit)
├── pipeline/
│   └── orchestrator.py     # asyncio fan-out: capture / ws / playback
├── gui/                    # PySide6 + qasync
│   ├── app.py
│   ├── main_window.py
│   ├── subtitle_view.py
│   └── bus.py
└── utils/
    └── log.py
```

## Concurrency model

```
[ sounddevice mic callback thread ]
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
        │ parse → route by event
        │ on TTSResponse: feed opus decoder
        │ on sentence_end: decode → push playback
        ▼
[ playback buffer (jitter buf) ]
        │
        │ sounddevice playback callback (audio thread)
        ▼
[ CABLE Input device ]
```

- All coroutines run on a single asyncio event loop (`asyncio.run(orchestrator.run())`).
- sounddevice callbacks live in their own audio threads. They only touch thread-safe primitives (`queue.Queue`, `threading.Event`); a bridge coroutine moves data into asyncio land. They never touch the asyncio loop directly, which means safe shutdown.
- When the capture queue fills up, the oldest chunk is dropped (real-time priority).
- When playback runs dry, it outputs silence rather than blocking.

## Doubao AST 2.0 protocol (pure protobuf)

**Critical facts** (verified against official `ast_demo.py` + `.proto`):
- Doubao 同传 2.0 does **not** use a V3 binary frame wrapper. Each WebSocket message is a raw protobuf payload.
- No `START_CONNECTION` event: send `StartSession` (event=100) immediately after the WS handshake.
- All requests are `TranslateRequest`; all responses are `TranslateResponse`.

### Authentication headers (WebSocket upgrade)

```
X-Api-App-Key:     <APP_KEY>
X-Api-Access-Key:  <ACCESS_KEY>
X-Api-Resource-Id: volc.service_type.10053
X-Api-Connect-Id:  <uuid4>
```

### Protobuf schema (excerpt; full sources in `engine/protos/`)

```proto
message TranslateRequest {
  common.RequestMeta request_meta = 1;   // SessionID/...
  event.Type event = 2;                  // 100=StartSession / 200=TaskRequest / 102=FinishSession
  User user = 3;
  Audio source_audio = 4;                // format/rate/bits/channel + binary_data
  Audio target_audio = 5;                // only set on StartSession
  ReqParams request = 6;                 // mode/source_language/target_language/corpus
}

message TranslateResponse {
  common.ResponseMeta response_meta = 1; // SessionID/StatusCode/Message
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
TaskRequest               = 200    # audio chunks

# downstream
SessionStarted            = 150
SessionCanceled           = 151
SessionFinished           = 152
SessionFailed             = 153
UsageResponse             = 154    # billing
AudioMuted                = 250
TTSSentenceStart          = 350
TTSSentenceEnd            = 351
TTSResponse               = 352    # translated audio (pcm or ogg_opus)
SourceSubtitleStart       = 650
SourceSubtitleResponse    = 651
SourceSubtitleEnd         = 652    # full source utterance
TranslationSubtitleStart  = 653
TranslationSubtitleResponse = 654
TranslationSubtitleEnd    = 655    # full translated utterance
```

### Status codes
- Success: `StatusCode == 20000000`
- Anything non-zero and non-`20000000` is an error
- Full error code list in `engine/protos/products/understanding/base/au_base.proto` (`Code` enum)

## Session lifecycle

```
Client → WS handshake (X-Api-* headers)
Server → 101 Switching Protocols

Client → StartSession (event=100, source_audio + target_audio + request)
Server → SessionStarted (event=150, status=20000000)

loop:
  Client → TaskRequest (event=200, source_audio.binary_data = 80ms PCM 16k mono)
  Server → SourceSubtitleStart/Response/End (event=650/651/652, text)
  Server → TranslationSubtitleStart/Response/End (event=653/654/655, text)
  Server → TTSSentenceStart (350) → TTSResponse×N (352, audio bytes) → TTSSentenceEnd (351)
  Server → AudioMuted (250) when user is silent
  Server → UsageResponse (154) for billing

Client → FinishSession (event=102)
Server → SessionFinished (event=152)
```

### Keep-alive

When the mic is silent the client must send a 1280-sample silence frame every ~80 ms; the server otherwise times the session out. This matches sokuji/VolcengineAST2Client.ts.

## StartSession TranslateRequest fields

Aligned with the official `ast_demo.py`:

```python
req.request_meta.SessionID    = <uuid4>     # only field; gateway is already authenticated by header
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
req.request.source_language   = "zh"
req.request.target_language   = "en"
req.request.speaker_id        = ""          # optional
```

## Config loading order

1. `.env` file at project root
2. Process environment variables
3. CLI flags (highest priority)

## Error handling

| Event | Action |
|---|---|
| WebSocket dropped | Exponential backoff: 1 s, 2 s, 4 s, 8 s, capped at 30 s |
| `SessionFailed` / `SessionCanceled` | Retry transient codes only; auth/format codes are fatal — exit |
| `ConnectionFailed` | Drop the connection, retry |
| Playback queue overflow | Drop oldest audio |
| Capture queue overflow | Drop oldest audio |

## Performance notes

1. **Minimise copies**: capture writes one `bytes(...)` per chunk and never re-serialises.
2. **GIL-free I/O**: network in asyncio, audio in PortAudio C callbacks.
3. **Batch playback writes**: full sentence concatenated then played in one go (with ogg_opus).
4. **Low-latency WASAPI**: enabled by default via `latency='low'`.
5. **TCP_NODELAY**: enabled by `websockets`.

## Tests

- `tests/test_protocol.py` — protobuf round-trip + event constants
- `examples/probe_api.py` — interactive: connect + StartSession + FinishSession smoke test
- `examples/probe_e2e.py` — interactive: capture 15 s mic and dump translated audio to `out.wav`
- `examples/probe_mic.py` — interactive: try every (device, sample-rate) combo to find one that works
