from unittest import mock
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from pulp_ansible.app.serializers import RoleSerializer

from pulpcore.plugin.models import Artifact


class TestRoleSerializer(TestCase):
    """Test RoleSerializer."""

    def setUp(self):
        """Set up the RoleSerializer tests."""
        self.artifact = Artifact.objects.create(
            sha224="9a6297eb28d91fad5277c0833856031d0e940432ad807658bd2b60f4",
            sha256="c8ddb3dcf8da48278d57b0b94486832c66a8835316ccf7ca39e143cbfeb9184f",
            sha384="53a8a0cebcb7780ed7624790c9d9a4d09ba74b47270d397f5ed7bc1c46777a0fbe362aaf2bbe7f0966a350a12d76e28d",  # noqa
            sha512="a94a65f19b864d184a2a5e07fa29766f08c6d49b6f624b3dd3a36a98267b9137d9c35040b3e105448a869c23c2aec04c9e064e3555295c1b8de6515eed4da27d",  # noqa
            size=1024,
            file=SimpleUploadedFile("test_filename", b"test content"),
        )
        self.data = {
            "artifact": "{}artifacts/{}/".format(settings.V3_API_ROOT, self.artifact.pk),
            "version": "0.1.2.3",
            "name": "test1",
            "namespace": "testns",
        }

    def test_valid_data(self):
        """Test that the RoleSerializer accepts valid data."""
        view = mock.Mock()
        serializer = RoleSerializer(data=self.data, context={"view": view})
        self.assertTrue(serializer.is_valid())

    def test_duplicate_data(self):
        """Test that the RoleSerializer does not accept data."""
        view = mock.Mock()
        serializer = RoleSerializer(data=self.data, context={"view": view})
        self.assertTrue(serializer.is_valid())
        serializer.save()
        serializer = RoleSerializer(data=self.data, context={"view": view})
        self.assertFalse(serializer.is_valid())
