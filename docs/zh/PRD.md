# Doppelvoice — 产品需求文档 PRD

[English](../en/PRD.md)

版本：v0.2.0
日期：2026-04-26
平台：Windows 10/11 (x64)

---

## 1. 项目目标

让用户在任意视频会议、直播、通话软件（Zoom、Teams、腾讯会议、飞书、Google Meet、Discord、OBS…）中：

- 用任意支持语种自然说话（zh/en/ja/id/es/pt/de/fr 8 种 + 中英互译模式 zhen）
- 对方**实时**听到**用户本人音色**的目标语种语音
- 延迟 ≤ 3 秒（端到端，含采集+网络+合成+注入）
- 会议软件无感，不需要任何插件或破解

后续可扩展：实时字幕显示、本地录音留档、push-to-talk、跨平台（macOS / Linux）。

## 2. 目标用户 & 典型场景

| 场景 | 用法 |
|------|------|
| 跨国视频会议 | 会议中发言，对方听到英文 |
| 海外直播/带货 | 直播间观众听到英文 |
| 面试 / 路演 | 不干扰思考节奏地说中文，评委听英文 |
| 线下演讲+线上参会者 | 会场说中文，Zoom 远端听英文 |

## 3. 功能需求 (MVP)

### 3.1 必需功能（已实现）
- **F1**：从用户选择的麦克风采集音频（设备列表去重，每颗物理设备一条）
- **F2**：通过火山引擎豆包同传 2.0 (`ast/v2/translate`) WebSocket 实时流式翻译
- **F3**：接收含用户音色的目标语 PCM/Opus 音频流
- **F4**：写入 Windows 虚拟音频设备（VB-Audio Virtual Cable 的 `CABLE Input`）
- **F5**：CLI + GUI 双入口（`run.bat` / `gui.bat`）
- **F6**：实时日志 + GUI 状态栏指标（采集/播放队列、延迟、字节数）
- **F7**：分层配置：`.env` + 环境变量 + CLI（前两层 frozen，运行时由 settings dialog 热改）
- **F18**：**9 种语言** (zh/en/ja/id/es/pt/de/fr) + 中英互译模式 (zhen)
- **F19**：**音色克隆细节保留**：显式 `denoise=false` 关掉服务端降噪
- **F20**：**日志全局脱敏**：API key / Bearer token / 长 token 自动遮罩

### 3.2 重要功能（已实现）
- **F8**：网络中断自动重连（指数退避，1→2→4→…→30s）
- **F9**：会话级 0 样本音色复刻
- **F10**：Ctrl+C / 关窗优雅退出（FinishSession + 资源清理）
- **F11**：自检模式 `--check`：列设备、测试麦克风、测试 API 连通性
- **F12**：静音门限可选（默认关 0.0，因为豆包服务端有自己的 VAD）
- **F21**：**WebSocket URL 校验**：hostname 白名单 + 4MB 帧上限 + ParseFromString 长度防御
- **F22**：**`.env` 原子写**：避免崩溃丢密钥

### 3.3 次要（后续迭代）
- **F13**：字幕 overlay 窗口（独立小窗）
- **F15**：热词/术语表注入（豆包 `UpdateConfig` 支持）
- **F16**：录音留档（原声 + 译音双轨 wav）
- **F17**：系统托盘控制（开关、切语言、切设备）
- **F23**：Push-to-talk 热键（解决用外放时的声学反馈环）
- **F24**：跨平台（macOS BlackHole / Linux PipeWire null-sink）
- **F25**：Codex / WebRTC AEC3 集成（深度回声消除）

## 4. 非功能需求

| 指标 | 目标 |
|------|------|
| 端到端延迟 | ≤ 3 秒（豆包官方 2.21s 语音→语音，加 IO 开销） |
| 音频抖动 | 播放侧 jitter buffer ≥ 200ms |
| CPU 占用 | 空载 <2%，工作态 <10% (i5 级 CPU) |
| 内存 | <300MB |
| 长时稳定性 | 连续 2 小时无累积延迟 / 无崩溃 |
| 启动时间 | <3s |

