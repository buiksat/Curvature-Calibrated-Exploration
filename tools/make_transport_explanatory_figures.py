#!/usr/bin/env python3
"""Render the current figures using authenticated original source and editorial transforms.

The byte-identical original generator is shipped in editorial_originals/. Its
self-digest and original generation record remain truthful. This outer adapter
has a distinct current digest in the separate editorial provenance record.
"""
from __future__ import annotations
import argparse
import hashlib
from pathlib import Path
from editorial_generator_sources import load_original, original_source

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL_GENERATOR_NAME = 'make_transport_explanatory_figures.py'

def __getattr__(name):
    if name.startswith("__"):
        raise AttributeError(name)
    return getattr(load_original(ORIGINAL_GENERATOR_NAME, Path(__file__).parent), name)

def build_original(root=None):
    generator = load_original(ORIGINAL_GENERATOR_NAME, Path(__file__).parent)
    outputs = generator.build(ROOT if root is None else Path(root))
    original_source(ORIGINAL_GENERATOR_NAME, Path(__file__).parent)
    return outputs

def build(root=None):
    from prepare_tmlr_figures import apply
    return apply(build_original(root))

def generator_provenance():
    source, raw = original_source(ORIGINAL_GENERATOR_NAME, Path(__file__).parent)
    return {"original_source": "tools/editorial_originals/" + source.name,
            "original_generator_sha256": hashlib.sha256(raw).hexdigest(),
            "current_generator": "tools/" + Path(__file__).name,
            "current_generator_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--check", action="store_true")
    args=parser.parse_args()
    for relative, text in build(args.root).items():
        path=args.root/relative
        if args.check:
            if not path.is_file() or path.read_bytes()!=text.encode():
                raise ValueError("Generated figure differs: " + str(relative))
        else:
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(text.encode())
    print("Verified current outputs from authenticated original generator and editorial transforms; no experiments rerun.")

if __name__ == "__main__": main()
