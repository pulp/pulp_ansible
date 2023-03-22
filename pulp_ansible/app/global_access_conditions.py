from pulp_ansible.app import models


def v3_can_view_repo_content(request, view, action):
    """
    Check if the repo is private, only let users with view repository permissions
    view the collections here.
    """

    if "distro_base_path" in view.kwargs:
        distro_base_path = view.kwargs["distro_base_path"]
        distro = models.AnsibleDistribution.objects.select_related(
            "repository", "repository_version"
        ).get(base_path=distro_base_path)
        if not (repo := distro.repository):
            if not (repo_ver := distro.repository_version):
                return False
            repo = repo_ver.repository
        repo = repo.cast()

        if repo.private:
            perm = "ansible.view_ansiblerepository"
            return request.user.has_perm(perm) or request.user.has_perm(perm, repo)

    return True


def v3_can_modify_repo_content(request, view, action):
    """
    Check if the user has Permission to modify Repository content.

    Returns True if the user has model or object-level permissions on the repository.
    False otherwise.
    """

    permission = "ansible.modify_ansible_repo_content"

    if request.user.has_perm(permission):
        return True

    if "distro_base_path" in view.kwargs:
        distro_base_path = view.kwargs["distro_base_path"]
        distro = models.AnsibleDistribution.objects.select_related(
            "repository", "repository_version"
        ).get(base_path=distro_base_path)
        if not (repo := distro.repository):
            if not (repo_ver := distro.repository_version):
                return False
            repo = repo_ver.repository
        repo = repo.cast()
        return request.user.has_perm(permission, repo)

    return False
