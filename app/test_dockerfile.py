from pathlib import Path
import re

DOCKERFILE = Path(__file__).parent.parent / "Dockerfile"
TEXT = DOCKERFILE.read_text(encoding="utf-8") if DOCKERFILE.exists() else ""

def test_dockerfile_exists_and_not_empty():
    assert DOCKERFILE.exists(), f"Dockerfile not found at {DOCKERFILE}"
    assert DOCKERFILE.stat().st_size > 0

def test_base_image_is_python_3_11_slim():
    assert re.search(r"^\s*FROM\s+python:3\.11(?:-slim)?\b", TEXT, re.M), "Base image should be python:3.11(-slim)"

def test_workdir_and_copy_present():
    assert "WORKDIR /app" in TEXT
    assert "COPY . /app" in TEXT

def test_playwright_browsers_install_present():
    assert re.search(r"python\s+-m\s+playwright\s+install", TEXT), "Playwright browsers install missing"

def test_apt_get_packages_installed():
    assert re.search(r"apt-get\s+.*install\s+.*libnss3", TEXT, re.S), "Expected apt packages (libnss3 etc.)"

def test_env_expose_and_cmd_uvicorn():
    assert "ENV PYTHONUNBUFFERED=1" in TEXT
    assert re.search(r"EXPOSE\s+8000", TEXT)
    assert re.search(r"CMD\s+uvicorn\s+app\.main:app.*--port\s+\$PORT", TEXT), "CMD should start uvicorn using $PORT"