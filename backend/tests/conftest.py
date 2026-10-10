import os
import shutil
import tempfile
import pytest

# CRITICAL: Isolate test database to prevent polluting production user data
_test_data_dir = tempfile.mkdtemp(prefix="museflow_test_data_")
os.environ["MUSEFLOW_DATA_DIR"] = _test_data_dir

from app.core.db import init_db

@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    """Ensure database schema and tables are created in isolated test environment."""
    init_db()
    yield
    # Cleanup test data directory after all tests finish
    shutil.rmtree(_test_data_dir, ignore_errors=True)

