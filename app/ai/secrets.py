"""Claves de API cifradas con DPAPI de Windows: solo tu usuario de Windows puede descifrarlas."""
import base64
import ctypes
import ctypes.wintypes as wt
import logging

log = logging.getLogger(__name__)


class _BLOB(ctypes.Structure):
    _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    crypt32, kernel32 = ctypes.windll.crypt32, ctypes.windll.kernel32
    buf = ctypes.create_string_buffer(data, len(data))
    src, dst = _BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), _BLOB()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    if not fn(ctypes.byref(src), None, None, None, None, 0x1, ctypes.byref(dst)):  # CRYPTPROTECT_UI_FORBIDDEN
        raise OSError("DPAPI falló")
    try:
        return ctypes.string_at(dst.pbData, dst.cbData)
    finally:
        kernel32.LocalFree(dst.pbData)


def encrypt_key(key: str) -> str:
    return base64.b64encode(_dpapi(key.encode("utf-8"), True)).decode("ascii") if key else ""


def decrypt_key(blob: str) -> str:
    if not blob:
        return ""
    try:
        return _dpapi(base64.b64decode(blob), False).decode("utf-8")
    except Exception:
        log.warning("no se pudo descifrar una clave de API (¿otro usuario u otro PC?)")
        return ""
