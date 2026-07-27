from pathlib import Path
import time


class LoopLock:
    def __init__(self, lock_file: str | Path = ".loopforge/loop.lock"):
        self.lock_file = Path(lock_file)

    def acquire(self, session_id: str) -> bool:
        if self.lock_file.exists():
            return False
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.write_text(f"session_id={session_id}\ntime={time.time()}\n", encoding="utf-8")
        return True

    def release(self) -> bool:
        if self.lock_file.exists():
            self.lock_file.unlink()
            return True
        return False
