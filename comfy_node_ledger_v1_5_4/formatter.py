"""
formatter.py - LogFormatter

Converts a NodePreset into:
  - A proper Markdown string (.md) - headings, tables, MD syntax
  - A plain text string (.txt) - original indented format, unchanged
  - A structured dict ready for JSON export

Markdown output (.md):
    # Title

    ---

    **Header text**

    ---

    ### ClassType :: NodeLabel :: NodeID

    | Parameter | Value |
    |-----------|-------|
    | seed      | 42    |

    ---

    *Footer note*

    **Comments:**

    comment text here

Plain text output (.txt) - identical to original format:
    Title
    ----------------------------------------
    Header text
    ----------------------------------------

    [ClassType :: NodeLabel :: NodeID]
      param : value

    ----------------------------------------
    Footer note

    Comments:
      comment text here
"""

import json
from typing import Any

from .preset import NodePreset

_SEP_CHAR    = "-"
_SEP_MIN_LEN = 40


def _separator(reference_text: str = "") -> str:
    """Build a plain-text separator line."""
    width = max(_SEP_MIN_LEN, len(reference_text))
    return _SEP_CHAR * width


class LogFormatter:
    """Stateless formatter. Call format_log(), format_json(), or format_override_json()."""

    #---public---

    def format_log(self, preset: NodePreset) -> str:
        """Route to md or plain-text formatter based on preset.log_format."""
        if preset.log_format == "md":
            return self.format_md(preset)
        return self.format_text(preset)

    def format_md(self, preset: NodePreset) -> str:
        """Return a properly structured Markdown log string."""
        parts: list[str] = []

        title = self._title_from_prefix(preset.filename_prefix)
        if title:
            parts.append(f"# {title}")
            parts.append("")
            parts.append("---")
            parts.append("")

        if preset.header:
            parts.append(f"**{preset.header}**")
            parts.append("")
            parts.append("---")
            parts.append("")

        for entry in preset.entries:
            parts.append(self._format_entry_md(entry))

        parts.append("---")
        parts.append("")

        if preset.footer:
            parts.append(f"*{preset.footer}*")
            parts.append("")

        if preset.comments:
            parts.append("**Comments:**")
            parts.append("")
            for line in preset.comments.splitlines():
                parts.append(line)
            parts.append("")

        return "\n".join(parts)

    def format_text(self, preset: NodePreset) -> str:
        """Return the plain-text log string (original format, fully preserved)."""
        parts: list[str] = []

        sep = _separator(preset.header or preset.filename_prefix)

        title = self._title_from_prefix(preset.filename_prefix)
        if title:
            parts.append(title)
            parts.append(sep)

        if preset.header:
            parts.append(preset.header)
            parts.append(sep)

        parts.append("")

        for entry in preset.entries:
            parts.append(self._format_entry_text(entry))

        parts.append(sep)

        if preset.footer:
            parts.append(preset.footer)

        if preset.comments:
            parts.append("")
            parts.append("Comments:")
            for line in preset.comments.splitlines():
                parts.append(f"  {line}")

        return "\n".join(parts)

    def format_json(self, preset: NodePreset) -> str:
        """Return a JSON string of the captured data."""
        return json.dumps(self._build_json_dict(preset), indent=2, ensure_ascii=False)

    def format_override_json(self, preset: NodePreset) -> str:
        """
        Return a pipeline-override JSON string in the format set by override_type:
          by_id     { "by_id":    { "node_id":    { param: value } } }
          by_title  { "by_title": { "Node Title": { param: value } } }
          by_type   { "by_type":  { "ClassType":  { param: value } } }
        For by_type, multiple nodes of the same class are merged.
        """
        otype = preset.override_type
        if otype == "by_id":
            data = self._build_override_by_id(preset.entries)
        elif otype == "by_title":
            data = self._build_override_by_title(preset.entries)
        else:
            data = self._build_override_by_type(preset.entries)
        return json.dumps(data, indent=2, ensure_ascii=False)

    #---entry formatters---

    @staticmethod
    def _format_entry_md(entry: dict[str, Any]) -> str:
        """Format one watched-node block as a Markdown section with a param table."""
        class_type = entry.get("class_type", "Unknown")
        label      = entry.get("label", "")
        node_id    = entry.get("node_id", "?")
        params: dict = entry.get("params", {})

        heading = (
            f"### {class_type} :: {label} :: {node_id}"
            if label and label != class_type
            else f"### {class_type} :: {node_id}"
        )

        lines = [heading, ""]

        if not params:
            lines.append("*(no parameters selected)*")
        else:
            lines.append("| Parameter | Value |")
            lines.append("|-----------|-------|")
            for key, value in params.items():
                fv  = LogFormatter._format_value(value).replace("|", "\\|")
                fk  = str(key).replace("|", "\\|")
                lines.append(f"| {fk} | {fv} |")

        lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _format_entry_text(entry: dict[str, Any]) -> str:
        """Format one watched-node block as plain indented text (original format)."""
        class_type = entry.get("class_type", "Unknown")
        label      = entry.get("label", "")
        node_id    = entry.get("node_id", "?")
        params: dict = entry.get("params", {})

        heading = (
            f"[{class_type} :: {label} :: {node_id}]"
            if label and label != class_type
            else f"[{class_type} :: {node_id}]"
        )

        lines = [heading]

        if not params:
            lines.append("  (no parameters selected)")
        else:
            max_key_len = max(len(k) for k in params)
            for key, value in params.items():
                lines.append(f"  {key.ljust(max_key_len)} : {LogFormatter._format_value(value)}")

        lines.append("")
        return "\n".join(lines)

    #---value formatter---

    @staticmethod
    def _format_value(value: Any) -> str:
        if value is None:
            return "(not captured)"
        if isinstance(value, float):
            formatted = f"{value:.6f}".rstrip("0")
            dot_pos = formatted.find(".")
            if dot_pos == -1:
                formatted += ".00"
            elif len(formatted) - dot_pos - 1 < 2:
                formatted = formatted.ljust(dot_pos + 3, "0")
            return formatted
        if isinstance(value, str):
            return value
        return str(value)

    #---override builders---

    @staticmethod
    def _build_override_by_id(entries: list[dict]) -> dict:
        return {"by_id": {str(e.get("node_id", "?")): e.get("params", {}) for e in entries}}

    @staticmethod
    def _build_override_by_title(entries: list[dict]) -> dict:
        nodes: dict = {}
        for e in entries:
            label = e.get("label") or e.get("class_type", "Unknown")
            nodes[label] = e.get("params", {})
        return {"by_title": nodes}

    @staticmethod
    def _build_override_by_type(entries: list[dict]) -> dict:
        nodes: dict = {}
        for e in entries:
            ct = e.get("class_type", "Unknown")
            if ct not in nodes:
                nodes[ct] = {}
            nodes[ct].update(e.get("params", {}))
        return {"by_type": nodes}

    #---helpers---

    @staticmethod
    def _title_from_prefix(prefix: str) -> str:
        if not prefix:
            return ""
        return prefix.replace("\\", "/").rstrip("/").split("/")[-1]

    @staticmethod
    def _build_json_dict(preset: NodePreset) -> dict:
        return {
            "ledger_version": "1.0.0",
            "filename_prefix": preset.filename_prefix,
            "header":   preset.header,
            "footer":   preset.footer,
            "comments": preset.comments,
            "nodes": [
                {
                    "node_id":    e.get("node_id"),
                    "class_type": e.get("class_type"),
                    "label":      e.get("label"),
                    "params":     e.get("params", {}),
                }
                for e in preset.entries
            ],
        }
