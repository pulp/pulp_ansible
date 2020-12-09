from semantic_version import Version


def update_highest_version(collection_version):
    """
    Checks if this version is greater than the most highest one.

    If this version is the first version in collection, is_highest is set to True.
    If this version is greater than the highest version in collection, set is_highest
    equals False on the last highest version and True on this version.
    Otherwise does nothing.
    """
    last_highest = collection_version.collection.versions.filter(is_highest=True).first()
    if not last_highest:
        collection_version.is_highest = True
        return None
    if Version(collection_version.version) > Version(last_highest.version):
        last_highest.is_highest = False
        collection_version.is_highest = True
        last_highest.save()
        collection_version.save()
