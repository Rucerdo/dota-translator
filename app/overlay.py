"""Overlay transparente sobre el juego: siempre encima y deja pasar los clics."""
import ctypes
import queue
import time
import tkinter as tk
import tkinter.font as tkfont

user32 = ctypes.windll.user32
GWL_EXSTYLE = -20
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE, WS_EX_TOPMOST = (
    0x80000, 0x20, 0x80, 0x08000000, 0x8)
HWND_TOPMOST, SWP_FLAGS = -1, 0x0001 | 0x0002 | 0x0010  # NOSIZE | NOMOVE | NOACTIVATE

TRANSPARENT = "#010203"
GRAY = "#9AA0A6"


class Overlay:
    def __init__(self, master: tk.Misc, cfg: dict, enabled: bool = True):
        self.cfg = dict(cfg)
        self.q: queue.Queue = queue.Queue()
        self.lines: list[tuple[float, list[tuple[str, str]]]] = []
        self.enabled = enabled

        self.win = tk.Toplevel(master)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.config(bg=TRANSPARENT)
        self.win.attributes("-transparentcolor", TRANSPARENT)
        self.canvas = tk.Canvas(self.win, bg=TRANSPARENT, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self._layout()
        self.win.update_idletasks()
        self.hwnd = self._make_click_through()
        if not enabled:
            self.win.withdraw()
        self.win.after(100, self._tick)
        self.win.after(2000, self._keep_on_top)

    # ---------- configuración ----------
    def _layout(self):
        c = self.cfg
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        self.w, self.h = int(sw * c["width_frac"]), int(sh * 0.30)
        x, y = int(sw * c["x_frac"]), max(0, int(sh * c["y_frac"]) - self.h)
        self.win.geometry(f"{self.w}x{self.h}+{x}+{y}")
        self.canvas.config(width=self.w, height=self.h)
        self.font = tkfont.Font(family=c["font_family"], size=int(c["font_size"]), weight="bold")
        self.small = tkfont.Font(family=c["font_family"], size=max(8, int(c["font_size"]) - 3))

    def _make_click_through(self) -> int:
        hwnd = user32.GetParent(self.win.winfo_id()) or self.win.winfo_id()
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED | WS_EX_TRANSPARENT
                              | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE | WS_EX_TOPMOST)
        return hwnd

    def _keep_on_top(self):
        if self.enabled:
            user32.SetWindowPos(self.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_FLAGS)
        self.win.after(2000, self._keep_on_top)

    # ---------- API thread-safe ----------
    def push(self, segments: list[tuple[str, str]]):
        """segments = [(texto, color), ...]; color GRAY = línea secundaria pequeña."""
        self.q.put(("line", segments))

    def set_enabled(self, enabled: bool):
        self.q.put(("enabled", enabled))

    def toggle(self):
        self.q.put(("enabled", None))

    def apply_cfg(self, cfg: dict):
        self.q.put(("cfg", dict(cfg)))

    # ---------- bucle ----------
    def _tick(self):
        changed = False
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "line":
                    self.lines.append((time.time(), data))
                    self.lines = self.lines[-int(self.cfg["max_lines"]):]
                elif kind == "enabled":
                    self.enabled = (not self.enabled) if data is None else data
                    if self.enabled:
                        self.win.deiconify()
                        self._make_click_through()
                    else:
                        self.win.withdraw()
                elif kind == "cfg":
                    self.cfg = data
                    self._layout()
                changed = True
        except queue.Empty:
            pass
        now = time.time()
        alive = [l for l in self.lines if now - l[0] < float(self.cfg["line_seconds"])]
        if len(alive) != len(self.lines):
            self.lines, changed = alive, True
        if changed:
            self._redraw()
        self.win.after(100, self._tick)

    def _text(self, x, y, txt, color, font, tag):
        width = max(50, self.w - x - 6)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):  # contorno para leer sobre cualquier fondo
            self.canvas.create_text(x + dx, y + dy, text=txt, fill="#000001", font=font,
                                    anchor="nw", width=width, tags=tag)
        return self.canvas.create_text(x, y, text=txt, fill=color, font=font, anchor="nw", width=width, tags=tag)

    def _draw_line(self, segs, tag):
        x, y = 4, 0
        for txt, color in segs:
            small = color == GRAY
            f = self.small if small else self.font
            if small:
                bbox = self.canvas.bbox(tag)
                x, y = 22, (bbox[3] if bbox else 0)
            item = self._text(x, y, txt, color, f, tag)
            bb = self.canvas.bbox(item)
            if not small and bb:
                x = bb[2] + 4
                if x > self.w * 0.6:
                    x, y = 4, bb[3]

    def _redraw(self):
        self.canvas.delete("all")
        y = self.h
        for i, (_, segs) in enumerate(reversed(self.lines)):
            tag = f"L{i}"
            self._draw_line(segs, tag)
            bbox = self.canvas.bbox(tag)
            lh = (bbox[3] - bbox[1]) if bbox else 20
            y -= lh + 4
            if y < 0:
                self.canvas.delete(tag)
                break
            self.canvas.move(tag, 0, y)
