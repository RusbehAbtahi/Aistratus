#  app.py  – Desktop GUI — GUI-001…005  (test-safe cost-poller)
import json, threading, time, requests, os, configparser, tkinter as tk
from tkinter import ttk, messagebox

INI_PATH    = os.path.expanduser("~/.tl-fif.ini")
INI_SECTION = "gui"
_IS_TESTING = bool(os.environ.get("TL_TESTING"))

class TinyLlamaGUI(tk.Tk):
    """TinyLlama desktop GUI (prompt, spinner, stop-GPU, idle-timeout, live cost)."""

    def __init__(self) -> None:
        super().__init__()
        self.title("TinyLlama Prompt")
        self.idle_minutes = self._load_idle_timeout()
        self.cost_var     = tk.StringVar(value="€ --.--")

        # ------- Prompt -------
        self.prompt_box = tk.Text(self, width=80, height=5, wrap="word")
        self.prompt_box.pack(padx=10, pady=10)

        # ------- Controls -------
        ctrl = ttk.Frame(self); ctrl.pack(fill="x", padx=10, pady=5)
        self.send_btn = ttk.Button(ctrl, text="Send", command=self._on_send); self.send_btn.pack(side="left")
        self.spinner  = ttk.Progressbar(ctrl, mode="indeterminate", length=120)

        ttk.Label(ctrl, text="Idle-min:").pack(side="left", padx=(15,2))
        self.idle_spin = ttk.Spinbox(ctrl, from_=1, to=30, width=3, command=self._on_idle_change)
        self.idle_spin.set(str(self.idle_minutes)); self.idle_spin.pack(side="left")

        self.stop_btn = tk.Button(ctrl, text="Stop GPU", bg="#d9534f", fg="white", command=self._on_stop_gpu)
        self.stop_btn.pack(side="right", padx=(10,0))

        self.cost_label = tk.Label(self, textvariable=self.cost_var, font=("TkDefaultFont", 9))
        self.cost_label.pack(pady=(0,10))

        self.prompt_box.bind("<Control-Return>", self._on_send_event)

        # cost-poller thread (disabled during tests)
        if not _IS_TESTING:
            threading.Thread(target=self._cost_poller, daemon=True).start()

    # ---------- persistence ----------
    def _load_idle_timeout(self) -> int:
        cfg = configparser.ConfigParser()
        if cfg.read(INI_PATH) and cfg.has_option(INI_SECTION, "idle"):
            try:
                v = int(cfg[INI_SECTION]["idle"]); return max(1, min(30, v))
            except ValueError:
                pass
        return 5

    def _save_idle_timeout(self, minutes: int) -> None:
        cfg = configparser.ConfigParser()
        if os.path.exists(INI_PATH): cfg.read(INI_PATH)
        if INI_SECTION not in cfg: cfg[INI_SECTION] = {}
        cfg[INI_SECTION]["idle"] = str(minutes)
        with open(INI_PATH, "w") as f: cfg.write(f)

    # ---------- helpers ----------
    def _set_busy(self, busy: bool) -> None:
        if busy:
            self.send_btn.state(["disabled"])
            self.spinner.pack(side="left", padx=10); self.spinner.start(10)
        else:
            self.spinner.stop(); self.spinner.pack_forget()
            self.send_btn.state(["!disabled"])

    # ---------- live-cost ----------
    def _cost_poller(self) -> None:
        """Poll CurrentSpendEUR every 30 s; single pass in tests."""
        while True:
            try:
                eur = self._fetch_cost_api()
                if _IS_TESTING:
                    self._set_cost(eur)        # immediate, no Tk event queue
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
        if eur > 15:
            color = "#d9534f"
        elif eur > 10:
            color = "#f0ad4e"
        else:
            color = "#212529"
        self.cost_label.config(fg=color)

    # ---------- handlers ----------
    def _on_idle_change(self):
        try:
            v = int(self.idle_spin.get())
            if 1 <= v <= 30:
                self.idle_minutes = v
                self._save_idle_timeout(v)
        except ValueError:
            pass

    def _on_send_event(self, event):
        self._on_send(); return "break"

    def _on_send(self):
        text = self.prompt_box.get("1.0", tk.END).rstrip("\n")
        payload = json.dumps({"prompt": text, "idle": self.idle_minutes})
        self._set_busy(True)
        threading.Thread(target=self._send_to_api, args=(payload,), daemon=True).start()

    def _on_stop_gpu(self):
        self.stop_btn.config(state="disabled")
        threading.Thread(target=self._stop_gpu_api, daemon=True).start()

    # ---------- backend stubs ----------
    def _send_to_api(self, payload: str):
        time.sleep(2); print(payload)
        self.after(0, lambda: self._set_busy(False))

    def _stop_gpu_api(self):
        try:
            r = requests.post("http://localhost:8000/stop", timeout=8); r.raise_for_status()
            self.after(0, lambda: messagebox.showinfo("GPU", "GPU stopped."))
        except Exception as exc:
            self.after(0, lambda e=exc: messagebox.showerror("GPU", f"Stop failed: {e}"))
        finally:
            self.after(0, lambda: self.stop_btn.config(state="normal"))

if __name__ == "__main__":
    TinyLlamaGUI().mainloop()
