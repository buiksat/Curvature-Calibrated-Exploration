#!/usr/bin/env python3
"""External driver of the unchanged repository Claude review runner."""
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys

RUNNER = Path('/workspace/Curvature-Calibrated-Exploration/tools/claude_review.py')
OUT = Path('/workspace/cce-research/review/publication_assessment_fable')
MODEL = 'claude-fable-5'
MAIN = 'add7a565e779230949b72c2f3018ae4753ac3c97'
RESEARCH = '8647166427c8c97e3a9230b40135809b82961ea4'

def sha(data): return hashlib.sha256(data).hexdigest()
def save(name,value): (OUT/name).write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')

spec = importlib.util.spec_from_file_location('existing_claude_runner', RUNNER)
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
r.MAX_TOOL_CALLS = 64
r.MAX_TOOL_BYTES = 512 * 1024

class Snapshot:
    def __init__(self):
        self.by_ref = {
            'manuscript':r.RepoSnapshot(RUNNER.parents[1], MAIN, MAIN),
            'implementation':r.RepoSnapshot('/workspace/cce-research',RESEARCH,RESEARCH),
        }
        self.refs = {key:snapshot.refs[key] for key,snapshot in self.by_ref.items()}
        self.files = {key:snapshot.files[key] for key,snapshot in self.by_ref.items()}
        self.coverage = []
    def invoke(self,name,arguments):
        if not isinstance(arguments,dict) or arguments.get('ref') not in self.by_ref:
            raise r.ReviewError('ref must be manuscript or implementation.')
        snapshot = self.by_ref[arguments['ref']]
        response = snapshot.invoke(name,arguments)
        record = {'name':name,'arguments':arguments,'response_utf8_sha256':sha(response.encode()),'response_bytes':len(response.encode())}
        if name in ('read_file','inspect_json'):
            record['source_git_blob'] = snapshot.files[arguments['ref']][arguments['path']]['oid']
            record['source_commit'] = self.refs[arguments['ref']]['sha']
        self.coverage.append(record)
        save('source_coverage.json',self.coverage)
        save('tool_responses/response_%03d.json'%len(self.coverage),{'request':record,'result':json.loads(response)})
        return response

class RecordingClient(r.APIClient):
    def __init__(self,key):
        super().__init__(key,timeout=300)
        self.responses = []
    def request(self,method,path,payload=None):
        response = super().request(method,path,payload)
        if method == 'POST':
            self.responses.append(response)
            save('raw_responses/response_%02d.json'%len(self.responses),response)
            returned = response.get('model')
            print(f'Received response {len(self.responses)}: model={returned}, stop={response.get("stop_reason")}.',flush=True)
            if returned != MODEL:
                raise r.ReviewError('Returned model differs from the explicitly requested model; response preserved and review stopped.')
        return response

manifest = {'created_at':dt.datetime.now(dt.timezone.utc).isoformat(),'requested_model':MODEL,'status':'prepared','access_verified':False,'purpose':'Fresh independent publication-worthiness and TMLR readiness assessment','limits':{'max_turns':12,'max_tokens_per_response':12000,'max_tool_calls':r.MAX_TOOL_CALLS,'max_tool_bytes':r.MAX_TOOL_BYTES},'runner_sha256':sha(RUNNER.read_bytes()),'external_driver_sha256':sha(Path(__file__).read_bytes())}
client = None
try:
    assert not (OUT/'manifest.json').exists(), 'Refuse to overwrite existing review.'
    for directory in ('raw_responses','tool_responses'):
        (OUT/directory).mkdir(exist_ok=False)
    snapshot = Snapshot()
    prompt = (OUT/'prompt.md').read_text()
    manifest.update(refs=snapshot.refs,prompt_sha256=sha(prompt.encode()),tracked_files={key:sorted(files) for key,files in snapshot.files.items()})
    r.save_manifest(OUT,manifest)
    key = os.environ.get('ANTHROPIC_API_KEY')
    if not key: raise r.ReviewError('ANTHROPIC_API_KEY is missing from the secure environment.')
    client = RecordingClient(key)
    model, available = r.resolve_model(client,MODEL)
    manifest.update(access_verified=True,available_models=available,model=model)
    r.save_manifest(OUT,manifest)
    print(f'Access verified: exact requested model {model}. Beginning publication assessment of two pinned commits.',flush=True)
    r.run_review(client,snapshot,prompt,model,OUT,max_turns=12,max_tokens=12000,manifest=manifest)
    final = client.responses[-1]
    exact = '\n\n'.join(block.get('text','') for block in final['content'] if block.get('type')=='text')
    save('verbatim_review.json',{'text':exact,'sha256_utf8':sha(exact.encode())})
    manifest.update(returned_models=sorted({x.get('model') for x in client.responses}),final_stop_reason=final.get('stop_reason'),response_ids=[x.get('id') for x in client.responses],completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),tool_call_count=len(manifest['tool_calls']),successful_tool_access_count=len(snapshot.coverage),review_sha256=sha((OUT/'review.md').read_bytes()),review_bytes=(OUT/'review.md').stat().st_size,verbatim_review_sha256=sha(exact.encode()),verbatim_review_bytes=len(exact.encode()),qualification='Complete API response with read-only pinned text-source inspection; no execution, rendered-PDF inspection, external literature/policy search, or independent raw-data replay.')
    r.save_manifest(OUT,manifest)
    record = {k:v for k,v in manifest.items() if k not in ('tracked_files','tool_calls')}
    save('review_record.json',record)
    (OUT/'partial-review.md').unlink(missing_ok=True)
    (OUT/'README.md').write_text('# Fresh Fable publication assessment\n\n`review.md` is the complete model review, without editorial changes (the existing runner adds a terminal newline). `verbatim_review.json` preserves its exact returned text; `raw_responses/` retains every full API response. `prompt.md`, `review_record.json`, `manifest.json`, `source_coverage.json`, and `tool_responses/` record the request, model, immutable commits, usage, stop reason and accessed evidence. This is a source-inspection review, not an acceptance prediction, test execution, raw replay, rendered-PDF inspection or live literature search. No model substitution or automatic paid-request retry occurred.\n')
    files=sorted(p for p in OUT.rglob('*') if p.is_file() and p.name not in ('ARTIFACTS.sha256','execution.log'))
    (OUT/'ARTIFACTS.sha256').write_text(''.join(sha(p.read_bytes())+'  '+str(p.relative_to(OUT))+'\n' for p in files))
    print('COMPLETE '+str(OUT/'review.md'),flush=True)
    print(json.dumps(record,indent=2),flush=True)
except Exception as exc:
    message = str(exc) if isinstance(exc,r.ReviewError) else f'Local review orchestration failed ({type(exc).__name__}); no automatic retry.'
    manifest.update(status='incomplete' if client and client.responses else 'blocked',error=message)
    r.save_manifest(OUT,manifest)
    print(message,file=sys.stderr,flush=True)
    sys.exit(1)
