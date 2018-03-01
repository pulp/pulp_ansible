from pulpcore.plugin import PulpPluginAppConfig


class PulpAnsiblePluginAppConfig(PulpPluginAppConfig):
    name = 'pulp_ansible.app'
    label = 'pulp_ansible'
