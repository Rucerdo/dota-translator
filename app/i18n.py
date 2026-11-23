"""Textos de la interfaz (es / en) y lista de idiomas de traducción."""

# Idiomas de traducción (código de Google Translate, nombre nativo)
LANGUAGES = [
    ("es", "Español"), ("en", "English"), ("ru", "Русский"), ("zh-CN", "中文 (简体)"), ("zh-TW", "中文 (繁體)"),
    ("pt", "Português"), ("uk", "Українська"), ("de", "Deutsch"), ("fr", "Français"), ("it", "Italiano"),
    ("pl", "Polski"), ("tr", "Türkçe"), ("ko", "한국어"), ("ja", "日本語"), ("th", "ไทย"), ("vi", "Tiếng Việt"),
    ("id", "Bahasa Indonesia"), ("tl", "Filipino"), ("ms", "Bahasa Melayu"), ("ar", "العربية"), ("fa", "فارسی"),
    ("he", "עברית"), ("el", "Ελληνικά"), ("ro", "Română"), ("cs", "Čeština"), ("hu", "Magyar"), ("sv", "Svenska"),
    ("fi", "Suomi"), ("bg", "Български"), ("sr", "Српски"), ("kk", "Қазақ"), ("hi", "हिन्दी"),
]
LANG_NAMES = dict(LANGUAGES)


def lang_label(code: str) -> str:
    return f"{LANG_NAMES.get(code, code)} ({code})"


def lang_from_label(label: str) -> str:
    return label.rsplit("(", 1)[-1].rstrip(")") if "(" in label else label


UI_LANGS = [("es", "Español"), ("en", "English")]

