from django.contrib.postgres import search as psql_search
from django.db import migrations


#  A view that does a view things:
#   * subquery to make a count of signatures attached to the CV and the repo
#   * subquery to make a count of deprecations related to the CV
#   * The app code has an unmanaged model that makes this view look like any
#     other model and is compatible with filtersets and serializers.
#
# Why?
#   * The x-repo search requirements want the same CV listed N times per
#     repositories containing the CV.
#   * Many models and objects and concepts desired for cross repo search
#     filtering are not directly related to repositories.
#   * Using the queryset language to build the counts for signatures and
#     deprecations were drifting from wizardry into impossibility.
#   * Creating a real index model requires too many hooks in various
#     obscure workflows for CRUD and new devs will always make mistakes.

CREATE_REPOSITORY_COLLECTIONVERSION_VIEW = '''
DROP VIEW IF EXISTS ansible_cross_repository_collection_versions_view CASCADE;
DROP VIEW IF EXISTS ansible_cross_repository_collection_version_signatures_view CASCADE;
DROP VIEW IF EXISTS ansible_cross_repository_collection_deprecations_view CASCADE;

DROP VIEW IF EXISTS ansible_cv_semantic_version_map_view CASCADE;
DROP VIEW IF EXISTS ansible_highest_repo_cv_view CASCADE;

DROP FUNCTION IF EXISTS parse_semantic_version;
DROP TYPE IF EXISTS semantic_parser_result;


CREATE TYPE semantic_parser_result AS (
  version INT[],
  prerelease text,
  is_prerelease BOOLEAN
);


CREATE OR REPLACE FUNCTION parse_semantic_version(text)
RETURNS semantic_parser_result AS $$
DECLARE
  version text := $1;
  sections text[];
  new_section text;
  this_section text;
  this_section_index INT;
  major INT;
  minor INT;
  patch INT;
  prerelease text;
  is_prerelease BOOLEAN;
BEGIN

  IF SUBSTRING(version, 1, 1) = 'v' THEN
    version := SUBSTRING(version FROM 2);
  END IF;

  this_section = version;
  FOR i IN 1..3 LOOP

    IF i = 3 THEN
        sections := array_append(sections, this_section);
    ELSE
        this_section_index := POSITION('.' IN this_section);

        IF this_section_index = 0 THEN
          new_section := this_section;
        ELSE
          new_section = SUBSTRING(this_section, 0, this_section_index);
          this_section := SUBSTRING(this_section, this_section_index + 1);
        END IF;

        sections := array_append(sections, new_section);
    END IF;

  END LOOP;

  SELECT sections[1]::INT INTO major;
  SELECT sections[2]::INT INTO minor;
  SELECT sections[3]::text INTO prerelease;

  IF POSITION('-' IN prerelease) > 0 THEN
    SELECT split_part(prerelease, '-', 1)::INT INTO patch;
    this_section_index := POSITION('-' IN prerelease);
    prerelease := SUBSTRING(prerelease, this_section_index + 1);
  ELSE
    IF POSITION('+' IN prerelease) > 0 THEN
        SELECT split_part(prerelease, '+', 1)::INT INTO patch;
        this_section_index := POSITION('+' IN prerelease);
        prerelease := SUBSTRING(prerelease, this_section_index + 1);
    ELSE
        IF POSITION('.' IN prerelease) > 0 THEN
            SELECT split_part(prerelease, '.', 1)::INT INTO patch;
            this_section_index := POSITION('.' IN prerelease);
            prerelease := SUBSTRING(prerelease, this_section_index + 1);
        ELSE
            SELECT prerelease::INT INTO patch;
            SELECT '' INTO prerelease;
        END IF;
    END IF;
  END IF;

  IF prerelease = '' THEN
    is_prerelease := FALSE;
  ELSE
    is_prerelease := TRUE;
  END IF;

  RETURN (ARRAY[major::INT, minor::INT, patch::INT], prerelease, is_prerelease);
END;
$$ LANGUAGE plpgsql;


-- a lookup map for a version string to a parsed semver
CREATE OR REPLACE VIEW ansible_cv_semantic_version_map_view AS
SELECT
    DISTINCT
    namespace,
    name,
    version AS oversion,
    (parsed_version).version AS semver,
    (parsed_version).prerelease AS prerelease,
    (parsed_version).is_prerelease AS is_prerelease
FROM
        (
            SELECT
            namespace,
            name,
            version,
            parse_semantic_version(version) AS parsed_version
        FROM
            ansible_collectionversion
        ) AS t
GROUP BY
    t.namespace,t.name,t.version,t.parsed_version
;


-- a lookup map for the highest verson by repo,namespace,name
CREATE OR REPLACE VIEW ansible_highest_repo_cv_view AS
SELECT
    repository_id,
    acv.namespace AS namespace,
    acv.name AS name,
    MAX(svm.semver) AS highest_semver
FROM
    core_repositorycontent crc
INNER JOIN
    ansible_collectionversion acv ON acv.content_ptr_id=crc.content_id
LEFT JOIN
    ansible_cv_semantic_version_map_view svm
    ON
    (
        svm.namespace=acv.namespace
        AND
        svm.name=acv.name
        AND
        svm.oversion=acv.version
    )
WHERE
    svm.is_prerelease IS FALSE
GROUP BY
    crc.repository_id,
    acv.namespace,
    acv.name
;


CREATE OR REPLACE VIEW ansible_cross_repository_collection_version_signatures_view AS
SELECT

    cr.pulp_id as repository_id,
    cr.name,
    acvs.content_ptr_id,
    acvs.signed_collection_id as collectionversion_id,

    MAX(crv1.number) as sig_vadded,
    coalesce(MAX(crv2.number), -1) as sig_vremoved,

    True as is_signed

from
    core_repositorycontent crc
left join
    ansible_collectionversionsignature acvs on acvs.content_ptr_id=crc.content_id
left join
    core_repository cr on cr.pulp_id=crc.repository_id
left join
    core_repositoryversion crv1 on crv1.pulp_id=crc.version_added_id
left join
    core_repositoryversion crv2 on crv2.pulp_id=crc.version_removed_id
left join
    ansible_collectionversion acv on acv.content_ptr_id=acvs.content_ptr_id
WHERE
    acvs.content_ptr_id is not null
GROUP BY
    cr.pulp_id, acvs.content_ptr_id
HAVING
    MAX(crv1.number) > coalesce(MAX(crv2.number), -1)
;

CREATE OR REPLACE VIEW ansible_cross_repository_collection_deprecations_view AS
SELECT

    cr.pulp_id as deprecated_repository_id,
    cr.name as deprecated_repository_name,

    acd.content_ptr_id as deprecation_ptr_id,
    acd.namespace as deprecated_namespace,
    acd.name as deprecated_name,

    CONCAT(cr.name, ':', acd.namespace, ':', acd.name) as deprecated_fqn,

    MAX(crv1.number) as deprecation_vadded,
    coalesce(MAX(crv2.number), -1) as deprecation_vremoved,

    True as is_deprecated

from
    core_repositorycontent crc
left join
    ansible_ansiblecollectiondeprecated acd on acd.content_ptr_id=crc.content_id
left join
    core_repository cr on cr.pulp_id=crc.repository_id
left join
    core_repositoryversion crv1 on crv1.pulp_id=crc.version_added_id
left join
    core_repositoryversion crv2 on crv2.pulp_id=crc.version_removed_id
GROUP BY
    cr.pulp_id, acd.content_ptr_id
HAVING
    acd.content_ptr_id is not NULL
    AND
    MAX(crv1.number) > coalesce(MAX(crv2.number), -1)
;

CREATE OR REPLACE VIEW ansible_cross_repository_collection_versions_view AS
SELECT

    CONCAT(cr.pulp_id, '-', acv.content_ptr_id) as id,

    cd.pulp_id as distribution_id,
    cd.pulp_id as dist_id,
    cd.name as distribution_name,
    cd.base_path as base_path,

    cr.pulp_id as repository_id,
    cr.pulp_id as repo_id,
    cr.name as reponame,

    acv.content_ptr_id as collectionversion_id,
    acv.namespace as namespace,
    acv.name as name,
    acv.version as version,

    svm.semver as semver,
    svm.prerelease as prerelease,
    svm.is_prerelease as is_prerelease,

    core_content.pulp_created as cv_created_at,
    core_content.pulp_last_updated as cv_updated_at,
    acv.requires_ansible as cv_requires_ansible,
    acv.dependencies as cv_dependencies,

    coalesce((rcd.is_deprecated), False) as is_deprecated,
    coalesce((rcvs.is_signed), False) as is_signed,

    MAX(habr.highest_semver) AS highest_semver

from
    core_repositorycontent crc
left join
    ansible_collectionversion acv on acv.content_ptr_id=crc.content_id
left join
    ansible_cv_semantic_version_map_view svm
    ON
    (
        svm.namespace=acv.namespace
        AND
        svm.name=acv.name
        AND
        svm.oversion=acv.version
    )
left join
    ansible_highest_repo_cv_view habr
    ON
    (
        habr.repository_id=crc.repository_id
        AND
        habr.namespace=acv.namespace
        AND
        habr.name=acv.name
    )
left join
    core_content on acv.content_ptr_id=core_content.pulp_id
left join
    core_repository cr on cr.pulp_id=crc.repository_id
left join
    core_distribution cd on cd.repository_id=cr.pulp_id
left join
    core_repositoryversion crv1 on crv1.pulp_id=crc.version_added_id
left join
    core_repositoryversion crv2 on crv2.pulp_id=crc.version_removed_id
left join
    ansible_cross_repository_collection_version_signatures_view rcvs on
    (
        cr.pulp_id=rcvs.repository_id
        AND
        acv.content_ptr_id=rcvs.collectionversion_id
    )
left join ansible_cross_repository_collection_deprecations_view rcd on
    CONCAT(cr.name, ':', acv.namespace, ':', acv.name)=rcd.deprecated_fqn
WHERE
    acv.content_ptr_id is not null
GROUP BY
    cd.pulp_id,
    cr.pulp_id,
    acv.content_ptr_id,
    core_content.pulp_id,
    svm.semver,
    svm.prerelease,
    svm.is_prerelease,
    rcvs.is_signed,
    rcd.is_deprecated
HAVING
   cd.pulp_id is not null
   AND
   MAX(crv1.number) > coalesce(MAX(crv2.number), -1)
;
'''


DROP_REPOSITORY_COLLECTIONVERSION_VIEW = '''
DROP VIEW IF EXISTS ansible_cross_repository_collection_versions_view CASCASE;
DROP VIEW IF EXISTS ansible_cross_repository_collection_version_signatures_view CASCADE;
DROP VIEW IF EXISTS ansible_cross_repository_collection_deprecations_view CASCADE;
DROP VIEW IF EXISTS ansible_cv_semantic_version_map_view CASCADE;
DROP VIEW IF EXISTS ansible_highest_repo_cv_view CASCADE;

DROP FUNCTION IF EXISTS parse_semantic_version;
DROP TYPE IF EXISTS semantic_parser_result;
'''


class Migration(migrations.Migration):

    dependencies = [
        ('ansible', '0046_add_fulltext_search_fix'),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_REPOSITORY_COLLECTIONVERSION_VIEW,
            reverse_sql=DROP_REPOSITORY_COLLECTIONVERSION_VIEW,
        ),
    ]
