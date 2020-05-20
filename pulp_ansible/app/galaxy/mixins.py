from pulpcore.plugin.tasking import enqueue_with_reservation

from pulp_ansible.app.tasks.collections import import_collection


class UploadGalaxyCollectionMixin:
    """
    Provides a method that dispatches a task.
    """

    def _dispatch_import_collection_task(self, artifact_pk, repository=None, **kwargs):
        """
        Dispatch a Import Collection creation task.
        """
        locks = [str(artifact_pk)]
        kwargs["artifact_pk"] = artifact_pk
        if repository:
            kwargs["repository_pk"] = str(repository.pk)

        return enqueue_with_reservation(import_collection, locks, kwargs=kwargs)
