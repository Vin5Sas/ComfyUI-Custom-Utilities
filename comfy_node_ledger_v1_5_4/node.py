"""
node.py - ComfyNodeLedger

The main ComfyUI node class. Defines all inputs, outputs, and execution logic.

Inputs:
  filename_prefix (STRING, required)  - save path + filename stem
  header          (STRING, optional)  - banner text at top of log
  export_json     (BOOLEAN)           - write a .json file alongside the log
  export_log      (BOOLEAN)           - write the .md / .txt log file
  log_format      (["md","txt"])      - file extension for the log
  footer          (STRING, optional)  - footer line at end of log
  comments        (STRING, optional)  - appended after footer
  export_override (BOOLEAN)           - write a pipeline-override .json file
  override_type   (combo)             - by_id | by_title | by_type
  watched_nodes   (STRING, hidden)    - JSON-encoded watch list (managed by JS)
  node_preset     (NODE_PRESET, opt)  - accumulated data from a prior Ledger node
  wait_for        (*)                 - optional execution-order dependency

Outputs:
  display_text    (STRING)  - formatted log text for any display node
  node_preset     (STRING)  - serialised NodePreset for chaining
  fileprefix_out  (STRING)  - the filename_prefix value passed through
"""

import json
import logging
import traceback
from typing import Any, Optional

from .formatter import LogFormatter
from .preset import NodePreset
from .watcher import NodeWatcher
from .writer import FileWriteError, FileWriter

log = logging.getLogger(__name__)

_COMFY_OUTPUT_DIR: str = "./output"
try:
    import folder_paths  # type: ignore
    _COMFY_OUTPUT_DIR = folder_paths.get_output_directory()
except ImportError:
    log.warning(
        "folder_paths not found - defaulting output directory to './output'. "
        "This is expected outside a ComfyUI environment."
    )

_FORMATTER = LogFormatter()
_WRITER = FileWriter(_COMFY_OUTPUT_DIR)


