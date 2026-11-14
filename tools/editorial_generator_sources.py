"""Authenticate original generator preimages before executing their exact bytes."""
from __future__ import annotations
import hashlib
from pathlib import Path
from types import ModuleType

ORIGINAL_GENERATOR_DIGESTS = {'make_transport_explanatory_figures.py': '464083a92053499c9dacba950707a3cbd4749fe0e908531c06b27da5e5b43150',
 'make_transport_table_charts.py': 'ed0e3fb6b1e5449009fa4a9f0a2850e32c205ce2bbd47923958039512ce6e479'}

def original_source(name: str, tools_directory: Path) -> tuple[Path, bytes]:
    if name not in ORIGINAL_GENERATOR_DIGESTS:
        raise ValueError(f"Unknown original generator: {name}")
    directory = Path(tools_directory) / "editorial_originals"
    source = directory / name
    if directory.is_symlink() or source.is_symlink() or not source.is_file():
        raise ValueError(f"Original generator source missing or linked: {name}")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != ORIGINAL_GENERATOR_DIGESTS[name]:
        raise ValueError(f"Original generator source digest differs: {name}")
    return source, raw

def load_original(name: str, tools_directory: Path) -> ModuleType:
    source, raw = original_source(name, tools_directory)
    module = ModuleType("_authenticated_original_" + source.stem)
    module.__file__ = str(source)
    # Execute exactly the bytes authenticated above; no second loader read or
    # unauthenticated bytecode cache can substitute another implementation.
    exec(compile(raw, str(source), "exec"), module.__dict__)
    return module
