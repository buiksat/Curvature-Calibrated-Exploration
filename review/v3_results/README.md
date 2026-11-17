# Protocol v3 tuning and evaluation outputs

Protocol: `PROTOCOL_V3.md` revision 2, approved 2026-11-16 (commit `d700ce11`).
Every run below ran on commit `d700ce1133497f2ea150b0e7a7abe550f555c0a6`,
`dirty: false`, `experiments/transport_v3.py` SHA-256
`5c040e850682fff8e228ef62dbe55eedc18ec11e97d323036dc2623f19cc8402`.

Commands (repository root, `OPENBLAS_NUM_THREADS=1`, NumPy 2.2.3):

```
python -B -m experiments.transport_v3 --phase tuning --seeds 41100-41109 --c 1 \
  --learning-rate 3e-6 1e-5 3e-5 --steps 5 20 --methods tuning_uniform --output <tuning> --workers 20
python -B -m experiments.analyze_transport_v3 tuning <tuning>/runs.jsonl --output tuning_selection.json
python -B -m experiments.transport_v3 --phase evaluation --seeds 41200-41249 --c 1 \
  --learning-rate 3e-6 --steps 5 --methods transport_hessian transport_endpoint \
  frozen_reference naive_current linucb ucb_glm --output <wT> --workers 20
python -B -m experiments.transport_v3 --phase evaluation --seeds 41200-41249 \
  --c 0.005 0.0005 0.00005 --learning-rate 3e-6 --steps 5 --methods transport_hessian \
  transport_endpoint frozen_reference naive_current frozen_reference_no_envelope \
  naive_current_no_envelope linucb ucb_glm --output <small> --workers 20
cat <wT>/runs.jsonl <small>/runs.jsonl > eval_runs.jsonl
python -B -m experiments.analyze_transport_v3 evaluation eval_runs.jsonl --output eval_analysis.json
```

Wall time (20 workers): tuning 24 s (371 CPU-s); design cell 3 min 45 s
(4,261 CPU-s); descriptive cells 16 min 2 s (18,888 CPU-s).

| File | SHA-256 |
|---|---|
| `tuning_runs.jsonl` (60 runs) | 231dd0f3b515f937d77704507fc2dcb4c5b147e31f3a9b343cab26531131b5cf |
| `tuning_manifest.json` | 790b2829e1421ccdb1c7a9b039150e8e9df47929b7c3821e05e2dd63630d64d3 |
| `tuning_selection.json` | f2b6033a76ea818ae0216683cb90115625e1e4ea4bb2202eb548b715ba81f8a5 |
| `eval_runs.jsonl` (1,500 runs) | 8f989c5d2336184fbc819889fe57d2ef64918e7e6ba9e1b98a3986e5501b89e3 |
| `eval_manifest_wT.json` | 03b2a2c9753d49aa0958b4ed118d025650ec03b92727cbc33a482c83c36c99b9 |
| `eval_manifest_small.json` | 925949025c07403c54f6a6d8d765f9dad1a842a8861bbf90ddc515913c148f4c |
| `eval_analysis.json` | 225c67538961c887c7b1350c01e3aa3301704f231923d353e4835369b4a58dcf |
