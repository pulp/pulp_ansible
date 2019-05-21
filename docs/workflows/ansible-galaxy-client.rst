.. _ansible-galaxy-cli:

Install a Role, hosted by Pulp, using ``ansible-galaxy``
--------------------------------------------------------

Using a direct path
~~~~~~~~~~~~~~~~~~~

To install your role using a link to the direct tarball, do the following:

``$ ansible-galaxy install http://localhost:24816/pulp/content/dev/elastic/elasticsearch/6.2.4.tar.gz,,elastic.elasticsearch``


Using the Pulp Galaxy API
~~~~~~~~~~~~~~~~~~~~~~~~~~

Alternatively, Pulp offers a built-in Galaxy API. To use this, set up your distribution in your
ansible config (e.g. ``~/.ansible.cfg`` or ``/etc/ansible/ansible.cfg``):

.. code::

    [galaxy]
    server: http://localhost:24817/pulp_ansible/galaxy/dev

Then install your role using namespace and name:

.. code::

   $ ansible-galaxy install elastic.elasticsearch,6.2.4
   - downloading role 'elasticsearch', owned by elastic
   - downloading role from http://localhost:24816/pulp/content/dev/elastic/elasticsearch/6.2.4.tar.gz
   - extracting elastic.elasticsearch to /home/vagrant/.ansible/roles/elastic.elasticsearch
   - elastic.elasticsearch (6.2.4) was installed successfully
