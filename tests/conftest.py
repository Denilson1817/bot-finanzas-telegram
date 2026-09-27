import pytest

from app.db import create_session_factory


@pytest.fixture
def session_factory(tmp_path):
    db_path = tmp_path / "test.db"
    return create_session_factory(f"sqlite:///{db_path}")


@pytest.fixture
def session(session_factory):
    with session_factory() as s:
        yield s
