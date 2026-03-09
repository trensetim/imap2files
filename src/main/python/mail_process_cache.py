from dataclasses import dataclass
from pathlib import Path
from asyncio import Lock
import datetime
import base64

from imap_tools import MailMessage

@dataclass
class MailProcessCacheEntry:

    uid: str
    """UID of the mail message"""
    unix_ms: int
    """Unix timestamp of the mail, in milliseconds. Used for timeout in the circular buffer cache"""

    subject: str

    def __init__(self, uid: str, unix_ms: int, subject: str):
        self.uid = uid
        self.unix_ms = unix_ms
        self.subject = subject

    def __eq__(self, value):
        return value.uid == self.uid

    def __hash__(self):
        return hash(self.uid)

    @staticmethod
    def parse(line: str) -> "MailProcessCacheEntry":
        parts = line.strip().split(",")
        if len(parts) != 3:
            raise ValueError("Invalid line format, expected 'uid,unix_ms,b64subject'")

        uid = parts[0]
        unix_ms = int(parts[1])
        subject = base64.b64decode(parts[2]).decode("utf-8")

        return MailProcessCacheEntry(uid, unix_ms, subject)

    @staticmethod
    def of(msg: MailMessage) -> "MailProcessCacheEntry":
        unix_ts = int(msg.date.timestamp() * 1000)
        uid = msg.uid if msg.uid is not None else str(unix_ts)

        return MailProcessCacheEntry(uid, unix_ts, msg.subject)

    def serialize(self) -> str:
        abbreviated_subject = self.subject.replace("\n", " ").replace("\r", " ")[:250]
        base64_subject = base64.b64encode(self.subject.encode("utf-8")).decode("utf-8")
        buffer = ""
        buffer += "# " + abbreviated_subject
        buffer += "\n# " + datetime.datetime.fromtimestamp(self.unix_ms/1000.0).isoformat(sep=" ")
        buffer += f"\n{self.uid},{self.unix_ms},{base64_subject}"
        return buffer


class MailProcessCache:
    """
    The process cache is not a guarantee for exactly-once processing,
    but it is a best-effort attempt to avoid processing the same mail multiple times, for improved performance.

    The cache is not crash-safe and multiple concurrent replica processes of this application are not synced.
    Thus, the runtime configuration MUST still produce idempotent results
    (eg. do not use "seen/unseen" flag status in filenames, since those might change over time).
    """

    _db_file_path: str
    """Where to store the cache database"""
    _max_size: int = 1000
    """Maximum number of entries to keep in the cache. Oldest entries will be removed when the cache exceeds this size"""
    _entries: set[MailProcessCacheEntry] = set()
    _mutex: Lock = Lock() # to prevent concurrent mutations of the cache

    def __init__(self, db_file_path: str, max_size: int = 1000):
        self._db_file_path = db_file_path
        self._max_size = max_size

        if self._max_size <= 0 or self._max_size > pow(10, 9): # max = 1000 million
            raise ValueError("max_size must be reasonable")

        db_parent = Path(self._db_file_path).parent
        if not db_parent.exists():
            db_parent.mkdir(parents=True, exist_ok=True) # raises, if it fails to create the directory

    def has(self, msg: MailMessage) -> bool:
        return MailProcessCacheEntry.of(msg) in self._entries

    async def add(self, msg: MailMessage) -> bool:
        """Returns whether the message was added to the cache. False if already present"""
        async with self._mutex:
            if self.has(msg):
                return False

            self._entries.add(MailProcessCacheEntry.of(msg))
            self._enforce_size_limit()

        await self.save()
        return True

    async def load(self):
        count = 0
        new_set: set[MailProcessCacheEntry] = set()
        with open(self._db_file_path, "r", encoding="utf-8") as f:
            for line in f:
                count += 1
                if count > self._max_size:
                    break
                if line.strip().startswith("#") or not line.strip():
                    continue # ignore comments and empty lines
                new_set.add(MailProcessCacheEntry.parse(line))
        async with self._mutex:
            self._entries = new_set

    async def try_load(self):
        """Tries to create the database parent directory and to load a possibly-existing database from therein. If there is no database file, leaves the existing runtime cache untouched"""
        path = Path(self._db_file_path)
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True) # raises, if it fails to create the directory
        if path.exists():
            await self.load()
            print(f"Loaded {len(self._entries)} entries into the cache from {self._db_file_path}")

    async def save(self):
        async with self._mutex:
            with open(self._db_file_path, "w", encoding="utf-8") as f:
                for entry in self._entries:
                    f.write(entry.serialize() + "\n")

    def _enforce_size_limit(self):
        while len(self._entries) > self._max_size:
            oldest_entry = min(self._entries, key=lambda e: e.unix_ms)
            self._entries.remove(oldest_entry)
