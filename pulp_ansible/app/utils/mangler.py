#!/usr/bin/env python


'''
(py3) [jtanner@jtw530 role_mangler]$ ansible-galaxy role import --help
usage: ansible-galaxy role import [-h] [-s API_SERVER] [--token API_KEY] [-c] [-v] [--no-wait] [--branch REFERENCE] [--role-name ROLE_NAME] [--status] github_user github_repo

positional arguments:
  github_user           GitHub username
  github_repo           GitHub repository

optional arguments:
  -h, --help            show this help message and exit
  -s API_SERVER, --server API_SERVER
                        The Galaxy API server URL
  --token API_KEY, --api-key API_KEY
                        The Ansible Galaxy API key which can be found at https://galaxy.ansible.com/me/preferences.
  -c, --ignore-certs    Ignore SSL certificate validation errors.
  -v, --verbose         verbose mode (-vvv for more, -vvvv to enable connection debugging)
  --no-wait             Don't wait for import results.
  --branch REFERENCE    The name of a branch to import. Defaults to the repository's default branch (usually master)
  --role-name ROLE_NAME
                        The name the role should have, if different than the repo name
  --status              Check the status of the most recent import request for given github_user/github_repo.
'''

'''
# https://github.com/ansible/ansible/blob/devel/lib/ansible/galaxy/role.py
    def fetch(self, role_data):
        """
        Downloads the archived role to a temp location based on role data
        """
        if role_data:

            # first grab the file and save it to a temp location
            if self.download_url is not None:
                archive_url = self.download_url
            elif "github_user" in role_data and "github_repo" in role_data:
                archive_url = 'https://github.com/%s/%s/archive/%s.tar.gz' % (role_data["github_user"], role_data["github_repo"], self.version)
            else:
                archive_url = self.src
'''

'''
# https://galaxy.ansible.com/api/v1/roles/11121
{
  "id": 11121,
  "url": "/api/v1/roles/11121/",
  "related": {
    "dependencies": "/api/v1/roles/11121/dependencies/",
    "imports": "/api/v1/roles/11121/imports/"
  },
  "summary_fields": {
    "dependencies": [],
    "namespace": {
      "id": 36,
      "name": "zxcvbnius",
      "is_vendor": false
    },
    "platforms": [
      {
        "name": "Ubuntu",
        "release": "trusty"
      }
    ],
    "provider_namespace": {
      "id": 36,
      "name": "zxcvbnius"
    },
    "repository": {
      "id": 35125,
      "name": "ubuntu-server"
    },
    "tags": [
      "installer",
      "ubuntu"
    ],
    "versions": [],
    "videos": []
  },
  "created": "2016-07-22T03:50:37.163480Z",
  "modified": "2018-06-30T05:12:25.255624Z",
  "name": "ubuntu-server",
  "role_type": "ANS",
  "namespace": 36,
  "is_valid": true,
  "min_ansible_version": "2.0",
  "license": "MIT",
  "company": "duolC",
  "description": "Quick and easy base packages installer",
  "readme": "",
  "readme_html": "",
  "travis_status_url": "",
  "download_count": 96,
  "imported": "2016-07-22T00:39:22.846415-04:00",
  "active": true,
  "github_user": "zxcvbnius",
  "github_repo": "ubuntu-server",
  "github_branch": "master",
  "stargazers_count": 0,
  "forks_count": 0,
  "open_issues_count": 0,
  "commit": "92252c32ab5f02474385224ee81d690ccc18317a",
  "commit_message": "Update README.md",
  "commit_url": "https://github.com/zxcvbnius/ubuntu-server/commit/92252c32ab5f02474385224ee81d690ccc18317a",
  "issue_tracker_url": "https://github.com/zxcvbnius/ubuntu-server/issues"
}
'''


'''
# http://localhost:8002/api/automation-hub/v3/collections/geerlingguy/mysql/versions/1.0.2/
{
    "version": "1.0.2",
    "href": "/api/automation-hub/v3/collections/geerlingguy/mysql/versions/1.0.2/",
    "created_at": "2021-10-06T20:01:44.957795Z",
    "updated_at": "2021-10-06T20:01:44.957818Z",
    "requires_ansible": ">=2.10,<2.11",
    "artifact": {
        "filename": "geerlingguy-mysql-1.0.2.tar.gz",
        "sha256": "0be950bb08d82cea431356dfc11e12dfd8aaab6082183777f8ddeff88acea839",
        "size": 1575
    },
    "collection": {
        "id": "37fd69b4-c655-4e69-b870-29cd6edcf5d5",
        "name": "mysql",
        "href": "/api/automation-hub/v3/collections/geerlingguy/mysql/"
    },
    "download_url": "http://localhost:5001/api/automation-hub/v3/artifacts/collections/published/geerlingguy-mysql-1.0.2.tar.gz",
    "name": "mysql",
    "namespace": {
        "name": "geerlingguy"
    },
    "metadata": {
        "authors": [
            "geerlingguy"
        ],
        "contents": [],
        "dependencies": {},
        "description": "MySQL server for RHEL/CentOS and Debian/Ubuntu.",
        "documentation": "https://github.com/geerlingguy/ansible-role-mysql",
        "homepage": "https://github.com/geerlingguy/ansible-role-mysql",
        "issues": "https://github.com/geerlingguy/ansible-role-mysql/issues",
        "license": [
            "MIT"
        ],
        "repository": "https://github.com/geerlingguy/ansible-role-mysql",
        "tags": [
            "ngrole",
            "database",
            "mysql",
            "mariadb",
            "db",
            "sql"
        ]
    },
    "manifest": {},
    "files": {}
}
'''


