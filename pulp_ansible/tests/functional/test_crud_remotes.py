# coding=utf-8
"""Tests that CRUD remotes."""
from functools import partial
import random
import unittest

from requests.exceptions import HTTPError
from urllib.parse import urljoin

from pulp_smash import api, config, selectors, utils
from pulp_smash.tests.pulp3.constants import BASE_REMOTE_PATH, REPO_PATH
from pulp_smash.tests.pulp3.utils import gen_repo
from pulp_smash.tests.pulp3.utils import get_auth

ANSIBLE_FEED_URL = 'https://galaxy.ansible.com/api/v1/roles/?namespace=ansible'
ANSIBLE2_FEED_URL = 'https://galaxy.ansible.com/api/v1/roles/?namespace=pulp'
ANSIBLE_REMOTE_PATH = urljoin(BASE_REMOTE_PATH, 'ansible/')


skip_if = partial(selectors.skip_if, exc=unittest.SkipTest)


class CRUDRemotesTestCase(unittest.TestCase):
    """CRUD remotes."""

    @classmethod
    def setUpClass(cls):
        """Create class-wide variables.

        In order to create an remote a repository has to be created first.
        """
        cls.cfg = config.get_config()
        cls.client = api.Client(cls.cfg, api.json_handler)
        cls.client.request_kwargs['auth'] = get_auth()
        cls.remote = {}
        cls.repo = cls.client.post(REPO_PATH, gen_repo())

    @classmethod
    def tearDownClass(cls):
        """Clean class-wide variable."""
        cls.client.delete(cls.repo['_href'])

    def test_01_create_remote(self):
        """Create an remote."""
        body = _gen_verbose_remote()
        type(self).remote = self.client.post(ANSIBLE_REMOTE_PATH, body)
        for key in ('username', 'password'):
            del body[key]
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.remote[key], val)

    @skip_if(bool, 'remote', False)
    def test_02_read_remote(self):
        """Read a remote by its href."""
        remote = self.client.get(self.remote['_href'])
        for key, val in self.remote.items():
            with self.subTest(key=key):
                self.assertEqual(remote[key], val)

    @skip_if(bool, 'remote', False)
    def test_02_read_remotes(self):
        """Read an remote by its name."""
        page = self.client.get(ANSIBLE_REMOTE_PATH, params={
            'name': self.remote['name']
        })
        self.assertEqual(len(page['results']), 1)
        for key, val in self.remote.items():
            with self.subTest(key=key):
                self.assertEqual(page['results'][0][key], val)

    @skip_if(bool, 'remote', False)
    def test_03_partially_update(self):
        """Update an remote using HTTP PATCH."""
        body = _gen_verbose_remote()
        self.client.patch(self.remote['_href'], body)
        for key in ('username', 'password'):
            del body[key]
        type(self).remote = self.client.get(self.remote['_href'])
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.remote[key], val)

    @skip_if(bool, 'remote', False)
    def test_04_fully_update(self):
        """Update an remote using HTTP PUT."""
        body = _gen_verbose_remote()
        self.client.put(self.remote['_href'], body)
        for key in ('username', 'password'):
            del body[key]
        type(self).remote = self.client.get(self.remote['_href'])
        for key, val in body.items():
            with self.subTest(key=key):
                self.assertEqual(self.remote[key], val)

    @skip_if(bool, 'remote', False)
    def test_05_delete(self):
        """Delete an remote."""
        self.client.delete(self.remote['_href'])
        with self.assertRaises(HTTPError):
            self.client.get(self.remote['_href'])


def _gen_remote():
    """Return a semi-random dict for use in creating an remote."""
    return {
        'name': utils.uuid4(),
    }


def _gen_verbose_remote():
    """Return a semi-random dict for use in defining an remote.

    For most tests, it's desirable to create remotes with as few attributes
    as possible, so that the tests can specifically target and attempt to break
    specific features. This module specifically targets remotes, so it makes
    sense to provide as many attributes as possible.

    Note that 'username' and 'password' are write-only attributes.
    """
    attrs = _gen_remote()
    attrs.update({
        'url': random.choice((ANSIBLE_FEED_URL, ANSIBLE2_FEED_URL)),
        'password': utils.uuid4(),
        'username': utils.uuid4(),
        'validate': random.choice((False, True)),
    })
    return attrs
