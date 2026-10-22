from __future__ import annotations

import json
import socket
from typing import Any

# Counted in bytes: files are opened in binary mode. Room for a manifest of tens of thousands of chunk hashes.
MAX_LINE_BYTES = 16 * 1024 * 1024


class ProtocolError(Exception):
    pass


class ConnectionClosedError(ProtocolError):
    pass


class MessageTooLargeError(ProtocolError):
    pass


def send_message(sock: socket.socket, message: dict[str, Any]) -> None:
    wire = json.dumps(message, separators=(",", ":")).encode("utf-8") + b"\n"
    sock.sendall(wire)


def receive_message(sock_file) -> dict[str, Any]:
    line = sock_file.readline(MAX_LINE_BYTES + 1)
    if not line:
        raise ConnectionClosedError("Connection closed unexpectedly")
    if len(line) > MAX_LINE_BYTES:
        raise MessageTooLargeError("Message too large")
    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"Invalid JSON payload: {line[:80]!r}") from exc
    if not isinstance(message, dict):
        raise ProtocolError("Message must be a JSON object")
    return message
