"""python -m doppelvoice 入口。

Bundle 模式（PyInstaller 打包后双击 Doppelvoice.exe 启动）：
若用户没有显式传任何参数，默认进 GUI；CLI 子命令仍可通过
`Doppelvoice.exe --check` 等方式触发。开发模式 `python -m doppelvoice`
行为不变（默认走 CLI）。
"""
import sys

from doppelvoice.cli import main

if __name__ == "__main__":
    if getattr(sys, "frozen", False) and len(sys.argv) == 1:
        sys.argv.append("--gui")
    sys.exit(main())
