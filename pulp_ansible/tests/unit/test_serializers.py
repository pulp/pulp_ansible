from unittest import mock
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from pulp_ansible.app.serializers import AnsibleRoleSerializer, AnsibleRoleVersionSerializer
from pulp_ansible.app.models import AnsibleRole

from pulpcore.plugin.models import Artifact


class TestAnsibleRoleSerializer(TestCase):
    """Test AnsibleRoleSerializer."""

    def setUp(self):
        """Set up the tests."""
        self.data = {'name': 'test1', 'namespace': 'testnamespace1'}

    def test_valid_data(self):
        """Test that the AnsibleRoleSerializer accepts valid data."""
        serializer = AnsibleRoleSerializer(data=self.data)
        self.assertTrue(serializer.is_valid())
        self.assertEqual(serializer.validated_data, self.data)

    def test_duplicate_data(self):
        """Test that the AnsibleRoleSerializer does not accept data."""
        AnsibleRole.objects.create(**self.data)
        serializer = AnsibleRoleSerializer(data=self.data)
        self.assertFalse(serializer.is_valid())


class TestAnsibleRoleVersionSerializer(TestCase):
    """Test AnsibleRoleVersionSerializer."""

    def setUp(self):
        """Set up the AnsibleRoleVersionSerializer tests."""
        self.artifact = Artifact.objects.create(
            md5="ec0df26316b1deb465d2d18af7b600f5",
            sha1="cf6121b0425c2f2e3a2fcfe6f402d59730eb5661",
            sha224="9a6297eb28d91fad5277c0833856031d0e940432ad807658bd2b60f4",
            sha256="c8ddb3dcf8da48278d57b0b94486832c66a8835316ccf7ca39e143cbfeb9184f",
            sha384="53a8a0cebcb7780ed7624790c9d9a4d09ba74b47270d397f5ed7bc1c46777a0fbe362aaf2bbe7f0966a350a12d76e28d",  # noqa
            sha512="a94a65f19b864d184a2a5e07fa29766f08c6d49b6f624b3dd3a36a98267b9137d9c35040b3e105448a869c23c2aec04c9e064e3555295c1b8de6515eed4da27d",  # noqa
            size=1024,
            file=SimpleUploadedFile('test_filename', b'test content')

        )
        self.role = AnsibleRole.objects.create(name='test1', namespace='testnamespace1')
        self.data = {
            "_artifact": "/pulp/api/v3/artifacts/{}/".format(self.artifact.pk),
            "version": "0.1.2.3",
        }

    def test_valid_data(self):
        """Test that the AnsibleRoleVersionSerializer accepts valid data."""
        view = mock.Mock()
        view.kwargs = {'role_pk': self.role.pk}
        serializer = AnsibleRoleVersionSerializer(data=self.data, context={'view': view})
        self.assertTrue(serializer.is_valid())

    def test_duplicate_data(self):
        """Test that the AnsibleRoleVersionSerializer does not accept data."""
        view = mock.Mock()
        view.kwargs = {'role_pk': self.role.pk}
        serializer = AnsibleRoleVersionSerializer(data=self.data, context={'view': view})
        self.assertTrue(serializer.is_valid())
        serializer.save()
        serializer = AnsibleRoleVersionSerializer(data=self.data, context={'view': view})
        self.assertFalse(serializer.is_valid())