import argparse
import json
import os
import shutil
import subprocess
import tempfile
import yaml

import requests
#from fuzzywuzzy import fuzz


LICENSES_URL = 'https://raw.githubusercontent.com/spdx/license-list-data/master/json/licenses.json'


def clean_tag(tag):
    # ERROR! Galaxy import process failed: Invalid collection metadata. 'tag' has invalid format: cloud:ec2 (Code: UNKNOWN)
    tag = tag.replace(':', '')
    tag = tag.replace(' ', '')
    tag = tag.replace('-', '')
    tag = tag.strip()
    return tag


def munge_role_name(role_name):
    if isinstance(role_name, dict):
        if 'src' in role_name:
            role_name = role_name['src']
        elif 'role' in role_name:
            role_name = role_name['role']
        elif 'name' in role_name:
            role_name = role_name['name']
        #else:
        #    import epdb; epdb.st()

    role_name = role_name.replace('-', '_')
    role_name = role_name.lower()
    return role_name


class CollectionSCMShim:

    def __init__(self, namespace, name, repository, branch=None, tag=None, sha=None):
        self.namespace = namespace
        self.name = name
        self.repository = repository
        self.branch = branch
        self.tag = tag
        self.sha = sha

        self.clone_path = tempfile.mkdtemp()
        self.tarfile = None

        self.clone_repo()
        self.build_artifact()

    @property
    def scm_sha(self):
        if self.sha is not None:
            return self.sha
        cmd = f'cd {self.clone_path} && git log -1 --pretty=format:"%H"'
        proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        self.sha = proc.stdout.decode('utf-8').strip()
        return self.sha

    def clone_repo(self):

        if os.path.exists(self.clone_path):
            shutil.rmtree(self.clone_path)

        # clone the repo
        cmd = f'git clone {self.repository} {self.clone_path}'
        subprocess.run(cmd, shell=True)

        # list the repo ...
        subprocess.run(f'find {self.clone_path}', shell=True)

        # set the right branch ...
        if self.branch:
            cmd = f'cd {self.clone_path} && git checkout {self.branch}'
            proc = subprocess.run(cmd, shell=True)

        # set the right commit sha ...
        if self.sha:
            cmd = f'cd {self.clone_path} && git checkout {self.sha}'
            proc = subprocess.run(cmd, shell=True)

    def build_artifact(self):
        cmd = f'cd {self.clone_path} && ansible-galaxy collection build .'
        proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        if proc.returncode != 0:
            raise Exception('build failure')
        self.tarfile = proc.stdout.decode('utf-8').strip().split()[-1]


