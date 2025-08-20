import importlib
import traceback
import uvicorn

try:
    mod = importlib.import_module("app.main")
    app = getattr(mod, "app")
    print("Imported app:", app)
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="debug")
except Exception:
    traceback.print_exc()