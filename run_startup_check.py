import importlib
import traceback
from pathlib import Path
from dotenv import load_dotenv
from fastapi.testclient import TestClient
import inspect

# load .env so startup sees the same env you put in backend/.env
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

print("Importing app...")
try:
    mod = importlib.import_module("app.main")
    app = getattr(mod, "app")
    print("Imported app:", app)
except Exception:
    print("Error importing app:")
    traceback.print_exc()
    raise SystemExit(1)

def describe_callable(fn):
    try:
        name = getattr(fn, "__name__", repr(fn))
        module = getattr(fn, "__module__", "")
        is_coro = inspect.iscoroutinefunction(fn)
        return f"{module}.{name} (async={is_coro})"
    except Exception:
        return repr(fn)

print("\non_startup handlers:")
for fn in getattr(app.router, "on_startup", []):
    print(" -", describe_callable(fn))

print("\non_shutdown handlers:")
for fn in getattr(app.router, "on_shutdown", []):
    print(" -", describe_callable(fn))

print("\nRoutes (path -> endpoint):")
for r in app.routes:
    try:
        ep = getattr(r, "endpoint", None)
        print(f" - {getattr(r, 'path', repr(r))} -> {describe_callable(ep)}")
    except Exception:
        print(" - (route inspect failed)", repr(r))

print("\nRunning TestClient to exercise lifespan/startup handlers...")
try:
    with TestClient(app) as client:
        print("Startup completed successfully inside TestClient.")
        # optional small check
        try:
            r = client.get("/health")
            print("GET /health ->", r.status_code, r.text)
        except Exception as e:
            print("GET /health failed:", e)
except Exception:
    print("Startup/ Lifespan raised an exception:")
    traceback.print_exc()

print("\ndone")