from pathlib import Path
from dotenv import load_dotenv

# load .env from project folder so the server process sees SUPABASE_*/OPENAI_*
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

from uvicorn.config import Config
from uvicorn.server import Server
import importlib
import traceback
import os

try:
    mod = importlib.import_module("app.main")
    app = getattr(mod, "app")
    print("Imported app:", app)
except Exception:
    print("Error importing app:")
    traceback.print_exc()
    raise SystemExit(1)

PORT = int(os.getenv("UVICORN_PORT", "8000"))
config = Config(app=app, host="127.0.0.1", port=PORT, log_level="debug")
server = Server(config)

print("Starting server.run() (blocking) ...")
try:
    server.run()
    print("server.run() returned")
    print("server.started:", getattr(server, "started", None))
    print("server.should_exit:", getattr(server, "should_exit", None))
except Exception:
    print("Exception from server.run():")
    traceback.print_exc()

def process_lead_with_openai(lead, openai_client=None, db=None):
    """
    Process a single lead. Accepts:
      - lead (required)
      - openai_client (optional) -> if None, create or pick default
      - db (optional) -> if provided, persist results
    """
    # ensure lead is available
    if lead is None:
        raise ValueError("lead is required")

    # lazily obtain openai client if not supplied
    if openai_client is None:
        from .openai_client import get_default_openai_client  # adjust import as needed
        openai_client = get_default_openai_client()

    # do processing (sync example)
    result = openai_client.process(lead)  # replace with your real call

    if db is not None:
        # persist or update DB
        db.save(result)  # adjust to your DB API

    return result