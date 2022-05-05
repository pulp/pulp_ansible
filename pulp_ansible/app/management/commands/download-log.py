from gettext import gettext as _
import json
import sys

from django.core.management import BaseCommand, CommandError

from pulp_ansible.app.models import DownloadLog


SEPARATOR = "\t"


class Command(BaseCommand):
    """
    Django management command for getting a data dump of deprecated permission.
    """

    help = _("Print the Download log.")

    def add_arguments(self, parser):
        """Add arguments."""
        parser.add_argument("--tabular", action="store_true", help=_("Output table format."))

    def handle(self, *args, **options):
        """Print the contents of the download log."""
        tabular = options.get("tabular", False)

        if tabular:
            try:
                from prettytable import PrettyTable
            except ImportError:
                raise CommandError("'prettytable' package must be installed for tabular output.")
        qs = DownloadLog.objects.order_by("pulp_created").prefetch_related("content_unit", "user")
        data = [
            {
                "time": str(entry.pulp_created),
                "content_unit": str(entry.content_unit.cast()),
                "user": entry.user and entry.user.username,
                "ip": entry.ip,
                "extra_data": entry.extra_data,
                "user_agent": entry.user_agent,
                "repository": entry.repository.name,
            }
            for entry in qs
        ]

        # User model permissions
        if tabular:
            print("# ==== " + _("Download Log") + " ====")
            table = PrettyTable()
            table.field_names = [
                _("time"),
                _("content unit"),
                _("user"),
                _("ip"),
                _("extra_data"),
                _("user agent"),
                _("repository"),
            ]
            table.add_rows(
                (
                    [
                        entry["time"],
                        entry["content_unit"],
                        entry["user"],
                        entry["ip"],
                        entry["extra_data"],
                        entry["user_agent"],
                        entry["repository"],
                    ]
                    for entry in data
                )
            )
            print(table)
            print()

        else:
            json.dump(
                data,
                sys.stdout,
            )
            print()
