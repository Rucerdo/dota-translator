"""Actualizaciones automáticas desde GitHub Releases.

Flujo:
  1. check_latest() consulta la API pública de GitHub (sin token, límite 60 peticiones/hora por IP).
  2. download() baja el .exe nuevo junto al actual y verifica su SHA-256 con SHA256SUMS.txt.
  3. install_and_restart() renombra el .exe en uso a *.old.exe (Windows permite renombrar un
     ejecutable abierto, pero no sobrescribirlo), coloca el nuevo en su sitio y lo lanza.
  4. cleanup_old() borra el *.old.exe en el siguiente arranque.
"""
import hashlib
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import requests

from . import EXE_NAME, GITHUB_REPO, __version__

log = logging.getLogger(__name__)

# DCT_UPDATE_API permite probar el actualizador contra un servidor local
API_URL = os.environ.get("DCT_UPDATE_API") or f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"
HEADERS = {"User-Agent": "DotaChatTranslator-updater", "Accept": "application/vnd.github+json"}


@dataclass
class UpdateInfo:
    version: str
    notes: str
    page_url: str
    exe_url: str | None
    sha_url: str | None
    size: int = 0


def parse_version(v: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", v.split("-")[0].split("+")[0])
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def current_exe() -> Path:
    return Path(sys.executable).resolve()


def check_latest(timeout: float = 8) -> UpdateInfo | None:
    """Devuelve la info de la última release si es más nueva que la versión actual; si no, None."""
    r = requests.get(API_URL, headers=HEADERS, timeout=timeout)
    if r.status_code == 404:  # todavía no hay releases
        return None
    r.raise_for_status()
    data = r.json()
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = str(data.get("tag_name") or "")
    if not tag or not is_newer(tag):
        return None
    assets = {a.get("name"): a for a in data.get("assets") or []}
    exe = assets.get(EXE_NAME)
    sha = assets.get("SHA256SUMS.txt")
    return UpdateInfo(
        version=tag.lstrip("vV"),
        notes=(data.get("body") or "").strip(),
        page_url=data.get("html_url") or RELEASES_PAGE,
        exe_url=exe.get("browser_download_url") if exe else None,
        sha_url=sha.get("browser_download_url") if sha else None,
        size=int(exe.get("size") or 0) if exe else 0,
    )


def can_self_update(info: UpdateInfo) -> bool:
    """Solo el .exe compilado puede reemplazarse a sí mismo, y solo si su carpeta es escribible."""
    if not (is_frozen() and info.exe_url):
        return False
    folder = current_exe().parent
    probe = folder / ".dct_write_test"
    try:
        probe.write_text("x")
        probe.unlink()
        return True
    except OSError:
        return False


def _expected_sha(sha_url: str) -> str | None:
    r = requests.get(sha_url, headers=HEADERS, timeout=10)
    r.raise_for_status()
    for line in r.text.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].lstrip("*") == EXE_NAME:
            return parts[0].lower()
    return None


def download(info: UpdateInfo, progress: Callable[[float], None] | None = None) -> Path:
    """Descarga el .exe nuevo junto al actual (*.new.exe) y verifica el SHA-256. Devuelve su ruta."""
    target = current_exe().with_name(current_exe().stem + ".new.exe")
    expected = _expected_sha(info.sha_url) if info.sha_url else None
    h = hashlib.sha256()
    with requests.get(info.exe_url, headers=HEADERS, stream=True, timeout=30) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length") or info.size or 0)
        done = 0
        with open(target, "wb") as f:
            for chunk in r.iter_content(chunk_size=256 * 1024):
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress and total:
                    progress(min(done / total, 1.0))
    digest = h.hexdigest()
    if expected and digest != expected:
        target.unlink(missing_ok=True)
        raise ValueError(f"SHA-256 no coincide (esperado {expected[:12]}…, recibido {digest[:12]}…)")
    if not expected:
        log.warning("la release no incluye SHA256SUMS.txt; se instala sin verificar el checksum")
    log.info("actualización descargada en %s (sha256 %s)", target, digest)
    return target


def install_and_restart(new_exe: Path):
    """Sustituye el .exe en ejecución por el nuevo y lo lanza. Quien llama debe cerrar la app después."""
    exe = current_exe()
    old = exe.with_name(exe.stem + ".old.exe")
    old.unlink(missing_ok=True)
    exe.rename(old)
    try:
        new_exe.rename(exe)
    except OSError:
        old.rename(exe)  # deshacer
        raise
    env = dict(os.environ)
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"  # que el nuevo .exe no reutilice la carpeta temporal de este
    subprocess.Popen([str(exe)], env=env, cwd=str(exe.parent), close_fds=True,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
    log.info("actualización instalada; reiniciando")


def cleanup_old():
    """Borra restos de una actualización anterior (en segundo plano: el proceso viejo puede seguir cerrándose)."""
    if not is_frozen():
        return

    def run():
        import time
        leftovers = [current_exe().with_name(current_exe().stem + s) for s in (".old.exe", ".new.exe")]
        for _ in range(30):
            pending = []
            for p in leftovers:
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pending.append(p)
            if not pending:
                return
            leftovers = pending
            time.sleep(1)

    import threading
    threading.Thread(target=run, daemon=True).start()
