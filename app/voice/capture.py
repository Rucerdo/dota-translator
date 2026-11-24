"""Audio de UN proceso (dota2.exe) con la API 'process loopback' de Windows.

ActivateAudioInterfaceAsync("VAD\\Process_Loopback", AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK):
captura solo lo que reproduce ese proceso (y sus hijos). No necesita drivers ni tarjetas virtuales.
Probado en Windows 10 22H2 (build 19045) y Windows 11.
"""
import ctypes
import logging
import threading
import time
from ctypes import POINTER, Structure, byref, c_int, c_uint16, c_uint32, c_uint64, c_ulong, c_ushort, c_void_p
from ctypes import wintypes
from typing import Callable

log = logging.getLogger(__name__)

SAMPLE_RATE = 16000  # lo que espera Whisper; Windows convierte el formato (AUTOCONVERTPCM)

# ---------------- búsqueda del proceso ----------------
TH32CS_SNAPPROCESS = 0x2


class PROCESSENTRY32W(Structure):
    _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD), ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", c_void_p), ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wintypes.DWORD), ("szExeFile", ctypes.c_wchar * 260)]


_k32 = ctypes.WinDLL("kernel32", use_last_error=True)
_k32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE


def find_pid(exe_name: str) -> int | None:
    snap = _k32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snap or snap == wintypes.HANDLE(-1).value:
        return None
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        ok = _k32.Process32FirstW(snap, byref(entry))
        while ok:
            if entry.szExeFile.lower() == exe_name.lower():
                return int(entry.th32ProcessID)
            ok = _k32.Process32NextW(snap, byref(entry))
    finally:
        _k32.CloseHandle(snap)
    return None


def _pid_alive(pid: int) -> bool:
    h = _k32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        code = wintypes.DWORD()
        return bool(_k32.GetExitCodeProcess(h, byref(code))) and code.value == 259  # STILL_ACTIVE
    finally:
        _k32.CloseHandle(h)


# ---------------- WASAPI ----------------
AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK = 1
PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE = 0
VT_BLOB = 65
AUDCLNT_SHAREMODE_SHARED = 0
AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000
AUDCLNT_STREAMFLAGS_EVENTCALLBACK = 0x00040000
AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM = 0x80000000
AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY = 0x08000000
AUDCLNT_BUFFERFLAGS_SILENT = 0x2


class _LOOPBACK_PARAMS(Structure):
    _fields_ = [("TargetProcessId", wintypes.DWORD), ("ProcessLoopbackMode", c_int)]


class _ACTIVATION_PARAMS(Structure):
    _fields_ = [("ActivationType", c_int), ("ProcessLoopbackParams", _LOOPBACK_PARAMS)]


class _BLOB(Structure):
    _fields_ = [("cbSize", c_ulong), ("pBlobData", c_void_p)]


class _PROPVARIANT(Structure):
    _fields_ = [("vt", c_ushort), ("r1", c_ushort), ("r2", c_ushort), ("r3", c_ushort), ("blob", _BLOB)]


class _WAVEFORMATEX(Structure):
    _fields_ = [("wFormatTag", c_uint16), ("nChannels", c_uint16), ("nSamplesPerSec", c_uint32),
                ("nAvgBytesPerSec", c_uint32), ("nBlockAlign", c_uint16), ("wBitsPerSample", c_uint16),
                ("cbSize", c_uint16)]


