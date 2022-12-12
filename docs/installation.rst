Installation
============

Install using Ansible
---------------------

pulpcore provides an `Ansible Installer <https://galaxy.ansible.com/pulp/pulp_installer>`_ that can be used to
install ``pulp_ansible``. For example if your host is in your Ansible inventory as ``myhost`` you
can install onto it with:

.. code-block:: bash

    ansible-galaxy install geerlingguy.postgresql
    ansible-galaxy collection install pulp.pulp_installer

Create your pulp_ansible.yml playbook to use with the installer:

.. code-block:: yaml

  ---
  - hosts: all
    vars:
      pulp_settings:
        secret_key: << YOUR SECRET HERE >>
        content_origin: "http://{{ ansible_fqdn }}"
      pulp_default_admin_password: << YOUR PASSWORD HERE >>
      pulp_install_plugins:
        pulp-ansible: {}
    roles:
      - role: pulp.pulp_installer.pulp_all_services
    environment:
      DJANGO_SETTINGS_MODULE: pulpcore.app.settings

Then install it onto ``myhost`` with:

.. code-block:: bash

    ansible-playbook pulp_ansible.yml -l myhost


Install with pulplift
---------------------

`pulplift <https://github.com/pulp/pulplift>`_ combines the Ansible installer above with `Vagrant
<https://www.vagrantup.com/intro/index.html>`_ to easily try ``pulp_ansible`` on a local VM.

First you'll need to `install Vagrant <https://www.vagrantup.com/docs/installation/>`_.

.. code-block:: bash

    git clone --recurse-submodules https://github.com/pulp/pulplift.git
    cd pulplift

Configure pulplift to install ``pulp_ansible``:

.. code-block:: bash

    cat > local.user-config.yml <<EOF
    pulp_default_admin_password: password
    pulp_install_plugins:
      pulp-ansible: {}

    pulp_settings:
      secret_key: "unsafe_default"
      content_origin: "http://{{ ansible_fqdn }}"
    EOF

Then run Vagrant up for fedora30 using:

.. code-block:: bash

    vagrant up pulp3-sandbox-fedora30

Then once finished ssh to your ``pulp_ansible`` environment with:

.. code-block:: bash

    vagrant ssh pulp3-sandbox-fedora30


Install ``pulp_ansible`` From PyPI
----------------------------------

.. code-block:: bash

   pip install pulp-ansible

After installing the code, configure Pulp to connect to Redis and PostgreSQL with the `pulpcore
configuration instructions <https://docs.pulpproject.org/installation/
instructions.html#database-setup>`_


Install ``pulp_ansible`` from source
------------------------------------

.. code-block:: bash

   git clone https://github.com/pulp/pulp_ansible.git
   cd pulp_ansible
   python setup.py develop

After installing the code, configure Pulp to connect to Redis and PostgreSQL with the `pulpcore
configuration instructions <https://docs.pulpproject.org/installation/
instructions.html#database-setup>`_


Run Migrations
--------------

.. code-block:: bash

   django-admin migrate ansible


Run Services
------------

.. code-block:: bash

   django-admin runserver 24817
   gunicorn pulpcore.content:server --bind 'localhost:24816' --worker-class 'aiohttp.GunicornWebWorker' -w 2
   sudo systemctl restart pulpcore-resource-manager
   sudo systemctl restart pulpcore-worker@1


Checking your Installation
--------------------------

The Status API is a good way to check your installation. Here's an example using httpie in a Fedora
environment::

    sudo yum install httpie -y
    http :80/pulp/api/v3/status/
