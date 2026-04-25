# Doppelvoice — 产品需求文档 PRD

[English](../en/PRD.md)

版本：v0.1  
日期：2026-04-21  
平台：Windows 10/11 (x64)  
作者：user + Claude

---

## 1. 项目目标

让用户在任意视频会议、直播、通话软件（Zoom、Teams、腾讯会议、飞书、Google Meet、Discord、OBS…）中：

- 用**中文**自然说话
- 对方**实时**听到**用户本人音色**的**英文**语音
- 延迟 ≤ 3 秒（端到端，含采集+网络+合成+注入）
- 会议软件无感，不需要任何插件或破解

后续可扩展：英→中、日语、韩语、实时字幕显示、本地录音留档。

## 2. 目标用户 & 典型场景

| 场景 | 用法 |
|------|------|
| 跨国视频会议 | 会议中发言，对方听到英文 |
| 海外直播/带货 | 直播间观众听到英文 |
| 面试 / 路演 | 不干扰思考节奏地说中文，评委听英文 |
| 线下演讲+线上参会者 | 会场说中文，Zoom 远端听英文 |

## 3. 功能需求 (MVP)

### 3.1 必需功能
- **F1**：从默认麦克风（或用户指定设备）采集音频
- **F2**：通过火山引擎豆包同传 2.0 (`ast/v2/translate`) WebSocket 实时流式翻译（S2S 模式）
- **F3**：接收含用户音色的英文 PCM 音频流
- **F4**：写入 Windows 虚拟音频设备（VB-Audio Virtual Cable 的 `CABLE Input`），供任何会议软件选用
- **F5**：命令行启动，可一键 `run.bat` 启动
- **F6**：实时日志：延迟、发送/接收字节、会话状态、错误
- **F7**：配置文件化：API 密钥、输入输出设备、语言对、音频格式

### 3.2 重要功能
- **F8**：网络中断自动重连（指数退避）
- **F9**：会话级 0 样本音色复刻（豆包原生支持，无需预录）
- **F10**：Ctrl+C 优雅退出，正确 FinishSession + FinishConnection
- **F11**：自检模式 `--check`：列设备、测试麦克风、测试 API 连通性
- **F12**：静音门限 (VAD / 能量门限)，避免空流量消耗

### 3.3 次要（后续迭代）
- **F13**：实时字幕 GUI (PyQt / Web overlay)
- **F14**：英→中反向翻译（需要第二路会话）
- **F15**：热词/术语表注入（豆包 `UpdateConfig` 支持）
- **F16**：录音留档（原声 + 译音双轨 wav）
- **F17**：系统托盘控制（开关、切语言、切设备）

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

- **v0.1 (当前)**：CLI 能跑通中→英 S2S
- **v0.2**：延迟优化 + 重连 + 自检
- **v0.3**：GUI (tray icon + 字幕 overlay)
- **v0.4**：双向翻译 + 热词表
- **v0.5**：录音留档 + 转写导出
