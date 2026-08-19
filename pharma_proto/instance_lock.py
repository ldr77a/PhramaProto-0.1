"""Windows process lock and loopback instance state."""

from __future__ import annotations

import json
import msvcrt
import os
from dataclasses import dataclass
from pathlib import Path


class InstanceAlreadyRunning(RuntimeError):
    pass


@dataclass
class InstanceLock:
    path: Path
    _file: object
    _released: bool = False

    @property
    def state_path(self) -> Path:
        return self.path.with_suffix(".json")

    @classmethod
    def acquire(cls, path: str | Path) -> "InstanceLock":
        lock_path = Path(path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        stream = lock_path.open("a+b")
        try:
            stream.seek(0, os.SEEK_END)
            if stream.tell() == 0:
                stream.write(b"0")
                stream.flush()
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as error:
            stream.close()
            raise InstanceAlreadyRunning from error
        return cls(path=lock_path, _file=stream)

    def write_state(self, *, pid: int, port: int) -> None:
        if self._released:
            raise RuntimeError("instance lock has been released")
        state = {"pid": int(pid), "port": int(port)}
        temporary = self.state_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.state_path)

    @staticmethod
    def read_state(path: str | Path) -> dict[str, int] | None:
        state_path = Path(path).with_suffix(".json")
        try:
            value = json.loads(state_path.read_text(encoding="utf-8"))
            pid = int(value["pid"])
            port = int(value["port"])
            if pid <= 0 or not 1 <= port <= 65535:
                return None
            return {"pid": pid, "port": port}
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        try:
            self._file.seek(0)  # type: ignore[attr-defined]
            msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)  # type: ignore[attr-defined]
        finally:
            self._file.close()  # type: ignore[attr-defined]
            try:
                self.state_path.unlink()
            except FileNotFoundError:
                pass


__all__ = ["InstanceAlreadyRunning", "InstanceLock"]
