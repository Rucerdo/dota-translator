"""Ventana principal (CustomTkinter): Inicio, Chat en vivo, Historial y Ajustes."""
import io
import logging
import os
import queue
import threading
import tkinter as tk
import webbrowser
from datetime import datetime
from tkinter import filedialog, messagebox, ttk

import customtkinter as ctk
import keyboard
from PIL import Image, ImageTk

from . import APP_NAME, __version__
from . import config as cfgmod
from . import dota, portraits, updater
from .core import Engine
from .gsi import SLOT_COLORS
from .i18n import LANGUAGES, UI_LANGS, lang_from_label, lang_label, set_lang, t

log = logging.getLogger(__name__)

BG, SIDEBAR, CARD, CARD2 = "#0E1217", "#141A21", "#1A212A", "#222B36"
TEXT, MUTED, ACCENT, ACCENT_HOVER = "#E6EAEE", "#8B96A3", "#C8402B", "#A9331F"
GREEN, YELLOW, RED, ORANGE, CYAN = "#5FCF80", "#F2C94C", "#E5534B", "#FFB74D", "#4FC3F7"


def font(size=13, weight="normal"):
    return ctk.CTkFont(family="Segoe UI", size=size, weight=weight)


def png_photo(png: bytes | None, height: int, master) -> ImageTk.PhotoImage | None:
    if not png:
        return None
    try:
        img = Image.open(io.BytesIO(png))
        return ImageTk.PhotoImage(img.resize((max(1, round(img.width * height / img.height)), height),
                                             Image.LANCZOS), master=master)
    except Exception:
        return None