## 5. 依赖与前置条件

### 5.1 用户本机
- Windows 10 / 11 64 位
- Python 3.10+
- 麦克风（建议降噪耳麦）
- **虚拟音频线**：[VB-Audio Virtual Cable](https://vb-audio.com/Cable/)（免费，必装）
  - 可选升级：[VoiceMeeter Banana](https://vb-audio.com/Voicemeeter/banana.htm)（多路混音）

### 5.2 火山引擎账号
- 已开通 **豆包同声传译 2.0** (`volc.service_type.10053`)
- 三个密钥：`APP_KEY`（AppID）、`ACCESS_KEY`（Access Token）、`RESOURCE_ID = volc.service_type.10053`

## 6. 交互流程

```
[麦克风] ──(16kHz/16bit/mono PCM, 80ms chunks)──► [采集线程]
                                                       │
                                                       ▼
                                              [asyncio 发送队列]
                                                       │
                                                       ▼
                      [WebSocket 发送协程] ──► wss://openspeech.bytedance.com/api/v4/ast/v2/translate
                                                       │
                                           (豆包端到端同传+音色克隆)
                                                       │
                           ◄─────────── [TTSResponse 英文 PCM 流]
                                                       │
                                                       ▼
                                              [asyncio 接收队列]
                                                       │
                                                       ▼
                                              [Jitter Buffer ~200ms]
                                                       │
                                                       ▼
                                         [输出到 CABLE Input 设备]
                                                       │
                                                       ▼
                     Zoom/Teams/腾讯会议 选 "CABLE Output" 作麦克风
                                                       │
                                                       ▼
                                                    对方听见
```

## 7. 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 采集库 | `sounddevice` | 比 pyaudio 新、跨平台、API 简洁、WASAPI 支持好 |
| 异步库 | `asyncio` + `websockets` | 原生协程、低开销、websockets 成熟 |
| 音频格式 | 16kHz/16bit/mono PCM | 豆包官方推荐 |
| 打包块大小 | 80ms = 1280 samples | 官方推荐平衡延迟与包率 |
| Jitter buffer | 200ms | 经验值，平衡流畅与延迟 |
| 配置 | `.env` + CLI 参数 | 密钥不入库、参数可覆盖 |
| 日志 | `loguru` | 开箱即用、彩色、易配 |
| 虚拟麦 | VB-Cable | 最广泛、免费、驱动稳定 |

## 8. 验收标准

- [ ] `python -m Doppelvoice --check` 能列出 CABLE Input 设备且测试通过
- [ ] `python -m Doppelvoice` 启动后对着麦克风说中文，Zoom 测试通话里对方听到英文
- [ ] 连续 10 分钟对话延迟始终 ≤ 3 秒
- [ ] 拔网 10 秒后插回能自动恢复
- [ ] Ctrl+C 能优雅退出，无残留连接

## 9. 风险与缓解

| 风险 | 缓解 |
|------|------|
| 协议字段与官方 Demo 不一致 | 所有 payload 抽离成 `protocol_defaults.py`，可热改 |
| 网络抖动导致音频卡顿 | Jitter buffer + 自适应延迟 |
| 音色克隆在短句上不稳定 | 前 10s 静音/空转给模型采样时间 |
| VB-Cable 采样率不匹配 | 运行时查询设备采样率并 resample |
| 长会议累计延迟 | 监控播放队列深度，过大时丢弃最早音频 |

## 10. 迭代路径

- **v0.1.0**：CLI/GUI 能跑通中→英 S2S（已完成 2026-04-22）
- **v0.1.1**：项目重命名 Doppelvoice + 双语文档（已完成 2026-04-25）
- **v0.2.0 (当前)**：4 路代码审查全包：9 语言 + 设备去重 + 音色克隆调优 + frozen
  config + 日志脱敏 + 协议安全加固 + 测试 3→46（已完成 2026-04-26）
- **v0.3**：PyInstaller 打包 + tray icon + push-to-talk 热键
- **v0.4**：字幕 overlay + 热词表 + 录音留档
- **v0.5**：跨平台（macOS / Linux）+ AEC3 集成
