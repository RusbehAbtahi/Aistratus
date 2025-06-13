import json, threading, time
import tkinter as tk
from tkinter import ttk


class TinyLlamaGUI(tk.Tk):
    """Desktop prompt window (GUI-001 / GUI-002)."""

    # ---------- ctor ----------
    def __init__(self) -> None:
        super().__init__()
        self.title("TinyLlama Prompt")

        # prompt box: 5×80
        self.prompt_box = tk.Text(self, width=80, height=5, wrap="word")
        self.prompt_box.pack(padx=10, pady=10)

        # send button + spinner
        btn_frame = ttk.Frame(self)
        btn_frame.pack(padx=10, pady=5, fill="x")

        self.send_btn = ttk.Button(btn_frame, text="Send", command=self._on_send)
        self.send_btn.pack(side="left")

        self.spinner = ttk.Progressbar(
            btn_frame, mode="indeterminate", length=120
        )                                            # initially hidden

        # Ctrl+Enter == send
        self.prompt_box.bind("<Control-Return>", self._on_send_event)

    # ---------- helpers ----------
    @staticmethod
    def build_payload(text: str) -> str:
        """Return JSON string preserving newlines."""
        return json.dumps({"prompt": text})

    def _set_busy(self, busy: bool) -> None:
        """Enable/disable send button & toggle spinner."""
        if busy:
            self.send_btn.state(["disabled"])
            self.spinner.pack(side="left", padx=10)
            self.spinner.start(10)                  # 10 ms per step
        else:
            self.spinner.stop()
            self.spinner.pack_forget()
            self.send_btn.state(["!disabled"])

    # ---------- handlers ----------
    def _on_send_event(self, event):
        self._on_send()
        return "break"

    def _on_send(self):
        """Read prompt, disable UI, call API thread, re-enable on done."""
        text = self.prompt_box.get("1.0", tk.END).rstrip("\n")
        payload = self.build_payload(text)
        self._set_busy(True)

        # simulate (or later: real) API call in background thread
        threading.Thread(
            target=self._send_to_api, args=(payload,), daemon=True
        ).start()

    # ---------- backend ----------
    def _send_to_api(self, payload: str) -> None:
        """Stub that blocks 2 s then prints payload (simulate inference)."""
        time.sleep(2)                               # 2-s artificial delay
        print(payload)
        # after thread completes, re-enable UI in main thread
        self.after(10, lambda: self._set_busy(False))


if __name__ == "__main__":
    TinyLlamaGUI().mainloop()
