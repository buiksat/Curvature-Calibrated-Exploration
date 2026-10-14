"""Original second read-only primary diagnostic, preserved after execution.

Executed with /workspace/cce-research-env/bin/python via a shell heredoc.
No policy, optimizer, simulator, or numerical solver is called. Recommendations
are evaluated at the primary behavior policy's logged states. Their one-step
regret is not the cumulative regret of alternative adaptive policies.

The confidence-radius ratio median is the ordinary median across all 50,000
dependent rounds in each W cell, including the 50 initial zero ratios.
The tie audit here checks stored-score ties only; primary_scan_original.py
checks high-precision argmax on every primary round.

This script is preserved verbatim apart from this docstring and formatting.
"""
from pathlib import Path
from collections import Counter, defaultdict
from decimal import Decimal, localcontext
import json
import math
import statistics
import time

start = time.monotonic()
for condition in sorted(Path('/workspace/cce-full-local/raw/evaluation/T-1000').iterdir()):
    counts = Counter()
    sums = defaultdict(float)
    bad = []
    ratios = []
    absorption_rounds = []
    for p in sorted((condition / 'transport_hessian').glob('seed-*/raw.jsonl')):
        with p.open() as f:
            for line in f:
                r = json.loads(line)
                m = r['metrics']
                if 'selected_action' not in m:
                    continue
                a = m['selected_action']
                mu = m['true_means']
                best = max(mu)
                c = m['corrected_centers']
                w = m['current_widths']
                s = m['scores']
                B = m['beta_t_corr'] * m['exp_bar_D_over_2']
                bias = m['current_bias']
                counts['rounds'] += 1
                ratios.append(m['beta_hist'] / m['beta_stat'])
                sums['primary_logged_one_step_regret'] += best - mu[a]
                for name, key in [('endpoint', 'endpoint_transport_scores'), ('frozen', 'frozen_reference_scores'), ('naive', 'naive_current_scores')]:
                    scores = m[key]
                    aa = max(range(5), key=scores.__getitem__)
                    counts[name + '_recommendation_disagrees'] += aa != a
                    sums[name + '_same_primary_history_one_step_regret'] += best - mu[aa]
                if s.count(max(s)) > 1:
                    with localcontext() as ctx:
                        ctx.prec = 250
                        scores = [Decimal.from_float(c[j]) + Decimal.from_float(B) * Decimal.from_float(w[j]) + Decimal.from_float(bias) for j in range(5)]
                        ae = max(range(5), key=scores.__getitem__)
                        if scores[a] != max(scores):
                            bad.append({'seed': r['seed'], 'round': m['round'], 'selected': a, 'exact': ae, 'B': B, 'lost_exact_score_gap': float(max(scores) - scores[a]), 'gap_in_score_ulps': float((max(scores) - scores[a]) / Decimal.from_float(math.ulp(max(s))))})
    print(json.dumps({'condition': condition.name, 'counts': dict(counts), 'mean_one_step_regret': {k: v / counts['rounds'] for k, v in sums.items()}, 'beta_hist_over_beta_stat': {'min': min(ratios), 'median': statistics.median(ratios), 'max': max(ratios)}, 'stored_input_exact_ranking_mismatches': bad}, sort_keys=True), flush=True)
print('elapsed_seconds', time.monotonic() - start)
