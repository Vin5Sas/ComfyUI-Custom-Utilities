"""
Comfy Node Ledger - ComfyUI custom node
Records parameter values of watched nodes on each successful execution.

Version: 1.5.4
"""

from .node import ComfyNodeLedger

NODE_CLASS_MAPPINGS = {
    "ComfyNodeLedger": ComfyNodeLedger,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ComfyNodeLedger": "Comfy Node Ledger",
}

WEB_DIRECTORY = "./js"

__version__ = "1.5.4"
__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS", "WEB_DIRECTORY"]
