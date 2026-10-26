"""Current-user Windows DPAPI envelope for local integration key material."""
import os
from contextlib import contextmanager

PREFIX=b'kingdom.dpapi.v1\0'


@contextmanager
def key_file_lock(path):
    """Serialize first creation/migration before another process reads the file."""
    with os.fdopen(os.open(path,os.O_CREAT|os.O_RDWR,0o600),'r+b') as lock:
        if os.fstat(lock.fileno()).st_size==0:lock.write(b'0');lock.flush()
        lock.seek(0)
        if os.name=='nt':
            import msvcrt
            msvcrt.locking(lock.fileno(),msvcrt.LK_LOCK,1)
        else:
            import fcntl
            fcntl.flock(lock,fcntl.LOCK_EX)
        try:yield
        finally:
            lock.seek(0)
            if os.name=='nt':msvcrt.locking(lock.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(lock,fcntl.LOCK_UN)


def _dpapi(value, decrypt=False):
    import ctypes
    from ctypes import wintypes
    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buffer=ctypes.create_string_buffer(value)
    source=Blob(len(value),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte)))
    target=Blob()
    api=ctypes.WinDLL('crypt32',use_last_error=True)
    fn=api.CryptUnprotectData if decrypt else api.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    fn.restype=wintypes.BOOL
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(target)):
        raise OSError('Current-user key protection failed',ctypes.get_last_error())
    release=ctypes.WinDLL('kernel32',use_last_error=True).LocalFree
    release.argtypes=[ctypes.c_void_p];release.restype=ctypes.c_void_p
    try:return ctypes.string_at(target.data,target.size)
    finally:release(target.data)


def protect_user_key(value):
    if not isinstance(value,bytes) or not 1<=len(value)<=65536:raise ValueError('Bounded key material required')
    return PREFIX+_dpapi(value) if os.name=='nt' else value


def unprotect_user_key(value):
    if value.startswith(PREFIX):
        if os.name!='nt':raise ValueError('This key belongs to its original Windows user')
        return _dpapi(value[len(PREFIX):],decrypt=True)
    return value  # Legacy/local POSIX key; callers retain filesystem protection.
