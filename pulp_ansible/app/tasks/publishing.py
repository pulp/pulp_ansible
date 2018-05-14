import logging

from gettext import gettext as _

from pulpcore.plugin.models import (
    RepositoryVersion,
    Publication,
    PublishedArtifact,
    RemoteArtifact)
from pulpcore.plugin.tasking import WorkingDirectory

from pulp_ansible.app.models import AnsiblePublisher


log = logging.getLogger(__name__)


def publish(publisher_pk, repository_version_pk):
    """
    Use provided publisher to create a Publication based on a RepositoryVersion.

    Args:
        publisher_pk (str): Use the publish settings provided by this publisher.
        repository_version_pk (str): Create a publication from this repository version.
    """
    publisher = AnsiblePublisher.objects.get(pk=publisher_pk)
    repository_version = RepositoryVersion.objects.get(pk=repository_version_pk)

    log.info(
        _('Publishing: repository=%(repository)s, version=%(version)d, publisher=%(publisher)s'),
        {
            'repository': repository_version.repository.name,
            'version': repository_version.number,
            'publisher': publisher.name,
        })

    with WorkingDirectory():
        with Publication.create(repository_version, publisher) as publication:
            populate(publication)

    log.info(
        _('Publication: %(publication)s created'),
        {
            'publication': publication.pk
        })


def populate(publication):
    """
    Populate a publication.

    Create published artifacts and yield a Manifest Entry for each.

    Args:
        publication (pulpcore.plugin.models.Publication): A Publication to populate.

    Yields:
        Entry: Each manifest entry.
    """
    def find_artifact():
        _artifact = content_artifact.artifact
        if not _artifact:
            _artifact = RemoteArtifact.objects.filter(content_artifact=content_artifact).first()
        return _artifact

    for content in publication.repository_version.content:
        content_artifact = content.contentartifact_set.get()
        published_artifact = PublishedArtifact(
            relative_path=content_artifact.relative_path,
            publication=publication,
            content_artifact=content_artifact)
        published_artifact.save()
