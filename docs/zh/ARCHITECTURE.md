# 架构设计 ARCHITECTURE

[English](../en/ARCHITECTURE.md)

## 模块布局

```
src/doppelvoice/
├── cli.py                  # 入口 / 参数解析 / 子命令
├── config.py               # 配置数据类（frozen 子 config + AppConfig 容器 + snapshot）
├── audio/
│   ├── devices.py          # 枚举 + 按物理设备去重（处理 MME 31 字符截断）
│   ├── capture.py          # 麦克风 → asyncio queue + peak_level 暴露
│   ├── playback.py         # asyncio queue → 虚拟麦
│   ├── opus_decoder.py     # ogg/opus 整句解码
│   └── resample.py         # int16 重采样（soxr 优先 / 线性兜底），三方共享
├── engine/
│   ├── protocol.py         # protobuf 桥（绝对路径 import，无 sys.path hack）
│   ├── doubao.py           # WebSocket 客户端：会话生命周期 + URL 校验 + 帧上限
│   ├── protos/             # 官方 .proto 源
│   └── _pb/                # 生成的 protobuf 绑定（绝对路径 import 已重写）
├── pipeline/
│   └── orchestrator.py     # asyncio 编排：sender / receiver / metrics + _ReceiverContext
├── gui/                    # PySide6 + qasync
│   ├── app.py
│   ├── main_window.py      # 工具栏 / 9 语言下拉 / 设备下拉 / 字幕 / 状态栏
│   ├── settings_dialog.py  # 三 tab：API / 音频 / 高级（含 denoise 开关）
│   ├── subtitle_view.py    # QTextEdit + MAX_BLOCKS=2000 内存上限
│   ├── i18n.py             # zh/en UI 文案 + 9 语言显示名
│   ├── theme.py / bus.py / env_io.py  # 样式 / 信号总线 / .env 原子读写
│   └── widgets/            # 状态徽章 / 电平表
└── utils/
    └── log.py              # loguru 配置 + 全局密钥脱敏 patcher
```

## 线程 / 协程模型

```
[ sounddevice 麦回调（音频线程）]
        │ thread-safe queue.Queue.put_nowait
        ▼
   thread Queue (capture-side, maxsize=50)
        │ run_in_executor 拉
        ▼
   asyncio.Queue (capture_q, maxsize=50)
        │ async for chunk
        ▼
[ sender 协程 ] ── ws.send ──► 豆包
                                  │
                       ws.recv    ▼
[ receiver 协程 ] ◄────────────────┘
        │ parse → _ReceiverContext + 4 个 _handle_* 协助函数
        │ kind == "audio"     → push opus decoder
        │ kind == "sentence_end" → drain decoder → push playback
        │ kind == "target_text" → emit GuiEventBus
        │ kind == "error"     → 分类 fatal/transient
        ▼
[ playback buffer (jitter buf) ]
        │
        │ sounddevice 播放回调（音频线程）
        ▼
[ CABLE Input 设备 ]
```

- 全部协程跑在单个 asyncio event loop（qasync 与 Qt 共享）
- 音频回调线程只接触 thread-safe primitives（`queue.Queue`、`threading.Event`、原子的
  `_peak_level: float`）；通过 bridge 协程把数据搬进 asyncio 域，永不直接调 loop
- 采集队列满 → 丢最早 chunk（保实时性）
- 播放回调下溢 → 直接吐静音，不阻塞
- **GUI 电平表复用 capture 的 RMS**，不再开第二路 InputStream（v0.1 那个独立流已删）

## 配置数据流

```
.env / 环境变量 ──► AppConfig.load()
                    │ ┌─ Credentials (mutable，支持密钥轮换)
                    │ └─ AudioConfig (frozen) / TranslationConfig (frozen) / NetworkConfig (frozen)
                    ▼
                 main_window.cfg
                    │
       ┌────────────┴────────────┐
       ▼                         ▼
  SettingsDialog 改 cfg     orchestrator = Orchestrator(cfg)
  (replace 整个子 config)         │
       │                         ▼
       │               self.cfg = cfg.snapshot()  ← 浅拷贝快照
       │                         │
       │               跑会话期间这份 snapshot 不变
       ▼
  下次新会话才生效，
  当前跑着的会话不受影响
```

子 config 用 `@dataclass(frozen=True)` —— 想改必须 `dataclasses.replace(cfg.audio, …)`
返回新副本再赋回 `cfg.audio`。Orchestrator `__init__` 调 `cfg.snapshot()` 拍快照，
保证会话内部状态不会被 GUI 中途改的设备 / 采样率污染。

