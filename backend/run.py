import os
import uvicorn
from app.core.config import SERVER_HOST, SERVER_PORT

if __name__ == "__main__":
    reload_enabled = os.getenv("MUSEFLOW_RELOAD", "0").lower() in ("1", "true", "yes")
    print(f"Starting MuseFlow Core at http://{SERVER_HOST}:{SERVER_PORT}")
    uvicorn.run("app.main:app", host=SERVER_HOST, port=SERVER_PORT, reload=reload_enabled)
