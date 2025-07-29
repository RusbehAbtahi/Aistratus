"""
TinyLlamaView – pure Tkinter presentation layer.
Implements all widgets and UI helpers; **no business logic or HTTP calls**.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, Literal, Any

# _EventKey defines the exact allowed strings for callback keys.
_EventKey = Literal[
    "send",
    "stop",
    "login",
    "idle_changed",
    # >>> ADD >>> backend selection event
    "backend_changed",
    # <<< ADD <<<
]

class TinyLlamaView:
    def __init__(self) -> None:
        # Main application window (Tk root object)
        self.root = tk.Tk()
        self.root.title("TinyLlama Prompt")

        # Multiline text input for user prompt (the main typing area)
        self.prompt_box = tk.Text(self.root, width=80, height=5, wrap="word")
        self.prompt_box.pack(padx=10, pady=10)

        # Control bar holds buttons and spinbox
        ctrl = ttk.Frame(self.root)
        ctrl.pack(fill="x", padx=10, pady=5)

        # "Send" button for submitting prompt
        self.send_btn = ttk.Button(ctrl, text="Send")
        self.send_btn.pack(side="left")

        # >>> ADD >>> login button for authentication
        self.login_btn = ttk.Button(ctrl, text="Login")
        self.login_btn.pack(side="left", padx=(5, 0))
        # <<< ADD <<<

        # >>> ADD >>> Username & Password inputs
        ttk.Label(ctrl, text="Username:").pack(side="left", padx=(15, 2))
        self.username_entry = ttk.Entry(ctrl, width=20)
        self.username_entry.pack(side="left", padx=(0, 5))

        ttk.Label(ctrl, text="Password:").pack(side="left", padx=(5, 2))
        self.password_entry = ttk.Entry(ctrl, width=20, show="*")
        self.password_entry.pack(side="left", padx=(0, 5))
        # <<< ADD <<<

        # Spinner: shows activity while sending (hidden by default)
        self.spinner = ttk.Progressbar(ctrl, mode="indeterminate", length=120)

        # >>> ADD >>> backend dropdown
        ttk.Label(ctrl, text="Backend:").pack(side="left", padx=(15, 2))
        self.backend_var = tk.StringVar(value="AWS TinyLlama")
        self.backend_menu = ttk.Combobox(
            ctrl,
            textvariable=self.backend_var,
            values=["AWS TinyLlama", "OpenAI GPT-3.5"],
            state="readonly",
            width=18
        )
        self.backend_menu.pack(side="left", padx=(0, 4))
        self.backend_menu.bind(
            "<<ComboboxSelected>>",
            lambda e: self._on_backend_select(self.backend_var.get())
        )
        # <<< ADD <<<

        # >>> ADD >>> authentication status lamp
        self.auth_lamp = tk.Canvas(ctrl, width=16, height=16, highlightthickness=1, highlightbackground="black")
        self.auth_lamp.pack(side="left", padx=(5, 0))
        self.update_auth_lamp("off")   # use mapped color instead of invalid "off"
        # <<< ADD <<<

        # "Idle-min" label and spinbox for selecting idle timeout in minutes
        ttk.Label(ctrl, text="Idle-min:").pack(side="left", padx=(15, 2))
        self.idle_spin = ttk.Spinbox(ctrl, from_=1, to=30, width=3)
        self.idle_spin.pack(side="left")

        # "Stop GPU" button for stopping GPU (red button)
        self.stop_btn = tk.Button(
            ctrl, text="Stop GPU", bg="#d9534f", fg="white"
        )
        self.stop_btn.pack(side="right", padx=(10, 0))

        # Cost label (shows current cost)
        self.cost_var = tk.StringVar(value="€ --.--")
        self.cost_label = tk.Label(self.root, textvariable=self.cost_var, font=("TkDefaultFont", 9))
        self.cost_label.pack(pady=(0, 10))

        # Keyboard shortcut: Ctrl+Enter triggers send
        self.prompt_box.bind("<Control-Return>", self._on_ctrl_enter)

        # _callbacks: stores event-to-function mapping, filled by bind()
        self._callbacks: Dict[_EventKey, Callable] = {}

    def bind(self, controller_map: Dict[_EventKey, Callable[..., Any]]) -> None:
        """
        Connects UI button events and spinbox changes to controller callbacks.
        controller_map is a dictionary like {"send": ..., "stop": ..., ...}
        """
        self._callbacks = controller_map
        # Bind "Send" button to its handler
        self.send_btn.config(command=self._on_send_click)
        # Bind "Login" button to its handler
        self.login_btn.config(command=self._on_login_click)
        # Bind "Stop GPU" button to its handler
        self.stop_btn.config(command=self._on_stop_click)
        # Bind Idle spinbox change to its handler
        self.idle_spin.config(command=self._on_idle_spin_change)

    def get_prompt(self) -> str:
        """
        Returns the text entered in the prompt box, stripping trailing newlines.
        """
        return self.prompt_box.get("1.0", tk.END).rstrip("\n")

    def clear_prompt(self) -> None:
        """
        Clears the user input area.
        """
        self.prompt_box.delete("1.0", tk.END)

    def update_cost(self, eur: float) -> None:
        """
        Updates the cost label. Changes color depending on the value.
        """
        self.cost_var.set(f"€ {eur:,.2f} (today)")
        if eur > 15:
            color = "#d9534f"
        elif eur > 10:
            color = "#f0ad4e"
        else:
            color = "#212529"
        self.cost_label.config(fg=color)

    def append_output(self, text: str) -> None:
        """
        Appends output text to the output pane (creating it the first time).
        """
        if not hasattr(self, "_out_pane"):
            self._out_pane = tk.Text(self.root, width=80, height=15, state="disabled")
            self._out_pane.pack(padx=10, pady=(10, 0), fill="both", expand=True)
        self._out_pane.config(state="normal")
        self._out_pane.insert(tk.END, text + "\n")
        self._out_pane.yview_moveto(1.0)
        self._out_pane.config(state="disabled")

    def set_busy(self, flag: bool) -> None:
        """
        Shows or hides the spinner, disables/enables the send button.
        """
        if flag:
            self.send_btn.state(["disabled"])
            self.spinner.pack(side="left", padx=10)
            self.spinner.start(10)
        else:
            self.spinner.stop()
            self.spinner.pack_forget()
            self.send_btn.state(["!disabled"])

    # -------------------- UI Event Handlers (private) --------------------------

    def _on_send_click(self) -> None:
        if cb := self._callbacks.get("send"):
            cb(self.get_prompt())

    def _on_login_click(self) -> None:
        self.update_auth_lamp("pending")
        if cb := self._callbacks.get("login"):
            cb()

    def _on_stop_click(self) -> None:
        if cb := self._callbacks.get("stop"):
            cb()

    def _on_ctrl_enter(self, _event) -> str:
        self._on_send_click()
        return "break"

    def _on_idle_spin_change(self) -> None:
        try:
            minutes = int(self.idle_spin.get())
            if cb := self._callbacks.get("idle_changed"):
                cb(minutes)
        except ValueError:
            messagebox.showerror("Idle-minutes", "Value must be an integer 1–30")

    def _on_backend_select(self, selection: str) -> None:
        if cb := self._callbacks.get("backend_changed"):
            cb(selection)
        # reset lamp when backend changes
        self.update_auth_lamp("off")

    # -------------------- Lamp helper methods -------------------------------

    def _draw_lamp(self, color: str) -> None:
        """
        Internal: draw the auth status lamp with given fill color.
        """
        self.auth_lamp.delete("all")
        self.auth_lamp.create_oval(2, 2, 14, 14, fill=color)

    def update_auth_lamp(self, status: str) -> None:
        """
        Update authentication lamp.
        status in {"off","pending","ok","error"}.
        """
        colors = {"off": "grey", "pending": "yellow", "ok": "green", "error": "red"}
        self._draw_lamp(colors.get(status, "grey"))

    # >>> ADD >>> -----------------------------------------------------------------
    def bind_state(self, state) -> None:
        """
        Subscribe this view to AppState so the authentication lamp
        automatically reflects every change to ``auth_status``.
        """
        state.subscribe("auth_status", self.update_auth_lamp)
    # <<< ADD <<<

    # >>> ADD >>> helper getters for credentials
    def get_username(self) -> str:
        return self.username_entry.get().strip()

    def get_password(self) -> str:
        return self.password_entry.get()
    # <<< ADD <<<

# -------------------- Manual test run: open window, no backend required -------------------
if __name__ == "__main__":
    def noop(*_a, **_kw): ...
    v = TinyLlamaView()
    v.bind({
        "send": noop,
        "stop": noop,
        "login": noop,
        "idle_changed": noop,
        "backend_changed": lambda b: print("backend ->", b),
    })
    v.root.mainloop()