def _com():
    """Interfaces COM (se definen al primer uso para no importar comtypes si la voz está apagada)."""
    global _COM
    if "_COM" in globals():
        return _COM
    import comtypes
    from comtypes import COMMETHOD, COMObject, GUID, HRESULT, IUnknown

    class IAudioCaptureClient(IUnknown):
        _iid_ = GUID("{C8ADBD64-E71E-48a0-A4DE-185C395CD317}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetBuffer", (["out"], POINTER(POINTER(ctypes.c_byte)), "ppData"),
                      (["out"], POINTER(c_uint32), "pNumFramesToRead"),
                      (["out"], POINTER(wintypes.DWORD), "pdwFlags"),
                      (["out"], POINTER(c_uint64), "pu64DevicePosition"),
                      (["out"], POINTER(c_uint64), "pu64QPCPosition")),
            COMMETHOD([], HRESULT, "ReleaseBuffer", (["in"], c_uint32, "NumFramesRead")),
            COMMETHOD([], HRESULT, "GetNextPacketSize", (["out"], POINTER(c_uint32), "pNumFramesInNextPacket")),
        ]

    class IAudioClient(IUnknown):
        _iid_ = GUID("{1CB9AD4C-DBFA-4c32-B178-C2F568A703B2}")
        _methods_ = [
            COMMETHOD([], HRESULT, "Initialize", (["in"], c_int, "ShareMode"),
                      (["in"], wintypes.DWORD, "StreamFlags"), (["in"], ctypes.c_longlong, "hnsBufferDuration"),
                      (["in"], ctypes.c_longlong, "hnsPeriodicity"), (["in"], POINTER(_WAVEFORMATEX), "pFormat"),
                      (["in"], POINTER(GUID), "AudioSessionGuid")),
            COMMETHOD([], HRESULT, "GetBufferSize", (["out"], POINTER(c_uint32), "pNumBufferFrames")),
            COMMETHOD([], HRESULT, "GetStreamLatency", (["out"], POINTER(ctypes.c_longlong), "phnsLatency")),
            COMMETHOD([], HRESULT, "GetCurrentPadding", (["out"], POINTER(c_uint32), "pNumPaddingFrames")),
            COMMETHOD([], HRESULT, "IsFormatSupported", (["in"], c_int, "ShareMode"),
                      (["in"], POINTER(_WAVEFORMATEX), "pFormat"),
                      (["out"], POINTER(POINTER(_WAVEFORMATEX)), "ppClosest")),
            COMMETHOD([], HRESULT, "GetMixFormat", (["out"], POINTER(POINTER(_WAVEFORMATEX)), "ppDeviceFormat")),
            COMMETHOD([], HRESULT, "GetDevicePeriod", (["out"], POINTER(ctypes.c_longlong), "phnsDefault"),
                      (["out"], POINTER(ctypes.c_longlong), "phnsMinimum")),
            COMMETHOD([], HRESULT, "Start"),
            COMMETHOD([], HRESULT, "Stop"),
            COMMETHOD([], HRESULT, "Reset"),
            COMMETHOD([], HRESULT, "SetEventHandle", (["in"], wintypes.HANDLE, "eventHandle")),
            COMMETHOD([], HRESULT, "GetService", (["in"], POINTER(GUID), "riid"), (["out"], POINTER(c_void_p), "ppv")),
        ]

    class IActivateAudioInterfaceAsyncOperation(IUnknown):
        _iid_ = GUID("{72A22D78-CDE4-431D-B8CC-843A71199B6D}")
        _methods_ = [
            COMMETHOD([], HRESULT, "GetActivateResult", (["out"], POINTER(HRESULT), "activateResult"),
                      (["out"], POINTER(POINTER(IUnknown)), "activatedInterface")),
        ]

    class IActivateAudioInterfaceCompletionHandler(IUnknown):
        _iid_ = GUID("{41D949AB-9862-444A-80F6-C261334DA5EB}")
        _methods_ = [
            COMMETHOD([], HRESULT, "ActivateCompleted",
                      (["in"], POINTER(IActivateAudioInterfaceAsyncOperation), "activateOperation")),
        ]

    class IAgileObject(IUnknown):
        _iid_ = GUID("{94ea2b94-e9cc-49e0-c0ff-ee64ca8f5b90}")
        _methods_ = []

    class Handler(COMObject):
        _com_interfaces_ = [IActivateAudioInterfaceCompletionHandler, IAgileObject]

        def __init__(self):
            super().__init__()
            self.done = threading.Event()

        def ActivateCompleted(self, op):
            self.done.set()
            return 0

    fn = ctypes.WinDLL("Mmdevapi.dll").ActivateAudioInterfaceAsync
    fn.restype = HRESULT
    fn.argtypes = [wintypes.LPCWSTR, POINTER(GUID), POINTER(_PROPVARIANT), c_void_p,
                   POINTER(POINTER(IActivateAudioInterfaceAsyncOperation))]
    _COM = dict(comtypes=comtypes, IAudioClient=IAudioClient, IAudioCaptureClient=IAudioCaptureClient,
                IActivateAudioInterfaceAsyncOperation=IActivateAudioInterfaceAsyncOperation,
                IActivateAudioInterfaceCompletionHandler=IActivateAudioInterfaceCompletionHandler,
                Handler=Handler, activate=fn)
    return _COM


