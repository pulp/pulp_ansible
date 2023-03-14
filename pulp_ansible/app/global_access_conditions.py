from pulp_ansible.app import models


def v3_can_view_repo_content(request, view, action):
    """
    Check if the repo is private, only let users with view repository permissions
    view the collections here.
    """

    if "distro_base_path" in view.kwargs:
        distro_base_path = view.kwargs["distro_base_path"]
        repo = models.AnsibleDistribution.objects.get(base_path=distro_base_path).repository.cast()

        if repo.private:
            return request.user.has_perm("ansible.view_ansiblerepository")

    return True
