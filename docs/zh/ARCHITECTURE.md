# 架构设计 ARCHITECTURE

## 模块分层

```
Doppelvoice/
├── cli.py                    # 入口、参数解析、子命令
├── config.py                 # 配置数据类、环境变量加载
├── audio/
│   ├── devices.py            # 枚举/选择声卡设备
│   ├── capture.py            # 麦克风 → 采集队列
│   └── playback.py           # 播放队列 → 虚拟麦
├── client/
│   ├── protocol.py           # V3 二进制帧编解码（无状态、纯函数）
│   └── doubao.py             # WebSocket 客户端（有状态、会话生命周期）
├── pipeline/
│   └── orchestrator.py       # asyncio 编排 capture/ws/playback
└── utils/
    └── log.py                # loguru 配置
```

## 线程 / 协程模型

```
[ sounddevice 回调线程 (mic) ]
        │ put_nowait(bytes)
        ▼
  asyncio.Queue (capture_q, maxsize=50)
        │
        │ async for chunk
        ▼
[ sender 协程 ] ──ws.send──► 豆包
                                 │
                   ws.recv        ▼
[ receiver 协程 ] ◄──────────────┘
        │ parse → route by event
        │ if TTS_RESPONSE: put audio
        ▼
  asyncio.Queue (playback_q, maxsize=200)
        │
        │ 消费协程 → np.concatenate → chunk
        ▼
[ sounddevice 输出回调线程 ]
```

- 所有协程跑在单个 event loop，`asyncio.run(orchestrator.run())`
- sounddevice 采集/播放回调跑在各自的音频线程，通过 `loop.call_soon_threadsafe` 或 `run_coroutine_threadsafe` 往 asyncio 队列投递
- 采集队列满时丢最早（保实时性）
- 播放队列空时输出静音（避免底层 underrun）

## 豆包 AST 2.0 协议 (纯 protobuf)

**关键事实（来自 sokuji 开源项目逆向 + 官方 .proto 定义）**：
- 豆包同传 2.0 **不用** V3 二进制框架，WebSocket 消息体就是 pure protobuf。
- 无 START_CONNECTION：WS 握手成功后直接发 StartSession（event=100）。
- 请求/响应都是 `TranslateRequest` / `TranslateResponse` 消息。

### 鉴权 Header（WebSocket 升级时）
```
X-Api-App-Key:     <APP_KEY>
X-Api-Access-Key:  <ACCESS_KEY>
X-Api-Resource-Id: volc.service_type.10053
X-Api-Connect-Id:  <uuid4>
```

### Protobuf schema（摘录，完整见 src/Doppelvoice/client/protos/）
```proto
message TranslateRequest {
  common.RequestMeta request_meta = 1;   // SessionID/ConnectionID/Sequence/…
  event.Type event = 2;                  // 100=StartSession / 200=TaskRequest / 102=FinishSession
  User user = 3;
  Audio source_audio = 4;                // format/rate/bits/channel + binary_data
  Audio target_audio = 5;                // 只在 StartSession 设置
  ReqParams request = 6;                 // mode/source_language/target_language/corpus
}

message TranslateResponse {
  common.ResponseMeta response_meta = 1; // SessionID/StatusCode/Message
  event.Type event = 2;                  // 150/152/153/350-352/650-655
  bytes data = 3;                        // TTS 返回的音频 bytes
  string text = 4;                       // 字幕文本
}
```

### 事件码（节选）
```
# 上行
StartSession     = 100
FinishSession    = 102
TaskRequest      = 200   # 音频 chunks

# 下行
SessionStarted          = 150
SessionFailed           = 153
UsageResponse           = 154   # 计费
AudioMuted              = 250
TTSSentenceStart        = 350
TTSSentenceEnd          = 351
TTSResponse             = 352   # 译音 bytes（pcm 或 ogg_opus）
SourceSubtitleStart     = 650
SourceSubtitleResponse  = 651
SourceSubtitleEnd       = 652   # 完整的原语句
TranslationSubtitleStart = 653
TranslationSubtitleResponse = 654
TranslationSubtitleEnd  = 655   # 完整的译文句
```

