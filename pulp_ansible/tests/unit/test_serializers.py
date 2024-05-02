import hashlib
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
        rawbin = b"test content"
        self.artifact = Artifact.objects.create(
            size=len(rawbin),
            file=SimpleUploadedFile("test_filename", rawbin),
            **{
                algorithm: hashlib.new(algorithm, rawbin).hexdigest()
                for algorithm in Artifact.DIGEST_FIELDS
            },
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
