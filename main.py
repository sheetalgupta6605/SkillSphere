from pathlib import Path
import sys


backend_directory = Path(__file__).resolve().parent / "backend"
if str(backend_directory) not in sys.path:
    sys.path.insert(0, str(backend_directory))

from app.main import app


__all__ = ["app"]
