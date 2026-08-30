import os
import sys
import types

# Ensure that imports like 'from backend.main import app' work even though Vercel 
# executes this from inside the 'backend' folder without a parent 'backend' folder.
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)

if "backend" not in sys.modules:
    backend_mod = types.ModuleType("backend")
    backend_mod.__path__ = [root_dir]
    sys.modules["backend"] = backend_mod

from backend.main import app
