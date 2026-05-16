"""
writer.py - FileWriter

Handles all filesystem interaction:
  - Resolves save paths (relative to ComfyUI output dir, or absolute)
  - Generates versioned filenames (_v001, _v002, ...) to avoid overwrites
  - Writes log (.md / .txt) and JSON files atomically (write-then-rename)
  - Raises clear, typed exceptions for permission and path errors

No network access. No external dependencies beyond the standard library.
"""

import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

# Maximum version number before we stop trying to find a free slot
_MAX_VERSION = 9999


class FileWriteError(Exception):
    """Raised when a file cannot be written for any reason."""


class FileWriter:
    """
    Resolves output paths and writes log + JSON files.

    Args:
        comfy_output_dir: Absolute path to ComfyUI's default output directory.
                          Injected from folder_paths at node construction time.
    """

    def __init__(self, comfy_output_dir: str) -> None:
        self._output_dir = Path(comfy_output_dir)

    #---public---

    def write_log(
        self,
        filename_prefix: str,
        content: str,
        extension: str,  # "md" or "txt"
    ) -> Path:
        """
        Write the human-readable log file.
        Returns the path of the file written.
        """
        path = self._versioned_path(filename_prefix, extension)
        self._atomic_write(path, content, mode="text")
        log.info("Ledger: log written → %s", path)
        return path

    def write_json(self, filename_prefix: str, content: str) -> Path:
        """
        Write the JSON export file.
        Returns the path of the file written.
        """
        path = self._versioned_path(filename_prefix, "json")
        self._atomic_write(path, content, mode="text")
        log.info("Ledger: JSON written → %s", path)
        return path

    def write_override_json(self, filename_prefix: str, content: str) -> Path:
        """
        Write the pipeline-override JSON file.
        Filename stem gets an '_overrides' suffix before the version number:
          e.g. MyLog_overrides_v001.json
        Returns the path of the file written.
        """
        override_prefix = filename_prefix.rstrip("/").rstrip("\\") + "_overrides"
        path = self._versioned_path(override_prefix, "json")
        self._atomic_write(path, content, mode="text")
        log.info("Ledger: override JSON written → %s", path)
        return path

    #---path helpers---

    def resolve_directory(self, filename_prefix: str) -> Path:
        """
        Derive the target directory from the prefix string.

        Rules:
          - Absolute path --> use as-is (parent dir created if needed)
          - Relative path with '/' --> join to ComfyUI output dir
          - Bare filename (no slashes) --> ComfyUI output dir
        """
        prefix = filename_prefix.replace("\\", "/").strip()
        if not prefix:
            raise FileWriteError("filename_prefix is empty - cannot resolve path.")

        p = Path(prefix)
        if p.is_absolute():
            return p.parent
        if "/" in prefix:
            # Relative: resolve against ComfyUI output dir
            return (self._output_dir / p).parent
        # Bare token - write directly to output dir
        return self._output_dir

    def _versioned_path(self, filename_prefix: str, extension: str) -> Path:
        """
        Return a Path that does not already exist on disk,
        appending _v001, _v002, ... until a free slot is found.
        """
        directory = self.resolve_directory(filename_prefix)
        stem = self._stem_from_prefix(filename_prefix)

        # Ensure target directory exists
        try:
            directory.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise FileWriteError(
                f"Cannot create output directory '{directory}': {exc}"
            ) from exc

        for version in range(1, _MAX_VERSION + 1):
            candidate = directory / f"{stem}_v{version:03d}.{extension}"
            if not candidate.exists():
                return candidate

        raise FileWriteError(
            f"All {_MAX_VERSION} versions of '{stem}' already exist in '{directory}'."
        )

    @staticmethod
    def _stem_from_prefix(filename_prefix: str) -> str:
        """Extract the filename stem from the prefix (last token after '/')."""
        clean = filename_prefix.replace("\\", "/").rstrip("/")
        token = clean.split("/")[-1]
        # Strip any characters that are unsafe in filenames
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", token)
        return safe or "ledger_output"

    #---atomic write---

    @staticmethod
    def _atomic_write(path: Path, content: str, mode: str = "text") -> None:
        """
        Write content to path via a temp file in the same directory,
        then rename - prevents partial files on crash or power loss.
        """
        directory = path.parent
        try:
            fd, tmp_path = tempfile.mkstemp(dir=directory, suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(content)
                os.replace(tmp_path, path)
            except Exception:
                # Clean up the temp file if something went wrong mid-write
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except PermissionError as exc:
            raise FileWriteError(
                f"Permission denied writing to '{path}': {exc}"
            ) from exc
        except OSError as exc:
            raise FileWriteError(
                f"OS error writing to '{path}': {exc}"
            ) from exc
