from collections import defaultdict

from semantic_version import Version


def filter_highest_version(queryset):
    """Filter CollectionVersion by is_highest."""
    latest_pks = []
    namespace_name_dict = defaultdict(lambda: defaultdict(list))
    for namespace, name, version, pk in queryset.values_list(
        "namespace", "name", "version", "pk"
    ).iterator():
        version_entry = (Version(version), pk)
        namespace_name_dict[namespace][name].append(version_entry)

    for namespace, name_dict in namespace_name_dict.items():
        for name, version_list in name_dict.items():
            version_list.sort(reverse=True)
            latest_pk = version_list[0][1]
            latest_pks.append(latest_pk)

    return queryset.filter(pk__in=latest_pks)
