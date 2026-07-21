#!/usr/bin/env python3
"""Static LaTeX validation (no TeX engine available in this environment)."""
import re, sys, collections

MAIN = "main.tex"
MACROS = "macros.tex"

def read(p):
    with open(p) as f:
        return f.read()

def strip_comments(s):
    # remove % comments (not \%), line by line
    out = []
    for line in s.splitlines():
        res, i, esc = [], 0, False
        for ch in line:
            if ch == '%' and not esc:
                break
            res.append(ch)
            esc = (ch == '\\' and not esc)
        out.append(''.join(res))
    return '\n'.join(out)

main_raw = read(MAIN)
main = strip_comments(main_raw)
macros = strip_comments(read(MACROS))

problems = []

# 1. Brace balance
bal, pos = 0, None
for i, ch in enumerate(main):
    if ch == '{' and (i == 0 or main[i-1] != '\\'):
        bal += 1
    elif ch == '}' and (i == 0 or main[i-1] != '\\'):
        bal -= 1
        if bal < 0:
            problems.append(f"brace goes negative at char {i}")
            bal = 0
print(f"[braces] net balance = {bal} (0 = OK)")
if bal != 0: problems.append(f"unbalanced braces net={bal}")

# 2. $ parity (count unescaped $, ignoring $$)
noesc = re.sub(r'\\\$', '', main)
noesc = noesc.replace('$$', '')
dollars = noesc.count('$')
print(f"[math $] unescaped single-$ count = {dollars} ({'even OK' if dollars%2==0 else 'ODD - PROBLEM'})")
if dollars % 2 != 0: problems.append("odd number of $")

# 3. \left / \right balance
nl = len(re.findall(r'\\left', main)); nr = len(re.findall(r'\\right', main))
print(f"[left/right] \\left={nl} \\right={nr} ({'OK' if nl==nr else 'MISMATCH'})")
if nl != nr: problems.append(f"left/right mismatch {nl} vs {nr}")

# 4. environment balance
begins = re.findall(r'\\begin\{([^}]+)\}', main)
ends = re.findall(r'\\end\{([^}]+)\}', main)
cb, ce = collections.Counter(begins), collections.Counter(ends)
for env in set(list(cb)+list(ce)):
    if cb[env] != ce[env]:
        problems.append(f"env '{env}': begin={cb[env]} end={ce[env]}")
        print(f"[env] MISMATCH {env}: begin={cb[env]} end={ce[env]}")
print(f"[env] {len(set(begins))} distinct environments checked")

# 5. labels: duplicates
labels = re.findall(r'\\label\{([^}]+)\}', main)
dup = [l for l,c in collections.Counter(labels).items() if c>1]
print(f"[labels] {len(labels)} labels, {len(dup)} duplicates")
if dup: problems.append(f"duplicate labels: {dup}")

# 6. refs resolve
refcmds = re.findall(r'\\(?:eqref|ref|Cref|cref)\{([^}]+)\}', main)
refkeys = set()
for r in refcmds:
    for k in r.split(','):
        refkeys.add(k.strip())
labelset = set(labels)
unresolved = sorted(k for k in refkeys if k and k not in labelset)
print(f"[refs] {len(refkeys)} distinct ref targets, {len(unresolved)} unresolved")
if unresolved: problems.append(f"unresolved refs: {unresolved}")

# 7. citations in .bib
bib = read("references.bib")
bibkeys = set(re.findall(r'@\w+\{([^,]+),', bib))
cites = re.findall(r'\\cite[a-z]*\{([^}]+)\}', main)
citekeys = set()
for c in cites:
    for k in c.split(','):
        citekeys.add(k.strip())
misscite = sorted(k for k in citekeys if k and k not in bibkeys)
print(f"[cites] {len(citekeys)} distinct cite keys, {len(misscite)} missing from .bib")
if misscite: problems.append(f"missing citations: {misscite}")

# 8. deleted macros must not be USED (definitions removed already)
deleted = [r'\\diego', r'\\bahram', r'\\houssam', r'\\brett',
           r'\\resultTBD', r'\\epsdrift\b', r'\\epsdriftbar', r'\\Eopt\b',
           r'\\iffinalresults', r'\\finalresults', r'\\ifcomments', r'\\commentsfalse']
for d in deleted:
    hits = re.findall(d, main)
    if hits:
        problems.append(f"deleted macro still used: {d} ({len(hits)}x)")
        print(f"[deleted] STILL USED {d}: {len(hits)}")
print("[deleted] deleted-macro usage check done")

# 9. macros used in main defined in macros.tex or main preamble or standard
defined = set(re.findall(r'\\newcommand\{\\(\w+)\}', macros)) | \
          set(re.findall(r'\\newcommand\{\\(\w+)\}', main)) | \
          set(re.findall(r'\\DeclareMathOperator\*?\{\\(\w+)\}', macros)) | \
          set(re.findall(r'\\newcommand\*?\{\\(\w+)\}', main))
custom = ['bh','Calg','Lamalg','Valg','Gamdyn','Gmat','Dmat','cHist','epsCGbar',
          'cE','cF','cG','cA','cH','cO','cL','R','btheta','bx','bg','bu','bv','bI',
          'bH','bC','bCbar','epslin','argmin','argmax','tr']
for m in custom:
    if m not in defined:
        print(f"[macro def] NOTE: '{m}' not found in newcommand scan (may be builtin/aliascnt)")
print("[macro def] custom macro definition check done")

# 10. stale-notation sweep
stale = ['eta^{pred}', r'\eta^{\mathrm{pred}}', 'alpha_drift', r'\alpha_{\mathrm{drift}}',
         'beta_max', 'never the worst', '+3.5', 'scalar, not geometric',
         'separates scalar', 'external validity', 'not an artifact',
         'equivalently the variation', 'observable via', 'non-standard potential',
         'strictly looser', 'no $\\sqrt{T}$ is introduced', 'elliptic-potential step',
         'asm:drift', 'lem:drift-sufficient']
print("[stale] sweep:")
for s in stale:
    n = main_raw.count(s)
    flag = "" if n==0 else "  <-- CHECK"
    if n: print(f"    {s!r}: {n}{flag}")
print("    (all others 0)")

print()
if problems:
    print("=== PROBLEMS ===")
    for p in problems: print("  -", p)
    sys.exit(1)
else:
    print("=== STATIC VALIDATION PASSED (no blocking issues) ===")
