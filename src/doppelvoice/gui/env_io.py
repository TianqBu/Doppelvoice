"""读写 .env 文件（保留注释和未触碰的 key）。"""
from __future__ import annotations

from pathlib import Path

from doppelvoice.config import PROJECT_ROOT


def env_path() -> Path:
    return PROJECT_ROOT / ".env"


def read_env() -> dict[str, str]:
    p = env_path()
    if not p.exists():
        return {}
    out: dict[str, str] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def write_env(updates: dict[str, str], *, preserve_unknown: bool = True) -> None:
    """把 updates 合并写回 .env。
    - preserve_unknown=True 时保留 .env 里我们没改的那些行（包括注释）
    """
    p = env_path()
    existing_lines: list[str] = []
    seen_keys: set[str] = set()

    if preserve_unknown and p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                existing_lines.append(line)
                continue
            if "=" in stripped:
                k = stripped.split("=", 1)[0].strip()
                if k in updates:
                    # 用新值替换
                    new_val = updates[k]
                    existing_lines.append(f"{k}={new_val}")
                    seen_keys.add(k)
                else:
                    existing_lines.append(line)

    # 追加新增 key
    for k, v in updates.items():
        if k not in seen_keys:
            existing_lines.append(f"{k}={v}")

    p.write_text("\n".join(existing_lines) + "\n", encoding="utf-8")


def has_credentials() -> bool:
    """检测 .env 里是否填了 APP_KEY 和 ACCESS_KEY。"""
    env = read_env()
    return bool(env.get("DOUBAO_APP_KEY", "").strip()) and bool(
        env.get("DOUBAO_ACCESS_KEY", "").strip()
    )
