"""端到端测试：麦克风 15s → 豆包 → 保存 out.wav + 打印字幕。

无需虚拟麦。验证"采集→API→返回译音"全链路。
"""
import asyncio
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import numpy as np
import sounddevice as sd
from loguru import logger

from doppelvoice.engine.doubao import DoubaoClient
from doppelvoice.config import AppConfig
from doppelvoice.utils.log import setup_logging


DURATION_S = 15
CHUNK_MS = 80


async def main():
    setup_logging(ROOT / "logs", "INFO")
    cfg = AppConfig.load()
    client = DoubaoClient(cfg)

    await client.connect()
    await client.start_session()

    received_audio = bytearray()
    cap_q: asyncio.Queue[bytes] = asyncio.Queue(maxsize=50)
    loop = asyncio.get_running_loop()

    sr = cfg.audio.input_sample_rate
    block = int(sr * CHUNK_MS / 1000)

    def _cb(indata, frames, time_info, status):
        if status:
            logger.debug("mic status: {}", status)
        data = bytes(indata)
        def _put():
            if cap_q.full():
                try:
                    cap_q.get_nowait()
                except asyncio.QueueEmpty:
                    pass
            cap_q.put_nowait(data)
        loop.call_soon_threadsafe(_put)

    stream = sd.RawInputStream(
        samplerate=sr, blocksize=block, channels=1, dtype="int16", callback=_cb
    )
    stream.start()
    # 并发启动 sender 和 receiver
    logger.warning("=" * 60)
    logger.warning(f"🎤 3 秒后开始录音 {DURATION_S} 秒，请说中文")
    logger.warning("=" * 60)
    await asyncio.sleep(3)
    logger.warning("▶️  开始录音！")

    async def sender():
        silence = b"\x00\x00" * block
        end = asyncio.get_running_loop().time() + DURATION_S
        while asyncio.get_running_loop().time() < end:
            try:
                chunk = await asyncio.wait_for(cap_q.get(), timeout=CHUNK_MS / 1000)
                await client.send_audio(chunk)
            except asyncio.TimeoutError:
                await client.send_audio(silence)

    async def receiver():
        async for ev in client.iter_events():
            if ev.kind == "audio" and ev.audio:
                received_audio.extend(ev.audio)
                logger.info(f"🔊 收到译音 {len(ev.audio)} bytes (累计 {len(received_audio)})")
            elif ev.kind == "target_text" and ev.text:
                tag = "译文" if ev.is_definite else "译文·"
                logger.info(f"[{tag}] {ev.text}")
            elif ev.kind == "source_text" and ev.text:
                tag = "原文" if ev.is_definite else "原文·"
                logger.info(f"[{tag}] {ev.text}")
            elif ev.kind == "error":
                logger.error(f"✗ 服务端错误: code={ev.status_code} msg={ev.message!r}")
                return
            elif ev.kind == "session_finished":
                logger.info("会话正常结束")
                return

    try:
        # 并发跑发送和接收
        recv_task = asyncio.create_task(receiver())
        send_task = asyncio.create_task(sender())
        await send_task
        logger.warning("⏹️  采集完成，等待尾部译音（最多 10s）…")
        try:
            await asyncio.wait_for(recv_task, timeout=10)
        except asyncio.TimeoutError:
            recv_task.cancel()
    finally:
        stream.stop()
        stream.close()
        await client.finish_session()
        await client.close()

    # 写译音到 out.wav
    out = ROOT / "out.wav"
    if received_audio:
        sr_out = cfg.audio.output_sample_rate
        arr = np.frombuffer(bytes(received_audio), dtype=np.int16)
        with wave.open(str(out), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(sr_out)
            w.writeframes(arr.tobytes())
        logger.info(f"✓ 已写入 {out} ({len(arr)/sr_out:.2f}s)")
    else:
        logger.warning("没有收到任何译音")


if __name__ == "__main__":
    asyncio.run(main())
