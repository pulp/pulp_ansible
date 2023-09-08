from django.conf import settings
from django.utils.module_loading import import_string
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

    def get_deferred_context(self, request):
        context = {}
        if "file" in request.data:
            context["filename"] = request.data["file"].name
        return context


def perform_import(value):
    if isinstance(value, str):
        return import_string(value)
    elif isinstance(value, (tuple, list)):
        return [perform_import(v) for v in value]
    return value


class GalaxyAuthMixin:
    """
    Provides the authentication and permission classes from settings.
    """

    authentication_classes = perform_import(settings.ANSIBLE_AUTHENTICATION_CLASSES)
    permission_classes = perform_import(settings.ANSIBLE_PERMISSION_CLASSES)
