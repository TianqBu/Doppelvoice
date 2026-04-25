"""诊断：尝试不同采样率/blocksize打开麦克风，定位 PortAudio -9997。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import sounddevice as sd

from doppelvoice.audio.devices import list_devices, find_device
from doppelvoice.config import AppConfig


def try_open(idx: int, sr: int, channels: int, blocksize: int) -> str:
    try:
        sd.check_input_settings(device=idx, samplerate=sr, channels=channels, dtype="int16")
        with sd.RawInputStream(
            samplerate=sr, blocksize=blocksize, device=idx,
            channels=channels, dtype="int16", latency="low",
        ):
            return "OK"
    except Exception as e:
        return f"FAIL: {type(e).__name__}: {e}"


def main():
    cfg = AppConfig.load()
    hint = cfg.audio.input_device
    dev = find_device(hint, need_input=True) if hint else None
    print(f"配置里指定的输入设备关键字: {hint!r}")
    print(f"匹配到: idx={dev.index if dev else 'None'} name={dev.name if dev else '系统默认'}")
    if dev is None:
        print("  （将用系统默认输入设备）")

    # 列所有合法输入设备，对每个设备尝试多种 (sr, blocksize)
    print("\n设备逐个测试（只列 input_channels>0）：")
    print(f"{'idx':>3}  {'host':<14} {'rate':>5}  {'name':<60} {'16kHz@80ms':<40} {'48kHz@0bs':<40} {'native@0bs':<40}")
    for d in list_devices():
        if d.max_input_channels == 0:
            continue
        row = f"{d.index:>3}  {d.hostapi_name[:14]:<14} {int(d.default_samplerate):>5}  {d.name[:60]:<60} "
        r1 = try_open(d.index, 16000, 1, 1280)
        r2 = try_open(d.index, 48000, 1, 0)
        r3 = try_open(d.index, int(d.default_samplerate), 1, 0)
        print(row + f"{r1[:38]:<40} {r2[:38]:<40} {r3[:38]:<40}")


if __name__ == "__main__":
    main()