class ProcessAudioCapture:
    """Hilo que captura el audio de 'exe_name' en PCM 16 kHz mono 16-bit y llama a
    on_audio(pcm_bytes, t_end_monotonic). Si el proceso no existe, espera; si se cierra, se reengancha."""

    def __init__(self, exe_name: str, on_audio: Callable[[bytes, float], None],
                 on_state: Callable[[str], None] | None = None):
        self.exe_name, self.on_audio, self.on_state = exe_name, on_audio, on_state or (lambda s: None)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.state = "stopped"

    def _set_state(self, s: str):
        if s != self.state:
            self.state = s
            self.on_state(s)

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="voice-capture", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(3)
        self._set_state("stopped")

    def _run(self):
        import sys
        # comtypes inicializa COM al importarse en el hilo que lo importa; aquí lo queremos en modo MTA
        sys.coinit_flags = 0  # COINIT_MULTITHREADED
        c = _com()
        try:
            c["comtypes"].CoInitializeEx(c["comtypes"].COINIT_MULTITHREADED)
        except OSError:
            pass  # ya inicializado en este hilo
        while not self._stop.is_set():
            # también acepta un PID numérico (pruebas)
            pid = int(self.exe_name) if str(self.exe_name).isdigit() else find_pid(self.exe_name)
            if pid and not _pid_alive(pid):
                pid = None
            if not pid:
                self._set_state("waiting")  # Dota no está abierto
                self._stop.wait(3)
                continue
            try:
                self._capture(pid)
            except Exception:
                log.exception("error capturando el audio de %s (pid %s)", self.exe_name, pid)
                self._set_state("error")
                self._stop.wait(5)

    def _capture(self, pid: int):
        c = _com()
        params = _ACTIVATION_PARAMS(AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK,
                                    _LOOPBACK_PARAMS(pid, PROCESS_LOOPBACK_MODE_INCLUDE_TARGET_PROCESS_TREE))
        pv = _PROPVARIANT()
        pv.vt = VT_BLOB
        pv.blob.cbSize = ctypes.sizeof(params)
        pv.blob.pBlobData = ctypes.cast(byref(params), c_void_p)
        handler = c["Handler"]()
        hptr = handler.QueryInterface(c["IActivateAudioInterfaceCompletionHandler"])
        op = POINTER(c["IActivateAudioInterfaceAsyncOperation"])()
        iid = c["IAudioClient"]._iid_
        c["activate"]("VAD\\Process_Loopback", byref(iid), byref(pv), ctypes.cast(hptr, c_void_p), byref(op))
        if not handler.done.wait(5):
            raise TimeoutError("ActivateAudioInterfaceAsync no respondió")
        hr, unk = op.GetActivateResult()
        if hr != 0:
            raise OSError(f"activación de captura falló: HRESULT 0x{hr & 0xFFFFFFFF:08X}")
        client = unk.QueryInterface(c["IAudioClient"])
        fmt = _WAVEFORMATEX(1, 1, SAMPLE_RATE, SAMPLE_RATE * 2, 2, 16, 0)
        flags = (AUDCLNT_STREAMFLAGS_LOOPBACK | AUDCLNT_STREAMFLAGS_EVENTCALLBACK
                 | AUDCLNT_STREAMFLAGS_AUTOCONVERTPCM | AUDCLNT_STREAMFLAGS_SRC_DEFAULT_QUALITY)
        client.Initialize(AUDCLNT_SHAREMODE_SHARED, flags, 200_000, 0, byref(fmt), None)
        event = _k32.CreateEventW(None, False, False, None)
        client.SetEventHandle(event)
        cap = ctypes.cast(client.GetService(byref(c["IAudioCaptureClient"]._iid_)), POINTER(c["IAudioCaptureClient"]))
        client.Start()
        self._set_state("capturing")
        log.info("capturando el audio de %s (pid %s)", self.exe_name, pid)
        last_check = time.monotonic()
        try:
            while not self._stop.is_set():
                _k32.WaitForSingleObject(event, 200)
                while True:
                    n = cap.GetNextPacketSize()
                    if not n:
                        break
                    data, frames, fl, _p, _q = cap.GetBuffer()
                    chunk = bytes(frames * 2) if fl & AUDCLNT_BUFFERFLAGS_SILENT else ctypes.string_at(data, frames * 2)
                    cap.ReleaseBuffer(frames)
                    self.on_audio(chunk, time.monotonic())
                if time.monotonic() - last_check > 2:  # ¿se cerró Dota?
                    last_check = time.monotonic()
                    if not _pid_alive(pid):
                        log.info("%s se cerró; esperando a que vuelva", self.exe_name)
                        return
        finally:
            try:
                client.Stop()
            except Exception:
                pass
            _k32.CloseHandle(event)
