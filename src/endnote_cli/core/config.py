"""Configuration management for endnote-cli."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


CONFIG_DIR = Path.home() / ".endnote-cli"
CONFIG_FILE = CONFIG_DIR / "config.json"


def _ensure_config_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {}


def save_config(config: dict) -> None:
    _ensure_config_dir()
    CONFIG_FILE.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def get_default_library() -> Optional[str]:
    config = load_config()
    return config.get("default_library")


def set_default_library(path: str) -> None:
    config = load_config()
    config["default_library"] = path
    save_config(config)


def get_library_dir() -> Optional[str]:
    config = load_config()
    return config.get("library_dir")


def set_library_dir(path: str) -> None:
    config = load_config()
    config["library_dir"] = path
    save_config(config)


def find_libraries(directory: Optional[str] = None) -> list[Path]:
    """Find all .enl files in a directory."""
    search_dir = Path(directory) if directory else Path(get_library_dir() or ".")
    if not search_dir.exists():
        return []
    return sorted(search_dir.glob("*.enl"))


def resolve_library_path(name_or_path: Optional[str] = None) -> Path:
    """Resolve a library name or path to an absolute .enl path."""
    if name_or_path:
        p = Path(name_or_path)
        if p.exists():
            return p
        # Try adding .enl extension
        if not p.suffix:
            p = p.with_suffix(".enl")
        if p.exists():
            return p
        # Try in library_dir
        lib_dir = get_library_dir()
        if lib_dir:
            candidate = Path(lib_dir) / p.name
            if candidate.exists():
                return candidate
            candidate = Path(lib_dir) / name_or_path
            if not candidate.suffix:
                candidate = candidate.with_suffix(".enl")
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Library not found: {name_or_path}")

    # Use default library
    default = get_default_library()
    if default:
        return resolve_library_path(default)

    raise ValueError(
        "No library specified and no default configured. "
        "Use --library or run: endnote-cli config set default-library <path>"
    )
