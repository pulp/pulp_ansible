"""Tests that verify download of content served by Pulp."""
import hashlib
import unittest
from random import choice
from urllib.parse import urljoin

from pulp_smash import api, config, utils
from pulp_smash.pulp3.utils import gen_distribution, gen_repo, publish, sync

from pulp_ansible.tests.functional.utils import (
    gen_ansible_publisher,
    gen_ansible_remote,
    get_ansible_content_paths,
)
from pulp_ansible.tests.functional.constants import (
    ANSIBLE_DISTRIBUTION_PATH,
    ANSIBLE_FIXTURE_URL,
    ANSIBLE_PUBLISHER_PATH,
    ANSIBLE_REMOTE_PATH,
    ANSIBLE_REPO_PATH,
)
from pulp_ansible.tests.functional.utils import set_up_module as setUpModule  # noqa:F401


@unittest.skip("FIXME: Re-enable later")
class DownloadContentTestCase(unittest.TestCase):
    """Verify whether content served by pulp can be downloaded."""

    def test_all(self):
        """Verify whether content served by pulp can be downloaded.

        The process of publishing content is more involved in Pulp 3 than it
        was under Pulp 2. Given a repository, the process is as follows:

        1. Create a publication from the repository. (The latest repository
           version is selected if no version is specified.) A publication is a
           repository version plus metadata.
        2. Create a distribution from the publication. The distribution defines
           at which URLs a publication is available, e.g.
           ``http://example.com/content/foo/`` and
           ``http://example.com/content/bar/``.

        Do the following:

        1. Create, populate, publish, and distribute a repository.
        2. Select a random content unit in the distribution. Download that
           content unit from Pulp, and verify that the content unit has the
           same checksum when fetched directly from Pulp-Fixtures.

        This test targets the following issues:

        * `Pulp #2895 <https://pulp.plan.io/issues/2895>`_
        * `Pulp Smash #872 <https://github.com/pulp/pulp-smash/issues/872>`_
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)

        repo = client.post(ANSIBLE_REPO_PATH, gen_repo())
        self.addCleanup(client.delete, repo["pulp_href"])

        body = gen_ansible_remote()
        remote = client.post(ANSIBLE_REMOTE_PATH, body)
        self.addCleanup(client.delete, remote["pulp_href"])

        sync(cfg, remote, repo)
        repo = client.get(repo["pulp_href"])

        # Create a publisher.
        publisher = client.post(ANSIBLE_PUBLISHER_PATH, gen_ansible_publisher())
        self.addCleanup(client.delete, publisher["pulp_href"])

        # Create a publication.
        publication = publish(cfg, publisher, repo)
        self.addCleanup(client.delete, publication["pulp_href"])

        # Create a distribution.
        body = gen_distribution()
        body["publication"] = publication["pulp_href"]
        distribution = client.post(ANSIBLE_DISTRIBUTION_PATH, body)
        self.addCleanup(client.delete, distribution["pulp_href"])

        # Pick a content unit, and download it from both Pulp Fixtures…
        unit_path = choice(get_ansible_content_paths(repo))
        fixtures_hash = hashlib.sha256(
            utils.http_get(urljoin(ANSIBLE_FIXTURE_URL, unit_path))
        ).hexdigest()

        # …and Pulp.
        client.response_handler = api.safe_handler

        unit_url = cfg.get_hosts("api")[0].roles["api"]["scheme"]
        unit_url += "://" + distribution["base_url"] + "/"
        unit_url = urljoin(unit_url, unit_path)

        pulp_hash = hashlib.sha256(client.get(unit_url).content).hexdigest()
        self.assertEqual(fixtures_hash, pulp_hash)
