"""loguru 配置 + 全局密钥脱敏。"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from loguru import logger

_SENTINEL = "***REDACTED***"

# Pass 1：键值对场景。匹配「字段名 + : 或 = + 值」。
# 字段名匹配带有 key/token/secret/password/authorization 子串的标识符（大小写无关）。
# 字段名前缀可选（`password=`、`token=` 这类裸关键字也要命中）。
# 分隔符允许 JSON 风格的 `"key": "value"`：key 末尾可能有 ", : 前后空格, value 前可能有 "。
# 用 `(?:^|(?<=\W))` 锚定到非词字符之后或行首，避免误吃普通单词中的 "key/token" 子串。
_KV_PATTERN = re.compile(
    r"(?:^|(?<=[\W]))"
    # 字段名：可选前缀 + 关键字 + 可选后缀
    # 前缀 `(?:[A-Za-z][\w\-]*?)?` 是 optional，所以裸 `password=` / `token=` / `secret=`
    # 也能命中（之前强制 `[A-Za-z]` 第一字符导致这类裸关键字漏检）
    r"((?:[A-Za-z][\w\-]*?)?(?:key|token|secret|password|authorization)[\w\-]*)"
    r'(["\']?\s*[:=]\s*["\']?)'
    r"([^\s\"',;}\]\[]+)",
    re.IGNORECASE,
)

# Pass 2：bearer xxx / Authorization Bearer xxx
_BEARER_PATTERN = re.compile(
    r"(bearer)(\s+)([^\s\"',;}\]\[]+)",
    re.IGNORECASE,
)

# Pass 3：高熵长 token 兜底（base64-ish ≥ 16，且不在 ***...*** 内）。
# 边界用 `(?<![\w*])` 防止在 sentinel 周围误命中，且要求至少含一个数字或 -/_，
# 避免误伤普通英文单词。
_LONG_TOKEN_PATTERN = re.compile(
    r"(?<![\w*])(?=[\w\-]*[\d_\-])[A-Za-z0-9][A-Za-z0-9_\-]{15,}(?![\w*])"
)


def _redact(text: str) -> str:
    """3 阶段脱敏：先 KV，再 Bearer，最后兜底长 token。"""
    out = _KV_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{_SENTINEL}", text)
    out = _BEARER_PATTERN.sub(lambda m: f"{m.group(1)}{m.group(2)}{_SENTINEL}", out)
    out = _LONG_TOKEN_PATTERN.sub(_SENTINEL, out)
    return out


def _patcher(record: dict) -> None:
    """loguru patcher：所有日志消息走脱敏。"""
    msg = record.get("message")
    if isinstance(msg, str):
        record["message"] = _redact(msg)
    # 异常字段：把 traceback 里同样的内容脱敏（exception.value/repr 都可能含密钥）
    exc = record.get("exception")
    if exc is not None and getattr(exc, "value", None) is not None:
        try:
            exc.value.args = tuple(
                _redact(a) if isinstance(a, str) else a for a in exc.value.args
            )
        except Exception as e:
            # 不能用 loguru（会递归触发本 patcher），直接走 stderr
            # 但 windowed PyInstaller bundle 下 sys.stderr 是 None
            if sys.stderr is not None:
                sys.stderr.write(f"[log._patcher] redact exception args failed: {e!r}\n")


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    logger.remove()
    logger.configure(patcher=_patcher)
    # PyInstaller windowed bundle (onefile + console=False) detaches stdio
    # → sys.stderr is None and loguru raises TypeError on add(None, ...).
    # Only attach the console sink when there's a real stream to write to.
    if sys.stderr is not None:
        logger.add(
            sys.stderr,
            level=level,
            format="<green>{time:HH:mm:ss.SSS}</green> | <level>{level: <7}</level> | "
                   "<cyan>{name}:{line}</cyan> | <level>{message}</level>",
            enqueue=False,
        )
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.add(
        log_dir / "doppelvoice_{time:YYYYMMDD}.log",
        level="DEBUG",
        rotation="50 MB",
        retention="7 days",
        encoding="utf-8",
        enqueue=True,
    )


def safe_error_message(exc: BaseException, max_len: int = 80) -> str:
    """供 UI 显示的"短且脱敏"错误消息。"""
    s = _redact(str(exc))
    if len(s) > max_len:
        s = s[:max_len] + "…"
    return s
