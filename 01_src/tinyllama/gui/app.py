# File: 01_src/tinyllama/gui/app.py

import json
import threading
import time
import requests
import os
import configparser
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from datetime import datetime

INI_PATH    = os.path.expanduser("~/.tl-fif.ini")
INI_SECTION = "gui"
_SCROLL_KEY = "scroll"
_IS_TESTING = bool(os.environ.get("TL_TESTING"))

class TinyLlamaGUI(tk.Tk):
    """TinyLlama GUI with prompt box, conversation pane, cost label, idle timeout, and GPU controls."""

    def __init__(self) -> None:
        super().__init__()
        self.title("TinyLlama Prompt")
        self.idle_minutes = self._load_idle_timeout()
        self.cost_var     = tk.StringVar(value="€ --.--")

        # ---------- Output pane (GUI-006) ----------
        self.out_pane = scrolledtext.ScrolledText(self, width=80, height=15, state="disabled")
        self.out_pane.pack(padx=10, pady=(10,0), fill="both", expand=True)
        self.after(100, self._restore_scroll_position)

        # ---------- Prompt ----------
        self.prompt_box = tk.Text(self, width=80, height=5, wrap="word")
        self.prompt_box.pack(padx=10, pady=10)

        # ---------- Controls ----------
        ctrl = ttk.Frame(self); ctrl.pack(fill="x", padx=10, pady=5)

        self.send_btn = ttk.Button(ctrl, text="Send", command=self._on_send)
        self.send_btn.pack(side="left")
        self.spinner  = ttk.Progressbar(ctrl, mode="indeterminate", length=120)

        ttk.Label(ctrl, text="Idle-min:").pack(side="left", padx=(15,2))
        self.idle_spin = ttk.Spinbox(ctrl, from_=1, to=30, width=3, command=self._on_idle_change)
        self.idle_spin.set(str(self.idle_minutes))
        self.idle_spin.pack(side="left")

        self.stop_btn = tk.Button(ctrl, text="Stop GPU", bg="#d9534f", fg="white", command=self._on_stop_gpu)
        self.stop_btn.pack(side="right", padx=(10,0))

        # ---------- Live-cost label (GUI-005) ----------
        self.cost_label = tk.Label(self, textvariable=self.cost_var, font=("TkDefaultFont", 9))
        self.cost_label.pack(pady=(0,10))

        # Key binding
        self.prompt_box.bind("<Control-Return>", self._on_send_event)

        # Start cost poller thread unless in test mode
        if not _IS_TESTING:
            threading.Thread(target=self._cost_poller, daemon=True).start()

    # ---------- persistence ----------
    def _load_idle_timeout(self) -> int:
        cfg = configparser.ConfigParser()
        if cfg.read(INI_PATH) and cfg.has_option(INI_SECTION, "idle"):
            try:
                return max(1, min(30, int(cfg[INI_SECTION]["idle"])))
            except ValueError:
                pass
        return 5

    def _save_idle_timeout(self, minutes: int) -> None:
        self._persist_value("idle", str(minutes))

    def _persist_scroll_position(self) -> None:
        frac = self.out_pane.yview()[0]
        self._persist_value(_SCROLL_KEY, f"{frac:.4f}")

    def _restore_scroll_position(self) -> None:
        cfg = configparser.ConfigParser()
        if cfg.read(INI_PATH) and cfg.has_option(INI_SECTION, _SCROLL_KEY):
            try:
                frac = float(cfg[INI_SECTION][_SCROLL_KEY])
                self.out_pane.yview_moveto(frac)
            except ValueError:
                pass

    def _persist_value(self, key: str, value: str) -> None:
        cfg = configparser.ConfigParser()
        if os.path.exists(INI_PATH):
            cfg.read(INI_PATH)
        if INI_SECTION not in cfg:
            cfg[INI_SECTION] = {}
        cfg[INI_SECTION][key] = value
        with open(INI_PATH, "w") as f:
            cfg.write(f)

    # ---------- live-cost (GUI-005) ----------
    def _cost_poller(self) -> None:
        while True:
            try:
                eur = self._fetch_cost_api()
                if _IS_TESTING:
                    self._set_cost(eur)
                else:
                    self.after(0, lambda e=eur: self._set_cost(e))
            except Exception:
                pass
            if _IS_TESTING:
                break
            time.sleep(30)

    def _fetch_cost_api(self) -> float:
        r = requests.get("http://localhost:8000/cost", timeout=4)
        r.raise_for_status()
        return float(r.json().get("eur", 0.0))

    def _set_cost(self, eur: float) -> None:
        self.cost_var.set(f"€ {eur:,.2f} (today)")
        self.cost_label.config(
            fg="#d9534f" if eur > 15 else "#f0ad4e" if eur > 10 else "#212529"
        )

    # ---------- helpers ----------
    def _set_busy(self, busy: bool) -> None:
        if busy:
            self.send_btn.state(["disabled"])
            self.spinner.pack(side="left", padx=10)
            self.spinner.start(10)
        else:
            self.spinner.stop()
            self.spinner.pack_forget()
            self.send_btn.state(["!disabled"])

    # ---------- event handlers ----------
    def _on_idle_change(self):
        try:
            v = int(self.idle_spin.get())
            if 1 <= v <= 30:
                self.idle_minutes = v
                self._save_idle_timeout(v)
        except ValueError:
            pass

    def _on_send_event(self, event):
        self._on_send()
        return "break"

    def _on_send(self):
        prompt = self.prompt_box.get("1.0", tk.END).rstrip("\n")
        ts = datetime.now().strftime("%H:%M:%S")
        self._append_output(f"[{ts}] USER: {prompt}\n")
        payload = json.dumps({"prompt": prompt, "idle": self.idle_minutes})
        self._set_busy(True)
        threading.Thread(target=self._send_to_api, args=(payload,), daemon=True).start()

    def _on_stop_gpu(self):
        self.stop_btn.config(state="disabled")
        threading.Thread(target=self._stop_gpu_api, daemon=True).start()

    # ---------- backend stubs ----------
    def _send_to_api(self, payload: str):
        time.sleep(1)  # simulate latency
        response = f"Echo: {json.loads(payload)['prompt']}"
        ts = datetime.now().strftime("%H:%M:%S")

        if _IS_TESTING:
            # Append directly so unit tests can see the text immediately
            self._append_output(f"[{ts}] BOT : {response}\n")
            self._set_busy(False)
        else:
            # Normal asynchronous GUI path
            self.after(0, lambda txt=f"[{ts}] BOT : {response}\n": self._append_output(txt))
            self.after(0, lambda: self._set_busy(False))

    def _stop_gpu_api(self):
        try:
            r = requests.post("http://localhost:8000/stop", timeout=8)
            r.raise_for_status()
            self.after(0, lambda: messagebox.showinfo("GPU", "GPU stopped."))
        except Exception as exc:
            # bind exc into lambda to avoid NameError
            self.after(0, lambda err=exc: messagebox.showerror("GPU", f"Stop failed: {err}"))
        finally:
            self.after(0, lambda: self.stop_btn.config(state="normal"))

    # ---------- output pane helper ----------
    def _append_output(self, text: str) -> None:
        self.out_pane.config(state="normal")
        self.out_pane.insert(tk.END, text)
        self.out_pane.yview_moveto(1.0)
        self.out_pane.config(state="disabled")
        self._persist_scroll_position()

if __name__ == "__main__":
    TinyLlamaGUI().mainloop()
