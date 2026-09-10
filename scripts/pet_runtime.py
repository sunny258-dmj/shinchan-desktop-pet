"""Shared instance lock. An OS lock is released even if Qt crashes."""
import os
from pathlib import Path


def runtime_root():
    return Path(os.environ.get('PET_RUNTIME_DIR') or
                Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'CrayonShinchanPet')


class InstanceLock:
    def __init__(self, root=None):
        self.path = (root or runtime_root()) / 'host.lock'
        self.file = None

    def acquire(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        f = open(self.path, 'a+b')
        try:
            if self.path.stat().st_size == 0:
                f.write(b'0')
                f.flush()
            f.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            f.close()
            return False
        self.file = f
        return True

    def release(self):
        if self.file:
            self.file.close()
            self.file = None


def is_running(root=None):
    lock = InstanceLock(root)
    if not lock.path.exists():
        return False
    if not lock.acquire():
        return True
    lock.release()
    return False
