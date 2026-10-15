#!/usr/bin/env python3
"""Render reviewed numerical tables as charts, retaining their published precision.

The original tables remain in the supplement and are independently regenerated
from the retained evidence. No experiments, new intervals, or interpolation.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import anonymous_package_contract as contract

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = Path('paper/figures')
INPUT_HASHES = {
 'transport_followup_drift_bounds': '6130e0e66e34c6117f5e6d4bc0d1b4a574394a1b00dbf4b363b50062530bac2c',
 'transport_followup_same_history': 'e3cbe9e68cf611f0ccf296fcee0e5c7adc34ff50b594933710be97e47d33105e',
 'transport_followup_mechanism_variation': '2725e1b7940683b696b5f93c90a1abbf7ba4c001915ce13cf43cf9dfadd8c851',
 'transport_followup_relative_audit': 'b7ff2a9c5d3fec423bf6811f0f444ea035c6115b7f91c36d6faca11b7a6626aa',
 'transport_instantiation_validity': '0ec0451563890ea9373a0710bbcbc33b2db28a14e405a798e6033062fab7634a',
 'transport_instantiation_performance': '5b2ea6000bfc123d9f52b38f37ddbb5aafb7eeb55139c8876a29d33879ee13ad',
 'transport_instantiation_tightness': '940106f9f33decab26a9033277c5bc354c6c2e8d09dc629b5b3b6954deb45311',
}
COLORS = ('tcOrange','tcBlue','tcGreen','tcPurple')
MARKS = ('*','triangle*','square*','diamond*')
POLICIES = ('Hessian','Endpoint','Frozen reference','Naive current')
WIDTHS = ('16','1','0.25')
TARGETS = ('0.25','0.5','1','2')
PALETTE = ''.join(r'\definecolor{' + name + '}{HTML}{' + color + '}\n'
                  for name,color in zip(COLORS, ('D55E00','0072B2','009E73','CC79A7')))


def numbers(cell):
    cell = cell.replace(r'\,', '')
    cell = re.sub(r'([0-9.]+)\\times10\^\{(-?\d+)\}', r'\1e\2', cell)
    return [float(x) for x in re.findall(r'-?(?:\d+\.\d*|\.\d+|\d+)(?:e[+-]?\d+)?', cell)]


def num(value):
    return format(float(value), '.12g')


def read_rows(root):
    if contract.package_required(None) and not contract.is_packaged_tree(root):
        raise ValueError('Required anonymous package declaration is missing')
    result = {}
    for name, digest in INPUT_HASHES.items():
        path = root / 'paper/tables' / (name + '.tex')
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Unreviewed chart input: ' + name)
        result[name] = [[c.strip() for c in line.removesuffix(r' \\').split('&')]
                        for line in path.read_text().splitlines() if re.match(r'^\d', line)]
    expected = (3,12,12,6,12,16,12)
    if tuple(map(len,result.values())) != expected:
        raise ValueError('Incomplete chart input grid')
    return result


def start(cols, rows, width=2.25, height=1.4, gap=0.62):
    return PALETTE + (r'\begin{tikzpicture}\begin{groupplot}['
        + 'group style={group size=' + str(cols) + ' by ' + str(rows)
        + ',horizontal sep=0.48in,vertical sep=' + str(gap) + 'in},'
        + f'scale only axis,width={width}in,height={height}in,'
        + r'/tikz/font=\normalsize,tick label style={font=\normalsize},'
        + r'label style={font=\normalsize},title style={font=\normalsize,align=center},'
        + r'axis lines=left,tick align=outside,clip=false,xmajorgrids,grid style={black!12}]' + '\n')


def axis(labels, title, xlabel, limits, *, hide=False):
    return (r'\nextgroupplot[title={' + title + '},xlabel={' + xlabel + '},'
        + 'ymin=-0.55,ymax=' + num(len(labels)-0.45) + ',ytick={'
        + ','.join(map(str,range(len(labels)))) + '},yticklabels={'
        + ','.join('' if hide else x for x in reversed(labels)) + '},' + limits + ']\n')


def point(cell, y, style=0, interval=False, ring=False, label=None):
    vals = numbers(cell) if isinstance(cell,str) else [float(cell)]
    x = vals[0]
    color,mark = COLORS[style],MARKS[style]
    text = ''
    if interval:
        if len(vals) != 3 or not vals[1] <= x <= vals[2]:
            raise ValueError('Invalid interval: ' + str(cell))
        lo,hi = vals[1:]
        text += r'\addplot[no marks,line width=1pt,color=' + color + '] coordinates {('
        text += num(lo)+','+num(y)+') ('+num(hi)+','+num(y)+')};\n'
        for end in (lo,hi):
            text += r'\addplot[no marks,color='+color+'] coordinates {('+num(end)+','+num(y-.08)+') ('+num(end)+','+num(y+.08)+')};\n'
    text += r'\addplot[only marks,mark='+mark+',mark size=2.6pt,color='+color+'] coordinates {('+num(x)+','+num(y)+')};\n'
    if ring:
        text += r'\addplot[only marks,mark=o,mark size=4.6pt,black] coordinates {('+num(x)+','+num(y)+')};\n'
    if label:
        text += r'\node[anchor=west,xshift=5pt] at (axis cs:'+num(x)+','+num(y)+') {'+label+'};\n'
    return text


def finish(scope, legend=()):
    text = r'\end{groupplot}\end{tikzpicture}\par\medskip'+'\n'
    if legend:
        for i,label in enumerate(legend):
            text += r'\tikz[baseline=-0.5ex]\draw[color='+COLORS[i]+',mark='+MARKS[i]+r'] plot coordinates {(0,0)}; '+label+r'\quad '
            if i==1 and len(legend)==4:
                text += r'\par\smallskip'+'\n'
        text += r'\par\medskip'+'\n'
    return text + r'\noindent\begin{minipage}{\linewidth}\raggedright '+scope+r'\end{minipage}'+'\n'


def build(root=None):
    root = ROOT if root is None else Path(root).resolve()
    tables = read_rows(root)
    output = {}
    def save(name,text):
        output[DESTINATION / ('transport_table_'+name+'.tex')] = '% Generated from reviewed numerical tables; no experiments rerun.\n'+text
    rows = tables['transport_followup_drift_bounds']
    labels = ['$W='+w+'$' for w in WIDTHS]
    s = start(1,2,4.8,1.55,0.85)
    s += axis(labels,'Largest recorded endpoint distance',r'Maximum $d_{\rm Th}$','xmin=0,xmax=1.85')
    for i,row in enumerate(rows): s += point(row[1],2-i,label=row[1])
    s += axis(labels,'How often each threshold is reached','Percentage of rounds','xmin=0,xmax=118,xtick={0,25,50,75,100}')
    for i,row in enumerate(rows):
        for j,count in enumerate(numbers(row[2])):
            s += point(count/500,2-i+(1-j)*.28,j,label=str(int(count)))
    s += finish(r'Hessian histories: 50 seeds $\times$ 1000 rounds per condition. Labels in the lower panel are counts out of 50,000. Thresholds are nested; rounds are dependent. No uncertainty intervals.',
                (r'$d_{\rm Th}\ge0.01$',r'$d_{\rm Th}\ge0.1$',r'$d_{\rm Th}\ge1$'))
    save('drift',s)
    rows = tables['transport_followup_same_history']
    s = start(1,3,4.8,1.35,0.68)
    for k,w in enumerate(WIDTHS):
        s += axis(POLICIES,'$W='+w+'$; rows identify logged behavior','Mean one-step pseudo-regret' if k==2 else '', 'xmin=0,xmax=0.36,xtick={0,0.1,0.2,0.3}')
        for i,row in enumerate(rows[k*4:k*4+4]):
            for j,cell in enumerate(row[2:]): s += point(cell,3-i+(.3-.2*j),j,ring=i==j)
    s += finish(r'Each mean uses 50,000 dependent recorded states. Black rings identify the behavior policy\textquotesingle s own score. Other points are alternative recommendations at those states, not alternative adaptive trajectories. No uncertainty intervals.',POLICIES)
    save('same_history',s)
    rows = tables['transport_followup_mechanism_variation']
    s = start(2,3,2.25,1.15,0.65)
    for k,w in enumerate(WIDTHS):
        for j,title in enumerate(('Width-argmax agreement','Strict sufficient condition')):
            s += axis(POLICIES,'$W='+w+r'$\\'+title,r'Rounds (\%; truncated axis)' if k==2 else '', 'xmin=92,xmax=100.5,xtick={92,96,100}',hide=bool(j))
            for i,row in enumerate(rows[k*4:k*4+4]): s += point(row[j+2],3-i,i,interval=True)
    s += finish(r'Every row diagnoses the Hessian score on the named behavior history. Dots: median over 50 seeds. Whiskers: minimum--maximum seed range, not confidence intervals. Each seed contributes a fraction of 1000 rounds.')
    save('mechanism',s)
    rows = tables['transport_followup_relative_audit']
    s = start(1,2,4.8,1.4,0.75)
    for k,(title,xlabel,limits) in enumerate((('Width inflation', 'Mean effective / reference width (log scale)','xmode=log,xmin=0.95,xmax=18,xtick={1,2,5,10},xticklabels={1,2,5,10}'),('Immediate recommendation loss','Mean one-step pseudo-regret','xmin=0,xmax=0.18,xtick={0,0.05,0.1,0.15},xticklabels={0,0.05,0.1,0.15}'))):
        s += axis(labels,title,xlabel,limits)
        if k==0: s += r'\draw[dashed,black!60] (axis cs:1,-.5)--(axis cs:1,2.5);'+'\n'
        for i,row in enumerate(rows[k*3:k*3+3]):
            for j,cell in enumerate(row[1:]): s += point(cell,2-i+(.3-.2*j),j)
    s += finish(r'Hessian\textquotesingle s fixed histories; 50 seeds per condition. Width ratios average over five actions and 1000 rounds, then seeds. Reference ratio $=1$. These are fixed-state diagnostics, not adaptive policy outcomes. No uncertainty intervals.',('Dense endpoint','Uniform','Category symmetric','Category asymmetric'))
    save('relative',s)
    rows = tables['transport_instantiation_validity']
    labels = ['$'+r[0]+r'\,/\,'+r[1]+'$' for r in rows]
    s = start(2,1,2.25,3.65)
    for k,(title,xlabel,limits,columns) in enumerate((('Median trajectory-maximum','Distance (log scale)','xmode=log,xmin=5e-8,xmax=1',(7,8)),('Median terminal outcome','Regret or RHS (log scale)','xmode=log,xmin=20,xmax=20000',(9,10)))):
        s += axis(labels,title,xlabel,limits,hide=bool(k))
        for i,row in enumerate(rows):
            for j,col in enumerate(columns): s += point(row[col],11-i+(.14-.28*j),2*k+j)
    s += finish(r'Rows: $D_{\rm target}/T$; 50 runs per cell. Reference coverage and optimism are each 50/50 in every cell (pointwise exact 95\% CI: [92.9\%, 100\%]); deterministic failures and joint-event bound violations are zero. Cells are not pooled. Original raw trajectories are unavailable; these are retained aggregate summaries.',(r'Path certificate $\bar D^Q$',r'Endpoint distance $d_{\rm Th}$','Sharp RHS','Pseudo-regret'))
    save('original_validity',s)
    rows = tables['transport_instantiation_performance']
    s = start(2,4,2.25,1.03,0.63)
    for k,target in enumerate(TARGETS):
        for j in range(2):
            s += axis(POLICIES,r'$D_{\rm target}='+target+'$', ('Mean regret' if j==0 else 'Difference from Hessian') if k==3 else '','xmin=75,xmax=98,xtick={75,85,95}' if j==0 else 'xmin=-15,xmax=1,xtick={-15,-10,-5,0}',hide=bool(j))
            if j: s += r'\draw[dashed,black!60] (axis cs:0,-.5)--(axis cs:0,3.5);'+'\n'
            for i,row in enumerate(rows[k*4:k*4+4]): s += point(row[2 if j==0 else 5],3-i,i,interval=True)
    s += finish(r'$T=1000$; 50 paired evaluation seeds per condition. Whiskers: pointwise 95\% bootstrap confidence intervals, without simultaneous coverage. Negative paired differences favor the comparator. Conditions change the task as well as curvature. Retained original-study summaries.')
    save('original_performance',s)
    labels = [r'$D_{\rm target}='+d+'$' for d in TARGETS]
    s = start(2,1,2.25,2.2)
    for j,(title,limits) in enumerate((('Median regret','xmin=75,xmax=98'),('Interquartile range','xmin=0,xmax=10'))):
        s += axis(labels,title,title,limits,hide=bool(j))
        for k in range(4):
            for i,row in enumerate(rows[k*4:k*4+4]): s += point(row[3+j],3-k+(.3-.2*i),i)
    s += finish(r'$T=1000$; descriptive summaries over 50 runs per cell, without uncertainty intervals. IQR is shown directly: separate quartiles are not available. Every policy retains optimism in 50/50 runs per condition (pointwise exact 95\% CI: [92.9\%,100\%]).',POLICIES)
    save('original_distribution',s)
    rows = tables['transport_instantiation_tightness']
    s = start(2,2,2.25,1.7,0.93)
    specs = ((r'Path certificate / endpoint','Ratio (log scale)','xmode=log,xmin=3e4,xmax=4e6',2),(r'Path certificate / quadrature','Ratio (log scale)','xmode=log,xmin=3e4,xmax=4e6',3),(r'Quadrature / endpoint','Ratio','xmin=1,xmax=1.3',4),('Excluded endpoint denominators',r'Count $n_0$','xmin=0,xmax=60',None))
    for p,(title,xlabel,limits,col) in enumerate(specs):
        s += axis(labels,title,xlabel,limits,hide=bool(p%2))
        for k in range(4):
            for j,row in enumerate(rows[k*3:k*3+3]):
                value = numbers(row[col].split('(')[0])[0] if col else int(re.search(r'n_0=(\d+)',row[2])[1])
                s += point(value,3-k+(.23-.23*j),j)
    s += finish(r'Medians over eligible pooled seed--round or seed--checkpoint ratios; denominators at or below the declared tolerance are excluded. The other two ratios exclude zero denominators in every cell. Target values are design conditions, not measured drift. No uncertainty intervals.',('$T=250$','$T=500$','$T=1000$'))
    save('original_path_ratios',s)
    s = start(1,3,4.8,1.15,0.93)
    for title,xlabel,limits,col in ((r'Transport multiplier',r'Median $e^{\bar D^Q/2}$','xmin=1,xmax=1.3,xtick={1,1.1,1.2,1.3}',5),('Historical radius','Median terminal radius','xmin=0,xmax=1.1',6),('Cumulative current bias','Median terminal bias','xmin=0,xmax=17',7)):
        s += axis(labels,title,xlabel,limits)
        for k in range(4):
            for j,row in enumerate(rows[k*3:k*3+3]): s += point(row[col],3-k+(.23-.23*j),j)
    s += finish(r'Transport multipliers pool all seed--round values. Terminal historical radii and cumulative current biases summarize 50 runs per cell. These marginal medians are not additive components of one bound. No uncertainty intervals.',('$T=250$','$T=500$','$T=1000$'))
    save('original_components',s)
    s = start(2,1,2.25,2.1)
    for j,(title,col) in enumerate((('Width / potential',8),('Sharp / simple bound',9))):
        s += axis(labels,title,'Median terminal ratio','xmin=0,xmax=1.05,xtick={0,0.5,1}',hide=bool(j))
        for k in range(4):
            for h,row in enumerate(rows[k*3:k*3+3]): s += point(row[col],3-k+(.23-.23*h),h)
    s += finish(r'Each point is a median over 50 terminal runs. Width/potential compares the frozen squared-width sum with its elliptic-potential bound; sharp/simple compares cumulative right-hand sides. No uncertainty intervals.',('$T=250$','$T=500$','$T=1000$'))
    save('original_bound_ratios',s)
    provenance = {'schema_version':1,'precision':'Published numerical-table precision; exact table cells retained in supplement.',
        'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'inputs':{'paper/tables/'+k+'.tex':v for k,v in INPUT_HASHES.items()},
        'outputs':{str(p):hashlib.sha256(t.encode()).hexdigest() for p,t in sorted(output.items())}}
    output[DESTINATION/'transport_table_provenance.json'] = json.dumps(provenance,indent=2,sort_keys=True)+'\n'
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    for relative,text in build(args.root).items():
        path = args.root/relative
        if args.check:
            if not path.is_file() or path.read_text()!=text:
                raise SystemExit('Chart differs: '+str(relative))
        else:
            path.write_text(text)
    print('Verified' if args.check else 'Generated', '10 charts and their provenance; no experiments rerun.')

if __name__=='__main__': main()
