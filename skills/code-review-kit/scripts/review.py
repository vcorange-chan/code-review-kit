import runpy
import sys
from _location import tool_root

root=tool_root()
sys.path.insert(0,str(root))
runpy.run_path(str(root/'review.py'),run_name='__main__')