class App(ctk.CTk):
    def __init__(self, cfg: dict):
        super().__init__(fg_color=BG)
        set_lang(cfg["ui_lang"])
        ctk.set_appearance_mode("dark")
        self.title(f"{APP_NAME}  v{__version__}")
        self.geometry("1060x700")
        self.minsize(920, 600)
        try:
            self.iconbitmap(str(cfgmod.resource_path("assets/icon.ico")))
        except tk.TclError:
            pass

        self.engine = Engine(self, cfg)
        self.cfg = cfg
        try:
            self.engine.start()
        except OSError:
            log.exception("no se pudo iniciar el servidor GSI")
            self.withdraw()
            messagebox.showerror(APP_NAME, t("err_port", port=cfg["gsi_port"]))
            self.destroy()
            raise SystemExit(1)

        # Variables compartidas entre Inicio y Ajustes
        self.v_in = tk.StringVar(value=lang_label(cfg["incoming_target_lang"]))
        self.v_out = tk.StringVar(value=self._out_label(cfg["outgoing_lang"]))
        self.v_overlay = tk.BooleanVar(value=cfg["overlay_enabled"])
        self.v_outgoing = tk.BooleanVar(value=cfg["enable_outgoing"])
        self.v_original = tk.BooleanVar(value=cfg["show_original"])

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()
        self.pages = {
            "home": self._build_home(),
            "live": self._build_live(),
            "history": self._build_history(),
            "settings": self._build_settings(),
        }
        self.show("home")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(200, self._poll)
        self.after(500, self._refresh_status)
        self.after(300, self._bring_to_front)
        updater.cleanup_old()
        if cfg.get("check_updates", True):
            self.after(2500, lambda: self._check_updates(manual=False))

    # ================= actualizaciones =================
    def _check_updates(self, manual: bool):
        def run():
            try:
                info, err = updater.check_latest(), None
            except Exception as ex:
                log.warning("no se pudo comprobar actualizaciones: %s", ex)
                info, err = None, ex
            self.engine.events.put(("update", (info, err, manual)))
        threading.Thread(target=run, daemon=True).start()

    def _on_update_result(self, info, err, manual: bool):
        if err is not None:
            if manual:
                messagebox.showerror(APP_NAME, t("update_check_failed", err=err))
            return
        if info is None:
            if manual:
                messagebox.showinfo(APP_NAME, t("up_to_date", v=__version__))
            return
        if not manual and info.version == self.cfg.get("skip_version"):
            return
        UpdateDialog(self, info)

    def _bring_to_front(self):
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(400, lambda: self.attributes("-topmost", False))
        self.focus_force()

    # ================= estructura =================
    def _build_sidebar(self):
        sb = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=0, width=220)
        sb.grid(row=0, column=0, sticky="nsw")
        sb.grid_propagate(False)
        sb.grid_rowconfigure(6, weight=1)
        ctk.CTkLabel(sb, text="DOTA", font=font(26, "bold"), text_color=ACCENT).grid(
            row=0, column=0, padx=22, pady=(26, 0), sticky="w")
        ctk.CTkLabel(sb, text="Chat Translator", font=font(17, "bold"), text_color=TEXT).grid(
            row=1, column=0, padx=22, pady=(0, 2), sticky="w")
        ctk.CTkLabel(sb, text=f"v{__version__} · open source", font=font(11), text_color=MUTED).grid(
            row=2, column=0, padx=22, pady=(0, 22), sticky="w")
        self.nav = {}
        for i, (key, label) in enumerate([("home", "nav_home"), ("live", "nav_live"),
                                          ("history", "nav_history"), ("settings", "nav_settings")]):
            b = ctk.CTkButton(sb, text=t(label), anchor="w", height=40, corner_radius=8, font=font(14),
                              fg_color="transparent", hover_color=CARD2, text_color=TEXT,
                              command=lambda k=key: self.show(k))
            b.grid(row=3 + i if i < 3 else 6, column=0, padx=12, pady=3, sticky="new")
            self.nav[key] = b
        # el botón de ajustes va arriba junto a los demás; la fila 6 es elástica
        self.nav["settings"].grid_configure(row=6, sticky="new")
        status = ctk.CTkFrame(sb, fg_color=CARD, corner_radius=10)
        status.grid(row=7, column=0, padx=12, pady=16, sticky="ew")
        self.status_dot = ctk.CTkLabel(status, text="●", font=font(16), text_color=YELLOW)
        self.status_dot.grid(row=0, column=0, padx=(12, 6), pady=10)
        self.status_text = ctk.CTkLabel(status, text=t("status_waiting"), font=font(12), text_color=TEXT,
                                        wraplength=150, justify="left")
        self.status_text.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="w")

    def show(self, key: str):
        for k, page in self.pages.items():
            page.grid_forget()
            self.nav[k].configure(fg_color="transparent")
        self.pages[key].grid(row=0, column=1, sticky="nsew", padx=24, pady=20)
        self.nav[key].configure(fg_color=CARD2)
        if key == "history":
            self._reload_history()

    def _page(self, title: str) -> ctk.CTkFrame:
        page = ctk.CTkFrame(self, fg_color="transparent")
        page.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(page, text=title, font=font(24, "bold"), text_color=TEXT).grid(
            row=0, column=0, sticky="w", pady=(0, 14))
        return page

    def _card(self, parent, title: str | None = None) -> ctk.CTkFrame:
        c = ctk.CTkFrame(parent, fg_color=CARD, corner_radius=12)
        c.grid_columnconfigure(0, weight=1)
        if title:
            ctk.CTkLabel(c, text=title.upper(), font=font(11, "bold"), text_color=MUTED).grid(
                row=0, column=0, columnspan=3, padx=16, pady=(14, 4), sticky="w")
        return c

    # ================= Inicio =================
    def _build_home(self):
        p = self._page(t("home_title"))
        top = ctk.CTkFrame(p, fg_color="transparent")
        top.grid(row=1, column=0, sticky="ew")
        for i in range(3):
            top.grid_columnconfigure(i, weight=1, uniform="cards")

        c1 = self._card(top, t("card_dota"))
        c1.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.lbl_dota = ctk.CTkLabel(c1, text="", font=font(12), text_color=TEXT, wraplength=210, justify="left",
                                     anchor="w")
        self.lbl_dota.grid(row=1, column=0, padx=16, sticky="w")
        self.lbl_gsi = ctk.CTkLabel(c1, text="", font=font(13, "bold"))
        self.lbl_gsi.grid(row=2, column=0, padx=16, pady=(6, 4), sticky="w")
        self.btn_gsi = ctk.CTkButton(c1, text="", height=30, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                                     command=self._toggle_gsi)
        self.btn_gsi.grid(row=3, column=0, padx=16, pady=(4, 14), sticky="w")

        c2 = self._card(top, t("card_connection"))
        c2.grid(row=0, column=1, sticky="nsew", padx=8)
        self.lbl_conn = ctk.CTkLabel(c2, text="", font=font(13, "bold"), wraplength=240, justify="left")
        self.lbl_conn.grid(row=1, column=0, padx=16, sticky="w")
        self.lbl_match = ctk.CTkLabel(c2, text="", font=font(12), text_color=MUTED)
        self.lbl_match.grid(row=2, column=0, padx=16, pady=(4, 14), sticky="w")

        c3 = self._card(top, t("card_session"))
        c3.grid(row=0, column=2, sticky="nsew", padx=(8, 0))
        self.lbl_in = ctk.CTkLabel(c3, text="0", font=font(28, "bold"), text_color=CYAN)
        self.lbl_in.grid(row=1, column=0, padx=16, sticky="w")
        ctk.CTkLabel(c3, text=t("session_in"), font=font(12), text_color=MUTED).grid(row=2, column=0, padx=16,
                                                                                     sticky="w")
        self.lbl_out = ctk.CTkLabel(c3, text="0", font=font(20, "bold"), text_color=ORANGE)
        self.lbl_out.grid(row=3, column=0, padx=16, pady=(6, 0), sticky="w")
        ctk.CTkLabel(c3, text=t("session_out"), font=font(12), text_color=MUTED).grid(row=4, column=0, padx=16,
                                                                                      pady=(0, 14), sticky="w")

        q = self._card(p, t("quick_title"))
        q.grid(row=2, column=0, sticky="ew", pady=16)
        q.grid_columnconfigure(1, weight=1)
        self._lang_row(q, 1, t("translate_to"), self.v_in, self._on_in_lang)
        self._lang_row(q, 2, t("send_in"), self.v_out, self._on_out_lang, auto=True)
        for i, (var, key, path) in enumerate([(self.v_overlay, "sw_overlay", "overlay_enabled"),
                                              (self.v_outgoing, "sw_outgoing", "enable_outgoing"),
                                              (self.v_original, "sw_original", "show_original")]):
            ctk.CTkSwitch(q, text=t(key), variable=var, font=font(13), progress_color=ACCENT,
                          command=lambda v=var, pth=path: self.engine.set(pth, bool(v.get()))).grid(
                row=3 + i, column=0, columnspan=2, padx=16, pady=(6 if i else 12, 6 if i < 2 else 16), sticky="w")

        tips = self._card(p, t("tips_title"))
        tips.grid(row=3, column=0, sticky="ew")
        ctk.CTkLabel(tips, text=t("tips"), font=font(12), text_color=TEXT, justify="left", anchor="w",
                     wraplength=720).grid(row=1, column=0, padx=16, pady=(0, 14), sticky="w")
        return p

    def _lang_row(self, parent, row, label, var, cmd, auto=False):
        ctk.CTkLabel(parent, text=label, font=font(13), text_color=TEXT).grid(row=row, column=0, padx=16,
                                                                             pady=6, sticky="w")
        values = ([t("auto_team")] if auto else []) + [lang_label(c) for c, _ in LANGUAGES]
        ctk.CTkOptionMenu(parent, values=values, variable=var, command=cmd, width=260, font=font(13),
                          fg_color=CARD2, button_color=CARD2, button_hover_color=ACCENT,
                          dropdown_font=font(12)).grid(row=row, column=1, padx=16, pady=6, sticky="w")

    def _out_label(self, code: str) -> str:
        return t("auto_team") if code == "auto" else lang_label(code)

    def _on_in_lang(self, value):
        self.engine.set("incoming_target_lang", lang_from_label(value))

    def _on_out_lang(self, value):
        self.engine.set("outgoing_lang", "auto" if value == t("auto_team") else lang_from_label(value))

    def _toggle_gsi(self):
        if not self.engine.dota_dir:
            self.show("settings")
            return
        try:
            if self.engine.gsi_installed():
                self.engine.uninstall_gsi()
                messagebox.showinfo(APP_NAME, t("uninstalled_ok"))
            else:
                self.engine.install_gsi()
                messagebox.showinfo(APP_NAME, t("installed_ok"))
        except OSError as e:
            messagebox.showerror(APP_NAME, str(e))
        self._refresh_status(once=True)

    def _refresh_status(self, once=False):
        e = self.engine
        if e.dota_dir:
            parts = e.dota_dir.parts
            short = str(e.dota_dir) if len(parts) <= 4 else "…\\" + "\\".join(parts[-3:])
            self.lbl_dota.configure(text=short, text_color=MUTED)
            inst = e.gsi_installed()
            self.lbl_gsi.configure(text=t("gsi_installed") if inst else t("gsi_not_installed"),
                                   text_color=GREEN if inst else YELLOW)
            self.btn_gsi.configure(text=t("uninstall") if inst else t("install"),
                                   fg_color=CARD2 if inst else ACCENT)
        else:
            inst = False
            self.lbl_dota.configure(text=t("dota_not_found"), text_color=RED)
            self.lbl_gsi.configure(text=t("gsi_not_installed"), text_color=YELLOW)
            self.btn_gsi.configure(text=t("nav_settings"), fg_color=ACCENT)
        if e.gsi.connected:
            self.lbl_conn.configure(text=t("conn_ok"), text_color=GREEN)
            mid = e.gsi.match_id
            self.lbl_match.configure(text=f"{t('match')}: {t('practice') if mid in ('', '0') else mid}")
            self.status_dot.configure(text_color=GREEN)
            self.status_text.configure(text=t("status_connected"))
        else:
            self.lbl_conn.configure(text=t("conn_waiting"), text_color=YELLOW)
            self.lbl_match.configure(text="")
            self.status_dot.configure(text_color=YELLOW if inst else RED)
            self.status_text.configure(text=t("status_waiting") if inst else t("status_no_gsi"))
        self.lbl_in.configure(text=str(e.stats["in"]))
        self.lbl_out.configure(text=str(e.stats["out"]))
        if not once:
            self.after(1000, self._refresh_status)

    # ================= Chat en vivo =================
    def _build_live(self):
        p = self._page(t("live_title"))
        p.grid_rowconfigure(1, weight=1)
        ctk.CTkButton(p, text=t("clear"), width=90, height=30, fg_color=CARD2, hover_color=ACCENT,
                      command=self._clear_live).grid(row=0, column=0, sticky="e", pady=(0, 14))
        self.live = ctk.CTkTextbox(p, fg_color=CARD, corner_radius=12, font=font(14), wrap="word",
                                   text_color=TEXT, border_spacing=12)
        self.live.grid(row=1, column=0, sticky="nsew")
        self.live.tag_config("muted", foreground=MUTED)
        self.live.tag_config("time", foreground="#5C6773")
        self.live.tag_config("white", foreground=TEXT)
        self.live.insert("end", t("live_empty"), "muted")
        self.live.configure(state="disabled")
        self._live_empty = True
        self._live_imgs: list = []  # referencias a los PhotoImage (si no, Tk los borra)
        bar = ctk.CTkFrame(p, fg_color="transparent")
        bar.grid(row=2, column=0, sticky="ew", pady=(12, 0))
        bar.grid_columnconfigure(0, weight=1)
        self.test_entry = ctk.CTkEntry(bar, placeholder_text=t("test_placeholder"), height=36, font=font(13),
                                       fg_color=CARD, border_color=CARD2)
        self.test_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.test_entry.bind("<Return>", lambda _e: self._test())
        ctk.CTkButton(bar, text=t("test_btn"), width=100, height=36, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._test).grid(row=0, column=1)
        return p

    def _test(self):
        text = self.test_entry.get().strip()
        if text:
            self.engine.test_translate(text)
            self.test_entry.delete(0, "end")

    def _clear_live(self):
        self.live.configure(state="normal")
        self.live.delete("1.0", "end")
        self.live.configure(state="disabled")
        self._live_imgs.clear()

    def _who(self, rec) -> tuple[str, str]:
        if rec["direction"] == "out":
            return f"{t('you')} → {rec['tgt_lang']}", ORANGE
        if rec["direction"] == "test":
            return t("test"), CYAN
        pid = rec.get("player_id")
        if isinstance(pid, int) and 0 <= pid < 10:
            return t(SLOT_COLORS[pid][0]), SLOT_COLORS[pid][1]
        return "?", TEXT

    def _append_live(self, rec: dict):
        who, color = self._who(rec)
        tag = "c" + color.lstrip("#")
        self.live.tag_config(tag, foreground=color)
        ch = {"all": f"[{t('ch_all')}] ", "team": f"[{t('ch_team')}] "}.get(rec.get("channel"), "")
        ts = rec.get("ts", "")[11:19] or datetime.now().strftime("%H:%M:%S")
        self.live.configure(state="normal")
        if self._live_empty:
            self.live.delete("1.0", "end")
            self._live_empty = False
        self.live.insert("end", f"{ts}  ", "time")
        photo = png_photo(rec.get("icon"), 26, self)
        if photo is not None:
            self.live._textbox.image_create("end", image=photo, padx=2, align="center")
            self.live.insert("end", " ")
            self._live_imgs = self._live_imgs[-300:] + [photo]
        self.live.insert("end", f"{ch}{who}: ", tag)
        self.live.insert("end", rec["translated"] + "\n", "white")
        if rec["translated"].strip().lower() != rec["original"].strip().lower():
            self.live.insert("end", f"          {rec['src_lang']} · {rec['original']}\n", "muted")
        self.live.insert("end", "\n")
        self.live.configure(state="disabled")
        self.live.see("end")

    # ================= Historial =================
    def _build_history(self):
        p = self._page(t("history_title"))
        p.grid_rowconfigure(2, weight=1)
        bar = ctk.CTkFrame(p, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        bar.grid_columnconfigure(0, weight=1)
        self.h_search = ctk.CTkEntry(bar, placeholder_text=t("search"), height=34, font=font(13),
                                     fg_color=CARD, border_color=CARD2)
        self.h_search.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.h_search.bind("<KeyRelease>", lambda _e: self._reload_history(keep_sessions=True))
        self.h_session_map: dict[str, str | None] = {t("all_matches"): None}
        self.v_session = tk.StringVar(value=t("all_matches"))
        self.h_sessions = ctk.CTkOptionMenu(bar, values=[t("all_matches")], variable=self.v_session, width=240,
                                            fg_color=CARD2, button_color=CARD2, button_hover_color=ACCENT,
                                            command=lambda _v: self._reload_history(keep_sessions=True))
        self.h_sessions.grid(row=0, column=1, padx=(0, 8))
        for i, (txt, cmd, col) in enumerate([(t("refresh"), self._reload_history, CARD2),
                                             (t("export"), self._export, CARD2),
                                             (t("delete_all"), self._delete_all, "#5A2620")]):
            ctk.CTkButton(bar, text=txt, width=110, height=34, fg_color=col, hover_color=ACCENT,
                          command=cmd).grid(row=0, column=2 + i, padx=(0, 8 if i < 2 else 0))

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("H.Treeview", background=CARD, fieldbackground=CARD, foreground=TEXT, rowheight=30,
                        borderwidth=0, bordercolor=CARD, lightcolor=CARD, darkcolor=CARD, font=("Segoe UI", 10))
        style.layout("H.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])  # sin marco de foco
        style.configure("H.Treeview", indent=0)  # la columna #0 solo lleva el retrato, sin sangría de árbol
        style.configure("H.Treeview.Heading", background=SIDEBAR, foreground=MUTED, relief="flat",
                        font=("Segoe UI", 10, "bold"), padding=6)
        style.map("H.Treeview", background=[("selected", "#3A2A28")], foreground=[("selected", TEXT)])
        style.map("H.Treeview.Heading", background=[("active", CARD2)])
        wrap = ctk.CTkFrame(p, fg_color=CARD, corner_radius=12)
        wrap.grid(row=2, column=0, sticky="nsew")
        wrap.grid_columnconfigure(0, weight=1)
        wrap.grid_rowconfigure(0, weight=1)
        # las columnas de texto empiezan estrechas y se estiran con el espacio sobrante
        cols = [("ts", "col_time", 92), ("match", "col_match", 92), ("dir", "col_dir", 72),
                ("channel", "col_channel", 66), ("player", "col_player", 78), ("lang", "col_lang", 78),
                ("original", "col_original", 100), ("translated", "col_translated", 100)]
        self.tree = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="tree headings", style="H.Treeview")
        self.tree.column("#0", width=58, minwidth=58, stretch=False, anchor="center")  # retrato del héroe
        self.tree.heading("#0", text="")
        self._h_imgs: dict[str, object] = {}
        for key, label, w in cols:
            self.tree.heading(key, text=t(label), anchor="w")
            self.tree.column(key, width=w, minwidth=50, anchor="w", stretch=key in ("original", "translated"))
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=10)
        sbar = ctk.CTkScrollbar(wrap, command=self.tree.yview)
        sbar.grid(row=0, column=1, sticky="ns", pady=10, padx=(0, 4))
        self.tree.configure(yscrollcommand=sbar.set)
        self.tree.bind("<<TreeviewSelect>>", self._show_detail)
        self.h_detail = ctk.CTkTextbox(p, height=90, fg_color=CARD, corner_radius=12, font=font(13), wrap="word")
        self.h_detail.grid(row=3, column=0, sticky="ew", pady=(10, 0))
        self.h_detail.configure(state="disabled")
        self.h_rows: dict[str, dict] = {}
        return p

    def _session_label(self, s: dict) -> str:
        mid = s["match_id"]
        name = t("practice") if mid in ("", "0") else mid
        return f"{s['start'][:16].replace('T', ' ')} · {name} ({s['n']})"

    def _reload_history(self, keep_sessions=False):
        h = self.engine.history
        if not keep_sessions:
            self.h_session_map = {t("all_matches"): None}
            for s in h.sessions():
                self.h_session_map[self._session_label(s)] = s["match_id"]
            self.h_sessions.configure(values=list(self.h_session_map))
            if self.v_session.get() not in self.h_session_map:
                self.v_session.set(t("all_matches"))
        rows = h.query(self.h_session_map.get(self.v_session.get()), self.h_search.get().strip())
        self.tree.delete(*self.tree.get_children())
        self.h_rows = {}
        self._h_imgs = {}
        dirs = {"in": t("dir_in"), "out": t("dir_out"), "test": t("dir_test")}
        chans = {"all": t("ch_all"), "team": t("ch_team")}
        for r in rows:
            pid = r.get("player_id")
            player = t("you") if r["direction"] == "out" else (
                t(SLOT_COLORS[pid][0]) if isinstance(pid, int) and 0 <= pid < 10 else "")
            mid = r["match_id"]
            photo = png_photo(r.get("icon"), 24, self)
            iid = self.tree.insert("", "end", image=photo or "", values=(
                r["ts"][5:16].replace("T", " "), t("practice") if mid in ("", "0") else mid,
                dirs.get(r["direction"], ""),
                chans.get(r["channel"], ""), player, f"{r['src_lang']}→{r['tgt_lang']}",
                r["original"], r["translated"]))
            self.h_rows[iid] = r
            if photo is not None:
                self._h_imgs[iid] = photo
        self._h_current = rows
        if not self.cfg.get("save_history", True) and not rows:
            self._set_detail(t("history_off"))

    def _set_detail(self, text: str):
        self.h_detail.configure(state="normal")
        self.h_detail.delete("1.0", "end")
        self.h_detail.insert("end", text)
        self.h_detail.configure(state="disabled")

    def _show_detail(self, _e=None):
        sel = self.tree.selection()
        if sel and sel[0] in self.h_rows:
            r = self.h_rows[sel[0]]
            self._set_detail(f"[{r['src_lang']}] {r['original']}\n[{r['tgt_lang']}] {r['translated']}")

    def _export(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile=f"dota-chat-{datetime.now():%Y%m%d-%H%M}.csv")
        if path:
            self.engine.history.export_csv(path, getattr(self, "_h_current", []))
            messagebox.showinfo(APP_NAME, t("exported", path=path))

    def _delete_all(self):
        if messagebox.askyesno(APP_NAME, t("confirm_delete"), icon="warning"):
            self.engine.history.clear()
            self._reload_history()
            self._set_detail("")

    # ================= Ajustes =================
    def _build_settings(self):
        p = self._page(t("settings_title"))
        p.grid_rowconfigure(1, weight=1)
        sc = ctk.CTkScrollableFrame(p, fg_color="transparent")
        sc.grid(row=1, column=0, sticky="nsew")
        sc.grid_columnconfigure(0, weight=1)
        e, cfg = self.engine, self.cfg
        r = 0

        def section(title):
            nonlocal r
            c = self._card(sc, title)
            c.grid(row=r, column=0, sticky="ew", pady=(0, 14), padx=(0, 6))
            c.grid_columnconfigure(1, weight=1)
            r += 1
            return c

        def label(parent, row, text, note=""):
            ctk.CTkLabel(parent, text=text + (f"  {note}" if note else ""), font=font(13), text_color=TEXT).grid(
                row=row, column=0, padx=16, pady=7, sticky="w")

        # --- General
        g = section(t("sec_general"))
        label(g, 1, t("ui_lang"), t("restart_note"))
        ui_names = {code: name for code, name in UI_LANGS}
        self.v_ui = tk.StringVar(value=ui_names.get(cfg["ui_lang"], "English"))
        ctk.CTkOptionMenu(g, values=list(ui_names.values()), variable=self.v_ui, width=200, fg_color=CARD2,
                          button_color=CARD2, button_hover_color=ACCENT,
                          command=lambda v: e.set("ui_lang", next(c for c, n in UI_LANGS if n == v))).grid(
            row=1, column=1, padx=16, sticky="w")
        self.v_hist = tk.BooleanVar(value=cfg["save_history"])
        ctk.CTkSwitch(g, text=t("sw_history"), variable=self.v_hist, progress_color=ACCENT, font=font(13),
                      command=lambda: e.set("save_history", bool(self.v_hist.get()))).grid(
            row=2, column=0, columnspan=2, padx=16, pady=7, sticky="w")
        ctk.CTkButton(g, text=t("open_data"), width=180, fg_color=CARD2, hover_color=ACCENT,
                      command=lambda: os.startfile(cfgmod.APP_DIR)).grid(row=3, column=0, padx=16, pady=(4, 16),
                                                                         sticky="w")

        # --- Traducción
        tr = section(t("sec_translation"))
        self._lang_row(tr, 1, t("translate_to"), self.v_in, self._on_in_lang)
        self._lang_row(tr, 2, t("send_in"), self.v_out, self._on_out_lang, auto=True)
        self.v_fallback = tk.StringVar(value=lang_label(cfg["outgoing_fallback_lang"]))
        self._lang_row(tr, 3, t("fallback_lang"), self.v_fallback,
                       lambda v: e.set("outgoing_fallback_lang", lang_from_label(v)))
        self.v_skip = tk.BooleanVar(value=cfg["skip_if_source_is_target"])
        for i, (var, key, path) in enumerate([(self.v_skip, "sw_skip_same", "skip_if_source_is_target"),
                                              (self.v_original, "sw_original", "show_original"),
                                              (self.v_outgoing, "sw_outgoing", "enable_outgoing")]):
            ctk.CTkSwitch(tr, text=t(key), variable=var, progress_color=ACCENT, font=font(13),
                          command=lambda v=var, pth=path: e.set(pth, bool(v.get()))).grid(
                row=4 + i, column=0, columnspan=2, padx=16, pady=6, sticky="w")
        label(tr, 7, t("ignore_list"))
        self.e_ignore = ctk.CTkEntry(tr, height=32, fg_color=CARD2, border_color=CARD2)
        self.e_ignore.insert(0, ", ".join(cfg["ignore_messages"]))
        self.e_ignore.grid(row=8, column=0, columnspan=2, padx=16, pady=(0, 16), sticky="ew")
        self.e_ignore.bind("<FocusOut>", lambda _e: e.set(
            "ignore_messages", [s.strip() for s in self.e_ignore.get().split(",") if s.strip()]))

        # --- Overlay
        ov = section(t("sec_overlay"))
        ctk.CTkSwitch(ov, text=t("sw_overlay"), variable=self.v_overlay, progress_color=ACCENT, font=font(13),
                      command=lambda: e.set("overlay_enabled", bool(self.v_overlay.get()))).grid(
            row=1, column=0, columnspan=2, padx=16, pady=7, sticky="w")
        sliders = [("ov_x", "x_frac", 0, 0.9, 90, "{:.0%}"), ("ov_y", "y_frac", 0.3, 1.0, 70, "{:.0%}"),
                   ("ov_width", "width_frac", 0.15, 0.7, 55, "{:.0%}"), ("ov_font", "font_size", 9, 24, 15, "{:.0f}"),
                   ("ov_seconds", "line_seconds", 4, 40, 36, "{:.0f}s"), ("ov_lines", "max_lines", 3, 15, 12, "{:.0f}")]
        for i, (key, ck, lo, hi, steps, fmt) in enumerate(sliders):
            label(ov, 2 + i, t(key))
            row = ctk.CTkFrame(ov, fg_color="transparent")
            row.grid(row=2 + i, column=1, padx=16, sticky="ew")
            val = ctk.CTkLabel(row, text=fmt.format(cfg["overlay"][ck]), width=50, font=font(12), text_color=MUTED)
            val.pack(side="right")

            def on(v, ck=ck, val=val, fmt=fmt):
                v = round(v) if ck in ("font_size", "line_seconds", "max_lines") else round(v, 3)
                val.configure(text=fmt.format(v))
                e.set(f"overlay.{ck}", v)
            s = ctk.CTkSlider(row, from_=lo, to=hi, number_of_steps=steps, command=on, button_color=ACCENT,
                              progress_color=ACCENT, button_hover_color=ACCENT_HOVER)
            s.set(cfg["overlay"][ck])
            s.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.v_icons = tk.BooleanVar(value=cfg.get("show_hero_icons", True))
        ctk.CTkSwitch(ov, text=t("sw_hero_icons"), variable=self.v_icons, progress_color=ACCENT, font=font(13),
                      command=lambda: e.set("show_hero_icons", bool(self.v_icons.get()))).grid(
            row=8, column=0, columnspan=2, padx=16, pady=7, sticky="w")
        ob = ctk.CTkFrame(ov, fg_color="transparent")
        ob.grid(row=9, column=0, columnspan=2, padx=16, pady=(8, 16), sticky="w")
        ctk.CTkButton(ob, text=t("preview"), width=140, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=e.preview_overlay).pack(side="left", padx=(0, 8))
        ctk.CTkButton(ob, text=t("test_capture"), width=200, fg_color=CARD2, hover_color=ACCENT,
                      command=lambda: PortraitCalibrator(self)).pack(side="left")

        # --- Atajos
        hk = section(t("sec_hotkeys"))
        self.hk_entries = {}
        for i, (key, ck) in enumerate([("hk_overlay", "toggle_overlay"), ("hk_send", "translate_and_send")]):
            label(hk, 1 + i, t(key))
            ent = ctk.CTkEntry(hk, width=200, height=32, fg_color=CARD2, border_color=CARD2)
            ent.insert(0, cfg["hotkeys"][ck])
            ent.grid(row=1 + i, column=1, padx=16, pady=6, sticky="w")
            self.hk_entries[ck] = ent
        ctk.CTkButton(hk, text=t("apply"), width=120, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._apply_hotkeys).grid(row=3, column=0, padx=16, pady=(6, 16), sticky="w")

        # --- Dota 2
        d = section(t("sec_dota"))
        label(d, 1, t("dota_folder"))
        self.e_dota = ctk.CTkEntry(d, height=32, fg_color=CARD2, border_color=CARD2)
        self.e_dota.insert(0, str(e.dota_dir or ""))
        self.e_dota.grid(row=2, column=0, columnspan=2, padx=16, sticky="ew")
        btns = ctk.CTkFrame(d, fg_color="transparent")
        btns.grid(row=3, column=0, columnspan=2, padx=16, pady=(8, 6), sticky="w")
        for txt, cmd in [(t("browse"), self._browse_dota), (t("detect"), self._detect_dota),
                         (t("install"), lambda: self._gsi_action(True)),
                         (t("uninstall"), lambda: self._gsi_action(False))]:
            ctk.CTkButton(btns, text=txt, width=150, fg_color=CARD2, hover_color=ACCENT,
                          command=cmd).pack(side="left", padx=(0, 8))
        label(d, 4, t("gsi_port"), t("restart_note"))
        self.e_port = ctk.CTkEntry(d, width=100, height=32, fg_color=CARD2, border_color=CARD2)
        self.e_port.insert(0, str(cfg["gsi_port"]))
        self.e_port.grid(row=4, column=1, padx=16, pady=(6, 16), sticky="w")
        self.e_port.bind("<FocusOut>", lambda _e: self._set_port())

        # --- Actualizaciones
        up = section(t("sec_updates"))
        label(up, 1, t("current_version", v=__version__))
        self.v_updates = tk.BooleanVar(value=cfg.get("check_updates", True))
        ctk.CTkSwitch(up, text=t("sw_check_updates"), variable=self.v_updates, progress_color=ACCENT,
                      font=font(13), command=lambda: e.set("check_updates", bool(self.v_updates.get()))).grid(
            row=2, column=0, columnspan=2, padx=16, pady=6, sticky="w")
        ctk.CTkButton(up, text=t("check_now"), width=150, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=lambda: self._check_updates(manual=True)).grid(row=3, column=0, padx=16,
                                                                             pady=(6, 16), sticky="w")
        return p

    def _apply_hotkeys(self):
        for ck, ent in self.hk_entries.items():
            hkv = ent.get().strip().lower()
            try:
                keyboard.parse_hotkey(hkv)
            except ValueError:
                messagebox.showerror(APP_NAME, f"Hotkey: {hkv}")
                return
            self.cfg["hotkeys"][ck] = hkv
        self.engine.set("hotkeys", self.cfg["hotkeys"])
        messagebox.showinfo(APP_NAME, t("saved"))

    def _browse_dota(self):
        folder = filedialog.askdirectory()
        if folder:
            self._use_dota(folder)

    def _detect_dota(self):
        d = dota.find_dota_dir()
        if d:
            self._use_dota(str(d))
        else:
            messagebox.showwarning(APP_NAME, t("dota_not_found"))

    def _use_dota(self, folder: str):
        if self.engine.set_dota_dir(folder):
            self.e_dota.delete(0, "end")
            self.e_dota.insert(0, str(self.engine.dota_dir))
            self._refresh_status(once=True)
        else:
            messagebox.showerror(APP_NAME, t("invalid_folder"))

    def _gsi_action(self, install: bool):
        if not self.engine.dota_dir:
            messagebox.showwarning(APP_NAME, t("dota_not_found"))
            return
        try:
            if install:
                self.engine.install_gsi()
                messagebox.showinfo(APP_NAME, t("installed_ok"))
            else:
                self.engine.uninstall_gsi()
                messagebox.showinfo(APP_NAME, t("uninstalled_ok"))
        except OSError as ex:
            messagebox.showerror(APP_NAME, str(ex))
        self._refresh_status(once=True)

    def _set_port(self):
        try:
            port = int(self.e_port.get())
        except ValueError:
            return
        if 1024 <= port <= 65535 and port != self.cfg["gsi_port"]:
            self.engine.set("gsi_port", port)
            messagebox.showinfo(APP_NAME, t("restart_note"))

    # ================= bucle de eventos =================
    def _poll(self):
        while True:
            try:
                kind, data = self.engine.events.get_nowait()
            except queue.Empty:
                break
            try:
                if kind == "record":
                    self._append_live(data)
                elif kind == "cfg":
                    self.v_overlay.set(self.cfg["overlay_enabled"])
                elif kind == "update":
                    self._on_update_result(*data)
            except Exception:
                log.exception("error actualizando la interfaz")
        self.after(150, self._poll)

    def on_close(self):
        self.engine.shutdown()
        self.destroy()


