def test_cross_repo_search_migration(migrate):
    apps = migrate([("ansible", "0050_crossrepositorycollectionversionindex")])
    AnsibleRepository = apps.get_model("ansible", "AnsibleRepository")
    AnsibleDistribution = apps.get_model("ansible", "AnsibleDistribution")

    # Make a Repository
    repository = AnsibleRepository.objects.create(pulp_type="ansible", name="foobar")
    repository.versions.create(number=0)

    # Make a Distribution
    AnsibleDistribution.objects.create(
        pulp_type="ansible", name="foobar", base_path="foobar", repository=repository
    )

    # Migrate the data
    migrate([("ansible", "0051_cvindex_build")])
