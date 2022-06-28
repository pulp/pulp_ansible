import datetime

from rest_framework import viewsets

from django.shortcuts import get_object_or_404
from rest_framework.response import Response

from pulpcore.plugin.models import Task
from pulpcore.plugin.tasking import dispatch

from pulp_ansible.app.models import AnsibleDistribution, Role
from pulp_ansible.app.galaxy.serializers import GalaxyRoleSerializer
from pulp_ansible.app.galaxy.v1.tasks import legacy_role_import


STATE_MAP = {"COMPLETED": "SUCCESS"}


TYPE_MAP = {"RUNNING": "INFO", "WAITING": "INFO", "COMPLETED": "SUCCESS"}


class LegacyImportView(viewsets.ModelViewSet):
    """
    APIView for Roles.
    """

    model = Role
    serializer_class = GalaxyRoleSerializer
    authentication_classes = []
    permission_classes = []

    def get_queryset(self):
        """
        Get the list of items for this view.
        """
        # distro = get_object_or_404(AnsibleDistribution, base_path=self.kwargs["path"])
        distro = get_object_or_404(AnsibleDistribution, base_path="legacy")

        if distro.repository_version:
            distro_content = distro.repository_version.content
        else:
            distro_content = distro.repository.latest_version().content
        roles = Role.objects.distinct("namespace", "name").filter(pk__in=distro_content)

        namespace = self.request.query_params.get("owner__username", None)
        if namespace:
            roles = roles.filter(namespace__iexact=namespace)
        name = self.request.query_params.get("name", None)
        if name:
            roles = roles.filter(name__iexact=name)

        return roles

    def get(self, request):
        """
        Get a single legacy role import task.
        """
        task_id = int(request.GET.get("id", None))

        this_task = None
        for t in Task.objects.all():
            tid = str(t.pulp_id)
            thash = abs(hash(tid))
            if thash == task_id:
                this_task = t
                break

        pulp_state = this_task.state.upper()
        mtype = TYPE_MAP.get(pulp_state, pulp_state)
        msg = ""
        if this_task.error:
            if this_task.error.get("traceback"):
                tb = this_task.error["description"]
                tb += "\n"
                tb += this_task.error["traceback"]
                msg += tb

        v1state = STATE_MAP.get(pulp_state, pulp_state)
        if v1state == "SUCCESS":
            msg = "role imported successfully"
        elif v1state == "RUNNING":
            msg = "running"

        return Response(
            {
                "results": [
                    {
                        "state": v1state,
                        "id": task_id,
                        "summary_fields": {
                            "task_messages": [
                                {
                                    "id": datetime.datetime.now().isoformat(),
                                    "message_text": msg,
                                    "message_type": mtype,
                                    "state": v1state,
                                }
                            ]
                        },
                    }
                ]
            }
        )

    def post(self, request):
        """
        Start a legacy role import task.
        """
        kwargs = {
            "github_user": request.data.get("github_user"),
            "github_repo": request.data.get("github_repo"),
            "github_reference": request.data.get("github_reference", ""),
            "repository_id": request.data.get("repository_id"),
            "alternate_role_name": request.data.get("alternate_role_name"),
        }
        role_name = kwargs["alternate_role_name"] or kwargs["github_repo"].replace(
            "ansible-role-", ""
        )

        task = dispatch(legacy_role_import, kwargs=kwargs)
        hashed = abs(hash(str(task.pulp_id)))

        return Response(
            {
                "results": [
                    {
                        "id": hashed,
                        "github_user": kwargs["github_user"],
                        "github_repo": kwargs["github_repo"],
                        "summary_fields": {"role": {"name": role_name}},
                    }
                ]
            }
        )
