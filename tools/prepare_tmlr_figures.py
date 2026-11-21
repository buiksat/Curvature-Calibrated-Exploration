#!/usr/bin/env python3
"""Authenticate and replay the approved figure editorial transforms.

The original generators still reconstruct all empirical values and coordinates.
This layer authenticates their original outputs, removes approved annotations
and comment payloads, and authenticates the resulting manuscript sources.
Original generation records retain their original generator and output digests.
The separate editorial record binds the current sources to those originals.
No experiments or new numerical results are generated.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FIGURES = Path("paper/figures")
FIGURE_PINS = {'transport_conceptual_geometry.tex': {'current_sha256': 'ff32d8d81a828a4b13d645685d816573822637dc12b8e7dce706815091483ce0',
                                       'original_sha256': '12f0039ce9c0c20f8d78aa46193b606042cac7015094837b6f3581d8b110fb5b'},
 'transport_conceptual_interfaces.tex': {'current_sha256': '65e5224212c4e39ae43af565af2c13c4bdfce341f9ffa4f6473671029294cd2e',
                                         'original_sha256': '6b1976da5525e1aa1aad47bb0775c37e4de0734617eacd17fefb0386b817e3e4'},
 'transport_explanatory_bounds.tex': {'current_sha256': '3fb25e8ee6e2e0ed3894bc5d7e26cae1fa79ce06fce61eb0c27714672d84c554',
                                      'original_sha256': 'bee87dd7c6c536c1ee44249901d329867a5f7bbd5a25da497620bff1f86ad324'},
 'transport_explanatory_outcomes.tex': {'current_sha256': '9b3bc251a8901b20cb79b417c3745fdbdf897b2235d98e3e34bbbde54cea230c',
                                        'original_sha256': 'a7c5d1303583be47e65b2140410f4c0a1bc7a604ce1b0d549352adc6b8bdb339'},
 'transport_instantiation_bound.tex': {'current_sha256': '9c6465521c216fa96fc6536044491684312108c510357f38cc92c0325319af3c',
                                       'original_sha256': '9c6465521c216fa96fc6536044491684312108c510357f38cc92c0325319af3c'},
 'transport_instantiation_regret.tex': {'current_sha256': '239ae5e923801ed1a2f9eafa75ba6a642e8bd2bb14ec2875c8d080f22ea5ec98',
                                        'original_sha256': '239ae5e923801ed1a2f9eafa75ba6a642e8bd2bb14ec2875c8d080f22ea5ec98'},
 'transport_instantiation_tightness.tex': {'current_sha256': '828590d0cab45e2621677474acec4ae1216857191d54e816d4f4b24a2fd276c2',
                                           'original_sha256': '828590d0cab45e2621677474acec4ae1216857191d54e816d4f4b24a2fd276c2'},
 'transport_table_drift.tex': {'current_sha256': '249442e06853424c9e73cfeb017e7ebc520df333270e06bbabc379bddb589e5b',
                               'original_sha256': '3698341c06b17ff36f817d2208d86fb84826ba8ff3fd9699b14e8d79c70449a6'},
 'transport_table_mechanism.tex': {'current_sha256': '221d6e46ca925cc9452472838490528f14d0301f9380e1f2e03ad1fe9a154650',
                                   'original_sha256': '93105c1ff803f4cfcb14a1cd8a943b761dc5df05077d8f59d4df348669bb236e'},
 'transport_table_original_bound_ratios.tex': {'current_sha256': 'a03b7e64641f3dc78680181caad1f903c318d02ef874ffac93979ae9b40469ac',
                                               'original_sha256': 'a03b7e64641f3dc78680181caad1f903c318d02ef874ffac93979ae9b40469ac'},
 'transport_table_original_components.tex': {'current_sha256': 'd3fd174043f4953f683f9dcb1e011de35a06e271f5c4560c023a021e6ccbac82',
                                             'original_sha256': 'd3fd174043f4953f683f9dcb1e011de35a06e271f5c4560c023a021e6ccbac82'},
 'transport_table_original_distribution.tex': {'current_sha256': '8cfe7cfff742229e3a2e45f26645b0c628a24e148df61f3b10d8010f1a2f7c48',
                                               'original_sha256': '8cfe7cfff742229e3a2e45f26645b0c628a24e148df61f3b10d8010f1a2f7c48'},
 'transport_table_original_path_ratios.tex': {'current_sha256': '266975d0e808119e7590443ba4696d16ddce58a4b9a97f06f5f022a8e9fa5d81',
                                              'original_sha256': '266975d0e808119e7590443ba4696d16ddce58a4b9a97f06f5f022a8e9fa5d81'},
 'transport_table_original_performance.tex': {'current_sha256': 'c8562163804e9fd3c47589037485692ed3e9e81c785206c56275505dda9acd06',
                                              'original_sha256': 'c8562163804e9fd3c47589037485692ed3e9e81c785206c56275505dda9acd06'},
 'transport_table_original_validity.tex': {'current_sha256': '16f8890b8758cfd6b8574648843d92a07386cf61fc0555db51e1cc8ebcef5e3c',
                                           'original_sha256': '16f8890b8758cfd6b8574648843d92a07386cf61fc0555db51e1cc8ebcef5e3c'},
 'transport_table_relative.tex': {'current_sha256': 'c8d5475da9ad8ef926bfe1003b1a717ca73746c1028f5747c14f3502e8c2c6c2',
                                  'original_sha256': 'f5f77ead8dd87ac4048f0421fe138a0ea091916e85c7c57c22dde0b453698170'},
 'transport_table_same_history.tex': {'current_sha256': '4ba36ea94863d8a0b07b8319061382abda31acb8a2bec6128470d3866522260d',
                                      'original_sha256': '80b867341dc4d08edef1322eb6c8f44abaf27c060c74635ee3e17ad885b20417'}}
ORIGINAL_RECORD_PINS = {'transport_explanatory_provenance.json': '7e8294965356fa113e7c8c67f8e0ceda6c21c85dcc44b14d5ef79489032067ea', 'transport_table_provenance.json': 'ab834344dd57663b671f2c1dc9f283e36aef28a53c8a0a7b290514ecd309766f'}

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def neutralize_comments(text):
    return re.sub(r"(?m)(?<!\\)%[^\n]*", "%", text)

def transform(name, original):
    pin = FIGURE_PINS[name]
    if digest(original.encode()) != pin["original_sha256"]:
        raise ValueError(f"Original generator figure differs: {name}")
    if name.startswith(("transport_instantiation_", "transport_table_original_")):
        return original, ["Retain original historical source bytes; outside the compiled manuscript."]
    text = original
    operations = []
    if name in {"transport_explanatory_outcomes.tex", "transport_explanatory_bounds.tex"}:
        text = text[:text.index(r"\par\medskip")]
        operations.append("Remove duplicate caveat note after the plotted figure.")
    elif name == "transport_table_drift.tex":
        text = text[:text.index(r"\noindent\begin{minipage}")]
        operations.append("Remove duplicate caveat minipage; retain the plot and threshold legend.")
    elif name == "transport_conceptual_geometry.tex":
        annotation = ("  \\node[anchor=west] at (0,-8.32)\n"
                      "    {This is not a realized learning trajectory or an observed policy failure.};\n")
        if annotation not in text:
            raise ValueError("Original conceptual disclaimer differs")
        text = text.replace(annotation, "")
        operations.append("Remove the duplicate disclaimer text node; retain metric/score geometry.")
    elif name == "transport_conceptual_interfaces.tex":
        label = "Same history, center, radius, and bias."
        if text.count(label) != 1:
            raise ValueError("Original conceptual comparison label differs")
        text = text.replace(label, "Same history, center, confidence multiplier and error allowance.")
        operations.append("Name the confidence multiplier and error allowance in the comparison label.")
    text = neutralize_comments(text)
    operations.append("Neutralize source comment payloads, preserving TeX line continuation semantics.")
    if digest(text.encode()) != pin["current_sha256"]:
        raise ValueError(f"Approved editorial source differs: {name}")
    return text, operations

def apply(outputs):
    return {path: transform(path.name, text)[0] if path.parent.name == "figures" and path.suffix == ".tex"
            and path.name in FIGURE_PINS else text for path, text in outputs.items()}

def build(root=ROOT):
    import make_transport_explanatory_figures as explanatory
    import make_transport_table_charts as charts
    import transport_artifact_expectations as historical
    root = Path(root).resolve()
    original = {**explanatory.build_original(root), **charts.build_original(root),
                **{path.relative_to(root): text for path, text in
                   historical.expected_original_artifact_text(root)[0].items()}}
    for name in FIGURE_PINS:
        if name.startswith("transport_conceptual"):
            original[FIGURES / name] = (Path(__file__).parent / "editorial_originals" / name).read_text()
    entries=[]
    outputs={}
    for name in sorted(FIGURE_PINS):
        text, operations = transform(name, original[FIGURES / name])
        outputs[FIGURES / name] = text
        entries.append({"path": str(FIGURES / name), **FIGURE_PINS[name], "transforms": operations})
    for name, pin in ORIGINAL_RECORD_PINS.items():
        if digest((root / FIGURES / name).read_bytes()) != pin or digest(original[FIGURES / name].encode()) != pin:
            raise ValueError(f"Original generation record changed: {name}")
    record={"schema_version": 3,
            "generators": [explanatory.generator_provenance(), charts.generator_provenance()],
            "scope": "Approved post-generation editorial transforms; no experiments or new plotted data.",
            "original_generation_records": [{"path": str(FIGURES / name), "sha256": pin,
                 "status": "original generation, unchanged"} for name,pin in sorted(ORIGINAL_RECORD_PINS.items())],
            "editorial_tool": {"path": "tools/prepare_tmlr_figures.py", "sha256": digest(Path(__file__).read_bytes())},
            "figures": entries}
    outputs[FIGURES / "transport_editorial_provenance.json"] = json.dumps(record,indent=2,sort_keys=True)+"\n"
    return outputs

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",type=Path,default=ROOT)
    parser.add_argument("--check",action="store_true")
    args=parser.parse_args()
    for relative,text in build(args.root).items():
        path=args.root/relative
        if args.check:
            if path.read_bytes()!=text.encode(): raise ValueError(f"Current editorial output differs: {relative}")
        else: path.write_text(text)
    print("PASS: 8 authenticated editorial transforms, 9 retained original figures and current provenance; original generation records unchanged")

if __name__ == "__main__": main()
