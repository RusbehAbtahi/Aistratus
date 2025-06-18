gh issue create \
  --title "GUI-007: Refactor Desktop Codebase into Modular MVC + Services Architecture" \
  --body "$(cat <<'EOF'
This issue tracks the structural refactor of the TinyLlama desktop GUI into a modular, professional architecture, replacing app.py with clean separation of view, controllers, shared state, and services as confirmed in Epic 1.

---

## 1 · Problem / Motivation  
`app.py` has grown into a 160-line “god-class” that mixes Tkinter widgets, HTTP calls, threading, persistence, and cost polling. This makes maintenance difficult, unit-tests brittle, and AI-assisted edits risky. Before adding Cognito auth, EC2 job polling, or mobile clients, the GUI must be split into clear, isolated modules.

## 2 · Goal (Definition of Done)  
Replace the monolith with the **TinyLlama Desktop Modular Architecture** confirmed in Epic 1. All existing GUI features (prompt send, spinner, cost label, idle spinbox, GPU stop, output pane, tests) must still work and all 15 tests must pass unchanged or with minimal rewiring.

## 3 · Reference Architecture (UML diagram will be attached manually)

## 4 · New File / Module Layout  

01_src/tinyllama/gui/
├── gui_view.py          # pure Tkinter view
├── thread_service.py    # background scheduling helper
├── app_state.py         # shared dataclass + tiny event bus
├── controllers/
│   ├── prompt_controller.py
│   ├── gpu_controller.py
│   ├── cost_controller.py
│   └── auth_controller.py
└── main.py              # composition root

*Each file should stay under ~80 LOC with one clear responsibility.*

## 5 · Key Responsibilities  

- **TinyLlamaView**: Defines widgets, layout, and exposes lightweight callback slots. No business logic.
- **AppState**: Dataclass fields (`idle_minutes`, `auth_token`, `current_cost`, `history`). Simple observer/callback list for UI updates.
- **ThreadService**: `run_async(fn, *args)` and `schedule(interval, fn)`, marshals back to UI thread.
- **PromptController**: Builds JSON payload, POSTs `/infer`, updates AppState with reply.
- **GPUController**: POSTs `/stop` (and later `/start`), updates AppState.
- **CostController**: Fetches `/cost` every 30s, pushes to AppState.
- **AuthController**: Launches Cognito login, manages tokens, stores in AppState.
- **main.py**: Wires all components and runs `view.mainloop()`.

## 6 · Testing Strategy  

- GUI (view) tests: Only verify that each button’s command points to the proper controller method.
- Controller tests: Pure Python, mock requests, interact with dummy AppState, verify side-effects.
- Integration smoke test (optional): Run main.py with ThreadService in sync mode, simulate prompt, assert updates.

All existing 15 tests must pass or be replaced with equivalent tests in the new layout.

## 7 · Acceptance Criteria  

1. File split matches layout; no Tk imports in controllers; no `requests` inside view.
2. Functionality parity: GUI behaves exactly like before.
3. Thread safety: all background work runs through ThreadService.
4. Tests green: `TL_TESTING=1 pytest 02_tests/gui` passes on all platforms.
5. Documentation: update README.md and architecture docs.
6. Commit log: single feature branch `feature/GUI-007-refactor-mvc`, squash-merge to main.

## 8 · Out of Scope  

- No new cloud features, Cognito flows, or Redis polling—controllers may stub these.
- No change to user-visible UX or styling.
- No dependency on external frameworks (keep pure Tkinter + stdlib).

## 9 · Implementation Checklist  

1. Scaffold `app_state.py` & `thread_service.py` (unit-test first).
2. Copy widgets from `app.py` into `gui_view.py`; strip logic.
3. Create controllers; port logic; inject dependencies via constructor.
4. Build `main.py` to wire everything.
5. Rewrite/relocate tests; remove old monkey-patch hacks.
6. Delete legacy `app.py` once tests pass.
7. Update docs and push PR.

*Attach UML class diagram after ticket creation.*

EOF
)"
