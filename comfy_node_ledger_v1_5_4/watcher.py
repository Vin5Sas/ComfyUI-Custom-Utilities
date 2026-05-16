"""
watcher.py - NodeWatcher

Reads live parameter values from the ComfyUI prompt graph at execution time.
Handles passthrough inputs (values wired from other nodes) and scalar literals.

"""

import logging
from typing import Any

log = logging.getLogger(__name__)

# Node class names whose values must not be watched - their outputs can change
# multiple times within a single queue run (loop constructs, accumulators).
_BLOCKED_CLASS_TYPES: frozenset[str] = frozenset(
    {
        "ForLoopOpen",
        "ForLoopClose",
        "WhileLoopOpen",
        "WhileLoopClose",
        "AccumulateNode",
        "FlowManipulator",
        # Add further loop/control-flow nodes here as the ecosystem evolves
    }
)


def is_blocked_node(class_type: str) -> bool:
    """Return True if this node type should never appear in the watch list."""
    return class_type in _BLOCKED_CLASS_TYPES


class NodeWatcher:
    """
    Resolves parameter values for a set of watched nodes from the prompt graph.

    Args:
        prompt: The full prompt dict passed by ComfyUI to execute()
                (maps node_id --> {class_type, inputs, ...}).
    """

    def __init__(self, prompt: dict[str, Any]) -> None:
        self._prompt = prompt

    #---public---

    def capture(
        self,
        node_id: str,
        param_names: list[str],
        injected: dict | None = None,
    ) -> dict[str, Any]:
        """
        Return {param_name: resolved_value} for the requested params of node_id.

        injected: optional dict of {param_name: value} pre-populated by the
                  JS widget for params that never appear in the server prompt
                  (e.g. control_after_generate, Note node text).
        Missing or unresolvable params are recorded as None.
        """
        injected = injected or {}
        node_data = self._prompt.get(str(node_id))

        # Note/Markdown nodes may have no server-side data at all -
        # their content lives only in the frontend. Fall back gracefully.
        if node_data is None:
            log.warning("NodeWatcher: node_id %s not found in prompt", node_id)
            return {p: injected.get(p) for p in param_names}

        raw_inputs: dict = node_data.get("inputs", {})
        result: dict[str, Any] = {}

        for param in param_names:
            if param in injected:
                # JS-injected value takes priority - it's the live frontend value
                result[param] = injected[param]
            else:
                result[param] = self._resolve(raw_inputs.get(param), depth=0)

        return result

    def node_info(self, node_id: str) -> dict[str, str]:
        """Return {class_type, label} for a node_id, or empty strings on miss."""
        node_data = self._prompt.get(str(node_id), {})
        meta = node_data.get("_meta", {})
        return {
            "class_type": node_data.get("class_type", ""),
            "label": meta.get("title", ""),
        }

    def all_node_ids(self) -> list[str]:
        """Return every node_id present in the prompt (blocked types excluded)."""
        return [
            nid
            for nid, data in self._prompt.items()
            if not is_blocked_node(data.get("class_type", ""))
        ]

    #---internal---

    def _resolve(self, value: Any, depth: int) -> Any:
        """
        Recursively follow ComfyUI link references until a scalar is reached.

        A link reference is represented as [source_node_id, output_index].
        Capping recursion at 8 to prevent runaway traversal in pathological graphs.
        """
        if depth > 8:
            log.debug("NodeWatcher: max link depth reached, returning raw value")
            return value

        # ComfyUI link: ["node_id_str", output_slot_int]
        if isinstance(value, list) and len(value) == 2:
            source_id, _slot = value
            if isinstance(source_id, str) and source_id in self._prompt:
                return self._resolve_source_node(source_id, _slot, depth)

        return value

    def _resolve_source_node(self, node_id: str, slot: int, depth: int) -> Any:
        """
        Pull the output value from a source node.

        For simple passthrough nodes (single-widget types like PrimitiveNode,
        CLIPTextEncode, etc.) we read back from their own inputs, since at
        execute-time their configured widget value is stored there.
        """
        node_data = self._prompt.get(node_id, {})
        inputs: dict = node_data.get("inputs", {})

        # Most primitive/passthrough nodes expose their value as their first input.
        # Attempt to find a non-link scalar input to use as the resolved value.
        for v in inputs.values():
            resolved = self._resolve(v, depth + 1)
            if not isinstance(resolved, list):  # reached a scalar
                return resolved

        # Fallback: return the node label so the log is still informative
        meta = node_data.get("_meta", {})
        return f"<linked: {meta.get('title', node_id)}>"
