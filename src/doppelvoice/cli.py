"""命令行入口：run / check / list-devices。"""
from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import replace

from loguru import logger

from doppelvoice.audio import devices
from doppelvoice.config import AppConfig
from doppelvoice.utils.log import setup_logging


def _make_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="doppelvoice",
        description="中→英实时同传（豆包 Seed LiveInterpret 2.0 + 虚拟麦克风）",
    )
    p.add_argument("--gui", action="store_true", help="启动图形界面")
    p.add_argument("--check", action="store_true", help="自检：列出设备+测试 API 连通")
    p.add_argument("--list-devices", action="store_true", help="只列出音频设备")
    p.add_argument("--input-device", help="麦克风设备名包含字符串")
    p.add_argument("--output-device", help="虚拟麦输出设备名包含字符串（默认: CABLE Input）")
    p.add_argument("--source", dest="source_lang", help="源语言，默认 zh")
    p.add_argument("--target", dest="target_lang", help="目标语言，默认 en")
    p.add_argument("--mode", choices=["s2s", "s2t"], help="翻译模式，默认 s2s")
    p.add_argument("--chunk-ms", type=int, help="每包音频时长，默认 80ms")
    p.add_argument("--jitter-ms", type=int, help="播放 jitter buffer 毫秒，默认 240")
    p.add_argument("--log-level", default=None, help="DEBUG/INFO/WARNING")
    return p


def _apply_overrides(cfg: AppConfig, args: argparse.Namespace) -> None:
    """子 config 是 frozen 的，必须用 replace() 构造新对象再赋回。"""
    audio_overrides: dict = {}
    if args.input_device:
        audio_overrides["input_device"] = args.input_device
    if args.output_device:
        audio_overrides["output_device"] = args.output_device
    if args.chunk_ms:
        audio_overrides["chunk_ms"] = args.chunk_ms
    if args.jitter_ms:
        audio_overrides["jitter_buffer_ms"] = args.jitter_ms
    if audio_overrides:
        cfg.audio = replace(cfg.audio, **audio_overrides)

    translation_overrides: dict = {}
    if args.source_lang:
        translation_overrides["source_language"] = args.source_lang
    if args.target_lang:
        translation_overrides["target_language"] = args.target_lang
    if args.mode:
        translation_overrides["mode"] = args.mode
    if translation_overrides:
        cfg.translation = replace(cfg.translation, **translation_overrides)

    if args.log_level:
        cfg.log_level = args.log_level


async def _api_probe(cfg: AppConfig) -> bool:
    """连通性测试：建 WS + StartSession + FinishSession。全流程过才算通过。"""
    from doppelvoice.engine.doubao import DoubaoClient
    client = DoubaoClient(cfg)
    try:
        await client.connect()
        logger.info("✓ WS 握手成功（header 鉴权通过）")
        await client.start_session()
        logger.info("✓ StartSession 成功（session 参数合法）")
        return True
    except Exception as e:
        logger.error(f"✗ API 连通失败: {e}")
        return False
    finally:
        await client.finish_session()
        await client.close()


def main() -> int:
    args = _make_parser().parse_args()

    if args.gui:
        from doppelvoice.gui.app import main as gui_main
        return gui_main()

    # --list-devices 不需要密钥
    if args.list_devices:
        # 为打印设备配置轻量日志
        from pathlib import Path
        setup_logging(Path("logs"), "INFO")
        logger.info(devices.pretty_print())
        return 0

    try:
        cfg = AppConfig.load()
    except RuntimeError as e:
        print(f"[配置错误] {e}", file=sys.stderr)
        return 2

    _apply_overrides(cfg, args)
    setup_logging(cfg.log_dir, cfg.log_level)

    logger.info(
        f"doppelvoice 启动 | {cfg.translation.source_language}→{cfg.translation.target_language} "
        f"mode={cfg.translation.mode} clone={cfg.translation.voice_clone}"
    )

    if args.check:
        ok = devices.check_setup(cfg.audio.input_device, cfg.audio.output_device)
        api_ok = asyncio.run(_api_probe(cfg))
        return 0 if (ok and api_ok) else 1

    # 正式启动
    from doppelvoice.pipeline.orchestrator import Orchestrator
    try:
        asyncio.run(Orchestrator(cfg).run())
    except KeyboardInterrupt:
        logger.info("收到 Ctrl+C，退出")
    return 0
