"""Helpers for capturing and reapplying CLI override values."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Tuple


def capture_cli_overrides(
    interpreter: Any,
    args: Any,
    argument_specs: Iterable[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return CLI overrides and attribute targets for later reapplication."""

    overrides: Dict[str, Any] = {}
    attribute_map: Dict[str, Any] = {}
    values = vars(args)

    for spec in argument_specs:
        attribute_spec = spec.get("attribute")
        if not attribute_spec:
            continue

        target_object = attribute_spec.get("object")
        attribute_name = attribute_spec.get("attr_name")

        if attribute_name is None:
            continue

        if target_object is interpreter:
            attribute_map[spec["name"]] = ("interpreter", attribute_name)
        elif target_object is interpreter.llm:
            attribute_map[spec["name"]] = ("llm", attribute_name)
        else:
            attribute_map[spec["name"]] = ("object", target_object, attribute_name)

        value = values.get(spec["name"])
        default = spec.get("default")

        if value is None:
            continue

        if value != default:
            overrides[spec["name"]] = value

    return overrides, attribute_map


def apply_cli_overrides(interpreter: Any) -> None:
    """Reapply stored CLI overrides to the interpreter after profile changes."""

    overrides: Dict[str, Any] = getattr(interpreter, "_cli_overrides", {})
    attribute_map: Dict[str, Any] = getattr(interpreter, "_cli_attribute_map", {})

    for name, value in overrides.items():
        target_spec = attribute_map.get(name)
        if not target_spec:
            continue

        if target_spec[0] == "interpreter":
            setattr(interpreter, target_spec[1], value)
        elif target_spec[0] == "llm":
            setattr(interpreter.llm, target_spec[1], value)
        elif target_spec[0] == "object":
            _, obj, attr_name = target_spec
            setattr(obj, attr_name, value)
