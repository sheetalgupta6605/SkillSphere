from pathlib import Path
import sys

import uvicorn


backend_directory = Path(__file__).resolve().parent
if str(backend_directory) not in sys.path:
    sys.path.insert(0, str(backend_directory))


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True, reload_dirs=[str(backend_directory / "app")])