STRINGS = {
    "es": {
        "nav_home": "Inicio", "nav_live": "Chat en vivo", "nav_history": "Historial", "nav_settings": "Ajustes",
        "status_waiting": "Esperando a Dota 2", "status_connected": "Conectado a Dota 2",
        "status_no_gsi": "Integración no instalada",
        # inicio
        "home_title": "Inicio",
        "card_dota": "Dota 2", "card_connection": "Conexión", "card_session": "Esta sesión",
        "dota_not_found": "No encontrado. Indica la carpeta en Ajustes.",
        "gsi_installed": "Integración instalada ✓", "gsi_not_installed": "Integración no instalada",
        "install": "Instalar integración", "uninstall": "Quitar integración",
        "conn_waiting": "Esperando datos…\nAbre Dota 2 (reinícialo si acabas de instalar la integración).",
        "conn_ok": "Recibiendo datos de Dota 2", "match": "Partida",
        "session_in": "Mensajes traducidos", "session_out": "Mensajes enviados",
        "quick_title": "Traducción",
        "translate_to": "Traducir el chat a", "send_in": "Enviar mis mensajes (Ctrl+Enter) en",
        "auto_team": "Automático (idioma del equipo)",
        "sw_overlay": "Mostrar overlay en el juego", "sw_outgoing": "Traducir mis mensajes con Ctrl+Enter",
        "sw_original": "Mostrar el texto original",
        "tips_title": "Antes de jugar",
        "tips": "• Pon Dota 2 en «Ventana sin bordes» (Ajustes → Vídeo). En pantalla completa el overlay no se ve.\n"
                "• Tras instalar la integración, reinicia Dota 2 una vez.\n"
                "• En el chat de Dota: Enter envía normal, Ctrl+Enter envía traducido.\n"
                "• Alt+D muestra u oculta el overlay.",
        # chat en vivo
        "live_title": "Chat en vivo", "clear": "Limpiar",
        "live_empty": "Aquí aparecerán los mensajes del chat de Dota 2 y sus traducciones.\n",
        "test_placeholder": "Escribe algo para probar la traducción…", "test_btn": "Probar",
        "you": "Tú", "test": "Prueba", "ch_all": "Todos", "ch_team": "Aliados",
        # colores
        "blue": "Azul", "teal": "Turquesa", "purple": "Morado", "yellow": "Amarillo", "orange": "Naranja",
        "pink": "Rosa", "olive": "Oliva", "light_blue": "Celeste", "green": "Verde", "brown": "Marrón",
        # historial
        "history_title": "Historial", "search": "Buscar…", "all_matches": "Todas las partidas",
        "practice": "Práctica / bots", "refresh": "Actualizar", "export": "Exportar CSV",
        "delete_all": "Borrar todo", "confirm_delete": "¿Borrar todo el historial? No se puede deshacer.",
        "exported": "Exportado: {path}", "col_time": "Fecha", "col_match": "Partida", "col_dir": "Tipo",
        "col_channel": "Canal", "col_player": "Jugador", "col_lang": "Idioma", "col_original": "Original",
        "col_translated": "Traducción", "dir_in": "Recibido", "dir_out": "Enviado", "dir_test": "Prueba",
        "history_off": "El historial está desactivado en Ajustes.",
        # ajustes
        "settings_title": "Ajustes",
        "sec_general": "General", "ui_lang": "Idioma de la aplicación", "restart_note": "(requiere reiniciar la app)",
        "sw_history": "Guardar historial de conversaciones",
        "open_data": "Abrir carpeta de datos",
        "sec_translation": "Traducción", "fallback_lang": "Si es automático y aún no hay datos, usar",
        "sw_skip_same": "No mostrar mensajes que ya están en mi idioma",
        "ignore_list": "Mensajes que no se traducen (separados por comas)",
        "sec_overlay": "Overlay", "ov_x": "Posición horizontal", "ov_y": "Posición vertical (borde inferior)",
        "ov_width": "Ancho", "ov_font": "Tamaño de letra", "ov_seconds": "Segundos en pantalla",
        "ov_lines": "Líneas máximas", "preview": "Vista previa",
        "sec_hotkeys": "Atajos de teclado", "hk_overlay": "Mostrar/ocultar overlay",
        "hk_send": "Traducir y enviar en el chat de Dota", "apply": "Aplicar",
        "sec_dota": "Dota 2", "dota_folder": "Carpeta de Dota 2", "browse": "Examinar…", "detect": "Detectar",
        "gsi_port": "Puerto local", "invalid_folder": "Esa carpeta no parece de Dota 2 (debe contener game/dota/cfg).",
        "installed_ok": "Integración instalada. Reinicia Dota 2 para activarla.",
        "uninstalled_ok": "Integración quitada.",
        "saved": "Guardado",
        # errores
        "err_port": "No se pudo abrir el puerto {port}. ¿Ya hay otra copia de la app abierta?",
        # retratos
        "sw_hero_icons": "Mostrar el retrato del héroe que escribe",
        "test_capture": "Calibrar retratos",
        "capture_countdown": "Cambia a Dota 2… capturando en {n}",
        "capture_title": "Calibrar retratos de héroe",
        "capture_help": "Entra en una partida (sirven bots), pulsa «Capturar» y cambia a Dota. Ajusta los "
                        "deslizadores hasta que cada recuadro encaje con un retrato de la barra superior; abajo "
                        "verás cómo quedan recortados. Luego pulsa «Guardar».",
        "capture_none": "No se encontró la ventana de Dota 2. Ábrelo (en ventana sin bordes) y vuelve a probar.",
        "capture_black": "La captura salió negra. Pon Dota en «Ventana sin bordes» y vuelve a capturar.",
        "calib_capture": "Capturar", "calib_reset": "Restablecer", "calib_save": "Guardar",
        "calib_saved": "Calibración guardada.", "calib_waiting": "Aún no hay captura.",
        "cal_radiant_first_center": "Posición Radiant (jugador 0)", "cal_dire_first_center": "Posición Dire (jugador 5)",
        "cal_pitch": "Separación entre retratos", "cal_half_width": "Ancho del retrato",
        "cal_top": "Borde superior", "cal_bottom": "Borde inferior",
        # actualizaciones
        "sec_updates": "Actualizaciones", "sw_check_updates": "Buscar actualizaciones al iniciar",
        "check_now": "Buscar ahora", "current_version": "Versión instalada: {v}",
        "up_to_date": "Ya tienes la última versión ({v}).", "update_check_failed": "No se pudo comprobar: {err}",
        "update_title": "Nueva versión disponible",
        "update_text": "Hay una versión nueva de Dota Chat Translator: {new} (tienes la {cur}).",
        "update_now": "Actualizar ahora", "update_later": "Más tarde", "update_skip": "Omitir esta versión",
        "update_open_page": "Abrir página de descarga", "update_notes": "Novedades",
        "update_downloading": "Descargando… {pct}%", "update_verifying": "Verificando…",
        "update_restarting": "Instalando y reiniciando…",
        "update_failed": "La actualización falló: {err}\n\nPuedes descargarla a mano desde GitHub.",
        "update_manual": "Esta copia no puede actualizarse sola (se ejecuta desde el código o la carpeta no "
                         "permite escribir). Se abrirá la página de descarga.",
        "preview_1": "иди мид, я на харде", "preview_2": "我们推塔吧",
    },
    "en": {
        "nav_home": "Home", "nav_live": "Live chat", "nav_history": "History", "nav_settings": "Settings",
        "status_waiting": "Waiting for Dota 2", "status_connected": "Connected to Dota 2",
        "status_no_gsi": "Integration not installed",
        "home_title": "Home",
        "card_dota": "Dota 2", "card_connection": "Connection", "card_session": "This session",
        "dota_not_found": "Not found. Set the folder in Settings.",
        "gsi_installed": "Integration installed ✓", "gsi_not_installed": "Integration not installed",
        "install": "Install integration", "uninstall": "Remove integration",
        "conn_waiting": "Waiting for data…\nOpen Dota 2 (restart it if you just installed the integration).",
        "conn_ok": "Receiving data from Dota 2", "match": "Match",
        "session_in": "Messages translated", "session_out": "Messages sent",
        "quick_title": "Translation",
        "translate_to": "Translate chat into", "send_in": "Send my messages (Ctrl+Enter) in",
        "auto_team": "Automatic (team's language)",
        "sw_overlay": "Show in-game overlay", "sw_outgoing": "Translate my messages with Ctrl+Enter",
        "sw_original": "Show original text",
        "tips_title": "Before playing",
        "tips": "• Set Dota 2 to “Borderless Window” (Settings → Video). The overlay is hidden in exclusive fullscreen.\n"
                "• After installing the integration, restart Dota 2 once.\n"
                "• In Dota chat: Enter sends as usual, Ctrl+Enter sends translated.\n"
                "• Alt+D shows or hides the overlay.",
        "live_title": "Live chat", "clear": "Clear",
        "live_empty": "Dota 2 chat messages and their translations will appear here.\n",
        "test_placeholder": "Type something to test the translation…", "test_btn": "Test",
        "you": "You", "test": "Test", "ch_all": "All", "ch_team": "Allies",
        "blue": "Blue", "teal": "Teal", "purple": "Purple", "yellow": "Yellow", "orange": "Orange",
        "pink": "Pink", "olive": "Olive", "light_blue": "Light blue", "green": "Green", "brown": "Brown",
        "history_title": "History", "search": "Search…", "all_matches": "All matches",
        "practice": "Practice / bots", "refresh": "Refresh", "export": "Export CSV",
        "delete_all": "Delete all", "confirm_delete": "Delete the whole history? This cannot be undone.",
        "exported": "Exported: {path}", "col_time": "Date", "col_match": "Match", "col_dir": "Type",
        "col_channel": "Channel", "col_player": "Player", "col_lang": "Language", "col_original": "Original",
        "col_translated": "Translation", "dir_in": "Received", "dir_out": "Sent", "dir_test": "Test",
        "history_off": "History is turned off in Settings.",
        "settings_title": "Settings",
        "sec_general": "General", "ui_lang": "App language", "restart_note": "(requires restarting the app)",
        "sw_history": "Save conversation history",
        "open_data": "Open data folder",
        "sec_translation": "Translation", "fallback_lang": "If automatic and nothing detected yet, use",
        "sw_skip_same": "Hide messages already in my language",
        "ignore_list": "Messages that are not translated (comma separated)",
        "sec_overlay": "Overlay", "ov_x": "Horizontal position", "ov_y": "Vertical position (bottom edge)",
        "ov_width": "Width", "ov_font": "Font size", "ov_seconds": "Seconds on screen",
        "ov_lines": "Max lines", "preview": "Preview",
        "sec_hotkeys": "Hotkeys", "hk_overlay": "Show/hide overlay",
        "hk_send": "Translate and send in Dota chat", "apply": "Apply",
        "sec_dota": "Dota 2", "dota_folder": "Dota 2 folder", "browse": "Browse…", "detect": "Detect",
        "gsi_port": "Local port", "invalid_folder": "That folder doesn't look like Dota 2 (it must contain game/dota/cfg).",
        "installed_ok": "Integration installed. Restart Dota 2 to activate it.",
        "uninstalled_ok": "Integration removed.",
        "saved": "Saved",
        "err_port": "Could not open port {port}. Is another copy of the app already running?",
        "sw_hero_icons": "Show the portrait of the hero who's typing",
        "test_capture": "Calibrate portraits",
        "capture_countdown": "Switch to Dota 2… capturing in {n}",
        "capture_title": "Calibrate hero portraits",
        "capture_help": "Join a match (bots are fine), press “Capture” and switch to Dota. Move the sliders until "
                        "each box fits a portrait in the top bar; below you'll see how they get cropped. "
                        "Then press “Save”.",
        "capture_none": "The Dota 2 window wasn't found. Open it (borderless window) and try again.",
        "capture_black": "The capture came out black. Set Dota to “Borderless window” and capture again.",
        "calib_capture": "Capture", "calib_reset": "Reset", "calib_save": "Save",
        "calib_saved": "Calibration saved.", "calib_waiting": "No capture yet.",
        "cal_radiant_first_center": "Radiant position (player 0)", "cal_dire_first_center": "Dire position (player 5)",
        "cal_pitch": "Spacing between portraits", "cal_half_width": "Portrait width",
        "cal_top": "Top edge", "cal_bottom": "Bottom edge",
        "sec_updates": "Updates", "sw_check_updates": "Check for updates on startup",
        "check_now": "Check now", "current_version": "Installed version: {v}",
        "up_to_date": "You already have the latest version ({v}).", "update_check_failed": "Could not check: {err}",
        "update_title": "New version available",
        "update_text": "A new version of Dota Chat Translator is available: {new} (you have {cur}).",
        "update_now": "Update now", "update_later": "Later", "update_skip": "Skip this version",
        "update_open_page": "Open download page", "update_notes": "What's new",
        "update_downloading": "Downloading… {pct}%", "update_verifying": "Verifying…",
        "update_restarting": "Installing and restarting…",
        "update_failed": "The update failed: {err}\n\nYou can download it manually from GitHub.",
        "update_manual": "This copy can't update itself (it runs from source or its folder isn't writable). "
                         "The download page will open.",
        "preview_1": "иди мид, я на харде", "preview_2": "我们推塔吧",
    },
}

_current = "en"


def set_lang(code: str):
    global _current
    _current = code if code in STRINGS else "en"


def t(key: str, **kw) -> str:
    s = STRINGS[_current].get(key) or STRINGS["en"].get(key) or key
    return s.format(**kw) if kw else s
