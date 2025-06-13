import json                   # Imports the json module for encoding and decoding JSON data
import tkinter as tk          # Imports the tkinter library and aliases it as tk for GUI components
from tkinter import ttk       # Imports themed tkinter widgets (ttk) for a modern look


class TinyLlamaGUI(tk.Tk):    # Defines a new class TinyLlamaGUI, which inherits from Tkinter's main window class
    """Desktop prompt window (GUI-001)."""

    def __init__(self) -> None:           # Constructor method, initializes the GUI
        super().__init__()                # Calls the parent (tk.Tk) constructor
        self.title("TinyLlama Prompt")    # Sets the window title

        # 5 rows × 80 cols prompt box
        self.prompt_box = tk.Text(self, width=80, height=5, wrap="word")  # Creates a multi-line Text widget for prompt input
        self.prompt_box.pack(padx=10, pady=10)                            # Adds the prompt box to the window with padding

        # Ctrl+Enter == Send
        self.prompt_box.bind("<Control-Return>", self._on_send_event)     # Binds Ctrl+Enter key event to the _on_send_event handler

        self.send_btn = ttk.Button(self, text="Send", command=self._on_send)  # Creates a Send button that calls _on_send when clicked
        self.send_btn.pack(padx=10, pady=5)                                   # Adds the Send button to the window with padding

    # ————— helpers ————
    @staticmethod
    def build_payload(text: str) -> str:                  # Static method to build a JSON payload from the input text
        """Return JSON string preserving newlines."""
        return json.dumps({"prompt": text})               # Converts a dictionary with the prompt text into a JSON-formatted string

    # ————— handlers ————
    def _on_send_event(self, event):          # Event handler for Ctrl+Enter
        self._on_send()                      # Calls the main send handler
        return "break"                       # Prevents Tkinter from adding a newline on Ctrl+Enter

    def _on_send(self):                      # Main send handler for both button click and Ctrl+Enter
        text = self.prompt_box.get("1.0", tk.END).rstrip("\n")  # Retrieves all text from the prompt box, strips trailing newlines
        payload = self.build_payload(text)                      # Builds a JSON payload from the entered text
        print(payload)                                          # Prints the payload (for now, as a stub for sending to API)


if __name__ == "__main__":           # Runs this code block only if the file is executed directly
    TinyLlamaGUI().mainloop()        # Creates an instance of TinyLlamaGUI and starts the Tkinter event loop
