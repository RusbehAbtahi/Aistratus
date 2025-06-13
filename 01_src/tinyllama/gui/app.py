import json, threading, time, requests, os, configparser, tkinter as tk
from tkinter import ttk, messagebox, filedialog

INI_PATH = os.path.expanduser("~/.tl-fif.ini")
INI_SECTION = "gui"

class TinyLlamaGUI(tk.Tk):
    """Desktop GUI — GUI-001…004."""

    # ---------- ctor ----------
    def __init__(self) -> None:
        super().__init__()
        self.title("TinyLlama Prompt")

        # load persisted idle timeout
        self.idle_minutes = self._load_idle_timeout()

        # prompt box
        self.prompt_box = tk.Text(self, width=80, height=5, wrap="word")
        self.prompt_box.pack(padx=10, pady=10)

        # controls frame
        ctrl = ttk.Frame(self); ctrl.pack(fill="x", padx=10, pady=5)

        # Send + spinner
        self.send_btn = ttk.Button(ctrl, text="Send", command=self._on_send)
        self.send_btn.pack(side="left")

        self.spinner = ttk.Progressbar(ctrl, mode="indeterminate", length=120)

        # Idle-timeout spinbox (1-30, default 5)
        ttk.Label(ctrl, text="Idle-min:").pack(side="left", padx=(15,2))
        self.idle_spin = ttk.Spinbox(
            ctrl, from_=1, to=30, width=3,
            command=self._on_idle_change
        )
        self.idle_spin.set(str(self.idle_minutes))
        self.idle_spin.pack(side="left")

        # Stop-GPU
        self.stop_btn = tk.Button(
            ctrl, text="Stop GPU", bg="#d9534f", fg="white",
            command=self._on_stop_gpu
        )
        self.stop_btn.pack(side="right", padx=(10,0))

        # keys
        self.prompt_box.bind("<Control-Return>", self._on_send_event)

    # ---------- persistence ----------
    def _load_idle_timeout(self) -> int:
        cfg = configparser.ConfigParser()
        if cfg.read(INI_PATH) and cfg.has_option(INI_SECTION, "idle"):
            try:
                v = int(cfg[INI_SECTION]["idle"])
                return max(1, min(30, v))
            except ValueError:
                pass
        return 5  # default

    def _save_idle_timeout(self, minutes: int) -> None:
        cfg = configparser.ConfigParser()
        if os.path.exists(INI_PATH):
            cfg.read(INI_PATH)
        if INI_SECTION not in cfg:
            cfg[INI_SECTION] = {}
        cfg[INI_SECTION]["idle"] = str(minutes)
        with open(INI_PATH, "w") as f:
            cfg.write(f)

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

    @staticmethod
    def _metric_manual_stops() -> None:
        print("CloudWatch: ManualStops +1")  # stub

    # ---------- handlers ----------
    def _on_idle_change(self):
        try:
            v = int(self.idle_spin.get())
            if 1 <= v <= 30:
                self.idle_minutes = v
                self._save_idle_timeout(v)
        except ValueError:
            pass  # ignore non-numeric input

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

    # ---------- backend (stubs) ----------
    def _send_to_api(self, payload: str):
        time.sleep(2)     # simulate
        print(payload)
        self.after(0, lambda: self._set_busy(False))

    def _stop_gpu_api(self):
        try:
            r = requests.post("http://localhost:8000/stop", timeout=8)
            r.raise_for_status()
            self._metric_manual_stops()
            self.after(0, lambda: messagebox.showinfo("GPU", "GPU stopped."))
        except Exception as exc:
            self.after(0, lambda exc=exc: messagebox.showerror("GPU", f"Stop failed: {exc}"))
        finally:
            self.after(0, lambda: self.stop_btn.config(state="normal"))


if __name__ == "__main__":
    TinyLlamaGUI().mainloop()
