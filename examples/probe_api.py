"""仅测 API 连通性（不依赖虚拟声卡）。"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from doppelvoice.config import AppConfig
from doppelvoice.engine.doubao import DoubaoClient
from doppelvoice.utils.log import setup_logging


async def main():
    setup_logging(Path("logs"), "DEBUG")
    cfg = AppConfig.load()
    client = DoubaoClient(cfg)
    try:
        await client.connect()
        print(">>> WS OK")
        await client.start_session()
        print(">>> SESSION OK session_id=", client.session_id)
        # 发几个静音帧看服务端如何响应
        silence = b"\x00\x00" * 1280  # 80ms of 16kHz int16 silence
        for _ in range(5):
            await client.send_audio(silence)
            await asyncio.sleep(0.08)

        async def _dump():
            async for ev in client.iter_events():
                print(
                    "EVENT kind=", ev.kind,
                    "event=", ev.raw_event,
                    "status=", ev.status_code,
                    "msg=", ev.message,
                    "text=", ev.text,
                    "audio_len=", len(ev.audio) if ev.audio else 0,
                    "definite=", ev.is_definite,
                )
        try:
            await asyncio.wait_for(_dump(), timeout=5)
        except asyncio.TimeoutError:
            pass
    except Exception as e:
        print(">>> ERROR:", repr(e))
    finally:
        await client.finish_session()
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
