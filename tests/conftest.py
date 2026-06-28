import os
import sys
import tempfile

# Make the repo root importable so `import app` / `import resolva` work no
# matter where pytest is invoked from.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Point all per-user data (knowledge base, audit log, config) at a throwaway
# temp directory so the test run never touches a real install, and force the
# offline path by making sure no API key is present in the environment.
_tmp = tempfile.mkdtemp(prefix="resolva-ci-")
os.environ["HOME"] = _tmp          # Linux / macOS data-dir base
os.environ["APPDATA"] = _tmp       # Windows data-dir base
os.environ.pop("ANTHROPIC_API_KEY", None)
