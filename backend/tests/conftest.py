import pytest
from app.core.db import init_db

@pytest.fixture(scope="session", autouse=True)
def initialize_test_database():
    """Ensure database schema and tables are created before running tests."""
    init_db()
