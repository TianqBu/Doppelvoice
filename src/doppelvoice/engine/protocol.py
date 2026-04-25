"""豆包 AST 2.0 (同声传译) 协议封装。

要点（由 sokuji/VolcengineAST2Client.ts 逆向 + 官方 .proto 验证）：
- wss://openspeech.bytedance.com/api/v4/ast/v2/translate
- WebSocket 二进制消息体 = 纯 protobuf `TranslateRequest` / `TranslateResponse`
- 无 START_CONNECTION：WS 握手成功后直接发 StartSession
- 每条消息都有 requestMeta（Endpoint/AppKey/ResourceID/ConnectionID/SessionID/Sequence）
- 成功状态码：20000000（非 0 / 非 20000000 即错误）
"""
from __future__ import annotations

import sys
from pathlib import Path

# 让生成的 pb 模块可直接 import（它们互相 import 彼此的 package 路径）
_PB_ROOT = Path(__file__).resolve().parent / "_pb"
if str(_PB_ROOT) not in sys.path:
    sys.path.insert(0, str(_PB_ROOT))

# 需要从生成的包里 import
from common import events_pb2 as events_pb  # noqa: E402
from common import rpcmeta_pb2 as rpcmeta_pb  # noqa: E402
from products.understanding.ast import ast_service_pb2 as ast_pb  # noqa: E402
from products.understanding.base import au_base_pb2 as au_pb  # noqa: E402

EventType = events_pb.Type
STATUS_SUCCESS = 20000000

__all__ = [
    "events_pb",
    "rpcmeta_pb",
    "ast_pb",
    "au_pb",
    "EventType",
    "STATUS_SUCCESS",
]