class ComfyNodeLedger:
    """
    Comfy Node Ledger - parameter value recorder for ComfyUI workflows.

    The node reads current values from user-selected nodes and parameters, formats them into a human-readable log, and optionally writes .md/.txt, .json, and pipeline-override .json files.
    """

    CATEGORY = "utils"

    @classmethod
    def INPUT_TYPES(cls) -> dict:
        return {
            "required": {
                "filename_prefix": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "e.g. outputs/MyWorkflowLog",
                    },
                ),
            },
            "optional": {
                "header": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional header text",
                    },
                ),
                "export_json":     ("BOOLEAN", {"default": True}),
                "export_log":      ("BOOLEAN", {"default": True}),
                "log_format":      (["md", "txt"],),
                
                # footer
                "footer": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": False,
                        "placeholder": "Optional footer text",
                    },
                ),
                
                # all fixed-height fields group together. LiteGraph allocates extra space for the multiline comments widget 

                "export_override": ("BOOLEAN", {"default": False}),
                "override_type":   (["by_id", "by_title", "by_type"],),
                "comments": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "placeholder": "Optional run notes / comments",
                    },
                ),
                
                # Chaining inputs
                "node_preset": ("NODE_PRESET", {}),
                "wait_for":    ("*", {}),
            },
            "hidden": {
                "prompt":       "PROMPT",
                "extra_pnginfo":"EXTRA_PNGINFO",
                "unique_id":    "UNIQUE_ID",
                # JSON-encoded watch list - managed entirely by the frontend widget.
                # Schema: [{"node_id","params":[...],"class_type","label",
                #           "injected":{param:value}}]
                "watched_nodes": ("STRING", {"default": "[]"}),
            },
        }

    RETURN_TYPES = ("STRING", "NODE_PRESET", "STRING")
    RETURN_NAMES = ("display_text", "node_preset", "fileprefix_out")

    FUNCTION = "execute"
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs) -> float:
        """
        Returning NaN forces re-execution on every run.
        Without this, ComfyUI's output cache skips our node when its own
        widget values haven't changed - even if watched-node values have.
        """
        return float("nan")

    #---execution---

    def execute(
        self,
        filename_prefix: str,
        header: str = "",
        export_json: bool = True,
        export_log: bool = True,
        log_format: str = "md",
        footer: str = "",
        comments: str = "",
        export_override: bool = False,
        override_type: str = "by_id",
        watched_nodes: str = "[]",
        node_preset: Optional[str] = None,
        wait_for: Any = None,
        prompt: Optional[dict] = None,
        extra_pnginfo: Optional[dict] = None,
        unique_id: Optional[str] = None,
    ) -> tuple:

        #---1. Validate required inputs---
        prefix = filename_prefix.strip()
        if not prefix:
            raise ValueError(
                "[Comfy Node Ledger] filename_prefix is required but was not provided."
            )

        #---2. Initialise or deserialise the incoming NodePreset---
        if node_preset:
            try:
                preset = NodePreset.from_dict(json.loads(node_preset))
            except (json.JSONDecodeError, KeyError) as exc:
                log.error("Ledger: failed to deserialise incoming node_preset: %s", exc)
                preset = NodePreset()
        else:
            preset = NodePreset()

        preset.filename_prefix = prefix
        preset.header          = header.strip()
        preset.footer          = footer.strip()
        # Accumulate comments across chained instances - prepend any existing
        # comments from upstream nodes so all are preserved in the final output.
        this_comment = comments.strip()
        if this_comment and preset.comments:
            preset.comments = preset.comments + "\n" + this_comment
        elif this_comment:
            preset.comments = this_comment
        # else: keep upstream comments unchanged when this instance has none
        preset.export_json     = export_json
        preset.export_log      = export_log
        preset.log_format      = log_format
        preset.export_override = export_override
        preset.override_type   = override_type

        #---3. Parse the watched-node list from the frontend widget---
        try:
            watch_specs: list[dict] = json.loads(watched_nodes)
        except json.JSONDecodeError:
            log.warning("Ledger: watched_nodes JSON is malformed - treating as empty.")
            watch_specs = []

        #---4. Capture live values from the ComfyUI prompt graph---
        if prompt and watch_specs:
            watcher = NodeWatcher(prompt)
            new_entries = self._capture_entries(watcher, watch_specs)
            preset.merge_entries(new_entries)

        #---5. Format output text---
        # format_log() routes to proper MD or plain text based on log_format.
        # The display_text output always uses plain text for clean in-node display.
        display_text = _FORMATTER.format_text(preset)
        log_content  = _FORMATTER.format_log(preset)

        #---6. Write files---
        errors: list[str] = []

        if export_log:
            try:
                _WRITER.write_log(prefix, log_content, log_format)
            except FileWriteError as exc:
                errors.append(f"Log write failed: {exc}")
                log.error("Ledger: %s", exc)

        if export_json:
            try:
                _WRITER.write_json(prefix, _FORMATTER.format_json(preset))
            except FileWriteError as exc:
                errors.append(f"JSON write failed: {exc}")
                log.error("Ledger: %s", exc)

        if export_override:
            try:
                override_content = _FORMATTER.format_override_json(preset)
                _WRITER.write_override_json(prefix, override_content)
            except FileWriteError as exc:
                errors.append(f"Override JSON write failed: {exc}")
                log.error("Ledger: %s", exc)

        if errors:
            display_text += "\n\n[LEDGER ERRORS]\n" + "\n".join(errors)

        #---7. Pass the accumulated preset downstream---
        preset_out = json.dumps(preset.to_dict())

        return (display_text, preset_out, prefix)

    #---helpers---

    @staticmethod
    def _capture_entries(
        watcher: NodeWatcher,
        watch_specs: list[dict],
    ) -> list[dict]:
        """
        Iterate the watch list and capture live param values for each node.

        watch_specs schema (from JS widget):
          [{"node_id": "42", "params": ["seed", "denoise"],
            "class_type": "KSampler", "label": "My Sampler",
            "injected": {"control_after_generate": "randomize"}}, ...]

        "injected" carries values that JS captured from the live frontend
        widget but that never appear in the server prompt
        (e.g. control_after_generate, Note node text content).
        """
        entries: list[dict] = []

        for spec in watch_specs:
            node_id  = str(spec.get("node_id", "")).strip()
            params   = spec.get("params", [])
            injected = spec.get("injected", {})

            if not node_id or not params:
                continue

            info = watcher.node_info(node_id)

            # Nodes absent from the server prompt (e.g. Note nodes) fall back
            # to class_type / label embedded in the JS payload.
            class_type = info["class_type"] or spec.get("class_type", "")
            label      = info["label"]      or spec.get("label", "")

            if not class_type and not injected:
                log.warning(
                    "Ledger: node_id %s not in prompt and no injected data - skipping.",
                    node_id,
                )
                continue

            captured = watcher.capture(node_id, params, injected=injected)
            entries.append(
                {
                    "node_id":    node_id,
                    "class_type": class_type,
                    "label":      label,
                    "params":     captured,
                }
            )

        return entries
