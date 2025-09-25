"""Tests for the modular service registry infrastructure."""

from __future__ import annotations

from typing import Any, Callable

import sys
import types


def _install_stub_module(name: str, **attributes: Any) -> types.ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = types.ModuleType(name)
        sys.modules[name] = module
    for attr, value in attributes.items():
        setattr(module, attr, value)
    return module


_install_stub_module(
    "litellm",
    suppress_debug_info=False,
    REPEATED_STREAMING_CHUNK_LIMIT=0,
    supports_function_calling=lambda *_: False,
    supports_vision=lambda *_: False,
    completion=lambda *_args, **_kwargs: None,
)
_install_stub_module("tokentrim", trim=lambda text, *_args, **_kwargs: text)

if "rich" not in sys.modules:
    rich_module = _install_stub_module("rich", print=lambda *_args, **_kwargs: None)
    markdown_module = types.ModuleType("rich.markdown")
    markdown_module.Markdown = type("Markdown", (), {"__init__": lambda self, *_a, **_k: None})
    rule_module = types.ModuleType("rich.rule")
    rule_module.Rule = type("Rule", (), {"__init__": lambda self, *_a, **_k: None})
    sys.modules["rich.markdown"] = markdown_module
    sys.modules["rich.rule"] = rule_module

_install_stub_module("inquirer", prompt=lambda *_a, **_k: None)
_install_stub_module(
    "psutil",
    virtual_memory=lambda: type("_Mem", (), {"total": 16 * 1024**3})(),
    disk_usage=lambda _path: type("_Disk", (), {"free": 128 * 1024**3})(),
)
_install_stub_module("wget", download=lambda *_a, **_k: None)
_install_stub_module("openai")

interfaces_pkg = types.ModuleType("open_interpreter.interfaces")
interfaces_pkg.__path__ = []
sys.modules.setdefault("open_interpreter.interfaces", interfaces_pkg)

terminal_pkg = types.ModuleType("open_interpreter.interfaces.terminal")
terminal_pkg.__path__ = []
sys.modules.setdefault("open_interpreter.interfaces.terminal", terminal_pkg)

display_module = types.ModuleType("open_interpreter.interfaces.terminal.display")
display_module.display_markdown_message = lambda *_a, **_k: None
sys.modules.setdefault(
    "open_interpreter.interfaces.terminal.display", display_module
)

render_module = types.ModuleType("open_interpreter.interfaces.terminal.render")
render_module.render_message = lambda *_a, **_k: ""
sys.modules.setdefault(
    "open_interpreter.interfaces.terminal.render", render_module
)

local_setup_module = types.ModuleType(
    "open_interpreter.interfaces.terminal.local_setup"
)
local_setup_module.local_setup = lambda interpreter, *_a, **_k: interpreter
sys.modules.setdefault(
    "open_interpreter.interfaces.terminal.local_setup", local_setup_module
)

terminal_interface_module = types.ModuleType(
    "open_interpreter.interfaces.terminal.terminal_interface"
)
terminal_interface_module.terminal_interface = lambda *_a, **_k: []
sys.modules.setdefault(
    "open_interpreter.interfaces.terminal.terminal_interface",
    terminal_interface_module,
)

runtime_module = types.ModuleType("open_interpreter.runtime")
runtime_module.AsyncInterpreter = type("AsyncInterpreter", (), {})
runtime_module.OpenInterpreter = type("OpenInterpreter", (), {})
runtime_module.computer = object()
runtime_module.interpreter = object()
sys.modules.setdefault("open_interpreter.runtime", runtime_module)

pil_pkg = types.ModuleType("PIL")
pil_pkg.__path__ = []
sys.modules.setdefault("PIL", pil_pkg)
image_module = types.ModuleType("PIL.Image")
image_module.Image = type("Image", (), {})
sys.modules.setdefault("PIL.Image", image_module)
pil_pkg.Image = image_module

ipython_pkg = types.ModuleType("IPython")
ipython_pkg.__path__ = []
sys.modules.setdefault("IPython", ipython_pkg)
ipython_display_module = types.ModuleType("IPython.display")
ipython_display_module.display = lambda *_a, **_k: None
sys.modules.setdefault("IPython.display", ipython_display_module)
ipython_pkg.display = ipython_display_module

import pytest

