from django.contrib.postgres import search as psql_search
from django.db import migrations


# This query generates full text search index based
# the following data ranked from A to D:
#   - Namespace name (weight A)
#   - Collection name (weight A)
#   - Collection tags (weight B)
#   - Collection content names (weight C)
#   - Collection description (weight D)
TS_VECTOR_SELECT = '''
    setweight(to_tsvector(coalesce(namespace,'')), 'A')
    || setweight(to_tsvector(coalesce(name, '')), 'A')
    || (
      SELECT
        setweight(to_tsvector(
          coalesce(string_agg("ansible_tag"."name", ' '), '')
        ), 'B')
      FROM
        "ansible_tag" INNER JOIN "ansible_collectionversion_tags" ON ("ansible_tag"."pulp_id" = "ansible_collectionversion_tags"."tag_id")
    )
    || (
      SELECT
        setweight(to_tsvector(
          coalesce(string_agg(cvc ->> 'name', ' '), '')
        ), 'C')
      FROM jsonb_array_elements(cv.contents) AS cvc
    )
    || setweight(to_tsvector(coalesce(description, '')), 'D')
'''

# Generates search vector for existing CollectionVersion objects in the database.
POPULATE_COLLECTIONS_TS_VECTOR = f'''
UPDATE ansible_collectionversion AS c
SET search_vector = (
    SELECT {TS_VECTOR_SELECT}
    FROM ansible_collectionversion cv
    WHERE c.content_ptr_id = cv.content_ptr_id
)
'''


# Creates a database function and a trigger to update collection search
# vector field when a collection reference to a newer version is updated.
#
# Since it's not possible to insert a collection version before a collection, a latest_version_id
# always gets updated as a separated query after collectionversion is inserted. Thus only `ON
# UPDATE` trigger is required.
CREATE_COLLECTIONS_TS_VECTOR_TRIGGER = f'''
CREATE OR REPLACE FUNCTION update_collection_ts_vector()
    RETURNS TRIGGER AS
$$
BEGIN
    NEW.search_vector := (
        SELECT {TS_VECTOR_SELECT}
        FROM ansible_collectionversion cv
        WHERE cv.content_ptr_id = NEW.content_ptr_id
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
CREATE TRIGGER update_ts_vector
    BEFORE UPDATE
    ON ansible_collectionversion
    FOR EACH ROW
EXECUTE PROCEDURE update_collection_ts_vector();
'''

DROP_COLLECTIONS_TS_VECTOR_TRIGGER = '''
DROP TRIGGER IF EXISTS update_ts_vector ON ansible_collectionversion;
DROP FUNCTION IF EXISTS update_collection_ts_vector();
'''


class Migration(migrations.Migration):

    dependencies = [
        ('ansible', '0003_add_tags_and_collectionversion_fields'),
    ]

    operations = [
        migrations.RenameField(
            model_name='tag',
            old_name='_id',
            new_name='pulp_id',
        ),
        migrations.AddField(
            model_name='collectionversion',
            name='search_vector',
            field=psql_search.SearchVectorField(default=''),
        ),
        migrations.RunSQL(
            sql=POPULATE_COLLECTIONS_TS_VECTOR,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql=CREATE_COLLECTIONS_TS_VECTOR_TRIGGER,
            reverse_sql=DROP_COLLECTIONS_TS_VECTOR_TRIGGER,
        )
    ]
