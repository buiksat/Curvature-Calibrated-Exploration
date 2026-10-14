"""Original read-only primary arithmetic diagnostic, preserved after execution.

Executed with /workspace/cce-research-env/bin/python via a shell heredoc.
No policy, optimizer, simulator, or numerical solver is called. This reads existing
primary evaluation JSONL files and writes diagnostic JSON only to stdout.

Decimal.from_float preserves each input double exactly. Decimal precision 250
is used for final score arithmetic, not a higher-precision trajectory rerun.
B = beta * inflation is first rounded as a Python float, as in the original
implementation's left-associative beta * inflation * current_widths expression.

This script is preserved verbatim apart from this docstring and formatting.
"""
from pathlib import Path
from collections import defaultdict, Counter
from decimal import Decimal, localcontext
import json
import math
import time

start = time.monotonic()
out = {}
with localcontext() as ctx:
    ctx.prec = 250
    for condition in sorted(Path('/workspace/cce-full-local/raw/evaluation/T-1000').iterdir()):
        counts = Counter()
        maxima = defaultdict(float)
        minima = {'width': float('inf'), 'top_score_gap_ulps': float('inf'), 'top_width_gap': float('inf')}
        examples = []
        paths = sorted((condition / 'transport_hessian').glob('seed-*/raw.jsonl'))
        for p in paths:
            counts['seeds'] += 1
            with p.open() as f:
                for line in f:
                    r = json.loads(line)
                    m = r['metrics']
                    if 'selected_action' not in m:
                        continue
                    counts['rounds'] += 1
                    c = m['corrected_centers']
                    w = m['current_widths']
                    s = m['scores']
                    beta = m['beta_t_corr']
                    infl = m['exp_bar_D_over_2']
                    bias = m['current_bias']
                    B = beta * infl
                    a = m['selected_action']
                    aw = max(range(5), key=w.__getitem__)
                    wm = max(w)
                    wt = sum(x == wm for x in w)
                    sm = max(s)
                    st = sum(x == sm for x in s)
                    counts['width_argmax_first_matches'] += a == aw
                    counts['width_argmax_set_matches'] += w[a] == wm
                    counts['width_top_tie'] += wt > 1
                    counts['score_top_tie'] += st > 1
                    counts['width_top_tie_after_round1'] += (wt > 1 and m['round'] > 1)
                    counts['score_top_tie_after_round1'] += (st > 1 and m['round'] > 1)
                    wsort = sorted(w, reverse=True)
                    wg = wsort[0] - wsort[1]
                    cr = max(c) - min(c)
                    counts['strict_width_dominance_sufficient'] += (B * wg > cr)
                    dn = [Decimal.from_float(x) for x in c]
                    dw = [Decimal.from_float(x) for x in w]
                    db = Decimal.from_float(B)
                    dk = Decimal.from_float(bias)
                    exact = [dn[j] + db * dw[j] + dk for j in range(5)]
                    ae = max(range(5), key=exact.__getitem__)
                    em = max(exact)
                    counts['exact_rank_first_mismatch'] += a != ae
                    counts['selected_not_exact_argmax_set'] += exact[a] != em
                    counts['exact_top_tie'] += sum(x == em for x in exact) > 1
                    counts['rounded_score_tie_exact_unique'] += (st > 1 and sum(x == em for x in exact) == 1)
                    counts['strict_width_dominance_sufficient_decimal'] += (
                        db * (dw[aw] - max(dw[j] for j in range(5) if j != aw)) > max(dn) - min(dn)
                    )
                    counts['width_argmax_is_exact_unique_max'] += (exact[aw] == em and sum(x == em for x in exact) == 1)
                    norm = [w[j] + c[j] / B for j in range(5)]
                    an = max(range(5), key=norm.__getitem__)
                    counts['normalized_rank_first_mismatch'] += a != an
                    no_center = [B * x + bias for x in w]
                    counts['all_centers_numerically_absorbed'] += all(s[j] == no_center[j] for j in range(5))
                    counts['some_centers_numerically_absorbed'] += any(c[j] != 0 and s[j] == no_center[j] for j in range(5))
                    counts['score_reconstruction_mismatch'] += any(s[j] != (c[j] + B * w[j]) + bias for j in range(5))
                    counts['nonfinite_score_or_coefficient'] += not all(math.isfinite(x) for x in s + [B])
                    counts['zero_width'] += any(x == 0 for x in w)
                    maxima['B'] = max(maxima['B'], B)
                    maxima['D_Q'] = max(maxima['D_Q'], m['D_Q'])
                    maxima['score'] = max(maxima['score'], max(s))
                    maxima['center_range'] = max(maxima['center_range'], cr)
                    maxima['theta_t_norm'] = max(maxima['theta_t_norm'], m['theta_t_norm'])
                    maxima['current_metric_condition_number'] = max(maxima['current_metric_condition_number'], m['current_metric_condition_number'])
                    minima['width'] = min(minima['width'], min(w))
                    if wg > 0:
                        minima['top_width_gap'] = min(minima['top_width_gap'], wg)
                    ss = sorted(s, reverse=True)
                    sg = ss[0] - ss[1]
                    if sg > 0:
                        minima['top_score_gap_ulps'] = min(minima['top_score_gap_ulps'], sg / math.ulp(sm))
                    if (a != ae or (st > 1 and m['round'] > 1)) and len(examples) < 8:
                        examples.append({'seed': r['seed'], 'round': m['round'], 'selected': a, 'width_argmax': aw, 'exact_argmax': ae, 'widths': w, 'scores': s, 'centers': c, 'B': B})
        out[condition.name] = {'counts': dict(counts), 'max': dict(maxima), 'min': minima, 'anomalous_examples': examples}
        print(json.dumps({condition.name: out[condition.name]}, sort_keys=True), flush=True)
print('elapsed_seconds', time.monotonic() - start)
