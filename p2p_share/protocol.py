from __future__ import annotations

import json
import socket
from typing import Any


class ProtocolError(Exception):
    pass



def send_message(sock: socket.socket, message: dict[str, Any]) -> None:
    wire = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
    sock.sendall(wire)



def receive_message(sock_file) -> dict[str, Any]:
    line = sock_file.readline()
    if not line:
        raise ProtocolError("Connection closed unexpectedly")
    try:
        return json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"Invalid JSON payload: {line!r}") from exc
