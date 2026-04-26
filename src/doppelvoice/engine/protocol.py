"""豆包 AST 2.0 (同声传译) 协议封装。

要点（由 sokuji/VolcengineAST2Client.ts 逆向 + 官方 .proto 验证）：
- wss://openspeech.bytedance.com/api/v4/ast/v2/translate
- WebSocket 二进制消息体 = 纯 protobuf `TranslateRequest` / `TranslateResponse`
- 无 START_CONNECTION：WS 握手成功后直接发 StartSession
- 每条消息都有 requestMeta（Endpoint/AppKey/ResourceID/ConnectionID/SessionID/Sequence）
- 成功状态码：20000000（非 0 / 非 20000000 即错误）

关于 import 路径：
原始 protoc 生成的 *_pb2.py 用的是绝对 import（`from common import events_pb2`），
对应 .proto 文件里的 `import "common/events.proto"`。我们已经把这些生成代码里的
`from common import` / `from products import` 全部改写成 `from doppelvoice.engine._pb.common import`
之类的完整路径，因此这里不再需要 sys.path 注入 hack —— PyInstaller 打包后也能直接 import。
"""
from __future__ import annotations

from doppelvoice.engine._pb.common import events_pb2 as events_pb
from doppelvoice.engine._pb.common import rpcmeta_pb2 as rpcmeta_pb
from doppelvoice.engine._pb.products.understanding.ast import ast_service_pb2 as ast_pb
from doppelvoice.engine._pb.products.understanding.base import au_base_pb2 as au_pb

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