## 豆包 AST 2.0 协议（纯 protobuf）

**关键事实**（由 sokuji 逆向 + 官方 ast_demo.py + 官方 .proto 验证 + 官方 PDF 1756902）：

- 豆包同传 2.0 **不用** V3 二进制框架。WebSocket 消息体就是裸 protobuf。
- 无 START_CONNECTION：WS 握手成功后直接发 StartSession（event=100）。
- 请求/响应都是 `TranslateRequest` / `TranslateResponse`。
- `denoise` 是 `optional bool` 字段（proto 字段编号 7）。我们显式设 `false` 以
  保留说话人特征供零样本克隆，不依赖服务端默认值。

### 鉴权 Header（WebSocket 升级时）
```
X-Api-App-Key:     <APP_KEY>
X-Api-Access-Key:  <ACCESS_KEY>
X-Api-Resource-Id: volc.service_type.10053
X-Api-Connect-Id:  <uuid4>
```

`DoubaoClient.connect()` 在握手前会校验 URL：scheme 必须 `wss://`，hostname 必须
在白名单 `{openspeech.bytedance.com}` 里。防止 `.env` 被注入恶意 URL 把密钥发到
攻击者。

### Protobuf schema（摘录，完整见 `engine/protos/`）
```proto
message TranslateRequest {
  common.RequestMeta request_meta = 1;
  event.Type event = 2;                  // 100=StartSession / 200=TaskRequest / 102=FinishSession
  User user = 3;
  Audio source_audio = 4;                // format/rate/bits/channel + binary_data
  Audio target_audio = 5;                // 仅在 StartSession 设置
  ReqParams request = 6;                 // mode/source_language/target_language/speaker_id/corpus
  optional bool denoise = 7;             // 显式 false 保留克隆音色细节
}

message TranslateResponse {
  common.ResponseMeta response_meta = 1;
  event.Type event = 2;                  // 150/152/153/350-352/650-655
  bytes data = 3;                        // TTS 音频
  string text = 4;                       // 字幕文本
}
```

### 事件码（节选）
```
# 上行
StartSession              = 100
FinishSession             = 102
TaskRequest               = 200    # 音频 chunks（每包 80ms PCM 16kHz mono）

# 下行
SessionStarted            = 150
SessionCanceled           = 151
SessionFinished           = 152
SessionFailed             = 153
UsageResponse             = 154    # 计费
AudioMuted                = 250    # 服务端检测到 2s 静音
TTSSentenceStart          = 350
TTSSentenceEnd            = 351
TTSResponse               = 352    # 译音 bytes（pcm 或 ogg_opus）
SourceSubtitleStart       = 650
SourceSubtitleResponse    = 651
SourceSubtitleEnd         = 652
TranslationSubtitleStart  = 653
TranslationSubtitleResponse = 654
TranslationSubtitleEnd    = 655
```

### 状态码
- 成功：`StatusCode == 20000000`
- 非 0 且非 20000000 → 错误
- 完整错误码见 `engine/protos/products/understanding/base/au_base.proto` 的 `Code` 枚举

### 支持的语言
9 种取值：`zh / en / ja / id / es / pt / de / fr / zhen`。
`zhen` 是中英互译自动模式 —— `source_language` 和 `target_language` **同时**填
`zhen`。其他语言是单向模式（如 `source_language=ja, target_language=en`）。

## 会话生命周期

```
Client → WS 握手（X-Api-* headers，URL 校验通过）
Server → 101 Switching Protocols

Client → StartSession (event=100)
         body 含 source_audio + target_audio + request + denoise=false
Server → SessionStarted (event=150, status=20000000)

会话期间循环：
  Client → TaskRequest (event=200)
           复用 _audio_req 模板，只改 binary_data 减少 protobuf 重建
  Server → SourceSubtitleStart/Response/End  (650/651/652)
  Server → TranslationSubtitleStart/Response/End  (653/654/655)
  Server → TTSSentenceStart (350) → TTSResponse×N (352) → TTSSentenceEnd (351)
  Server → AudioMuted (250) 当用户静音
  Server → UsageResponse (154) 定期计费

Client → FinishSession (event=102)
Server → SessionFinished (event=152)
```

### 保活机制

麦克风静音时客户端必须每 ~80ms 发一帧 1280 样本静音 PCM，否则服务端超时断连。
对应 `Orchestrator._sender_loop` 的 `keepalive_s` 路径。

