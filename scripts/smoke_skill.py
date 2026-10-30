"""Execute the exact release ZIP in an isolated folder; no agent/model calls."""
from pathlib import Path
import tempfile
import subprocess
import sys
import zipfile
import json
import os

ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    folder=Path(temp)
    with zipfile.ZipFile(ROOT/'dist/code-review-kit-skill.zip') as archive:
        archive.extractall(folder)
    skill=folder/'code-review-kit'
    state=folder/'writable-state'
    def run(*args):
        result=subprocess.run([sys.executable,*map(str,args)],cwd=skill,text=True,capture_output=True,encoding='utf-8',env={**os.environ,'PYTHONUTF8':'1','CODE_REVIEW_KIT_STATE':str(state)})
        if result.returncode:raise RuntimeError(result.stderr+'\n'+result.stdout)
        return result.stdout
    run(skill/'scripts/setup.py')
    doctor=json.loads(run(skill/'scripts/review.py','doctor'))
    output=folder/'report'
    report=json.loads(run(skill/'scripts/review.py','business',
        '--manifest',ROOT/'examples/document-pipeline/business.json','--repo',ROOT/'examples/document-pipeline',
        '--explanations',ROOT/'examples/document-pipeline/explanations.json','--depth','0','--max-nodes','64','--out',output,
        '--cache',folder/'cache'))
    assert doctor['ok'] and report['cards']==14 and report['explained']==14 and not report['stale_cards']
    assert state.is_dir() and not (skill/'scripts/tool/.deps').exists()
    print(json.dumps({'zip_executed':True,'cards':14,'stale_cards':report['stale_cards'],'native_platform_install':True,'dependency_state_outside_skill':True}))
