"""Build a self-contained skill ZIP from a source allowlist; never bundle user data."""
from pathlib import Path
import shutil
import zipfile
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]


def build(out=None):
    out=Path(out or ROOT/'dist');out.mkdir(parents=True,exist_ok=True)
    stage=out/'code-review-kit'
    if stage.exists():
        # This staging directory is exclusively owned by this builder.
        if not stage.resolve().is_relative_to(out.resolve()):raise ValueError('Invalid stage path')
        shutil.rmtree(stage)
    shutil.copytree(ROOT/'skills/code-review-kit',stage,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    tool=stage/'scripts/tool';tool.mkdir()
    for name in ['review.py','requirements.txt']:
        shutil.copyfile(ROOT/name,tool/name)
    shutil.copytree(ROOT/'reviewkit',tool/'reviewkit',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    if (ROOT/'LICENSE').exists():shutil.copyfile(ROOT/'LICENSE',stage/'LICENSE')
    target=out/'code-review-kit-skill.zip'
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(stage.rglob('*')):
            if path.is_file():
                info=zipfile.ZipInfo(path.relative_to(out).as_posix(),date_time=(1980,1,1,0,0,0))
                info.external_attr=0o644<<16
                archive.writestr(info,path.read_bytes(),compress_type=zipfile.ZIP_DEFLATED)
    metadata={'file':target.name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
              'bytes':target.stat().st_size,'native_dependencies_bundled':False}
    (out/'skill-build.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    print(json.dumps(metadata));return target


if __name__=='__main__':build()
