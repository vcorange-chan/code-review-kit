"""Install into this tool only, selecting the wheel for the actual execution OS."""
import subprocess
import sys
from _location import tool_root

root=tool_root()
command=[sys.executable,'-m','pip','install','--target',str(root/'.deps'),
         '--only-binary=:all:','--requirement',str(root/'requirements.txt'),'--disable-pip-version-check']
result=subprocess.run(command)
if result.returncode:raise SystemExit(result.returncode)
raise SystemExit(subprocess.run([sys.executable,str(root/'review.py'),'doctor']).returncode)
