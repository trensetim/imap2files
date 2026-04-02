from collections.abc import Callable
from dataclasses import dataclass
import fcntl
import os
from typing import IO

class IdCounter:
    """
    A counter to generate unique IDs, synchronized with a file.
    The counter will flock the file while accessing it exclusively.
    It will block indefinitely until it can acquire the lock.
    """

    _storage_file: str | None
    """File to sync the counter value to. If None, the counter will only be stored in memory and not persisted across runs."""
    _volatile_value: int
    """used if persistance is disabled (storage_file is None)"""

    def __init__(self, storage_file: str | None, initial_value: int = 0):
        self._storage_file = storage_file
        self._volatile_value = initial_value

        # make sure there is a valid file present. otherwise try to create it.
        if self._storage_file is not None:
            try:
                with open(self._storage_file, "r", encoding="utf-8") as f:
                    int(f.read().strip())
            except (FileNotFoundError, ValueError):
                self.reset(initial_value)

    def is_persistent(self) -> bool:
        """Returns whether this counter is persistent (ie. backed by a file) or only stored in memory."""
        return self._storage_file is not None

    def __with_locked_file(self, mode: str, action: Callable[[IO], any]) -> any:
        with open(self._storage_file, mode, encoding="utf-8") as f:
            fd = f.fileno()
            try:
                # Use flock on the file descriptor; caller can rely on exclusive access
                fcntl.flock(fd, fcntl.LOCK_EX)
                return action(f)
            finally:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                except OSError:
                    pass

    def reset(self, next_value: int = 0) -> None:
        """Sets the counter to a specific value (ie. the given one will be returned next). Default is 0."""
        def action(f: IO) -> None:
            f.write(str(next_value))
            f.truncate()
            f.flush()
            os.fsync(f.fileno())

        self.__with_locked_file("w", action)
        self._volatile_value = next_value

    def current(self) -> int:
        """Returns the current value of the counter without incrementing it."""

        if self._storage_file is None:
            return self._volatile_value

        def action(f: IO) -> int:
            file_content = f.read().strip()
            return int(file_content) if file_content else 0

        return self.__with_locked_file("r", action)

    def next(self) -> int:
        """Returns the next value of the counter and increments it by one. Throws an IO error if the backing file cannot be updated."""
        self._volatile_value += 1
        if self._storage_file is None:
            return self._volatile_value - 1

        def action(f: IO) -> int:
            file_content = f.read().strip()
            counter = int(file_content) if file_content else 0
            f.seek(0)
            f.write(str(counter + 1))
            f.truncate()
            f.flush()
            os.fsync(f.fileno())
            return counter
        return self.__with_locked_file("r+", action)

@dataclass
class FileIds:
    global_id: int
    file_specific_id: int

    def __init__(self, global_id: int, file_specific_id: int):
        self.global_id = global_id
        self.file_specific_id = file_specific_id

@dataclass
class IdDatabase:
    """Stores multiple incrementable ID counter for different purposes."""

    global_counter: IdCounter
    """Incremented every time any file is generated"""

    log_counter: IdCounter
    """Incremented every time a mail is logged to the console"""

    headers_counter: IdCounter
    """Incremented every time a headers file is generated"""

    body_text_counter: IdCounter
    """Incremented every time a body text file is generated"""

    body_html_counter: IdCounter
    """Incremented every time a body html file is generated"""

    custom_counter: IdCounter
    """Incremented every time a custom file is generated"""

    attachment_counter: IdCounter
    """Incremented every time an attachment file is generated (so increments faster/slower when receiving mails with multiple/none attachments)"""

    def __init__(self, storage_dir: str, persist_mode: str = "all"):
        persist_mode = persist_mode.lower()

        self.global_counter = IdCounter(os.path.join(storage_dir, "global.counter") if persist_mode == "all" or "global" in persist_mode else None)

        self.log_counter = IdCounter(os.path.join(storage_dir, "log.counter") if persist_mode == "all" or "log" in persist_mode else None)
        self.headers_counter = IdCounter(os.path.join(storage_dir, "headers.counter") if persist_mode == "all" or "headers" in persist_mode else None)
        self.body_text_counter = IdCounter(os.path.join(storage_dir, "body_text.counter") if persist_mode == "all" or "body_text" in persist_mode else None)
        self.body_html_counter = IdCounter(os.path.join(storage_dir, "body_html.counter") if persist_mode == "all" or "body_html" in persist_mode else None)
        self.custom_counter = IdCounter(os.path.join(storage_dir, "custom.counter") if persist_mode == "all" or "custom" in persist_mode else None)
        self.attachment_counter = IdCounter(os.path.join(storage_dir, "attachment.counter") if persist_mode == "all" or "attachment" in persist_mode else None)

        if any(counter.is_persistent() for counter in self._all_counters()):
            os.makedirs(storage_dir, exist_ok=True)

    def _all_counters(self) -> list[IdCounter]:
        return [self.global_counter, self.log_counter, self.headers_counter, self.body_text_counter, self.body_html_counter, self.custom_counter, self.attachment_counter]

    def next_log(self) -> FileIds:
        return FileIds(global_id=self.global_counter.current(), file_specific_id=self.log_counter.next())
    def next_headers(self) -> FileIds:
        return FileIds(global_id=self.global_counter.next(), file_specific_id=self.headers_counter.next())
    def next_body_text(self) -> FileIds:
        return FileIds(global_id=self.global_counter.next(), file_specific_id=self.body_text_counter.next())
    def next_body_html(self) -> FileIds:
        return FileIds(global_id=self.global_counter.next(), file_specific_id=self.body_html_counter.next())
    def next_custom(self) -> FileIds:
        return FileIds(global_id=self.global_counter.next(), file_specific_id=self.custom_counter.next())
    def next_attachment(self) -> FileIds:
        return FileIds(global_id=self.global_counter.next(), file_specific_id=self.attachment_counter.next())
