"""
Unit-tests for tinyllama.gui.main.main()

Verifies:
1. All core objects are instantiated.
2. view.bind() receives exactly the 5 required keys.
3. CostController.start_polling() is called once.
4. root.mainloop() is invoked.
"""
import sys
sys.modules.pop("tinyllama.gui.controllers.prompt_controller", None)

import sys
import importlib
from types import ModuleType


# ---------------------------------------------------------------------------
# Stub classes with their own `instances` lists
# ---------------------------------------------------------------------------
class StubView:
    instances = []

    def __init__(self):
        type(self).instances.append(self)
        class _Root:
            def __init__(self):
                self.mainloop_called = False
            def title(self, *args, **kwargs):
                pass
            def mainloop(self):
                self.mainloop_called = True

        self.root = _Root()
        self._bound_map = None
        self._state_bound = None

    def bind(self, controller_map):
        self._bound_map = controller_map

    def bind_state(self, state):
        self._state_bound = state


class StubState:
    def __init__(self):
        pass
    def set_idle(self, minutes):
        pass
    def set_backend(self, name):
        pass


class StubService:
    def __init__(self, *args, **kwargs):
        pass


class StubPromptController:
    def __init__(self, state, service, view):
        pass
    def on_send(self, prompt):
        pass


class StubCostController:
    instances = []

    def __init__(self, state, service, view):
        type(self).instances.append(self)
        self.start_polling_called = False
    def start_polling(self):
        self.start_polling_called = True


class StubGpuController:
    def __init__(self, state, service, view):
        pass
    def on_stop_gpu(self):
        pass


class StubAuthController:
    def __init__(self, state, service, view):
        pass
    def on_login(self):
        pass


# ---------------------------------------------------------------------------
# Inject stubs before importing main
# ---------------------------------------------------------------------------
def _inject_stubs(monkeypatch):
    def _mod(path, attr, obj):
        m = ModuleType(path)
        setattr(m, attr, obj)
        sys.modules[path] = m

    # Core modules
    _mod("tinyllama.gui.gui_view", "TinyLlamaView", StubView)
    _mod("tinyllama.gui.app_state", "AppState", StubState)
    _mod("tinyllama.gui.thread_service", "ThreadService", StubService)

    # Controllers package
    pkg = ModuleType("tinyllama.gui.controllers")
    sys.modules["tinyllama.gui.controllers"] = pkg

    # Controller modules
    _mod("tinyllama.gui.controllers.prompt_controller", "PromptController", StubPromptController)
    _mod("tinyllama.gui.controllers.cost_controller", "CostController", StubCostController)
    _mod("tinyllama.gui.controllers.gpu_controller", "GpuController", StubGpuController)
    _mod("tinyllama.gui.controllers.auth_controller", "AuthController", StubAuthController)


def test_main_happy_path(monkeypatch):
    """
    Happy-path: main.main() must
    - Instantiate AppState, View, Service, 4 controllers.
    - Bind view.bind with keys:
      send, stop, login, idle_changed, backend_changed.
    - Call CostController.start_polling() once.
    - Invoke root.mainloop().
    """
    # Arrange
    _inject_stubs(monkeypatch)
    main_mod = importlib.import_module("tinyllama.gui.main")

    # Act
    main_mod.main()

    # Assert exactly one view
    assert len(StubView.instances) == 1, "Expected one StubView instance"
    view = StubView.instances[0]

    # Callback map keys
    expected = {"send", "stop", "login", "idle_changed", "backend_changed"}
    assert view._bound_map is not None, "view.bind() was never called"
    assert set(view._bound_map.keys()) == expected

    # State bound
    assert view._state_bound is not None, "view.bind_state() was not called"

    # Cost polling
    assert len(StubCostController.instances) == 1, "Expected one CostController"
    cost_ctrl = StubCostController.instances[0]
    assert cost_ctrl.start_polling_called, "CostController.start_polling() was not invoked"

    # GUI loop
    assert view.root.mainloop_called, "mainloop() was not executed"
