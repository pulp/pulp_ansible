from django.core.files.uploadedfile import SimpleUploadedFile


def test_collection_version_sha256_migrate(migrate):
    apps = migrate([("ansible", "0055_alter_collectionversion_version_alter_role_version")])
    Artifact = apps.get_model("core", "Artifact")
    Collection = apps.get_model("ansible", "Collection")
    CollectionVersion = apps.get_model("ansible", "CollectionVersion")

    collection = Collection.objects.create(namespace="snap", name="crackle")

    # Create two collection versions, because `sha256=null` can violate the uniquenes constraint.
    artifact1 = Artifact.objects.create(
        size=8, sha256="SENTINEL1", file=SimpleUploadedFile("foo", b"deadbeef")
    )
    cv1 = CollectionVersion.objects.create(
        pulp_type="collection_version",
        collection=collection,
        namespace="snap",
        name="crackle",
        version="1.0.0",
        version_minor="1",
        version_major="0",
        version_patch="0",
    )
    cv1.contentartifact_set.create(artifact=artifact1)

    artifact2 = Artifact.objects.create(
        size=8, sha256="SENTINEL2", file=SimpleUploadedFile("foo", b"beefdead")
    )
    cv2 = CollectionVersion.objects.create(
        pulp_type="collection_version",
        collection=collection,
        namespace="snap",
        name="crackle",
        version="2.0.0",
        version_minor="2",
        version_major="0",
        version_patch="0",
    )
    cv2.contentartifact_set.create(artifact=artifact2)

    apps = migrate([("ansible", "0056_collectionversion_sha256")])
    CollectionVersion = apps.get_model("ansible", "CollectionVersion")

    cv1 = CollectionVersion.objects.get(pk=cv1.pk)
    assert cv1.sha256 == ""

    apps = migrate([("ansible", "0057_collectionversion_sha256_migrate")])
    CollectionVersion = apps.get_model("ansible", "CollectionVersion")

    cv1 = CollectionVersion.objects.get(pk=cv1.pk)
    assert cv1.sha256 == "SENTINEL1"

    apps = migrate([("ansible", "0058_fix_0056_regression")])
