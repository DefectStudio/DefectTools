"""The Python/Tk desktop client. All widget access happens on the UI thread."""

from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from .agent import AgentClient, DisconnectedAgent
from .storage import InstanceLock, Message, Session, Store, default_data_dir, timestamp


BG = "#12141c"
PANEL = "#191c27"
SURFACE = "#202432"
BORDER = "#2d3243"
FG = "#eceef6"
MUTED = "#a0a8bd"
ACCENT = "#bba7ff"
ACCENT_DARK = "#2b2542"
GREEN = "#8edbc5"
FONT = "Segoe UI"


def label(parent, text="", *, color=FG, size=10, bold=False, **kwargs):
    return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                    font=(FONT, size, "bold" if bold else "normal"), **kwargs)


def button(parent, text, command, *, primary=False, **kwargs):
    options = dict(
        text=text, command=command, relief="flat", bd=0,
        bg=ACCENT if primary else SURFACE, fg=BG if primary else FG,
        activebackground="#cbbcff" if primary else BORDER,
        activeforeground=BG if primary else FG, disabledforeground=MUTED,
        font=(FONT, 10, "bold"), cursor="hand2", padx=14, pady=9,
        highlightthickness=1, highlightbackground=BORDER,
        highlightcolor=ACCENT,
    )
    options.update(kwargs)
    return tk.Button(parent, **options)


class ScrollPanel(tk.Frame):
    def __init__(self, parent, *, bg):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = tk.Frame(self.canvas, bg=bg)
        self.window = self.canvas.create_window(0, 0, window=self.body, anchor="nw")
        self.body.bind("<Configure>", lambda event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(self.window, width=event.width))

    def wheel(self, event):
        # Bind only this panel and its rows; scrolling chat never scrolls sessions.
        if self.body.winfo_reqheight() > self.canvas.winfo_height():
            amount = -1 if event.delta > 0 or getattr(event, "num", None) == 4 else 1
            self.canvas.yview_scroll(amount * 3, "units")
        return "break"


