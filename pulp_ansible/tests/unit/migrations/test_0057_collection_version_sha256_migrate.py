from django.core.files.uploadedfile import SimpleUploadedFile


def test_collection_version_sha256_migrate(migrate):
    apps = migrate([("ansible", "0055_alter_collectionversion_version_alter_role_version")])
    Artifact = apps.get_model("core", "Artifact")
    Collection = apps.get_model("ansible", "Collection")
    CollectionVersion = apps.get_model("ansible", "CollectionVersion")

    artifact = Artifact.objects.create(
        size=8, sha256="SENTINEL", file=SimpleUploadedFile("foo", b"deadbeef")
    )
    collection = Collection.objects.create(
        namespace="snap",
        name="crackle",
    )
    cv = CollectionVersion.objects.create(
        pulp_type="collection_version",
        collection=collection,
        namespace="snap",
        name="crackle",
        version="pop",
        version_minor="1",
        version_major="2",
        version_patch="3",
    )
    cv.contentartifact_set.create(artifact=artifact)

    apps = migrate([("ansible", "0056_collectionversion_sha256")])
    CollectionVersion = apps.get_model("ansible", "CollectionVersion")

    cv = CollectionVersion.objects.get(pk=cv.pk)
    assert cv.sha256 == ""

    apps = migrate([("ansible", "0057_collectionversion_sha256_migrate")])
    CollectionVersion = apps.get_model("ansible", "CollectionVersion")

    cv = CollectionVersion.objects.get(pk=cv.pk)
    assert cv.sha256 == "SENTINEL"

    apps = migrate([("ansible", "0058_collectionversion_unique_sha256")])
    CollectionVersion = apps.get_model("ansible", "CollectionVersion")

    cv = CollectionVersion.objects.get(pk=cv.pk)
    assert cv.sha256 == "SENTINEL"
