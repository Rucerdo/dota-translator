"""Localiza Dota 2 e instala/quita el config de Game State Integration."""
import re
import winreg
from pathlib import Path

CFG_NAME = "gamestate_integration_dota_chat_translator.cfg"


def _steam_path() -> Path | None:
    for hive, key in [(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
                      (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam")]:
        try:
            with winreg.OpenKey(hive, key) as k:
                for val in ("SteamPath", "InstallPath"):
                    try:
                        return Path(winreg.QueryValueEx(k, val)[0])
                    except OSError:
                        pass
        except OSError:
            pass
    return None


def normalize(folder: str | Path) -> Path | None:
    """Acepta la carpeta raíz 'dota 2 beta' o '.../game/dota' y devuelve '.../game/dota'."""
    if not folder:
        return None
    p = Path(folder)
    for cand in (p, p / "game" / "dota", p / "dota"):
        if (cand / "cfg").is_dir() and cand.name.lower() == "dota":
            return cand
    return None


def find_dota_dir() -> Path | None:
    steam = _steam_path()
    if not steam:
        return None
    libs = [steam]
    vdf = steam / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        for m in re.finditer(r'"path"\s+"([^"]+)"', vdf.read_text(encoding="utf-8", errors="ignore")):
            libs.append(Path(m.group(1).replace("\\\\", "\\")))
    for lib in libs:
        d = normalize(lib / "steamapps" / "common" / "dota 2 beta")
        if d:
            return d
    return None


def cfg_path(dota_dir: Path) -> Path:
    return dota_dir / "cfg" / "gamestate_integration" / CFG_NAME


def cfg_content(port: int) -> str:
    return f'''"Dota Chat Translator"
{{
    "uri"        "http://127.0.0.1:{port}/"
    "timeout"    "2.0"
    "buffer"     "0.0"
    "throttle"   "0.1"
    "heartbeat"  "30.0"
    "data"
    {{
        "provider"  "1"
        "map"       "1"
        "events"    "1"
    }}
}}
'''


def is_installed(dota_dir: Path | None, port: int) -> bool:
    if not dota_dir:
        return False
    p = cfg_path(dota_dir)
    try:
        return p.read_text(encoding="utf-8") == cfg_content(port)
    except OSError:
        return False


LEGACY_NAMES = ["gamestate_integration_free_translator.cfg"]


def install(dota_dir: Path, port: int) -> Path:
    for old in LEGACY_NAMES:  # versiones previas de desarrollo
        try:
            (dota_dir / "cfg" / "gamestate_integration" / old).unlink()
        except OSError:
            pass
    p = cfg_path(dota_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(cfg_content(port), encoding="utf-8")
    return p


def uninstall(dota_dir: Path) -> bool:
    p = cfg_path(dota_dir)
    if p.exists():
        p.unlink()
        return True
    return False
