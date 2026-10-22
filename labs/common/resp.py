"""Minimal RESP client for standalone labs; no third-party dependency."""

from __future__ import annotations

import socket


class RedisError(RuntimeError):
    pass


class Resp:
    def __init__(self, host: str = "127.0.0.1", port: int = 6379, timeout: float = 5.0):
        self.socket = socket.create_connection((host, port), timeout=timeout)
        self.reader = self.socket.makefile("rb")

    def cmd(self, *args: object) -> object:
        payload = bytearray(f"*{len(args)}\r\n".encode())
        for arg in args:
            data = str(arg).encode("utf-8")
            payload.extend(f"${len(data)}\r\n".encode())
            payload.extend(data)
            payload.extend(b"\r\n")
        self.socket.sendall(payload)
        return self._reply()

    def _reply(self) -> object:
        prefix = self.reader.read(1)
        if prefix == b"+":
            return self._line().decode("utf-8")
        if prefix == b"-":
            raise RedisError(self._line().decode("utf-8"))
        if prefix == b":":
            return int(self._line())
        if prefix == b"$":
            length = int(self._line())
            if length == -1:
                return None
            data = self.reader.read(length)
            self.reader.read(2)
            return data.decode("utf-8")
        if prefix == b"*":
            length = int(self._line())
            if length == -1:
                return None
            return [self._reply() for _ in range(length)]
        raise RedisError(f"unexpected RESP prefix: {prefix!r}")

    def _line(self) -> bytes:
        return self.reader.readline()[:-2]

    def close(self) -> None:
        self.reader.close()
        self.socket.close()

    def __enter__(self) -> "Resp":
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
