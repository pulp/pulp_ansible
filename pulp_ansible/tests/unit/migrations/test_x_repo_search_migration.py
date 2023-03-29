#!/usr/bin/env python

from importlib import import_module

from django.apps import apps
from django.db import connection
from django.test import TestCase
from django.db.migrations.executor import MigrationExecutor

from pulp_ansible.app.models import AnsibleDistribution, AnsibleRepository


class TestMigrations(TestCase):

    @property
    def app(self):
        return 'ansible'

    migrate_from = None
    migrate_to = None

    def setUp(self):
        assert self.migrate_from and self.migrate_to, \
            "TestCase '{}' must define migrate_from and migrate_to properties".format(type(self).__name__)
        self.migrate_from = [(self.app, self.migrate_from)]
        self.migrate_to = [(self.app, self.migrate_to)]
        executor = MigrationExecutor(connection)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        # Reverse to the original migration
        executor.migrate(self.migrate_from)

        self.setUpBeforeMigration(old_apps)

        # Run the migration to test
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()  # reload.
        executor.migrate(self.migrate_to)

        self.apps = executor.loader.project_state(self.migrate_to).apps

    def setUpBeforeMigration(self, apps):
        pass


class TestCrossRepoSearchMigration(TestMigrations):

    migrate_from = '0050_crossrepositorycollectionversionindex'
    migrate_to = '0051_cvindex_build'

    def setUpBeforeMigration(self, apps):
        # make a repository
        repo = AnsibleRepository.objects.create(name='foobar')

        # make a distro
        distro = AnsibleDistribution.objects.create(name='foobar', base_path='foobar', repository=repo)

    def test_nothing(self):
        pass
