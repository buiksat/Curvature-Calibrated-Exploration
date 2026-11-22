# Secondary study: policies on their own adaptive histories

Runs 192, crashes 0.

## W = 100

| policy | n | mean regret | SD | minus frozen | 95% bootstrap | own-coverage fails | s/sbar range | max d_Th | potential bound (median) | bound < cap |
|---|---:|---:|---:|---:|---|---:|---|---:|---:|---:|
| frozen_reference | 64 | 48.25 | 4.92 | --- | --- | 0/64 | 0.9999--1.0025 | 0.004925 | 22199 | 64/64 |
| naive_current | 64 | 47.73 | 5.24 | -0.53 | [-1.42, 0.36] | 0/64 | 0.9999--1.0025 | 0.004925 | uncertified | --- |
| transport_endpoint | 64 | 47.55 | 5.55 | -0.70 | [-1.60, 0.20] | 0/64 | 0.9999--1.0025 | 0.004925 | 22210 | 64/64 |
