"""
tinyllama_app / main.py
Composition-root: wires state, services, controllers, and the Tkinter view.

Folder layout assumed:

01_src/tinyllama/gui/
    ├── gui_view.py          <-- TinyLlamaView class
    ├── app_state.py         <-- AppState
    ├── thread_service.py    <-- ThreadService
    └── controllers/
         ├── prompt_controller.py
         ├── gpu_controller.py
         ├── cost_controller.py
         └── auth_controller.py
"""

from pathlib import Path
import sys

# --- Import domain modules (they must exist in the package as per UML_Diagram.txt) ----------
from tinyllama.gui.gui_view import TinyLlamaView
from tinyllama.gui.app_state import AppState

from tinyllama.gui.thread_service import ThreadService
from tinyllama.gui.controllers.prompt_controller import PromptController

from tinyllama.gui.controllers.gpu_controller import GpuController

from tinyllama.gui.controllers.auth_controller import AuthController

from tinyllama.gui.controllers.cost_controller import CostController
from dotenv import load_dotenv
load_dotenv()

def main() -> None:
    """Entry point: build objects, bind callbacks, start mainloop."""
    # 1.  Global application state (observable dataclass)
    state = AppState()

    # 2.  Tkinter view (pure widgets)
    view = TinyLlamaView()

    # 3.  Thread / task scheduler (marshals work back to UI thread)
    service = ThreadService(ui_root=view.root)

    # 4.  Controllers — business logic; inject dependencies
    prompt_ctrl = PromptController(state=state, service=service, view=view)

    cost_ctrl = CostController(state=state, service=service, view=view)

    gpu_ctrl = GpuController(state=state, service=service, view=view)

    auth_ctrl = AuthController(state=state, service=service, view=view)

    # 5.  Bind view-events to controller methods or state setters
    # view.bind(
    #     {
    #         "send":  prompt_ctrl.on_send,
    #         "stop":  gpu_ctrl.on_stop_gpu,
    #         "login": auth_ctrl.on_login,
    #         "idle_changed": state.set_idle,   # direct link; simple & safe
    #         "backend_changed": state.set_backend,
    #     }
    # )
    # >>> ADD >>> real binding including login handler
    view.bind(
        {
            "send": prompt_ctrl.on_send,
            "stop": lambda: print("STOP (stub)"),
            "login": auth_ctrl.on_login,  # real login handler
            "idle_changed": state.set_idle,
            "backend_changed": state.set_backend,
        }
    )
    # <<< ADD <<<

    view.bind_state(state)

    # 6.  Kick off background cost polling
    cost_ctrl.start_polling()

    # 7.  Enter Tk main-loop
    view.root.mainloop()


if __name__ == "__main__":
    main()