## StartSession 字段（已发送的实际值）

对齐官方 `ast_demo.py`：

```python
req.request_meta.SessionID    = <uuid4>     # 唯一字段；网关已用 header 鉴权
req.event                     = 100         # StartSession

req.user.uid                  = "ast_py_client"
req.user.did                  = "ast_py_client"

req.source_audio.format       = "wav"       # 不是 "pcm"，wav 走对的服务端管线
req.source_audio.rate         = 16000
req.source_audio.bits         = 16
req.source_audio.channel      = 1

req.target_audio.format       = "ogg_opus"
req.target_audio.rate         = 48000       # fullband，比 24000 更自然

req.request.mode              = "s2s"       # 或 "s2t"
req.request.source_language   = "zh"        # 9 种之一
req.request.target_language   = "en"
req.request.speaker_id        = ""          # 空 = 克隆模式

req.denoise                   = False       # 显式发，避免服务端默认（推测 true）
```

## 错误恢复策略

| 事件 | 行为 |
|------|------|
| WebSocket 断开 | 指数退避：1s → 2s → 4s → 8s → … → 30s |
| `SessionFailed` / `SessionCanceled` | 仅瞬时码（`_TRANSIENT_CODES`）重连；鉴权/格式码 → fatal 退出 |
| 帧 > 4MB | 丢弃 + log warning（防恶意服务端 OOM） |
| 采集 / 播放队列溢出 | 丢最早音频块 |

## 安全加固

- **WS URL 校验**：连接前白名单 hostname + scheme=wss
- **帧大小**：`max_size=4MB`（从 64MB 收紧）+ `ParseFromString` 前长度检查
- **`.env` 原子写**：`tempfile.mkstemp` + `os.fsync` + `os.replace`，崩溃也不丢密钥
- **日志全局脱敏**：loguru patcher 三阶段（KV / Bearer / 长 token）替换为 `***REDACTED***`
- **`logger.exception` 替换为 `logger.warning(type(e).__name__)`**：避免 traceback 把
  服务端可能回显的密钥落盘
- **隐私默认**：`dump_audio_to_disk=False` / `log_subtitle_text=False`，需显式开

## 性能优化

| 优化点 | 收益 |
|---|---|
| send_audio 复用 `_audio_req` 模板 | 每秒省 12-13 次 protobuf 对象重建 |
| capture 回调里 `np.dot` 算 RMS | 比 `np.sqrt(np.mean(x**2))` 快 ~4× |
| playback `_callback` 直接写 ctypes outdata | 省一次中间 `bytes()` 拷贝 |
| opus_decoder 直接 resample 到设备原生率 | 避免 playback 二次重采样 |
| 删第二路 mic InputStream | 一颗物理麦只开一路 PortAudio |
| `silence_rms_threshold=0.0`（默认） | 不再误丢首字辅音/气声，省 300-500ms 首字延迟 |

## 已知设计限制

| 限制 | 影响 | 缓解 |
|---|---|---|
| 句末才整段解 ogg/opus | 输出端等满整句（3-5s）才出第一个字 | 待替换为流式 opus 解码（`opuslib`），或重测 `format=pcm` |
| 重连即新会话 | 零样本音色重新采样，长会话音色会突变 | 调研 `speaker_id` 是否支持复用；UI 提示用户 |
| Hardcode `CABLE Input` | 非 Windows 跑不起来 | 抽 `VirtualMicResolver` Protocol（v0.5 计划） |
| 用户用扬声器外放 | 声学反馈环 → 对方听到自己声音的翻译 | 戴耳机；未来加 push-to-talk |

## 测试

| 文件 | 覆盖 |
|---|---|
| `tests/test_protocol.py` | protobuf round-trip + 事件常量 |
| `tests/test_resample.py` | 重采样：等率 / 空输入 / 上下采样 / clipping |
| `tests/test_devices.py` | 设备去重：MME 31 字符截断 / 输入输出过滤 / host API 优先级 |
| `tests/test_doubao_classify.py` | `_classify` 每个 event 分支（10+ 用例） |
| `tests/test_log_redact.py` | 三阶段脱敏 + sentinel 不被二次匹配 |
| `tests/test_config.py` | frozen 行为 + snapshot 隔离 + AppConfig swap |
| `examples/probe_*.py` | 交互式：API 连通 / 端到端 / 麦设备探测 |

跑：`pytest tests/ -q`（46 个）。
