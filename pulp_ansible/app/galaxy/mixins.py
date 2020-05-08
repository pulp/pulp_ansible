import shutil
from tempfile import NamedTemporaryFile

from django.conf import settings
from pulpcore.plugin.tasking import enqueue_with_reservation

from pulp_ansible.app.tasks.collections import import_collection


class UploadGalaxyCollectionMixin:
    """
    Provides a method that dispatches a task.
    """

    def _create_temp_file(self, validated_file):
        """
        Create the temporary file.
        """
        with NamedTemporaryFile(dir=settings.WORKING_DIRECTORY, delete=False) as temp_import_file:
            shutil.copyfileobj(validated_file, temp_import_file)
            return temp_import_file.name

    def _dispatch_import_collection_task(self, repository, temp_file_path, **kwargs):
        """
        Dispatch a Import Collection creation task.
        """
        locks = []
        kwargs["temp_file_path"] = temp_file_path
        if repository:
            locks.append(repository)
            kwargs["repository_pk"] = repository.pk

        return enqueue_with_reservation(import_collection, locks, kwargs=kwargs)