class DoctorApp:
    def __init__(self, root: tk.Tk, store: Store, agent: AgentClient | None = None):
        self.root = root
        self.store = store
        self.agent = agent or DisconnectedAgent()
        self.sessions = store.list_sessions()
        self.session = self.sessions[0] if self.sessions else Session()
        preferences = store.preferences()
        for session in self.sessions:
            if session.id == preferences.get("last_session"):
                self.session = session
                break
        if not self.sessions:
            store.save(self.session)
            self.sessions.append(self.session)
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.reply_message: Message | None = None
        self.draft_timer = None
        self.poll_timer = None
        self.closed = False
        self.context_menu: tk.Menu | None = None
        self.search = tk.StringVar()
        self.status = tk.StringVar(value="All conversations stay on this computer.")
        self.root.title("Defect Doctor")
        self.root.configure(bg=BG)
        self.root.geometry("1160x800")
        self.root.minsize(940, 660)
        geometry = preferences.get("geometry", "")
        if isinstance(geometry, str) and geometry:
            try:
                self.root.geometry(geometry)
            except tk.TclError:
                pass
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._style()
        self._build()
        self._show_session()
        self.search.trace_add("write", lambda *_: self._render_sessions())
        self.root.bind("<Control-n>", lambda event: self.new_session())
        self.root.bind("<Control-f>", lambda event: self.search_entry.focus_set())
        self.root.bind("<Escape>", lambda event: self.stop_reply() if self.busy else None)
        self._poll()
        if store.warnings:
            self.root.after_idle(lambda: messagebox.showwarning(
                "Some history could not be opened",
                "These files were left untouched:\n\n" + "\n".join(store.warnings[:8]), parent=root,
            ))

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Vertical.TScrollbar", background=BORDER, troughcolor=PANEL,
                        bordercolor=PANEL, arrowcolor=MUTED, width=9)
        style.map("Vertical.TScrollbar", background=[("active", MUTED)])
        if sys.platform == "win32":
            try:
                import ctypes
                self.root.update_idletasks()
                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                enabled = ctypes.c_int(1)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(enabled), 4)
            except (AttributeError, OSError):
                pass

    def _build(self):
        sidebar = tk.Frame(self.root, bg=PANEL, width=260)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Frame(self.root, bg=BORDER, width=1).pack(side="left", fill="y")
        brand = tk.Frame(sidebar, bg=PANEL)
        brand.pack(fill="x", padx=22, pady=(28, 24))
        mark = tk.Canvas(brand, width=34, height=34, bg=PANEL, highlightthickness=0)
        mark.pack(side="left", padx=(0, 10))
        mark.create_oval(1, 1, 33, 33, fill=ACCENT_DARK, outline=ACCENT)
        mark.create_line(17, 10, 17, 24, fill=ACCENT, width=3)
        mark.create_line(10, 17, 24, 17, fill=ACCENT, width=3)
        words = tk.Frame(brand, bg=PANEL)
        words.pack(side="left")
        label(words, "DEFECT", size=9, color=MUTED, bold=True).pack(anchor="w")
        label(words, "Doctor", size=17, bold=True).pack(anchor="w")
        self.new_button = button(sidebar, "+  New session", self.new_session, primary=True)
        self.new_button.pack(fill="x", padx=18, pady=(0, 18))
        label(sidebar, "SEARCH CONVERSATIONS", color=MUTED, size=8, bold=True).pack(anchor="w", padx=22)
        self.search_entry = tk.Entry(sidebar, textvariable=self.search, bg=SURFACE, fg=FG,
                                     insertbackground=ACCENT, relief="flat", font=(FONT, 10),
                                     highlightthickness=1, highlightbackground=BORDER,
                                     highlightcolor=ACCENT)
        self.search_entry.pack(fill="x", padx=18, pady=(8, 22), ipady=8)
        label(sidebar, "RECENT SESSIONS", color=MUTED, size=8, bold=True).pack(anchor="w", padx=22, pady=(0, 10))
        foot = tk.Frame(sidebar, bg=PANEL)
        foot.pack(side="bottom", fill="x", padx=18, pady=18)
        tk.Frame(foot, height=1, bg=BORDER).pack(fill="x", pady=(0, 16))
        label(foot, "LOCAL HISTORY", color=GREEN, size=8, bold=True).pack(anchor="w")
        label(foot, "Saved automatically to disk", color=MUTED, size=9).pack(anchor="w", pady=(5, 12))
        button(foot, "Open history folder", self.open_folder).pack(fill="x")
        self.session_panel = ScrollPanel(sidebar, bg=PANEL)
        self.session_panel.pack(fill="both", expand=True, padx=(10, 4))
        self.session_panel.canvas.bind("<MouseWheel>", self.session_panel.wheel)
        self.session_panel.canvas.bind("<Button-4>", self.session_panel.wheel)
        self.session_panel.canvas.bind("<Button-5>", self.session_panel.wheel)

        main = tk.Frame(self.root, bg=BG)
        main.pack(side="left", fill="both", expand=True)
        header = tk.Frame(main, bg=BG)
        header.pack(fill="x", padx=32, pady=(27, 20))
        left = tk.Frame(header, bg=BG)
        left.pack(side="left", fill="x", expand=True)
        label(left, "YOUR DEFECT SUPPORT DESK", color=MUTED, size=8, bold=True).pack(anchor="w")
        self.title_label = label(left, "New session", size=17, bold=True, anchor="w")
        self.title_label.pack(fill="x", pady=(7, 0))
        self.title_label.bind("<Configure>", lambda event: self.title_label.configure(wraplength=max(250, event.width - 5)))
        tk.Frame(main, height=1, bg=BORDER).pack(fill="x")

        access = tk.Frame(main, bg=PANEL, highlightthickness=1, highlightbackground=BORDER)
        access.pack(fill="x", padx=32, pady=(20, 0))
        access_text = tk.Frame(access, bg=PANEL)
        access_text.pack(side="left", fill="x", expand=True, padx=16, pady=12)
        label(access_text, "Computer access is off", size=10, bold=True).pack(anchor="w")
        label(access_text, "Screen sharing and control will be available after the Hermes bridge is connected.",
              size=9, color=MUTED, anchor="w", wraplength=460, justify="left").pack(anchor="w", pady=(4, 0))
        self.access_button = button(access, "OFF", lambda: None, state="disabled")
        self.access_button.pack(side="right", padx=16)

        self.content = tk.Frame(main, bg=BG)
        self.content.pack(fill="both", expand=True, padx=32, pady=(18, 0))
        self.welcome = tk.Frame(self.content, bg=BG)
        self._build_welcome()
        self.transcript_frame = tk.Frame(self.content, bg=BG)
        self.transcript = tk.Text(self.transcript_frame, bg=BG, fg=FG, relief="flat", bd=0,
                                  wrap="word", font=(FONT, 11), padx=8, pady=14, cursor="arrow",
                                  selectbackground=ACCENT_DARK, selectforeground=FG, state="disabled",
                                  highlightthickness=0, spacing1=4, spacing3=12)
        scroll = ttk.Scrollbar(self.transcript_frame, orient="vertical", command=self.transcript.yview)
        self.transcript.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.transcript.pack(side="left", fill="both", expand=True)
        self.transcript.tag_configure("user", foreground=ACCENT, font=(FONT, 9, "bold"), spacing1=18, spacing3=4)
        self.transcript.tag_configure("assistant", foreground=GREEN, font=(FONT, 9, "bold"), spacing1=18, spacing3=4)
        self.transcript.tag_configure("body", lmargin1=0, lmargin2=0, spacing3=18)
        self.transcript.bind("<Control-a>", self._select_transcript)
        self.transcript.bind("<Control-c>", self._copy_transcript)

        bottom = tk.Frame(main, bg=BG)
        bottom.pack(fill="x", padx=32, pady=(10, 16))
        self.composer_border = tk.Frame(bottom, bg=SURFACE, highlightthickness=1, highlightbackground=BORDER)
        self.composer_border.pack(fill="x")
        self.composer = tk.Text(self.composer_border, height=3, wrap="word", bg=SURFACE, fg=FG,
                                insertbackground=ACCENT, relief="flat", bd=0, padx=16, pady=13,
                                font=(FONT, 11), undo=True, selectbackground=ACCENT_DARK,
                                highlightthickness=0)
        self.composer.pack(fill="x")
        self.composer.bind("<Return>", self._enter)
        self.composer.bind("<Shift-Return>", lambda event: None)
        self.composer.bind("<Control-Return>", self._enter)
        self.composer.bind("<<Modified>>", self._draft_changed)
        self.composer.bind("<FocusIn>", lambda event: self.composer_border.configure(highlightbackground=ACCENT))
        self.composer.bind("<FocusOut>", lambda event: self.composer_border.configure(highlightbackground=BORDER))
        composer_actions = tk.Frame(self.composer_border, bg=SURFACE)
        composer_actions.pack(fill="x", padx=13, pady=(0, 11))
        self.hint = label(composer_actions, "Enter to send  ·  Shift+Enter for a new line" if self.agent.connected
                          else "Enter to save  ·  Shift+Enter for a new line", color=MUTED, size=9)
        self.hint.pack(side="left")
        # Enter submits. A stop control appears only during an agent response.
        self.stop_button = button(composer_actions, "Stop  ■", self.stop_reply, primary=True)

    def _build_welcome(self):
        center = tk.Frame(self.welcome, bg=BG)
        center.place(relx=.5, rely=.48, anchor="center", relwidth=.90)
        label(center, "+", color=ACCENT, size=38).pack()

    def _select_transcript(self, event=None):
        self.transcript.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _copy_transcript(self, event=None):
        try:
            content = self.transcript.get("sel.first", "sel.last")
        except tk.TclError:
            return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        return "break"

    def _render_sessions(self):
        for child in self.session_panel.body.winfo_children():
            child.destroy()
        query = self.search.get().casefold().strip()
        visible = 0
        for session in sorted(self.sessions, key=lambda item: item.updated_at, reverse=True):
            haystack = session.title + " " + " ".join(message.content for message in session.messages)
            if query and query not in haystack.casefold():
                continue
            visible += 1
            selected = session.id == self.session.id
            bg = ACCENT_DARK if selected else PANEL
            row = tk.Frame(self.session_panel.body, bg=bg, cursor="hand2", padx=12, pady=12)
            row.pack(fill="x", pady=3, padx=(0, 4))
            title = label(row, session.title, color=FG if selected else MUTED, size=10,
                          bold=selected, wraplength=194, justify="left", anchor="w")
            title.pack(fill="x")
            count = len(session.messages)
            try:
                date = datetime.fromisoformat(session.updated_at).astimezone().strftime("%b %d")
            except ValueError:
                date = ""
            detail = label(row, f"{date}  ·  {count} message{'s' if count != 1 else ''}", color=MUTED, size=8)
            detail.pack(anchor="w", pady=(6, 0))
            for widget in (row, title, detail):
                widget.bind("<Button-1>", lambda event, item=session: self.select_session(item))
                widget.bind("<Button-3>", lambda event, item=session: self.session_menu(item))
                widget.bind("<MouseWheel>", self.session_panel.wheel)
                widget.bind("<Button-4>", self.session_panel.wheel)
                widget.bind("<Button-5>", self.session_panel.wheel)
        if not visible:
            label(self.session_panel.body, "No matching sessions", color=MUTED, size=10).pack(pady=20)

    def _render_transcript(self):
        if not self.session.messages:
            self.transcript_frame.pack_forget()
            self.welcome.pack(fill="both", expand=True)
            return
        self.welcome.pack_forget()
        self.transcript_frame.pack(fill="both", expand=True)
        self.transcript.configure(state="normal")
        self.transcript.delete("1.0", "end")
        for message in self.session.messages:
            time = datetime.fromisoformat(message.created_at).astimezone().strftime("%I:%M %p").lstrip("0")
            who = "YOU" if message.role == "user" else self.agent.name.upper()
            self.transcript.insert("end", f"{who}    {time}\n", message.role)
            self.transcript.insert("end", message.content + "\n", "body")
        self.transcript.configure(state="disabled")
        self.transcript.see("end")

    def _show_session(self):
        self.title_label.configure(text=self.session.title)
        self.composer.delete("1.0", "end")
        self.composer.insert("1.0", self.session.draft)
        self.composer.edit_modified(False)
        self.composer.edit_reset()
        self._render_sessions()
        self._render_transcript()
        self.composer.focus_set()

    def _draft_changed(self, event=None):
        if not self.composer.edit_modified():
            return
        self.composer.edit_modified(False)
        if self.draft_timer is not None:
            self.root.after_cancel(self.draft_timer)
        self.draft_timer = self.root.after(400, self._save_draft)

    def _persist(self, session: Session) -> bool:
        try:
            self.store.save(session)
            return True
        except OSError as exc:
            self.status.set("Could not save to disk. Keep this window open and try again.")
            messagebox.showerror("History could not be saved", str(exc), parent=self.root)
            return False

    def _save_draft(self) -> bool:
        if self.draft_timer is not None:
            self.root.after_cancel(self.draft_timer)
            self.draft_timer = None
        draft = self.composer.get("1.0", "end-1c")
        old = self.session.draft
        self.session.draft = draft
        # Also retries an earlier failed reply save before leaving this session.
        if not self._persist(self.session):
            self.session.draft = old
            return False
        return True

    def select_session(self, session: Session):
        if self.busy or session.id == self.session.id or not self._save_draft():
            return
        self.session = session
        self.status.set("Conversation restored from this computer.")
        self._show_session()

    def new_session(self):
        if self.busy or not self._save_draft():
            return
        if not self.session.messages and not self.session.draft:
            self.search.set("")
            self.composer.focus_set()
            return
        session = Session()
        if not self._persist(session):
            return
        self.session = session
        self.sessions.append(session)
        self.search.set("")
        self.status.set("New session. Your other conversations are saved.")
        self._show_session()

    def _enter(self, event=None):
        self.submit()
        return "break"

    def submit(self):
        if self.busy:
            self.stop_reply()
            return
        content = self.composer.get("1.0", "end-1c").strip()
        if not content:
            return
        # Keep the composer and the in-memory model intact if the write fails.
        old_title, old_updated, old_draft = self.session.title, self.session.updated_at, self.session.draft
        self.session.add("user", content)
        self.session.draft = ""
        if not self._persist(self.session):
            self.session.messages.pop()
            self.session.title, self.session.updated_at, self.session.draft = old_title, old_updated, old_draft
            return
        if self.draft_timer is not None:
            self.root.after_cancel(self.draft_timer)
            self.draft_timer = None
        self.composer.delete("1.0", "end")
        self.composer.edit_modified(False)
        self.composer.edit_reset()
        self.title_label.configure(text=self.session.title)
        self._render_sessions()
        self._render_transcript()
        if not self.agent.connected:
            self.status.set("Saved locally. Hermes isn’t connected yet, so no message has been sent.")
            return
        self._start_reply()

    def _start_reply(self):
        self.busy = True
        self.cancel = threading.Event()
        self.reply_message = None
        self.new_button.configure(state="disabled")
        self.composer.configure(state="disabled")
        self.stop_button.configure(text="Stop  ■")
        self.stop_button.pack(side="right")
        self.status.set(f"{self.agent.name} is replying…")
        messages = tuple(Message(item.role, item.content, item.created_at, item.id) for item in self.session.messages)
        cancel = self.cancel

        def work():
            try:
                for delta in self.agent.reply(messages, cancel):
                    if cancel.is_set():
                        break
                    if not isinstance(delta, str):
                        raise TypeError("The agent adapter returned a non-text response.")
                    if delta:
                        self.events.put(("chunk", delta))
                self.events.put(("done", None))
            except Exception as exc:
                self.events.put(("error", str(exc)))

        threading.Thread(target=work, daemon=True, name="defect-doctor-agent").start()

    def _poll(self):
        if self.closed:
            return
        changed = False
        completed = None
        for _ in range(200):
            try:
                kind, value = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "chunk" and not self.cancel.is_set():
                if self.reply_message is None:
                    self.reply_message = self.session.add("assistant", "")
                self.reply_message.content += str(value)
                self.session.updated_at = timestamp()
                changed = True
            elif kind in ("done", "error"):
                completed = (kind, value)
                break
        if changed:
            self._render_transcript()
        if completed is not None:
            self.busy = False
            self.new_button.configure(state="normal")
            self.composer.configure(state="normal")
            self.stop_button.pack_forget()
            kind, value = completed
            saved = self._persist(self.session)
            self._render_sessions()
            if saved:
                if kind == "error":
                    self.status.set(f"Agent connection failed: {value}. Your conversation is saved.")
                    messagebox.showerror("Agent connection failed", f"{value}\n\nYour conversation is saved.", parent=self.root)
                elif self.cancel.is_set():
                    self.status.set("Reply stopped. The conversation is saved.")
                elif self.reply_message is None:
                    self.status.set("The agent returned an empty reply. Your message is saved.")
                else:
                    self.status.set("Conversation saved on this computer.")
            self.composer.focus_set()
        self.poll_timer = self.root.after(60, self._poll)

    def stop_reply(self):
        if self.busy:
            self.cancel.set()
            self.status.set("Stopping reply…")
            self.stop_button.configure(text="Stopping…")

    def session_menu(self, session: Session):
        if self.busy:
            return
        self.select_session(session)
        if self.session.id != session.id:
            return
        if self.context_menu is None:
            self.context_menu = tk.Menu(self.root, tearoff=False, bg=SURFACE, fg=FG,
                                        activebackground=ACCENT_DARK, activeforeground=FG, bd=0)
            self.context_menu.add_command(label="Rename session…", command=self.rename_session)
            self.context_menu.add_command(label="Export conversation…", command=self.export_session)
        menu = self.context_menu
        try:
            menu.tk_popup(self.root.winfo_pointerx(), self.root.winfo_pointery())
        finally:
            menu.grab_release()

    def rename_session(self):
        if self.busy:
            return
        title = simpledialog.askstring("Rename session", "Session name:", initialvalue=self.session.title, parent=self.root)
        if not title or not title.strip():
            return
        old = self.session.title
        self.session.title = " ".join(title.split())[:100]
        if self._persist(self.session):
            self.title_label.configure(text=self.session.title)
            self._render_sessions()
        else:
            self.session.title = old

    def export_session(self):
        path = filedialog.asksaveasfilename(parent=self.root, title="Export conversation",
                                           defaultextension=".txt", filetypes=[("Text file", "*.txt")],
                                           initialfile="defect-doctor-conversation.txt")
        if not path:
            return
        lines = [self.session.title, "=" * len(self.session.title), ""]
        for message in self.session.messages:
            who = "You" if message.role == "user" else self.agent.name
            lines.extend([f"{who} ({message.created_at})", message.content, ""])
        try:
            Path(path).write_text("\n".join(lines), encoding="utf-8")
            self.status.set("Conversation exported.")
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc), parent=self.root)

    def open_folder(self):
        try:
            if sys.platform == "win32":
                os.startfile(self.store.directory)
            else:
                subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(self.store.directory)])
        except OSError as exc:
            messagebox.showerror("Could not open history folder", str(exc), parent=self.root)

    def close(self):
        if not self._save_draft():
            return
        try:
            self.store.save_preferences({"last_session": self.session.id, "geometry": self.root.geometry()})
        except OSError as exc:
            messagebox.showerror("Could not save settings", str(exc), parent=self.root)
            return
        self.cancel.set()
        self.closed = True
        if self.poll_timer is not None:
            self.root.after_cancel(self.poll_timer)
        self.root.destroy()


def main(argv: list[str] | None = None):
    parser = argparse.ArgumentParser(description="Defect Doctor desktop chat client")
    parser.add_argument("--data-dir", type=Path, help="Override the local history directory")
    args = parser.parse_args(argv)
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError, OSError):
            pass
    root = tk.Tk()
    root.withdraw()
    lock = None
    try:
        store = Store(args.data_dir or default_data_dir())
        lock = InstanceLock(store.directory)
        DoctorApp(root, store)
        root.deiconify()
        root.mainloop()
    except (OSError, RuntimeError) as exc:
        messagebox.showerror("Defect Doctor could not start", str(exc), parent=root)
        root.destroy()
    finally:
        if lock is not None:
            lock.close()


if __name__ == "__main__":
    main()
