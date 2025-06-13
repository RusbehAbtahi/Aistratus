import json, threading, time, requests, tkinter as tk
from tkinter import ttk, messagebox


class TinyLlamaGUI(tk.Tk):
    """Desktop GUI — GUI-001/002/003."""

    # ---------- ctor ----------
    def __init__(self) -> None:
        super().__init__()
        self.title("TinyLlama Prompt")

        # prompt
        self.prompt_box = tk.Text(self, width=80, height=5, wrap="word")
        self.prompt_box.pack(padx=10, pady=10)

        # button frame
        btn_frame = ttk.Frame(self)
        btn_frame.pack(padx=10, pady=5, fill="x")

        # Send button + spinner
        self.send_btn = ttk.Button(btn_frame, text="Send", command=self._on_send)
        self.send_btn.pack(side="left")

        self.spinner = ttk.Progressbar(btn_frame, mode="indeterminate", length=120)

        # NEW: Stop-GPU button
        self.stop_btn = tk.Button(
            btn_frame,
            text="Stop GPU",
            bg="#d9534f",
            fg="white",
            command=self._on_stop_gpu,
        )
        self.stop_btn.pack(side="right", padx=(10, 0))

        # keybinding
        self.prompt_box.bind("<Control-Return>", self._on_send_event)

    # ---------- helpers ----------
    @staticmethod
    def build_payload(text: str) -> str:
        return json.dumps({"prompt": text})

    def _set_busy(self, busy: bool) -> None:
        if busy:
            self.send_btn.state(["disabled"])
            self.spinner.pack(side="left", padx=10)
            self.spinner.start(10)
        else:
            self.spinner.stop()
            self.spinner.pack_forget()
            self.send_btn.state(["!disabled"])

    # ---------- handlers ----------
    def _on_send_event(self, event):
        self._on_send()
        return "break"

    def _on_send(self):
        text = self.prompt_box.get("1.0", tk.END).rstrip("\n")
        payload = self.build_payload(text)
        self._set_busy(True)
        threading.Thread(target=self._send_to_api, args=(payload,), daemon=True).start()

    def _on_stop_gpu(self):
        self.stop_btn.config(state="disabled")
        threading.Thread(target=self._stop_gpu_api, daemon=True).start()

    # ---------- backend ----------
    def _send_to_api(self, payload: str) -> None:
        time.sleep(2)                      # stub
        print(payload)
        self.after(0, lambda: self._set_busy(False))

    def _stop_gpu_api(self) -> None:
        """POST /stop and handle toast + metrics."""
        try:
            r = requests.post("http://localhost:8000/stop", timeout=8)
            r.raise_for_status()
            print("CloudWatch: ManualStops +1")      # stub metric
            self.after(0, lambda: messagebox.showinfo("GPU", "GPU stopped."))
        except Exception as exc:
            self.after(0, lambda exc=exc: messagebox.showerror("GPU", f"Stop failed: {exc}"))
        finally:
            self.after(0, lambda: self.stop_btn.config(state="normal"))


if __name__ == "__main__":
    TinyLlamaGUI().mainloop()
