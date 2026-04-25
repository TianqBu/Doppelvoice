"""音频设备枚举与查找。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import sounddevice as sd
from loguru import logger


@dataclass
class DeviceInfo:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    hostapi_name: str


def list_devices() -> List[DeviceInfo]:
    hostapis = sd.query_hostapis()
    out: List[DeviceInfo] = []
    for i, dev in enumerate(sd.query_devices()):
        hostapi_idx = dev.get("hostapi", 0)
        try:
            hostapi_name = hostapis[hostapi_idx]["name"]
        except Exception:
            hostapi_name = "?"
        out.append(DeviceInfo(
            index=i,
            name=dev["name"],
            max_input_channels=dev["max_input_channels"],
            max_output_channels=dev["max_output_channels"],
            default_samplerate=dev["default_samplerate"],
            hostapi_name=hostapi_name,
        ))
    return out


def find_device(
    name_hint: Optional[str],
    *,
    need_input: bool = False,
    need_output: bool = False,
) -> Optional[DeviceInfo]:
    """模糊匹配设备名。
    - 输入设备：优先 MME / DirectSound（共享模式下支持任意采样率）
    - 输出设备：优先 WASAPI（低延迟）
    """
    devs = list_devices()
    if name_hint is None:
        return None
    hint = name_hint.lower()
    candidates = [
        d for d in devs
        if hint in d.name.lower()
        and (not need_input or d.max_input_channels > 0)
        and (not need_output or d.max_output_channels > 0)
    ]
    if not candidates:
        return None
    if need_input:
        # WASAPI 不支持任意 sr 的共享模式，对 16kHz 采集不友好；放最低
        priority = {"MME": 0, "Windows DirectSound": 1, "Windows WASAPI": 3, "Windows WDM-KS": 4}
    else:
        priority = {"Windows WASAPI": 0, "MME": 1, "Windows DirectSound": 2}
    candidates.sort(key=lambda d: priority.get(d.hostapi_name, 99))
    return candidates[0]


def pretty_print() -> str:
    lines = ["\n音频设备列表："]
    lines.append(f"{'idx':>3}  {'in':>3}  {'out':>3}  {'rate':>6}  hostapi          name")
    for d in list_devices():
        lines.append(
            f"{d.index:>3}  {d.max_input_channels:>3}  {d.max_output_channels:>3}  "
            f"{int(d.default_samplerate):>6}  {d.hostapi_name:<16} {d.name}"
        )
    return "\n".join(lines)


def check_setup(input_hint: Optional[str], output_hint: Optional[str]) -> bool:
    ok = True
    logger.info(pretty_print())
    in_dev = find_device(input_hint, need_input=True) if input_hint else None
    out_dev = find_device(output_hint, need_output=True)
    if input_hint and not in_dev:
        logger.error(f"✗ 找不到输入设备包含 '{input_hint}'")
        ok = False
    else:
        logger.info(f"✓ 输入设备: {in_dev.name if in_dev else '(系统默认)'}")
    if not out_dev:
        logger.error(f"✗ 找不到输出设备 '{output_hint}'。请先装 VB-Audio Virtual Cable 并重启。")
        ok = False
    else:
        logger.info(f"✓ 输出设备: {out_dev.name} ({int(out_dev.default_samplerate)}Hz)")
    return ok
