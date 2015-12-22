# -*- coding: utf-8 -*-
#
# Copyright (C) 2014-2015 Bitergia
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
#
# Authors:
#     Santiago Dueñas <sduenas@bitergia.com>
#

import github3

from pullpo.backends import Backend, BackendError
from pullpo.db.model import User, Commit, Comment, Event, ReviewComment,\
    Repository, PullRequest


class GitHubRateLimitExceeded(BackendError):
    """Rate limit exceeded error"""


class GitHubBackend(Backend):

    PULL_REQUESTS_COUNT = 5

    def __init__(self, user, password, token, session, enterprise_url=None):
        super(GitHubBackend, self).__init__('github')

        if token:
            kwargs = {'token' : token}
        else:
            kwargs = {'username' : user,
                      'password' : password}

        if enterprise_url:
            self.gh = github3.GitHubEnterprise(enterprise_url, **kwargs)
        else:
            self.gh = github3.login(**kwargs)

        self.USERS_CACHE = {}
        self.session = session

    def fetch(self, owner, repository=None, since=None, newest=False):
        try:
            self._check_owner(owner)

            repositories = self._fetch_repositories_list(owner, repository)

            for repo in repositories:
                for r in  self._fetch(owner, repo, since, newest):
                    yield r
        except github3.exceptions.ForbiddenError, e:
            raise GitHubRateLimitExceeded(e.message)
        except github3.exceptions.AuthenticationFailed, e:
            raise BackendError("GitHub - " + e.message)

    def _fetch(self, owner, repository, since=None, newest=False):
        db_repo = Repository().as_unique(self.session,
                                         owner=owner,
                                         repository=repository)

        if not db_repo.id:
            db_repo.name = repository.name
            db_repo.url = repository.html_url

        direction = 'asc'

        if newest:
            direction = 'desc'

        issues = repository.issues(state='all', sort='updated',
                                   direction=direction, since=since)

        count = self.PULL_REQUESTS_COUNT

        for issue in issues:
            try:
                db_pr = self._fetch_pull_request(issue)

                # Check if the issue is a pull request
                if not db_pr:
                    continue

                # Events are stored in issue object
                for event in issue.events():
                    db_event = self._fetch_issue_event(event)
                    db_pr.events.append(db_event)

                db_repo.prs.append(db_pr)

                count = count - 1

                if not count:
                    count = self.PULL_REQUESTS_COUNT
                    yield db_repo
            except github3.exceptions.ServerError, e:
                import sys
                msg = "Cannot retrieve pull request #%s. Skipping it. Error: %s\n" \
                    % (issue.number, str(e))
                sys.stderr.write(msg)

        yield db_repo

    def _check_owner(self, owner):
        user = self.gh.user(owner)

        if isinstance(user, github3.null.NullObject):
            raise BackendError("GitHub - Owner %s does not exist." % (owner))

    def _fetch_repositories_list(self, owner, repository=None):
        if not repository:
            repos = self.gh.repositories_by(owner, type='owner')
            repositories = [r for r in repos]
        else:
            repo = self.gh.repository(owner, repository)

            if isinstance(repo, github3.null.NullObject):
                raise BackendError("GitHub - Repository %s:%s does not exist."
                                   % (owner, repository))

            repositories = [repo]

        return repositories

    def _fetch_pull_request(self, issue):
        pr = issue.pull_request()

        if not pr:
            return None

        db_pr = PullRequest().as_unique(self.session,
                                        github_id=pr.id)

        if not db_pr.id:
            db_pr.number = pr.number
            db_pr.created_at = self.unmarshal_timestamp(pr.created_at)

        # Don't trust on this pull request date
        # Take the one from the issue object
        updated_at = self.unmarshal_timestamp(issue.updated_at)

        if db_pr.updated_at != updated_at:
            db_pr.title = pr.title
            db_pr.body = pr.body
            db_pr.state = pr.state
            db_pr.updated_at = updated_at
            db_pr.closed_at = self.unmarshal_timestamp(pr.closed_at)
            db_pr.merged_at = self.unmarshal_timestamp(pr.merged_at)
            db_pr.mergeable_state = pr.mergeable_state

            if pr.is_merged():
                d = pr.as_dict()
                db_pr.merge_commit_sha = d[u'merge_commit_sha']
                db_pr.additions = d[u'additions']
                db_pr.deletions = d[u'deletions']
                db_pr.changed_files = d[u'changed_files']
                db_pr.merged = True

            db_pr.user = self._fetch_user(pr.user)

            if pr.merged_by:
                db_pr.merged_by = self._fetch_user(pr.merged_by)
            if pr.assignee:
                db_pr.assignee = self._fetch_user(pr.assignee)

        for comment in pr.issue_comments():
            db_comment = self._fetch_comment(comment, db_pr.id)
            db_pr.comments.append(db_comment)

        for review in pr.review_comments():
            db_review = self._fetch_review_comment(review, db_pr.id)
            db_pr.review_comments.append(db_review)

        for commit in pr.commits():
            db_commit = self._fetch_commit(commit, db_pr.id)
            db_pr.commits.append(db_commit)

        return db_pr

    def _fetch_issue_event(self, event):
        e = event.as_dict()
        event_id = e['id']

        db_event = Event().as_unique(self.session,
                                     event_id=event_id)
        db_event.event_id = event_id
        db_event.event = event.event
        db_event.created_at = self.unmarshal_timestamp(event.created_at)
        db_event.commit_id = event.commit_id
        db_event.actor = self._fetch_user(event.actor)

        if event.event in ('labeled', 'unlabeled'):
            db_event.extra = e['label']['name']
        return db_event

    def _fetch_user(self, user):
        if not user:
            return None

        if user.login not in self.USERS_CACHE:
            db_user = User().as_unique(self.session, login=user.login)
            db_user.email = user.email
            db_user.avatar_url = user.avatar_url
            db_user.url = user.url
            db_user.type = user.type

            self.USERS_CACHE[user.login] = db_user
        else:
            db_user = self.USERS_CACHE[user.login]

        return db_user

    def _fetch_comment(self, comment, pr_id):
        created_at = self.unmarshal_timestamp(comment.created_at)
        updated_at = self.unmarshal_timestamp(comment.updated_at)
        user = self._fetch_user(comment.user)

        if user:
            user_id = user.id
        else:
            user_id = None

        db_comment = Comment().as_unique(self.session, pull_request_id=pr_id,
                                         user_id=user_id,
                                         created_at=created_at)

        if db_comment.updated_at != updated_at:
            db_comment.body = comment.body
            db_comment.url = comment.url
            db_comment.updated_at = updated_at
            db_comment.user = user
        return db_comment

    def _fetch_review_comment(self, review, pr_id):
        created_at = self.unmarshal_timestamp(review.created_at)
        updated_at = self.unmarshal_timestamp(review.updated_at)
        user = self._fetch_user(review.user)

        if user:
            user_id = user.id
        else:
            user_id = None

        db_review = ReviewComment().as_unique(self.session, pull_request_id=pr_id,
                                              commit_id=review.commit_id,
                                              user_id=user_id,
                                              created_at=created_at)

        if db_review.updated_at != updated_at:
            db_review.body = review.body
            db_review.url = review.url
            db_review.updated_at = updated_at
            db_review.user = user
            db_review.original_commit_id = review.original_commit_id
        return db_review

    def _fetch_commit(self, commit, pr_id):
        db_commit = Commit().as_unique(self.session, pull_request_id=pr_id,
                                       sha=commit.sha)

        d = commit.as_dict()

        author = d['commit']['author']
        db_commit.author_date = self.unmarshal_timestamp(author['date'])
        db_commit.author = self._fetch_user(commit.author)

        if db_commit.author:
            db_commit.author.name = author['name']
            db_commit.author.email = author['email']

        committer = d['commit']['committer']
        db_commit.commit_date = self.unmarshal_timestamp(committer['date'])
        db_commit.committer = self._fetch_user(commit.committer)

        if db_commit.committer:
            db_commit.committer.name = committer['name']
            db_commit.committer.email = committer['email']

        return db_commit

    def unmarshal_timestamp(self, ts):
        import datetime
        import dateutil.parser

        if ts is None:
            return None
        elif isinstance(ts, datetime.datetime):
            return ts.replace(tzinfo=None)
        else:
            return dateutil.parser.parse(ts).replace(tzinfo=None)
