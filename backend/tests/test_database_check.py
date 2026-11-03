"""Database readiness unit tests without substituting SQLite."""

from app.core import database_check
from app.core.errors import DatabaseUnavailableError


class FakeConnection:
    def __init__(self) -> None:
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        return None

    def execute(self, statement) -> None:
        self.executed.append(str(statement))


class FakeEngine:
    def __init__(self) -> None:
        self.connection = FakeConnection()

    def connect(self):
        return self.connection


def test_database_check_executes_select_one(monkeypatch) -> None:
    engine = FakeEngine()
    monkeypatch.setattr(database_check, "get_engine", lambda: engine)

    database_check.check_database_connection()

    assert engine.connection.executed == ["SELECT 1"]


def test_database_check_converts_connection_failure(monkeypatch) -> None:
    class FailingEngine:
        def connect(self):
            raise ConnectionError("database is unavailable")

    monkeypatch.setattr(database_check, "get_engine", lambda: FailingEngine())

    try:
        database_check.check_database_connection()
    except DatabaseUnavailableError:
        return

    raise AssertionError("database failures must become DatabaseUnavailableError")
