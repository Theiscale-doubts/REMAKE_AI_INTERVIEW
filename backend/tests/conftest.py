"""Global test configuration.

The single most important thing here: the test suite must never touch the real
Google spreadsheet. tools.py loads the developer's .env at import time, so
without this a test that exercises the sync path writes production rows — which
is exactly what happened once during development.

Setting the flag in conftest guarantees it applies to every test module,
regardless of import order or which file the run starts from.
"""
import os
import tempfile

# Must be set before tools/main are imported by any test module.
os.environ["VOXHIRE_SKIP_DOTENV"] = "1"
os.environ.setdefault("SHEET_NAME", "VoxHire-Test-DO-NOT-CREATE")
os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="voxhire-pytest-"))
# Deterministic config so tests never depend on the developer's local .env.
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("ADMIN_PASSWORD", "test-admin-pw")
os.environ.pop("google_credentials_json", None)


def pytest_report_header(config):
    return (
        f"voxhire: production isolated (SHEET_NAME={os.environ['SHEET_NAME']}, "
        f"DATA_DIR={os.environ['DATA_DIR']})"
    )
