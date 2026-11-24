"""Textos de la interfaz (es / en) y lista de idiomas de traducción."""

# Idiomas de traducción (código de Google Translate, nombre nativo)
LANGUAGES = [
    ("es-ES", "Español (España)"), ("es-419", "Español (Latinoamérica)"), ("en", "English"), ("ru", "Русский"), ("zh-CN", "中文 (简体)"), ("zh-TW", "中文 (繁體)"),
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
        "translate_to": "Traducir el chat a", "send_in": "Traducir mis mensajes a",
        "auto_team": "Automático (idioma del equipo)",
        "sw_overlay": "Mostrar overlay en el juego",
        "sw_original": "Mostrar el texto original",
        "tips_title": "Antes de jugar",
        "tips": "• Pon Dota 2 en «Ventana sin bordes» (Ajustes → Vídeo). En pantalla completa el overlay no se ve.\n"
                "• Tras instalar la integración, reinicia Dota 2 una vez.\n"
                "• Para escribir a tu equipo en su idioma: en Dota pulsa Ctrl+Enter (Ctrl+Shift+Enter para todos), "
                "escribe y pulsa Enter: se traduce y se envía solo.",
        # chat en vivo
        "live_title": "Chat en vivo", "clear": "Limpiar",
        "live_empty": "Aquí aparecerán los mensajes del chat de Dota 2 y sus traducciones.\n",
        "compose_placeholder": "Escribe tu mensaje para el equipo…", "compose_btn": "Traducir y copiar",
        "compose_hint": "Se traduce al idioma de tu equipo y se copia: pégalo en el chat de Dota con Ctrl+V.",
        "compose_working": "Traduciendo…", "compose_done": "✓ Copiado ({lang}): {text}   →  pégalo en Dota con Ctrl+V",
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
        "sec_dota": "Dota 2", "dota_folder": "Carpeta de Dota 2", "browse": "Examinar…", "detect": "Detectar",
        "gsi_port": "Puerto local", "invalid_folder": "Esa carpeta no parece de Dota 2 (debe contener game/dota/cfg).",
        "installed_ok": "Integración instalada. Reinicia Dota 2 para activarla.",
        "uninstalled_ok": "Integración quitada.",
        "saved": "Guardado",
        # errores
        "err_port": "No se pudo abrir el puerto {port}. ¿Ya hay otra copia de la app abierta?",
        # escribir desde el juego
        "sec_compose": "Escribir desde el juego",
        "compose_desc": "Pulsa el atajo en Dota: aparece una caja encima del juego, escribes, eliges idioma si quieres "
                        "otro y pulsas Enter. Se traduce, se pega en el chat de Dota y se envía. Esc cancela. "
                        "Usa atajos nativos de Windows: la app no intercepta ninguna otra tecla.",
        "sw_compose": "Activar la caja de escribir con atajo", "compose_hk_team": "Atajo: escribir al equipo",
        "compose_hk_all": "Atajo: escribir a todos", "sw_autosend": "Enviar automáticamente (si no, solo lo pega)",
        "apply": "Aplicar", "compose_hk_ok": "✓ Atajos activos",
        "compose_hk_failed": "✗ Otro programa ya usa: {keys}. Elige otra combinación.",
        "box_placeholder": "Escribe tu mensaje…", "box_hint": "Enter: traducir y enviar   ·   Esc: cancelar",
        # motor de traducción
        "engine": "Motor de traducción", "engine_google": "Google Translate (gratis, sin cuenta)",
        "ai_help": "La IA traduce como hablaría un jugador y entiende la jerga y el contexto de la partida. Pega la "
                   "clave de API del servicio (se guarda cifrada con tu usuario de Windows). Si falla o se acaba la "
                   "cuota, se usa Google Translate automáticamente. Gemini y Groq tienen plan gratuito; Groq es el "
                   "más rápido. Nota: algunos planes gratuitos pueden usar los textos para mejorar sus modelos.",
        "ai_key": "Clave de API", "ai_key_optional": "Clave (opcional)", "ai_model": "Modelo",
        "ai_model_auto": "automático ({hint})", "ai_base_url": "Dirección del servidor",
        "ai_get_key": "Conseguir clave", "ai_test": "Probar", "ai_saved": "Guardado.",
        "ai_testing": "Probando…", "ai_ok": "✓ Funciona con {model} ({secs} s): «{sample}» → «{out}»",
        "ai_fail": "✗ No funciona: {err}", "ai_no_key": "Pega primero tu clave.",
        "ai_sample": "керри не фармит, пушим топ",
        "ai_plan_help": "Usa tu suscripción ChatGPT Plus o Pro, sin clave de API: inicias sesión en el navegador y das "
                        "permiso a la app. Cuenta para los límites de tu plan (puedes ponerle un tope a esta app en "
                        "«Gestionar uso»). Las cuentas gratuitas de ChatGPT no pueden usarlo. La app no ve tus "
                        "conversaciones. Si se acaba el límite, se usa Google Translate.",
        "engine_chatgpt_plan": "ChatGPT · tu plan Plus/Pro (sin clave)",
        "ai_account": "Cuenta", "ai_login_chatgpt": "Iniciar sesión con ChatGPT", "ai_logout": "Cerrar sesión",
        "ai_logged_as": "✓ Conectado{email}", "ai_not_logged": "Sin sesión iniciada",
        "ai_login_wait": "Acepta en la ventana del navegador que se ha abierto…", "ai_cancel": "Cancelar",
        "ai_login_ok": "✓ Listo. Pulsa «Probar» para comprobarlo.", "ai_login_fail": "✗ No se pudo conectar: {err}",
        "ai_need_login": "Inicia sesión primero.", "ai_usage_page": "Gestionar uso",
        "ai_connect_openrouter": "Conectar con OpenRouter",
        "ai_connected_key": "✓ Conectado: OpenRouter ha creado una clave para la app y se ha guardado.",
        # voz
        "voice": "Voz", "dir_voice": "Voz", "sec_voice": "Chat de voz (experimental)",
        "sw_voice": "Transcribir el chat de voz de Dota",
        "voice_desc": "Pasa a texto todo lo que se habla en el audio de Dota y lo traduce. Funciona en tu PC con "
                      "Whisper (sin enviar audio a internet) y solo escucha a dota2.exe, no a Discord ni al resto del "
                      "equipo. Incluye también las frases de los héroes. Necesita descargar el motor de voz una vez.",
        "voice_model": "Modelo", "voice_model_turbo": "Turbo · gráfica NVIDIA (recomendado)",
        "voice_model_small": "Small · procesador (más lento)",
        "voice_install": "Descargar motor de voz ({size})", "voice_remove": "Eliminar motor de voz ({size})",
        "voice_cancel": "Cancelar",
        "voice_st_not_installed": "Motor de voz no instalado.",
        "voice_st_installed": "Motor de voz instalado.",
        "voice_st_downloading": "Descargando {step}… {done} / {total} ({pct}%)",
        "voice_step_engine": "motor", "voice_step_cuda": "librerías de NVIDIA", "voice_step_model": "modelo Whisper",
        "voice_st_loading": "Cargando el modelo de voz…", "voice_st_listening": "Escuchando a Dota 2 🎤",
        "voice_st_waiting_dota": "Esperando a que abras Dota 2…", "voice_st_error": "Error en el motor de voz (ver app.log).",
        "voice_st_stopped": "Voz desactivada.",
        "voice_install_failed": "No se pudo descargar el motor de voz: {err}",
        "voice_confirm_install": "Se descargarán unos {size} (una sola vez) a la carpeta de datos de la app. ¿Continuar?",
        "voice_confirm_remove": "¿Eliminar el motor de voz y liberar {size}?",
        "voice_skip_title": "No traducir estos idiomas",
        "voice_skip_help": "Marca los idiomas que entiendes: lo que se diga por voz en ellos no se traduce (ni gasta "
                           "cuota de la IA). Todo lo demás, sí.",
        "sw_voice_show_skipped": "Mostrar igualmente su transcripción, sin traducir",
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
        "translate_to": "Translate chat into", "send_in": "Translate my messages into",
        "auto_team": "Automatic (team's language)",
        "sw_overlay": "Show in-game overlay",
        "sw_original": "Show original text",
        "tips_title": "Before playing",
        "tips": "• Set Dota 2 to “Borderless Window” (Settings → Video). The overlay is hidden in exclusive fullscreen.\n"
                "• After installing the integration, restart Dota 2 once.\n"
                "• To write to your team in their language: in Dota press Ctrl+Enter (Ctrl+Shift+Enter for all chat), "
                "type and press Enter: it gets translated and sent.",
        "live_title": "Live chat", "clear": "Clear",
        "live_empty": "Dota 2 chat messages and their translations will appear here.\n",
        "compose_placeholder": "Type your message for the team…", "compose_btn": "Translate & copy",
        "compose_hint": "It gets translated into your team's language and copied: paste it in Dota chat with Ctrl+V.",
        "compose_working": "Translating…", "compose_done": "✓ Copied ({lang}): {text}   →  paste it in Dota with Ctrl+V",
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
        "sec_dota": "Dota 2", "dota_folder": "Dota 2 folder", "browse": "Browse…", "detect": "Detect",
        "gsi_port": "Local port", "invalid_folder": "That folder doesn't look like Dota 2 (it must contain game/dota/cfg).",
        "installed_ok": "Integration installed. Restart Dota 2 to activate it.",
        "uninstalled_ok": "Integration removed.",
        "saved": "Saved",
        "err_port": "Could not open port {port}. Is another copy of the app already running?",
        "sec_compose": "Write from the game",
        "compose_desc": "Press the hotkey in Dota: a box appears over the game, type, pick another language if you "
                        "want and press Enter. It gets translated, pasted into Dota chat and sent. Esc cancels. "
                        "It uses native Windows hotkeys: the app doesn't intercept any other key.",
        "sw_compose": "Enable the typing box hotkey", "compose_hk_team": "Hotkey: write to team",
        "compose_hk_all": "Hotkey: write to all", "sw_autosend": "Send automatically (otherwise just paste)",
        "apply": "Apply", "compose_hk_ok": "✓ Hotkeys active",
        "compose_hk_failed": "✗ Another program already uses: {keys}. Pick another combination.",
        "box_placeholder": "Type your message…", "box_hint": "Enter: translate and send   ·   Esc: cancel",
        "engine": "Translation engine", "engine_google": "Google Translate (free, no account)",
        "ai_help": "The AI translates the way a player would talk and understands slang and match context. Paste the "
                   "service's API key (stored encrypted with your Windows user). If it fails or the quota runs out, "
                   "Google Translate is used automatically. Gemini and Groq have free plans; Groq is the fastest. "
                   "Note: some free plans may use the texts to improve their models.",
        "ai_key": "API key", "ai_key_optional": "Key (optional)", "ai_model": "Model",
        "ai_model_auto": "automatic ({hint})", "ai_base_url": "Server address",
        "ai_get_key": "Get a key", "ai_test": "Test", "ai_saved": "Saved.",
        "ai_testing": "Testing…", "ai_ok": "✓ Works with {model} ({secs} s): “{sample}” → “{out}”",
        "ai_fail": "✗ Doesn't work: {err}", "ai_no_key": "Paste your key first.",
        "ai_sample": "керри не фармит, пушим топ",
        "ai_plan_help": "Uses your ChatGPT Plus or Pro subscription, no API key: sign in in the browser and allow "
                        "the app. It counts towards your plan limits (you can cap this app in “Manage usage”). Free "
                        "ChatGPT accounts can't use it. The app can't see your conversations. If the limit runs out, "
                        "Google Translate is used.",
        "engine_chatgpt_plan": "ChatGPT · your Plus/Pro plan (no key)",
        "ai_account": "Account", "ai_login_chatgpt": "Sign in with ChatGPT", "ai_logout": "Sign out",
        "ai_logged_as": "✓ Connected{email}", "ai_not_logged": "Not signed in",
        "ai_login_wait": "Approve it in the browser window that just opened…", "ai_cancel": "Cancel",
        "ai_login_ok": "✓ Done. Click “Test” to check it.", "ai_login_fail": "✗ Couldn't connect: {err}",
        "ai_need_login": "Sign in first.", "ai_usage_page": "Manage usage",
        "ai_connect_openrouter": "Connect OpenRouter",
        "ai_connected_key": "✓ Connected: OpenRouter created a key for the app and it has been saved.",
        "voice": "Voice", "dir_voice": "Voice", "sec_voice": "Voice chat (experimental)",
        "sw_voice": "Transcribe Dota voice chat",
        "voice_desc": "Turns everything spoken in Dota's audio into text and translates it. Runs on your PC with "
                      "Whisper (no audio is sent online) and only listens to dota2.exe, not Discord or anything "
                      "else. Hero voice lines are included too. Requires downloading the voice engine once.",
        "voice_model": "Model", "voice_model_turbo": "Turbo · NVIDIA graphics card (recommended)",
        "voice_model_small": "Small · processor (slower)",
        "voice_install": "Download voice engine ({size})", "voice_remove": "Remove voice engine ({size})",
        "voice_cancel": "Cancel",
        "voice_st_not_installed": "Voice engine not installed.",
        "voice_st_installed": "Voice engine installed.",
        "voice_st_downloading": "Downloading {step}… {done} / {total} ({pct}%)",
        "voice_step_engine": "engine", "voice_step_cuda": "NVIDIA libraries", "voice_step_model": "Whisper model",
        "voice_st_loading": "Loading the voice model…", "voice_st_listening": "Listening to Dota 2 🎤",
        "voice_st_waiting_dota": "Waiting for you to open Dota 2…", "voice_st_error": "Voice engine error (see app.log).",
        "voice_st_stopped": "Voice turned off.",
        "voice_install_failed": "Could not download the voice engine: {err}",
        "voice_confirm_install": "About {size} will be downloaded (only once) to the app's data folder. Continue?",
        "voice_confirm_remove": "Remove the voice engine and free {size}?",
        "voice_skip_title": "Don't translate these languages",
        "voice_skip_help": "Tick the languages you understand: what's said on voice in them isn't translated (and "
                           "doesn't use AI quota). Everything else is.",
        "sw_voice_show_skipped": "Still show their transcription, untranslated",
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
