"""
main.py  (project root entry point)

Uvicorn entry point.
Run with:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Or simply:
    python main.py
"""
import uvicorn

from app.main import app  # noqa: F401  — exported for 'uvicorn main:app'

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None,   # Use our custom logging setup, not uvicorn's default
    )
