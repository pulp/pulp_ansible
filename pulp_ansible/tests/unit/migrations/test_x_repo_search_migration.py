def test_cross_repo_search_migration(migrate):
    apps = migrate([("ansible", "0050_crossrepositorycollectionversionindex")])
    AnsibleRepository = apps.get_model("ansible", "AnsibleRepository")
    AnsibleDistribution = apps.get_model("ansible", "AnsibleDistribution")

    # make a repository
    repository = AnsibleRepository.objects.create(pulp_type="ansible", name="foobar")
    repository.versions.create(number=0)

    # make a distro
    distro = AnsibleDistribution.objects.create(
        pulp_type="ansible", name="foobar", base_path="foobar", repository=repository
    )
    migrate([("ansible", "0051_cvindex_build")])
