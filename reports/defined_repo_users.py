#!/usr/bin/env python3

import stashy
import click

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

    projname = projects[0].get('name', '')
    projkey = projects[0].get('key', '')

    if (projname == project):
        repos = stash.projects[projkey].repos.list()
        slug = repos[0].get('slug', '')

        if (slug == repo):
            perms = stash.projects[projkey].repos[slug].permissions.users.list()

            for perm in perms:
                user = perm.get('user', None)
                if (user is not None):
                    name = user.get('emailAddress', None)
                    if (name is not None):
                        users[name] = ''

            perms = stash.projects[projkey].repos[slug].permissions.groups.list()
            group = perms[0].get('group').get('name')
            members = list(stash.admin.groups.more_members(group))
            for member in members:
                name = member.get('emailAddress', None)
                if (name is not None):
                    users[name] = ''

    print("{ \"usercnt\": %d }" % len(users.keys()))

if __name__ == '__main__':
    main()