class PortraitCalibrator(ctk.CTkToplevel):
    """Calibración en vivo de dónde están los retratos en la barra superior de Dota.

    Se captura UNA vez la franja superior de la ventana de Dota; al mover los deslizadores solo se
    redibujan los recuadros y los recortes sobre esa captura, así el ajuste es instantáneo."""
    VIEW_W = 900          # ancho de la vista previa en píxeles
    VIEW_HALF_SPAN = 470  # media anchura visible alrededor del centro (a 1080 px)

    def __init__(self, app: App):
        super().__init__(app, fg_color=BG)
        self.app = app
        self.title(t("capture_title"))
        self.resizable(False, False)
        self.transient(app)
        self.strip = None   # (imagen, client)
        self._photos: list = []
        self.values = {**portraits.DEFAULT_TOPBAR, **(app.cfg.get("topbar") or {})}

        ctk.CTkLabel(self, text=t("capture_help"), font=font(12), text_color=MUTED, wraplength=self.VIEW_W,
                     justify="left").grid(row=0, column=0, columnspan=2, padx=18, pady=(16, 10), sticky="w")
        self.view = tk.Canvas(self, width=self.VIEW_W, height=90, bg=CARD, highlightthickness=0)
        self.view.grid(row=1, column=0, columnspan=2, padx=18)
        self.tiles = tk.Canvas(self, width=self.VIEW_W, height=76, bg=BG, highlightthickness=0)
        self.tiles.grid(row=2, column=0, columnspan=2, padx=18, pady=(8, 6))

        sl = ctk.CTkFrame(self, fg_color=CARD, corner_radius=12)
        sl.grid(row=3, column=0, columnspan=2, padx=18, pady=8, sticky="ew")
        sl.grid_columnconfigure((1, 4), weight=1)
        self.sliders, self.labels = {}, {}
        for i, (key, (lo, hi)) in enumerate(portraits.CALIBRATION_RANGES.items()):
            r, c = divmod(i, 2)
            base = c * 3
            ctk.CTkLabel(sl, text=t(f"cal_{key}"), font=font(12), text_color=TEXT).grid(
                row=r, column=base, padx=(14, 6), pady=8, sticky="w")
            s = ctk.CTkSlider(sl, from_=lo, to=hi, number_of_steps=hi - lo, width=190, button_color=ACCENT,
                              progress_color=ACCENT, button_hover_color=ACCENT_HOVER,
                              command=lambda v, k=key: self._on_slider(k, v))
            s.set(self.values[key])
            s.grid(row=r, column=base + 1, pady=8, sticky="ew")
            lbl = ctk.CTkLabel(sl, text=str(self.values[key]), width=40, font=font(12), text_color=MUTED)
            lbl.grid(row=r, column=base + 2, padx=(4, 14))
            self.sliders[key], self.labels[key] = s, lbl

        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=4, column=0, columnspan=2, padx=18, pady=(6, 16), sticky="ew")
        self.btn_cap = ctk.CTkButton(bar, text=t("calib_capture"), width=200, fg_color=ACCENT,
                                     hover_color=ACCENT_HOVER, command=lambda: self._capture(3))
        self.btn_cap.pack(side="left")
        ctk.CTkButton(bar, text=t("calib_save"), width=120, fg_color=ACCENT, hover_color=ACCENT_HOVER,
                      command=self._save).pack(side="right")
        ctk.CTkButton(bar, text=t("calib_reset"), width=120, fg_color=CARD2, hover_color=CARD,
                      command=self._reset).pack(side="right", padx=8)
        self._redraw()
        self.after(100, lambda: (self.lift(), self.focus_force()))

    # ---------- captura ----------
    def _capture(self, n: int):
        if n > 0:
            self.btn_cap.configure(text=t("capture_countdown", n=n), state="disabled")
            self.after(1000, lambda: self._capture(n - 1))
            return
        self.btn_cap.configure(text=t("calib_capture"), state="normal")
        strip = portraits.capture_strip()
        self.lift()
        self.focus_force()
        if strip is None:
            messagebox.showwarning(APP_NAME, t("capture_none"), parent=self)
            return
        from PIL import ImageStat
        if ImageStat.Stat(strip[0].convert("L")).mean[0] < 3:
            messagebox.showwarning(APP_NAME, t("capture_black"), parent=self)
        self.strip = strip
        self._redraw()

    # ---------- ajustes ----------
    def _on_slider(self, key: str, value: float):
        self.values[key] = int(round(value))
        self.labels[key].configure(text=str(self.values[key]))
        if self.values["bottom"] <= self.values["top"] + 5:  # mantener un alto mínimo
            self.values["bottom"] = self.values["top"] + 6
            self.sliders["bottom"].set(self.values["bottom"])
            self.labels["bottom"].configure(text=str(self.values["bottom"]))
        self._redraw()

    def _reset(self):
        self.values = dict(portraits.DEFAULT_TOPBAR)
        for k, s in self.sliders.items():
            s.set(self.values[k])
            self.labels[k].configure(text=str(self.values[k]))
        self._redraw()

    def _save(self):
        # Solo se guardan las claves que difieren de los valores por defecto
        diff = {k: v for k, v in self.values.items() if portraits.DEFAULT_TOPBAR.get(k) != v}
        self.app.engine.set("topbar", diff)
        messagebox.showinfo(APP_NAME, t("calib_saved"), parent=self)

    # ---------- dibujo ----------
    def _redraw(self):
        self.view.delete("all")
        self.tiles.delete("all")
        self._photos = []
        if self.strip is None:
            self.view.create_text(self.VIEW_W // 2, 45, text=t("calib_waiting"), fill=MUTED,
                                  font=("Segoe UI", 12))
            return
        img, client = self.strip
        w, h = client[2], client[3]
        s = h / 1080.0
        cx, span = w / 2, self.VIEW_HALF_SPAN * s
        left = max(0, int(cx - span))
        crop = img.crop((left, 0, min(img.width, int(cx + span)), img.height))
        k = self.VIEW_W / crop.width
        view_h = max(1, int(crop.height * k))
        self.view.configure(height=view_h)
        photo = ImageTk.PhotoImage(crop.resize((self.VIEW_W, view_h), Image.LANCZOS), master=self)
        self._photos.append(photo)
        self.view.create_image(0, 0, image=photo, anchor="nw")
        x = 6
        for pid in range(10):
            box = portraits.tile_box(pid, client, self.values)
            color = SLOT_COLORS[pid][1]
            self.view.create_rectangle((box[0] - left) * k, box[1] * k, (box[2] - left) * k, box[3] * k,
                                       outline=color, width=2)
            tile = img.crop(box)
            if tile.width > 0 and tile.height > 0:
                th = 46
                tw = min(84, max(1, round(tile.width * th / tile.height)))
                tp = ImageTk.PhotoImage(tile.resize((tw, th), Image.LANCZOS), master=self)
                self._photos.append(tp)
                self.tiles.create_image(x, 4, image=tp, anchor="nw")
                self.tiles.create_rectangle(x - 1, 3, x + tw, 4 + th, outline=color, width=2)
                self.tiles.create_text(x + tw // 2, 64, text=str(pid), fill=color, font=("Segoe UI", 10, "bold"))
                x += tw + (14 if pid == 4 else 6)


class UpdateDialog(ctk.CTkToplevel):
    """Pregunta si actualizar, descarga con barra de progreso, verifica y reinicia."""

    def __init__(self, app: App, info: updater.UpdateInfo):
        super().__init__(app, fg_color=BG)
        self.app, self.info = app, info
        self.q: queue.Queue = queue.Queue()
        self.title(t("update_title"))
        self.geometry("560x440")
        self.resizable(False, False)
        self.transient(app)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(self, text=t("update_title"), font=font(20, "bold"), text_color=TEXT).grid(
            row=0, column=0, padx=24, pady=(22, 4), sticky="w")
        ctk.CTkLabel(self, text=t("update_text", new=info.version, cur=__version__), font=font(13),
                     text_color=MUTED, wraplength=500, justify="left").grid(row=1, column=0, padx=24, sticky="w")
        notes = ctk.CTkTextbox(self, fg_color=CARD, corner_radius=10, font=font(12), wrap="word")
        notes.grid(row=2, column=0, padx=24, pady=12, sticky="nsew")
        notes.insert("end", f"{t('update_notes')}\n\n{info.notes or '—'}")
        notes.configure(state="disabled")

        self.progress = ctk.CTkProgressBar(self, progress_color=ACCENT)
        self.progress.set(0)
        self.status = ctk.CTkLabel(self, text="", font=font(12), text_color=MUTED)
        self.status.grid(row=4, column=0, padx=24, sticky="w")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.grid(row=5, column=0, padx=24, pady=(8, 20), sticky="e")
        self.buttons = [
            ctk.CTkButton(btns, text=t("update_skip"), width=150, fg_color="transparent", hover_color=CARD2,
                          text_color=MUTED, command=self._skip),
            ctk.CTkButton(btns, text=t("update_later"), width=110, fg_color=CARD2, hover_color=CARD,
                          command=self.destroy),
            ctk.CTkButton(btns, text=t("update_now") if updater.is_frozen() else t("update_open_page"),
                          width=150, fg_color=ACCENT, hover_color=ACCENT_HOVER, command=self._update),
        ]
        for b in self.buttons:
            b.pack(side="left", padx=(8, 0))
        self.bind("<Return>", lambda _e: self._update())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(150, self._focus)

    def _focus(self):
        self.lift()
        self.focus_force()
        self.grab_set()

    def _skip(self):
        self.app.engine.set("skip_version", self.info.version)
        self.destroy()

    def _update(self):
        if not updater.can_self_update(self.info):
            if updater.is_frozen():
                messagebox.showinfo(APP_NAME, t("update_manual"), parent=self)
            webbrowser.open(self.info.page_url)
            self.destroy()
            return
        for b in self.buttons:
            b.configure(state="disabled")
        self.unbind("<Return>")
        self.progress.grid(row=3, column=0, padx=24, pady=(0, 6), sticky="ew")
        self.status.configure(text=t("update_downloading", pct=0))
        threading.Thread(target=self._download, daemon=True).start()
        self.after(100, self._poll)

    def _download(self):
        try:
            path = updater.download(self.info, progress=lambda f: self.q.put(("progress", f)))
            self.q.put(("done", path))
        except Exception as ex:
            log.exception("error descargando la actualización")
            self.q.put(("error", ex))

    def _poll(self):
        try:
            while True:
                kind, data = self.q.get_nowait()
                if kind == "progress":
                    self.progress.set(data)
                    self.status.configure(text=t("update_downloading", pct=int(data * 100)))
                elif kind == "done":
                    self.progress.set(1)
                    self.status.configure(text=t("update_restarting"))
                    self.update_idletasks()
                    self.after(300, lambda p=data: self._install(p))
                    return
                elif kind == "error":
                    messagebox.showerror(APP_NAME, t("update_failed", err=data), parent=self)
                    webbrowser.open(self.info.page_url)
                    self.destroy()
                    return
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _install(self, path):
        try:
            self.app.engine.shutdown()  # libera el puerto para la versión nueva
            updater.install_and_restart(path)
        except Exception as ex:
            log.exception("error instalando la actualización")
            messagebox.showerror(APP_NAME, t("update_failed", err=ex), parent=self)
            webbrowser.open(self.info.page_url)
            self.destroy()
            return
        self.app.destroy()
