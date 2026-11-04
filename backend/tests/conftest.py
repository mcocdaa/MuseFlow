import os
import shutil
import tempfile

# Isolate pytest runs into a temporary data directory so tests (e.g. test_sync_engine)
# never mutate or wipe the user's production backend/data/db/museflow.db.
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="museflow_pytest_data_")
os.environ["MUSEFLOW_DATA_DIR"] = _TEST_DATA_DIR

from app.core.db import init_db  # noqa: E402
import app.models.entities  # noqa: F401, E402

init_db()


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(_TEST_DATA_DIR, ignore_errors=True)
