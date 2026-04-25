# 安装与使用 SETUP

## 1. 装 Python 3.10+

官网下载 https://www.python.org/downloads/ → 安装时勾选 "Add to PATH"。

验证：
```cmd
python --version
```

## 2. 装 VB-Audio Virtual Cable（关键！）

1. 下载：https://vb-audio.com/Cable/ → 点 "Download" → 解压
2. 右键 `VBCABLE_Setup_x64.exe` → **以管理员运行** → Install Driver
3. **重启电脑**（必须）
4. 重启后在 Windows 声音设置能看到：
   - 输出设备：`CABLE Input (VB-Audio Virtual Cable)`
   - 输入设备：`CABLE Output (VB-Audio Virtual Cable)`

## 3. 安装本项目依赖

```cmd
cd C:\Users\86132\Desktop\Doppelvoice
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 4. 配置密钥

复制 `.env.example` → `.env`，填入火山引擎豆包同传 2.0 的密钥：

```env
DOUBAO_APP_KEY=你的AppID
DOUBAO_ACCESS_KEY=你的AccessToken
DOUBAO_RESOURCE_ID=volc.service_type.10053
```

位置：火山引擎控制台 → 语音技术 → 同声传译 2.0 → 应用管理。

## 5. 自检（先于实战）

```cmd
.venv\Scripts\activate
python -m Doppelvoice --check
```

预期输出：
- 列出所有音频设备（找到 `CABLE Input`）
- API 连通测试 PASS
- 麦克风采集测试 PASS

## 6. 启动同传

```cmd
python -m Doppelvoice
```

或双击 `run.bat`。

看到日志 `✓ SESSION_STARTED` 就可以开始说中文了。

## 7. 在会议软件里用

### Zoom
1. 设置 → 音频 → 麦克风 → 选 `CABLE Output (VB-Audio Virtual Cable)`
2. 取消勾选 "自动调节音量"
3. 测试通话里自己说中文，对方只听到英文

### 腾讯会议 / 飞书 / Teams / Google Meet (浏览器)
同样：音频设置 → 麦克风选 `CABLE Output`。

### OBS 直播
添加 "音频输入捕获" 源 → 选 `CABLE Output`。

## 8. 推荐硬件设置

- 戴**有线/蓝牙耳麦**，避免自己麦克风采集到扬声器播放的英文（会自循环）
- 或者：**输出给你自己听的声音**用主扬声器，麦克风用耳麦，物理隔离
- Windows 声音控制面板 → 麦克风属性 → 级别 = 80、增强关"杂音抑制"（豆包自带处理更好）

## 9. 常见问题

**Q: 启动报错 "找不到 CABLE Input 设备"**  
A: VB-Cable 没装好或没重启。打开 `控制面板 → 声音 → 播放` 看有没有 `CABLE Input`。

**Q: 会议里对方说 "你的声音断断续续"**  
A: 调高 `--jitter-ms` 到 300-500；或检查网络；或降低 `--chunk-ms` 到 60。

**Q: 延迟很高（>5s）**  
A: 先看日志里的 `网络延迟` 和 `播放队列深度`。两个指标都查一下：
- 网络延迟 > 1s：网络到火山机房慢，考虑换网络
- 播放队列深度持续增长：消费速度跟不上，降低 `--jitter-ms`

**Q: 想换成英→中方向**  
A: `.env` 里设 `SOURCE_LANG=en` `TARGET_LANG=zh`。

**Q: 音色复刻听起来不像我**  
A: 前 10s 多说几句让模型采样；或录一段 10s 干净的你的声音作为 reference（v0.3 计划加参数支持）。

**Q: 突然断流**  
A: 程序会自动重连，看日志 `reconnecting in Xs`。若频繁断，检查 API 余额/QPS 限制。
