# Testing

## Integration with the `ansible-galaxy`

These are all contained in the `pulp_ansible.tests.functional.cli` package. The following
workflows have tests:

- `ansible-galaxy collection install` - the installation of collection content is tested by
  `pulp_ansible.tests.functional.cli.test_collection_install`
- `ansible-galaxy collection publish` - this uploading of a collection to Pulp is tested by
  `pulp_ansible.tests.functional.cli.test_collection_upload`
- `ansible-galaxy role install` - the installation of role content is tested by
  `pulp_ansible.tests.functional.cli.test_role_install`

## Galaxy APIs

The Galaxy V2 and V3 APIs have tests.

- `pulp_ansible.tests.functional.api.collection.v2` - The V2 collection API
- `pulp_ansible.tests.functional.api.collection.v3` - The V3 collection API
- `pulp_ansible.tests.functional.api.role` - The V2 roles API

## Scale Testing Tools

These tools are contained in `pulp_ansible.tests.performance` and are standalone python utilities
to be called and passed arguments (they use argparse). Here are the tools:

- `generate_collections.py` which generates collections in parallel with Pulp workers.
- `fast_load_collections.py` which loads collections in parallel from a filesystem with Pulp
  workers.
- `create_repos_with_collections.py` which creates repositories and repository versions containing
  CollectionVersions already in Pulp.
- `promote.py` will select a content unit randomly and add it to N randomly selected
  AnsibleRepository objects. This is designed to benchmark adding new content to many repositories.
