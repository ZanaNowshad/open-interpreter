"""Regression tests for the Agent terminology facade."""

from __future__ import annotations

import importlib

import pytest

pytest.importorskip("open_interpreter")
pytest.importorskip("open_agent")

from open_agent import AsyncAgent, OpenAgent, agent, computer
from open_interpreter import AsyncInterpreter, OpenInterpreter


def test_runtime_aliases_share_same_objects() -> None:
    """Agent entrypoints should be thin aliases over interpreter ones."""

    from open_interpreter.runtime import computer as interpreter_computer
    from open_interpreter.runtime import interpreter as interpreter_singleton

    assert OpenAgent is OpenInterpreter
    assert AsyncAgent is AsyncInterpreter
    assert agent is interpreter_singleton
    assert computer is interpreter_computer


def test_submodule_aliases_point_to_same_module() -> None:
    """The mirrored namespace should reuse the original module objects."""

    agent_registry = importlib.import_module("open_agent.services.registry")
    interpreter_registry = importlib.import_module("open_interpreter.services.registry")

    assert agent_registry is interpreter_registry
