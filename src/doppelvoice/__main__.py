"""python -m doppelvoice 入口。

Bundle 模式（PyInstaller 打包后双击 Doppelvoice.exe 启动）：
若用户没有显式传任何参数，默认进 GUI；CLI 子命令仍可通过
`Doppelvoice.exe --check` 等方式触发。开发模式 `python -m doppelvoice`
行为不变（默认走 CLI）。
"""
import sys

from doppelvoice.cli import main

if __name__ == "__main__":
    # Windows 控制台默认 GBK，Python 3.7+ 下 stdout/stderr 默认走 UTF-8 编码会导致
    # 中文错误消息显示为 mojibake。强制 reconfigure 到 utf-8 让用户看清错误。
    # 注意：PyInstaller windowed bundle (onefile + console=False) 下 stdio 是 None。
    if sys.platform == "win32":
        for stream in (sys.stdout, sys.stderr):
            if stream is None:
                continue
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (AttributeError, ValueError):
                pass
    if getattr(sys, "frozen", False) and len(sys.argv) == 1:
        sys.argv.append("--gui")
    sys.exit(main())
