from __future__ import absolute_import

import re

from django.core.urlresolvers import reverse
from sentry.integrations.exceptions import ApiError, IntegrationError
from sentry.integrations.issues import IssueBasicMixin


class GitlabIssueBasic(IssueBasicMixin):
    def make_external_key(self, data):
        return u'{}:{}#{}'.format(self.model.metadata['domain_name'], data['project'], data['key'])

    def get_issue_url(self, key):
        match = re.match(r'.+:(.+)#(.+)', key)
        project, issue_id = match.group(1), match.group(2)
        return u'{}/{}/issues/{}'.format(
            self.model.metadata['base_url'],
            project,
            issue_id,
        )

    def get_create_issue_config(self, group, **kwargs):
        fields = super(GitlabIssueBasic, self).get_create_issue_config(group, **kwargs)
        try:
            projects = self.get_repos()
        except ApiError:
            project_choices = [(' ', ' ')]
        else:
            project_choices = [(project['identifier'], project['name']) for project in projects]

        params = kwargs.get('params', {})
        default_project = params.get('project', project_choices[0][0])

        org = group.organization
        autocomplete_url = reverse(
            'sentry-extensions-gitlab-search', args=[org.slug, self.model.id],
        )

        return [
            {
                'name': 'project',
                'label': 'Gitlab Project',
                'type': 'select',
                'default': default_project,
                'defaultLabel': default_project,
                'url': autocomplete_url,
                'updatesForm': True,
                'required': True,
            }
        ] + fields

    def create_issue(self, data, **kwargs):
        client = self.get_client()

        project = data.get('project')

        if not project:
            raise IntegrationError('project kwarg must be provided')

        try:
            issue = client.create_issue(
                project=project,
                data={
                    'title': data['title'],
                    'description': data['description'],
                })
        except ApiError as e:
            raise IntegrationError(self.message_from_error(e))

        return {
            'key': issue['iid'],
            'title': issue['title'],
            'description': issue['description'],
            'url': issue['web_url'],
            'project': project,
            'metadata': {
                'display_name': '%s#%s' % (project['path_with_namespace'], issue['id']),
            }
        }

    def get_link_issue_config(self, group, **kwargs):
        org = group.organization
        autocomplete_url = reverse(
            'sentry-extensions-gitlab-search', args=[org.slug, self.model.id],
        )

        return [
            {
                'name': 'externalIssue',
                'label': 'Issue',
                'default': '',
                'type': 'select',
                'url': autocomplete_url,
                'required': True,
                'updatesForm': True,
            },
        ]

    def get_issue(self, issue_id, **kwargs):
        data = kwargs['data']
        project_id, issue_num = data.get('externalIssue').split('#')
        client = self.get_client()

        if not project_id:
            raise IntegrationError('project must be provided')

        if not issue_num:
            raise IntegrationError('issue must be provided')

        try:
            issue = client.get_issue(project_id, issue_num)
            project = client.get_project(project_id)
        except ApiError as e:
            raise IntegrationError(self.message_from_error(e))

        return {
            'key': issue['iid'],
            'title': issue['title'],
            'description': issue['description'],
            'url': issue['web_url'],
            'project': project_id,
            'metadata': {
                'display_name': '%s#%s' % (project['path_with_namespace'], issue['id']),
            }
        }

    def get_issue_display_name(self, external_issue):
        if external_issue.metadata is None:
            return ''
        return external_issue.metadata['display_name']
