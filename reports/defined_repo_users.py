#!/usr/bin/env python3

import stashy
import click
import pprint from pprint

@click.command()
@click.option('--project', help='Bitbucket Project Name', required=True)
@click.option('--repo', help='Bitbucket Repository', required=True)
@click.option('--bburl', help='Bitbucket Repository',  envvar='BITBUCKET_URL', required=True)
@click.option('--userid', help='Bitbucket Repository',  envvar='BITBUCKET_USER', required=True)
@click.option('--password', help='Bitbucket Repository',  envvar='BITBUCKET_PASS', required=True)

def main(project, repo, bburl, userid, password):
    users = {}
    stash = stashy.connect(bburl, userid, password, verify=False)
    projects = stash.projects.list()

    if (len(projects) == 0):
        print("{ \"usercnt\": 0 }")
        return 0;

    for proj in projects:
        projname = proj.get('name', '')
        projkey = proj.get('key', '')

        if (projname == project):
            repos = stash.projects[projkey].repos.list()
            for r in repos:
                slug = r.get('slug', '')

                if (slug == repo):
                    perms = stash.projects[projkey].repos[slug].permissions.users.list()

                    for perm in perms:
                        user = perm.get('user', None)
                        if (user is not None):
                            name = user.get('emailAddress', None)
                            if (name is not None):
                                users[name.lower()] = ''

                    perms = stash.projects[projkey].repos[slug].permissions.groups.list()
                    for p in perms:
                        group = p.get('group').get('name')
                        members = list(stash.admin.groups.more_members(group))
                        for member in members:
                            name = member.get('emailAddress', None)
                            if (name is not None):
                                users[name.lower()] = ''

    print("{ \"usercnt\": %d }" % len(users.keys()))

if __name__ == '__main__':
    main()
