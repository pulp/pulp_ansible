from gettext import gettext as _
import logging
import json
import semantic_version
import tempfile

from django.core.files import File

from pulpcore.plugin.models import RepositoryVersion, PublishedMetadata

from pulp_ansible.app.models import Collection, CollectionVersion, AnsiblePublication
from pulp_ansible.app.galaxy.v3.serializers import CollectionSerializer, UnpaginatedCollectionVersionSerializer


log = logging.getLogger(__name__)

def publish(base_path, repository_version_pk):
    """
    Create a Publication based on a RepositoryVersion.

    Args:
        repository_version_pk (str): Create a Publication from this RepositoryVersion.

    """
    repo_version = RepositoryVersion.objects.get(pk=repository_version_pk)

    log.info(_('Publishing: repository={repo}, version={version}').format(
        repo=repo_version.repository.name,
        version=repo_version.number,
    ))

    with tempfile.TemporaryDirectory("."):
        with AnsiblePublication.create(repo_version, pass_through=True) as publication:
            publication.base_path = base_path
            write_collections_metadata(publication, base_path)
            write_collection_versions_metadata(publication, base_path)

    log.info(_('Publication: {pk} created').format(pk=publication.pk))

def write_collections_metadata(publication, base_path):
    """
    Writes metadata for the /collections/all/ endpoint.

    Args:
        publication (pulpcore.plugin.models.Publication): A publication to generate metadata for
    """
    # this endpoint is too complicated, and technically isn't related to the problem, but it should
    # be pre-computed
    pass
    # distro_content = publication.repository_version.content
    # query_set = Collection.objects.filter(versions__in=distro_content)


def write_collection_versions_metadata(publication, base_path):
    """
    Writes metadata for the /collection_versions/all/ endpoint.

    Args:
        publication (pulpcore.plugin.models.Publication): A publication to generate metadata for
    """
    distro_content = publication.repository_version.content
    queryset = CollectionVersion.objects.select_related("content_ptr__contentartifact").filter(
            pk__in=distro_content
        )
    queryset = sorted(
        queryset, key=lambda obj: semantic_version.Version(obj.version), reverse=True
    )
    serialized_cvs = UnpaginatedCollectionVersionSerializer(queryset, many=True, context={"path": base_path})
    cv_path = "collection_versions"
    with open(cv_path, 'w') as cv:
        json.dump(serialized_cvs.data, cv)

    cv_metadata = PublishedMetadata.create_from_file(
        relative_path=cv_path,
        publication=publication,
        file=File(open(cv_path, 'rb'))
    )
    cv_metadata.save()