class RoleMangler:

    _sha = None
    _role_path = None
    _collection_path = None
    _collection_tar = None
    _licenses = None

    def __init__(self, *args, **kwargs):
        self.github_user = kwargs.get('github_user')
        self.github_repo = kwargs.get('github_repo')
        self.role_name = kwargs.get('role_name')
        self.branch = kwargs.get('branch')
        self.server = kwargs.get('server')
        self.token = kwargs.get('token')
        self.version = kwargs.get('version')
        self._sha = kwargs.get('commit')

        # preload licenses ...
        self.licenses

        if self.github_user and self.github_repo:

            # clone the repo
            self._role_path = tempfile.mkdtemp()
            cmd = f'git clone {self.scm_url} {self._role_path}'
            subprocess.run(cmd, shell=True)

            # set the right branch ...
            if self.branch:
                cmd = f'cd {self._role_path} && git checkout {self.branch}'
                proc = subprocess.run(cmd, shell=True)

            # set the right commit sha ...
            if self._sha:
                cmd = f'cd {self._role_path} && git checkout {self._sha}'
                proc = subprocess.run(cmd, shell=True)

            # multi-role repos ...
            if os.path.exists(os.path.join(self._role_path, 'roles')):
                self._role_path = os.path.join(self._role_path, 'roles', self.role_name)

    @property
    def licenses(self):
        if self._licenses is not None:
            return self._licenses

        cfile = 'licenses.json'
        if os.path.exists(cfile):
            with open(cfile, 'r') as f:
                jdata = json.loads(f.read())

        else:
            rr = requests.get(LICENSES_URL)
            jdata = rr.json()

            with open(cfile, 'w') as f:
                f.write(json.dumps(jdata))

        self._licenses = [x['licenseId'] for x in jdata['licenses']]
        return self._licenses

    @property
    def scm_url(self):
        url = f'https://github.com/{self.github_user}/{self.github_repo}'
        return url

    @property
    def scm_sha(self):
        if self._sha is not None:
            return self._sha

        cmd = f'cd {self._role_path} && git log -1 --pretty=format:"%H"'
        proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        self._sha = proc.stdout.decode('utf-8').strip()

        return self._sha

    def get_role_data(self):
        mfiles = [
            os.path.join(self._role_path, 'meta', 'main.yml'),
            os.path.join(self._role_path, 'meta', 'main.yaml')
        ]
        for mfile in mfiles:
            if os.path.exists(mfile):
                with open(mfile, 'r') as f:
                    mdata = yaml.load(f.read())
                return mdata
        return {}

    def enumerate_license(self, rlicense):

        if rlicense == '' or rlicense is None:
            return 'Apache-2.0'

        if rlicense in self.licenses and rlicense not in ['GPL-3.0', 'GPL-2.0']:
            return rlicense
        elif 'MIT' in rlicense.upper():
            return 'MIT'
        elif 'gplv3' in rlicense.lower():
            return 'GPL-3.0-only'
        elif 'gplv2' in rlicense.lower():
            return 'GPL-2.0-only'
        elif 'general public license' in rlicense.lower() and '3' in rlicense:
            return 'GPL-3.0-only'
        elif 'general public license' in rlicense.lower() and '2' in rlicense:
            return 'GPL-2.0-only'
        elif 'gpl' in rlicense.lower():
            return 'GPL-3.0-only'
        elif 'gnu' in rlicense.lower():
            return 'GPL-3.0-only'
        elif 'BSD' in rlicense:
            return 'BSD-4-Clause'
        elif 'apache' in rlicense.lower() and '2' in rlicense:
            return 'Apache-2.0'
        elif 'apache' in rlicense.lower() and '1' in rlicense:
            return 'Apache-1.0'
        elif 'apache' in rlicense.lower():
            return 'Apache-2.0'
        elif rlicense == 'CC-BY':
            return 'CC-BY-1.0'
        elif 'goaccess' in rlicense.lower():
            return 'Apache-2.0'
        elif rlicense.lower() == 'public':
            return 'Apache-2.0'
        elif rlicense == 'aryanraj.org@ar913100':
            return 'Apache-2.0'
        elif 'cc0' in rlicense.lower():
            return 'CC0-1.0'
        elif rlicense.lower() == 'see license.txt':
            return 'Apache-2.0'
        elif rlicense.lower() == 'see license.md':
            return 'Apache-2.0'
        elif rlicense.lower() == 'the unlicense':
            return 'Apache-2.0'
        elif rlicense.lower() == 'see readme.md':
            return 'Apache-2.0'
        elif rlicense == 'BDS':
            return 'BSD-4-Clause'
        elif rlicense == 'All components of this product are Copyright (c) 2':
            return 'Apache-2.0'
        elif rlicense == 'as-is':
            return 'Apache-2.0'
        elif rlicense == 'opensource':
            return 'Apache-2.0'
        elif rlicense == 'Public Domain':
            return 'Apache-2.0'
        elif 'ALv2' in rlicense:
            return 'Apache-2.0'
        elif 'BST' in rlicense:
            return 'Apache-2.0'
        elif rlicense.lower() == 'proprietary':
            return 'Apache-2.0'
        elif 'unlicense' in rlicense.lower():
            return 'Unlicense'
        elif 'CC-BY-SA' in rlicense:
            return 'CC-BY-SA-1.0'
        elif rlicense == 'all rights reserved':
            return 'Apache-2.0'


        lmap = dict((x.lower(),x) for x in self.licenses if x.lower() != 'gpl-3.0')
        rlower = rlicense.lower()
        if rlower in lmap:
            return lmap[rlower]

        lmap_no_spaces_no_hyphens = dict((x.lower().replace(' ', '').replace('-',''),x) for x in self.licenses)
        rlower_no_spaces_no_hyphens = rlicense.lower().replace(' ', '').replace('-','')
        if rlower_no_spaces_no_hyphens in lmap_no_spaces_no_hyphens:
            return lmap_no_spaces_no_hyphens[rlower_no_spaces_no_hyphens]

        # fuzzy match
        scores = []
        for blicense in self.licenses:
            score = fuzz.ratio(rlower, blicense.lower())
            scores.append((score, blicense))
        scores = sorted(scores)
        if scores[-1][0] >= 50:
            return scores[-1][1]

        #print(rlicense)
        #import epdb; epdb.st()

        return 'Apache-2.0'

    def build_collection(self):
        tdir = tempfile.mkdtemp()
        cmd = f'cd {tdir} && ansible-galaxy collection init'
        cmd += f' {self.github_user}.{self.role_name}'
        proc = subprocess.run(cmd, shell=True)
        if proc.returncode != 0:
            raise Exception('init failure')

        cdir = os.path.join(tdir, self.github_user, self.role_name)
        galaxyfn = os.path.join(cdir, 'galaxy.yml')
        metafn = os.path.join(cdir, 'meta', 'main.yml')

        rdata = self.get_role_data()

        if os.path.exists(galaxyfn):
            with open(galaxyfn, 'r') as f:
                cdata = yaml.load(f.read())
        else:
            with open(metafn, 'r') as f:
                cdata = yaml.load(f.read())

        cdata['authors'] = [rdata['galaxy_info'].get('author', 'no-author')]
        if rdata['galaxy_info'].get('galaxy_tags'):
            cdata['tags'] = rdata['galaxy_info']['galaxy_tags'][:]
            cdata['tags'].insert(0, 'ngrole')
        else:
            cdata['tags'] = ['ngrole']

        #cdata['tags'] = [x.lower().replace(' ', '').replace('-', '') for x in cdata['tags']]
        cdata['tags'] = [clean_tag(x) for x in cdata['tags']]

        # ERROR! Galaxy import process failed: Invalid collection metadata. Expecting no more than 20 tags in metadata (Code: UNKNOWN)
        if len(cdata['tags']) > 20:
            cdata['tags'] = cdata['tags'][:19]

        cdata['description'] = rdata['galaxy_info'].get('description', '')
        if not rdata.get('dependencies'):
            cdata['dependencies'] = {}
        else:
            dnames = rdata['dependencies'][:]
            dnames = [munge_role_name(x) for x in dnames]
            cdata['dependencies'] = dict([(x, '*') for x in dnames])

        rlicense = rdata['galaxy_info']['license']
        if not rlicense:
            rlicense = 'MIT'
        if rlicense and isinstance(rlicense, list):
            rlicense = rlicense[0]

        cdata['license'] = self.enumerate_license(rlicense)
        cdata['repository'] = self.scm_url
        cdata['documentation'] = self.scm_url
        cdata['homepage'] = self.scm_url
        cdata['issues'] = self.scm_url + '/issues'
        #cdata['scm_url'] = self.scm_url
        #cdata['scm_branch'] = self.branch
        cdata['scm_sha'] = self.scm_sha
        cdata['scmref'] = None

        if self.version is not None:
            cdata['version'] = self.version

        with open(galaxyfn, 'w') as f:
            yaml.dump(cdata, f)

        cdir = os.path.join(tdir, self.github_user, self.role_name)
        mdir = os.path.join(cdir, 'meta')
        runtimefn = os.path.join(mdir, 'runtime.yml')
        if not os.path.exists(mdir):
            os.makedirs(mdir)
        with open(runtimefn, 'w') as f:
            yaml.dump({'requires_ansible': ">=2.10,<2.11"}, f)

        #import epdb; epdb.st()

        # now build it
        cmd = f'cd {cdir} && ansible-galaxy collection build'
        print(cmd)
        proc = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE)
        if proc.returncode != 0:
            raise Exception('build failure')
        self._collection_tar = proc.stdout.decode('utf-8').strip().split()[-1]

    def do_import(self):
        sha = self.scm_sha
        self.build_collection()

        if os.path.exists(os.path.basename(self._collection_tar)):
            os.remove(os.path.basename(self._collection_tar))

        shutil.copy(
            self._collection_tar,
            os.path.basename(self._collection_tar)
        )


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('object_type', choices=['role'])
    parser.add_argument('action', choices=['import'])
    parser.add_argument('github_user')
    parser.add_argument('github_repo')
    parser.add_argument('-s', '--server', help='API_SERVER')
    parser.add_argument('--token', '--api-key', help='API_KEY')
    parser.add_argument('-c', '--ignore-certs', action='store_true')
    parser.add_argument('-v', '--verbose')
    parser.add_argument('--no-wait', action='store_true')
    parser.add_argument('--branch', default='master')
    parser.add_argument('--commit', default=None)
    parser.add_argument('--role-name', help='ROLE_NAME')
    parser.add_argument('--status', action='store_true')
    parser.add_argument('--version')

    args = parser.parse_args()
    RoleMangler(**vars(args)).do_import()



if __name__ == "__main__":
    main()
