# single_instance.py

import ctypes, atexit, sys

ERROR_ALREADY_EXISTS = 183
_kernel32 = ctypes.windll.kernel32

def create_mutex(name: str):
    """
    Пытаемся создать именованный mutex.
    Возвращает (handle, already_running: bool)
    """
    handle = _kernel32.CreateMutexW(None, False, name)
    already_running = _kernel32.GetLastError() == ERROR_ALREADY_EXISTS
    return handle, already_running

def release_mutex(handle):
    if handle:
        _kernel32.ReleaseMutex(handle)
        _kernel32.CloseHandle(handle)