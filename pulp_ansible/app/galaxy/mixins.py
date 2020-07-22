from pulpcore.plugin.tasking import enqueue_with_reservation

from pulp_ansible.app.tasks.collections import import_collection


class UploadGalaxyCollectionMixin:
    """
    Provides a method that dispatches a task.
    """

    def _dispatch_import_collection_task(self, temp_file_pk, repository=None, **kwargs):
        """
        Dispatch a Import Collection creation task.
        """
        locks = []
        kwargs["temp_file_pk"] = temp_file_pk
        if repository:
            locks.append(repository)
            kwargs["repository_pk"] = repository.pk

        return enqueue_with_reservation(import_collection, locks, kwargs=kwargs)