from open_interpreter.services import (
    ServiceKeys,
    ServiceRegistry,
    build_service_context,
)
from open_interpreter.services import defaults as service_defaults


class DummyInterpreter:
    """Minimal interpreter stub used for service resolution tests."""


class _DummyConversationManager(dict):
    def __init__(self, state: Any, history: Any, renderer: Callable[..., Any]) -> None:
        super().__init__()
        self.state = state
        self.history = history
        self.renderer = renderer
        self.messages = []
        self.responding = False
        self.last_messages_count = 0

    def mark_checkpoint(self) -> None:  # pragma: no cover - behaviour unused in tests
        pass

    def persist_history(self, *_: Any, **__: Any) -> None:  # pragma: no cover
        pass

    def new_messages(self) -> list[Any]:  # pragma: no cover
        return []


class _DummyComputer:
    def __init__(self) -> None:
        self.skills = type("Skills", (), {"path": None})()
        self.import_computer_api = False
        self.import_skills = False
        self.save_skills = True

    def run(self, *_: Any, **__: Any) -> list[dict[str, Any]]:  # pragma: no cover
        return []


def _create_stub_registry() -> tuple[ServiceRegistry, dict[str, Any]]:
    registry = ServiceRegistry()

    sentinels: dict[str, Any] = {
        "state": object(),
        "history": object(),
        "capabilities": object(),
        "computer": _DummyComputer(),
    }

    def renderer(*_: Any, **__: Any) -> None:
        return None

    def telemetry(*_: Any, **__: Any) -> None:
        return None

    sentinels["renderer"] = renderer
    sentinels["telemetry"] = telemetry

    registry.register(ServiceKeys.CONVERSATION_STATE, lambda: sentinels["state"])
    registry.register(
        ServiceKeys.CONVERSATION_HISTORY,
        lambda: sentinels["history"],
        singleton=True,
    )
    registry.register(
        ServiceKeys.MESSAGE_RENDERER,
        lambda *, interpreter: sentinels["renderer"],
    )
    registry.register(
        ServiceKeys.CONVERSATION_MANAGER,
        lambda *, state, history, renderer: _DummyConversationManager(
            state, history, renderer
        ),
    )
    registry.register(
        ServiceKeys.EXECUTION_ORCHESTRATOR,
        lambda *, interpreter: ("execution", interpreter),
    )
    registry.register(
        ServiceKeys.CAPABILITY_REGISTRY,
        lambda: sentinels["capabilities"],
        singleton=True,
    )
    registry.register(
        ServiceKeys.TELEMETRY,
        lambda *, interpreter: sentinels["telemetry"],
    )
    registry.register(
        ServiceKeys.COMPUTER,
        lambda *, interpreter: sentinels["computer"],
        singleton=True,
    )
    registry.register(
        ServiceKeys.LLM,
        lambda *, interpreter: {"llm": interpreter},
    )

    return registry, sentinels


def test_registry_copy_preserves_configuration_isolation() -> None:
    registry = ServiceRegistry()
    sentinel = object()

    registry.register("single", lambda: sentinel, singleton=True)
    registry.register("factory", lambda: object())

    # Instantiate the singleton so it exists in the cache prior to copying.
    assert registry.get("single") is sentinel

    clone = registry.copy()

    assert clone is not registry
    assert clone.available_services() == registry.available_services()
    assert clone.get("single") is sentinel

    replacement = object()
    clone.override("factory", lambda: replacement)

    assert registry.get("factory") is not replacement
    assert clone.get("factory") is replacement


def test_build_service_context_applies_overrides_without_mutating_global(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    registry, sentinels = _create_stub_registry()

    monkeypatch.setattr(
        service_defaults,
        "_global_registry",
        registry,
        raising=False,
    )
    monkeypatch.setattr(service_defaults, "_bootstrapped", False, raising=False)

    override_llm = object()

    context = build_service_context(
        interpreter=DummyInterpreter(),
        overrides={
            ServiceKeys.LLM: (lambda *, interpreter: override_llm, True),
        },
    )

    assert context.registry is not registry
    assert context.llm is override_llm
    assert context.conversation_state is sentinels["state"]
    assert context.conversation_history is sentinels["history"]
    assert context.message_renderer is sentinels["renderer"]

    fresh_llm = service_defaults._global_registry.get(
        ServiceKeys.LLM, interpreter=DummyInterpreter()
    )
    assert fresh_llm is not override_llm
