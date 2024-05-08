import pytest

from django.db import connection
from django.db.migrations.executor import MigrationExecutor


@pytest.fixture
def migrate(django_db_serialized_rollback):
    executor = MigrationExecutor(connection)

    def _migrate(target):
        connection.cursor().execute("SET CONSTRAINTS ALL IMMEDIATE;")
        state = executor.migrate(target)
        executor.loader.build_graph()
        return state.apps

    return _migrate
