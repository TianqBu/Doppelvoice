# 常见问题排查

[English](../en/TROUBLESHOOTING.md)

## 连接 / API

### "API 连通失败: code=11200"
鉴权失败，检查 `.env`：
- `DOUBAO_APP_KEY` 应该是 AppID（纯数字，约 10 位）
- `DOUBAO_ACCESS_KEY` 应该是 Access Token（字母数字混合）
- 服务必须在火山引擎控制台开通

### "API 连通失败: code=11500"
请求参数错。最可能是 `source_language` / `target_language` 取了非法值。
官方接入文档（1756902）支持 9 种取值：`zh / en / ja / id / es / pt / de / fr / zhen`。
其中 `zhen` 是「中英互译」自动双向模式，源/目标必须同为 `zhen`。

### 卡在"建立会话…"不动
1. 网络无法到达 `openspeech.bytedance.com`，检查防火墙
2. 跑 `examples/probe_api.py` 单独验证
3. WS 通了但 StartSession 不回，检查火山引擎控制台的服务状态

## 音频采集

### "PortAudioError: Invalid sample rate (-9997)"
所选麦克风的 host API 不支持 16kHz。Doppelvoice 现已自动回退；若依然失败，跑 `examples/probe_mic.py` 找一个能用的设备。

WASAPI 共享模式只接受设备原生采样率。试试同一设备的 MME 或 DirectSound 版本。

### 麦克风采不到声音（无字幕）
1. Windows 设置 → 隐私 → 麦克风 → "允许应用访问麦克风" 必须开
2. 确认麦克风没在 Windows 音量混合器里被静音
3. 在下拉菜单里换一个麦试 —— 笔记本内置麦通常稳

## 播放 / 虚拟麦

### 对方完全听不到
1. 看 GUI 状态栏 "译音累计" 是不是 > 0 KB。如果是 0，是 API 没发音频（多半配置问题）
2. 验证 Zoom/Teams 的麦克风选的是 `CABLE Output (VB-Audio Virtual Cable)`
3. 直接测：打开"录音机"应用，把它的麦克风设成 `CABLE Output`，跑 Doppelvoice 说话 —— 录音机应该能录到译音

### 译音断断续续
- GUI 里 jitter 拉到 300+ ms
- chunk 加到 100 ms
- 如果有重复片段，把 静音门限 (RMS) 调到 0.015-0.020 过滤背景噪音

### 译音速度不对（太快/太慢）
这是 v0.1 的一个 bug，v0.2+ 通过把音频直接按设备原生 sr 路由解决。如果还遇到，把日志里 `opus decoded:` 和 `[sent #N]` 行截给我们 —— 这俩报告的 Hz 值应该一致且等于设备原生率。

### "对方听到的声音像死人在说话"
- 把 `output_sample_rate` 切到 **48000**（fullband），不是 24000 —— v0.2 起默认就是，但检查 `.env` 是否被覆盖
- 音色克隆质量看输入麦。AirPods 走蓝牙 HFP（电话模式 8kHz 窄带）克隆很差；换有线麦或笔记本内置麦

### 外放声学反馈环

**症状**：通话对面说话时，对方会听到「自己说的话被翻译过的版本」绕回来。

**原理**：
```
对方说话 → 你的电脑外放 → 你的真麦克风（外放声学耦合进去）→ Doppelvoice
       → 豆包翻译（系统以为是你说的中文）→ CABLE Input → 会议 app 再发回去
       → 对方耳朵：自己声音的中文翻译版
```

**根因**：用了**扬声器外放**，麦克风把外放的对方声音又收进去了。任何视频会议软件
（Zoom/Teams/微信）用外放都会有同样问题，只是它们内置 AEC（声学回声消除）能压一压，
我们当前没集成。

**解决**：**戴耳机**。这是物理隔绝声路，立竿见影 100% 解决。
不愿意戴耳机的话，软件层 mitigation：
- 集成 WebRTC AEC3 — 大工程，且需要"远端参考信号"（对方原始语音）才能减出来，会议 app 不暴露
- 加 push-to-talk 热键（按住才发麦） — 半天工作量，未来 release 可能加
- 短期最实用：在你的 Doppelvoice 设置里把 RMS 静音门限调高到 `0.020+`，能少误触发一些

## 音色克隆质量

### 克隆出来的声音单调机械
1. 公开 AST API 比火山控制台 demo（走的是不同的 BFF 端点，带额外韵律处理）差一截。这是硬天花板
2. 会话开头连续说 15+ 秒 —— 模型需要这段时间采样你的声音
3. 用宽频麦（≥48kHz 原生采样）
4. `.env` 里 `DENOISE=0`（默认）—— 服务端降噪会磨平气声/共鸣等独特音色细节，关掉能保留更多说话人特征
5. `SPEAKER_ID` 留空（默认）= 克隆模式；填如 `zh_female_vv_uranus_bigtts` 会**改用预设音色，不是你的**

## GUI / Windows

### `gui.bat` 不出窗口
老版 `gui.bat` 用 `pythonw`，错误被吞了。最新版用普通 `python` —— 重新拉再试。还不行就在 cmd 里跑看 traceback：

```cmd
set PYTHONPATH=src
.venv\Scripts\python.exe -m doppelvoice --gui
```

### `gui.bat` 报 `'te.bat' 不是命令`
你的 `gui.bat` 被改了，里面有非 ASCII 字符把 cmd.exe 搞糊涂了。从仓库重新拉，或纯 ASCII 重写一份（参考仓库主版本）。

### 关窗时 "RuntimeError: Event loop is closed"
最新版本在音频回调里加了 `_closing` 标志，关窗时会异步等收尾。还有这问题请提 issue 附完整 traceback。

## 隐私 / 数据

### 我的译音 / 字幕保存在哪里？
默认**哪都不存**。字幕文本和每句的 ogg 数据都不落盘。

调试时启用：
```env
DUMP_AUDIO=1
LOG_SUBTITLE=1
```
文件去 `logs/sentences/<时间戳>/NNN.ogg` 和 `logs/doppelvoice_*.log`。调试完记得删。

## 报 bug

请附上：
- Windows 版本（`winver`）
- Python 版本（`python --version`）
- VB-Cable 版本（声音设置 → 点 `CABLE Input` → 属性 → 驱动）
- 选的麦和 host API（`run.bat --list-devices`）
- `logs/doppelvoice_*.log` 里相关的几行 —— **分享前请涂掉 API 密钥**
- 复现步骤
