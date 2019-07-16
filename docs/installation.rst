Installation
============

Install using Ansible
---------------------

pulpcore provides an `Ansible Installer <https://github.com/pulp/ansible-pulp>`_ that can be used to
install ``pulp_ansible``. For example if your host is in your Ansible inventory as ``myhost`` you
can install onto it with:

.. code-block:: bash

    git clone https://github.com/pulp/ansible-pulp.git

Create your pulp_ansible.yml playbook to use with the installer:

.. code-block:: yaml

   ---
   - hosts: all
     vars:
       pulp_settings:
         secret_key: secret
         ansible_api_hostname: 'http://localhost:24817'
         ansible_ansible_content_hostname: 'http://localhost:24816/pulp/content'
         content_host: 'localhost:24816' 
       pulp_default_admin_password: password
       pulp_install_plugins:
         pulp-ansible:
           app_label: "ansible"
     roles:
       - pulp-database
       - pulp-workers
       - pulp-resource-manager
       - pulp-webserver
       - pulp-content
     environment:
       DJANGO_SETTINGS_MODULE: pulpcore.app.settings

Then install it onto ``myhost`` with:

.. code-block:: bash

    ansible-playbook pulp_ansible.yaml -l myhost



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

    cat >local.user-config.ymll <<EOL
    pulp_default_admin_password: password
    pulp_install_plugins:
      pulp-ansible:
        app_label: "ansible"
    pulp_secret_key: "unsafe_default"
    EOL

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
configuration instructions <https://docs.pulpproject.org/en/3.0/nightly/installation/
instructions.html#database-setup>`_


Install ``pulp_ansible`` from source
------------------------------------

.. code-block:: bash

   git clone https://github.com/pulp/pulp_ansible.git
   cd pulp_ansible
   pip install -e .

After installing the code, configure Pulp to connect to Redis and PostgreSQL with the `pulpcore
configuration instructions <https://docs.pulpproject.org/en/3.0/nightly/installation/
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
   sudo systemctl restart pulp-resource-manager
   sudo systemctl restart pulp-worker@1
