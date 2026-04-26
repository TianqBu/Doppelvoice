"""音频设备枚举与查找。

PortAudio 把同一颗物理设备在 MME / DirectSound / WASAPI / WDM-KS 4 个 host API
下各注册一次，UI 直接展示会出现 4 份重复条目。本模块提供 `list_unique_devices()`
做按 (设备名 + 方向) 去重，每颗物理设备只保留一条，并按 host API 优先级偷偷选
最佳后端：
- 输入：MME → DirectSound → WASAPI → WDM-KS（共享模式下高兼容率，支持任意 sr）
- 输出：WASAPI → MME → DirectSound（低延迟优先）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import sounddevice as sd
from loguru import logger

Direction = Literal["input", "output"]

# host API 优先级：值越小越优先
_INPUT_PRIORITY = {
    "MME": 0,
    "Windows DirectSound": 1,
    "Windows WASAPI": 2,
    "Windows WDM-KS": 3,
}
_OUTPUT_PRIORITY = {
    "Windows WASAPI": 0,
    "MME": 1,
    "Windows DirectSound": 2,
    "Windows WDM-KS": 3,
}


@dataclass
class DeviceInfo:
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    hostapi_name: str


@dataclass
class UniqueDevice:
    """每颗物理设备一条；隐藏 host API 细节，但仍记录所选后端供调试。"""
    name: str
    direction: Direction
    chosen_index: int                 # 最终用的 PortAudio index
    chosen_hostapi: str               # 实际选中的 host API 名（调试用）
    default_samplerate: float
    channels: int
    all_indices: list[int] = field(default_factory=list)  # 同名同向所有 PortAudio 入口
    all_hostapis: list[str] = field(default_factory=list)


# ── 原始（未去重）枚举 ──

def list_devices() -> list[DeviceInfo]:
    """枚举所有 PortAudio 暴露条目（每个 host API 一份）。供调试/兼容旧调用。"""
    hostapis = sd.query_hostapis()
    out: list[DeviceInfo] = []
    for i, dev in enumerate(sd.query_devices()):
        hostapi_idx = dev.get("hostapi", 0)
        try:
            hostapi_name = hostapis[hostapi_idx]["name"]
        except (IndexError, KeyError) as e:
            logger.debug(f"hostapi lookup failed for index {hostapi_idx}: {e}")
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


# ── 去重后的物理设备视图（推荐 UI 使用）──

def list_unique_devices(direction: Direction) -> List[UniqueDevice]:
    """按物理设备聚合，每颗设备返回一条 `UniqueDevice`。

    direction="input"  → 仅有麦克风输入能力的设备
    direction="output" → 仅有扬声器/虚拟麦输出能力的设备
    """
    raw = list_devices()
    priority = _INPUT_PRIORITY if direction == "input" else _OUTPUT_PRIORITY

    # 按设备名分桶（同一颗物理设备在多个 host API 下名字一致）
    buckets: dict[str, list[DeviceInfo]] = {}
    for d in raw:
        if direction == "input" and d.max_input_channels <= 0:
            continue
        if direction == "output" and d.max_output_channels <= 0:
            continue
        buckets.setdefault(d.name, []).append(d)

    # MME 把设备名截断到 31 字符，导致相同物理设备的 MME 条目名称比 DirectSound/WASAPI
    # 的短一截。识别这类 MME-only 桶并合并到对应的长名桶里，避免重复显示。
    mme_truncated_keys: list[str] = []
    for short_name, short_group in list(buckets.items()):
        if len(short_group) != 1:
            continue
        if short_group[0].hostapi_name != "MME":
            continue
        if len(short_name) < 31:
            # MME 截断只发生在 ≥31 字符的长名上；短名是真不同设备
            continue
        for long_name in buckets:
            if long_name == short_name:
                continue
            # 只往更长的非 MME 名字桶里合并
            if (
                len(long_name) > len(short_name)
                and long_name.startswith(short_name)
                and any(d.hostapi_name != "MME" for d in buckets[long_name])
            ):
                buckets[long_name].extend(short_group)
                mme_truncated_keys.append(short_name)
                break
    for k in mme_truncated_keys:
        del buckets[k]

    unique: list[UniqueDevice] = []
    for name, group in buckets.items():
        # 排序：优先级低的（数值小）排前面；未在表里的 host API 按 99 排到最后
        group.sort(key=lambda x: priority.get(x.hostapi_name, 99))
        chosen = group[0]
        ch = chosen.max_input_channels if direction == "input" else chosen.max_output_channels
        unique.append(UniqueDevice(
            name=name,
            direction=direction,
            chosen_index=chosen.index,
            chosen_hostapi=chosen.hostapi_name,
            default_samplerate=chosen.default_samplerate,
            channels=ch,
            all_indices=[d.index for d in group],
            all_hostapis=[d.hostapi_name for d in group],
        ))

    # 按设备名稳定排序，UI 更可读
    unique.sort(key=lambda u: u.name.lower())
    return unique


# ── 名称查找（保持向后兼容）──

def find_device(
    name_hint: str | None,
    *,
    need_input: bool = False,
    need_output: bool = False,
) -> DeviceInfo | None:
    """按名称子串匹配单个设备，自动按 host API 优先级选最佳后端。

    保持旧签名返回 DeviceInfo（带 host API 信息），用于 capture/playback 的
    底层 PortAudio 调用。UI 层应改用 `list_unique_devices()`。
    """
    if name_hint is None:
        return None
    hint = name_hint.lower()
    devs = list_devices()
    candidates = [
        d for d in devs
        if hint in d.name.lower()
        and (not need_input or d.max_input_channels > 0)
        and (not need_output or d.max_output_channels > 0)
    ]
    if not candidates:
        return None
    priority = _INPUT_PRIORITY if need_input else _OUTPUT_PRIORITY
    candidates.sort(key=lambda d: priority.get(d.hostapi_name, 99))
    return candidates[0]


def pretty_print() -> str:
    """调试用：列所有原始 PortAudio 条目（含 host API 重复）。"""
    lines = ["\n音频设备列表（原始 / 含 host API 重复）："]
    lines.append(f"{'idx':>3}  {'in':>3}  {'out':>3}  {'rate':>6}  hostapi          name")
    for d in list_devices():
        lines.append(
            f"{d.index:>3}  {d.max_input_channels:>3}  {d.max_output_channels:>3}  "
            f"{int(d.default_samplerate):>6}  {d.hostapi_name:<16} {d.name}"
        )
    return "\n".join(lines)


def check_setup(input_hint: str | None, output_hint: str | None) -> bool:
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