### 状态码
- 成功：`StatusCode == 20000000`
- 非 0 且非 20000000 → 错误
- 详细错误码见 `au_base.proto` 的 `Code` 枚举

## WebSocket 鉴权头

```
X-Api-App-Key:     <APP_KEY>     # AppID
X-Api-Access-Key:  <ACCESS_KEY>  # Access Token
X-Api-Resource-Id: volc.service_type.10053
X-Api-Connect-Id:  <uuid4>
X-Api-Request-Id:  <uuid4>       # 可选
```

## 会话生命周期

```
Client → WS 握手（X-Api-* headers 鉴权）
Server → 101 Switching Protocols

Client → StartSession(TranslateRequest event=100, source_audio/target_audio/request)
Server → SessionStarted(event=150, status=20000000)

loop:
  Client → TaskRequest(event=200, source_audio.binary_data=PCM 16kHz mono 80ms)
  Server → SourceSubtitleStart/Response/End (event=650/651/652, text)
  Server → TranslationSubtitleStart/Response/End (event=653/654/655, text)
  Server → TTSSentenceStart (350) → TTSResponse×N (352, data=audio) → TTSSentenceEnd (351)
  Server → AudioMuted (250) 当用户静音
  Server → UsageResponse (154) 定期计费

Client → FinishSession(event=102)
Server → SessionFinished(event=152)
```

### 保活机制
麦克风静音时，客户端必须每 ~80ms 发一个 1280 样本的 PCM 零填充帧，否则服务端会超时断连。这是 sokuji/VolcengineAST2Client.ts 的实测做法。

## StartSession TranslateRequest 字段（实际发送）

```python
req.request_meta.Endpoint     = "volc.service_type.10053"
req.request_meta.AppKey       = <APP_KEY>
req.request_meta.ResourceID   = "volc.service_type.10053"
req.request_meta.ConnectionID = <uuid4>
req.request_meta.SessionID    = <uuid4>
req.request_meta.Sequence     = 1
req.event                     = 100  # StartSession

req.user.uid                  = "Doppelvoice-client"
req.user.platform             = "windows"

req.source_audio.format       = "pcm"
req.source_audio.rate         = 16000
req.source_audio.bits         = 16
req.source_audio.channel      = 1

req.target_audio.format       = "pcm"      # 或 "ogg_opus"
req.target_audio.rate         = 24000

req.request.mode              = "s2s"      # 或 "s2t"
req.request.source_language   = "zh"
req.request.target_language   = "en"
# 可选：req.request.corpus.boosting_table_id 等（热词/术语表）
```

## 配置加载顺序

1. `.env` 文件（项目根）
2. 环境变量
3. CLI 参数（最高优先级）

## 错误恢复策略

| 事件 | 行为 |
|------|------|
| WebSocket 断开 | 指数退避重连：1s, 2s, 4s, 8s, 最长 30s |
| `SESSION_FAILED` | 丢弃会话，重发 `START_SESSION` |
| `CONNECTION_FAILED` | 丢弃连接，重连 |
| 音频播放队列溢出 | 丢弃最早音频块 |
| 采集队列溢出 | 丢弃最早音频块 |

## 性能优化点

1. **内存拷贝最少化**：采集回调里直接 `bytes(indata)`，全链路用 `bytes`/`memoryview`
2. **无 GIL 阻塞**：网络 IO 在 asyncio，音频 IO 在 C 回调
3. **批量写入**：播放端合并多个 TTSResponse 为一个 numpy 数组再 write
4. **低延迟 WASAPI**：`sounddevice` 默认使用，可指定 `latency='low'`
5. **禁 Nagle**：websockets 自动 TCP_NODELAY

## 测试策略

- `tests/test_protocol.py`：帧编解码往返测试
- 人工回放：录一段中文 wav，替代麦克风输入，看输出 wav
- 冒烟：`--check` 子命令
