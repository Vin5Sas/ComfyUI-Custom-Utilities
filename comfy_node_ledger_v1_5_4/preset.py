"""
preset.py - NodePreset dataclass

Carries state through a chain of Ledger instances.
Each instance merges its own watched data into this object.
Only the final instance in the chain writes to disk.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NodePreset:
    """
    Accumulates data from one or more chained Ledger nodes.
    Serialisable to/from plain dict for ComfyUI compatibility.
    """

    filename_prefix: str = ""
    header: str = ""
    footer: str = ""
    comments: str = ""
    export_json: bool = True
    export_log: bool = True
    log_format: str = "md"          # "md" or "txt"
    export_override: bool = False   # write a pipeline-override JSON
    override_type: str = "by_id"   # "by_id" | "by_title" | "by_type"

    # Ordered list of captured node entries:
    # [{"node_id": "42", "class_type": "KSampler",
    #   "label": "My Sampler", "params": {"seed": 42, "denoise": 0.75}}, ...]
    entries: list[dict[str, Any]] = field(default_factory=list)

    #---serialisation---

    def to_dict(self) -> dict:
        return {
            "filename_prefix": self.filename_prefix,
            "header": self.header,
            "footer": self.footer,
            "comments": self.comments,
            "export_json": self.export_json,
            "export_log": self.export_log,
            "log_format": self.log_format,
            "export_override": self.export_override,
            "override_type": self.override_type,
            "entries": self.entries,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NodePreset":
        obj = cls()
        obj.filename_prefix  = data.get("filename_prefix", "")
        obj.header           = data.get("header", "")
        obj.footer           = data.get("footer", "")
        obj.comments         = data.get("comments", "")
        obj.export_json      = data.get("export_json", True)
        obj.export_log       = data.get("export_log", True)
        obj.log_format       = data.get("log_format", "md")
        obj.export_override  = data.get("export_override", False)
        obj.override_type    = data.get("override_type", "by_id")
        obj.entries          = data.get("entries", [])
        return obj

    def merge_entries(self, new_entries: list[dict]) -> None:
        """Append entries from a downstream Ledger node."""
        self.entries.extend(new_entries)
