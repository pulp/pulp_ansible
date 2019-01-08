import logging

from gettext import gettext as _

from pulpcore.plugin.models import RepositoryVersion, Publication


log = logging.getLogger(__name__)


def publish(repository_version_pk):
    """
    Create a Publication based on a RepositoryVersion.

    Args:
        repository_version_pk (str): Create a publication from this repository version.
    """
    repository_version = RepositoryVersion.objects.get(pk=repository_version_pk)
    with Publication.create(repository_version, pass_through=True) as publication:
        pass

    log.info(_('Publication: {publication} created').format(publication=publication.pk))
