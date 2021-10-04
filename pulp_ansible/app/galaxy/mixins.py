from pulpcore.plugin.tasking import dispatch

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

        return dispatch(import_collection, exclusive_resources=locks, kwargs=kwargs)
