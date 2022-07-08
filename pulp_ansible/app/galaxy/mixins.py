from pulpcore.plugin.models import TaskGroup
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

    def _dispatch_import_collection_task_lockless(self, temp_file_pk, repository, **kwargs):
        """
        Dispatch a Import Collection creation task without any locking on the repository.
        """
        kwargs["temp_file_pk"] = temp_file_pk
        kwargs["lockless"] = True
        task_group = TaskGroup.objects.create(description=f"Import collection to {repository.name}")
        kwargs["repository_pk"] = repository.pk

        async_result = dispatch(import_collection, task_group=task_group, kwargs=kwargs)
        return task_group, async_result
