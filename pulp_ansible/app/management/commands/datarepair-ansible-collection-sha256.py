from gettext import gettext as _

from django.core.management import BaseCommand
from django.db import transaction

from pulp_ansible.app.models import CollectionVersion


class Command(BaseCommand):
    """
    Django management command to repair ansible collection versions without sha256.
    """

    help = (
        "This script repairs ansible collection versions without sha256 if artifacts are available."
    )

    def add_arguments(self, parser):
        """Set up arguments."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=_("Don't modify anything, just collect results."),
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        failed_units = 0
        repaired_units = 0

        unit_qs = CollectionVersion.objects.filter(sha256__isnull=True)
        count = unit_qs.count()
        print(f"CollectionVersions to repair: {count}")
        if count == 0:
            return

        for unit in unit_qs.prefetch_related("contenartifact_set").iterator():
            try:
                content_artifact = unit.contentartifact_set.get()
                artifact = content_artifact.artifact
                unit.sha256 = artifact.sha256

                if not dry_run:
                    with transaction.atomic():
                        unit.save(update_fields=["sha256"])
            except Exception as e:
                failed_units += 1
                print(
                    f"Failed to migrate collection version '{unit.namespace}.{unit.name}' "
                    f"'{unit.version}': {e}"
                )
            else:
                repaired_units += 1

        print(f"Successfully repaired collection versions: {repaired_units}")
        print(f"Collection versions failed to repair: {failed_units}")
