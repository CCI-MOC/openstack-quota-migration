#!/usr/bin/env python

from __future__ import print_function

import click
import json
import logging
import openstack
import sys

try:
    import jsondiff
except ImportError:
    jsondiff = None


LOG = logging.getLogger('quotas')


@click.group()
@click.option('--os-cloud', envvar='OS_CLOUD')
@click.option('-d', '--debug', 'loglevel', flag_value='DEBUG')
@click.option('-v', '--verbose', 'loglevel', flag_value='INFO')
@click.option('-q', '--quiet', 'loglevel', flag_value='WARNING', default=True)
@click.pass_context
def quotas(ctx, os_cloud, loglevel):
    logging.basicConfig(level=loglevel)
    conn = openstack.connect(cloud=os_cloud)
    ctx.obj = conn


def get_all_project_ids(conn):
    LOG.info('getting list of all projects')
    projects = conn.list_projects()
    return [project.id for project in projects]


def get_all_quotas(conn, projects):
    for p in projects:
        p_data = conn.get_project(p)
        LOG.info('looking up quotas for project %s', p_data.name)
        quotas = {}
        for qtype in ['compute', 'network', 'volume']:
            get_func = getattr(conn, 'get_{}_quotas'.format(qtype))
            quotas[qtype] = dict(get_func(p))

            # get rid of 'id' attribute in volume and compute quota
            # results.
            if 'id' in quotas[qtype]:
                del quotas[qtype]['id']

        yield({
            'id': p_data.id,
            'name': p_data.name,
            'quotas': quotas,
        })


@quotas.command()
@click.option('-o', '--output', default=sys.stdout, type=click.File('w'))
@click.argument('projects', nargs=-1)
@click.pass_context
def get(ctx, output, projects):
    conn = ctx.obj

    if not projects:
        projects = get_all_project_ids(conn)

    all_quotas = list(get_all_quotas(conn, projects))

    LOG.info('writing quotas')
    json.dump(all_quotas, output, indent=2)


def non_null_quotas(q):
    return {k: v for k, v in q.items() if v != -1 and k != 'id'}


@quotas.command()
@click.option('-p', '--project', multiple=True)
@click.option('-x', '--exclude', multiple=True)
@click.option('-X', '--exclude-from', type=click.File('r'))
@click.argument('quotafile', default=sys.stdin, type=click.File('r'))
@click.pass_context
def apply(ctx, project, exclude, exclude_from, quotafile):
    conn = ctx.obj
    quotas = json.load(quotafile)

    if exclude_from:
        addl_exclude = exclude_from.read().splitlines()
        exclude = list(exclude) + addl_exclude

    if project:
        try:
            selected = [quota for quota in quotas
                        if quota['id'] in project
                        or quota['name'] in project]
        except KeyError as e:
            raise click.ClickException(
                'no quota for project {.message}'.format(e))
    else:
        selected = [quota for quota in quotas
                    if quota['id'] not in exclude
                    and quota['name'] not in exclude]

    LOG.info('selected %d projects', len(selected))

    for project in selected:
        LOG.info('processing quotas for project %s', project['name'])
        for qtype in ['compute', 'network', 'volume']:
            if qtype not in project['quotas']:
                continue

            quota_values = non_null_quotas(project['quotas'][qtype])

            LOG.info('setting %s quota for project %s', qtype, project['name'])
            set_func = getattr(conn, 'set_{}_quotas'.format(qtype))
            #set_func(project['id'], **quota_values)


@quotas.command()
@click.option('-o', '--output', default=sys.stdout, type=click.File('w'))
@click.option('-q', '--quotafile', type=click.File('r'))
@click.argument('reference', type=click.File('r'))
@click.argument('projects', nargs=-1)
@click.pass_context
def compare(ctx, output, reference, quotafile, projects):
    conn = ctx.obj

    if jsondiff is None:
        raise click.ClickException('compare requires the jsondiff module')

    if quotafile is None:
        if not projects:
            projects = get_all_project_ids(conn)
        quotas = get_all_quotas(conn, projects)
    else:
        quotas = json.load(quotafile)

    reference = json.load(reference)

    diffs = []
    for project in quotas:
        diff = jsondiff.diff(reference['quotas'], project['quotas'])
        if diff:
            LOG.warning('quota for project %s differs from reference',
                     project['name'])
            diffs.append({
                'name': project['name'],
                'id': project['id'],
                'diff': diff,
            })

    json.dump(diffs, output, indent=2)


if __name__ == '__main__':
    quotas()
