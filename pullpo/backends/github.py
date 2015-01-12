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

from github3 import login

from pullpo.backends import Backend
from pullpo.db.model import User, Commit, Comment, Event, ReviewComment,\
    Repository, PullRequest


class GitHubBackend(Backend):

    def __init__(self, user, password):
        super(GitHubBackend, self).__init__('github')

        self.gh = login(user, password=password)
        self.USERS_CACHE = {}

    def fetch(self, owner, repository):
        repo = self.gh.repository(owner, repository)

        db_repo = Repository()
        db_repo.name = repo.name
        db_repo.url = repo.html_url

        issues = repo.issues(state='all')

        for issue in issues:
            pr = issue.pull_request()

            if not pr:
                continue

            db_pr = self.fetch_pull_request(pr)

            # Events are stored in issue object
            for event in issue.events():
                db_event = self.fetch_issue_event(event)
                db_pr.events.append(db_event)

            db_repo.prs.append(db_pr)

        return db_repo

    def fetch_pull_request(self, pr):
        db_pr = PullRequest()
        db_pr.number = pr.number
        db_pr.github_id = pr.id
        db_pr.title = pr.title
        db_pr.body = pr.body
        db_pr.state = pr.state
        db_pr.created_at = pr.created_at
        db_pr.updated_at = pr.updated_at
        db_pr.closed_at = pr.closed_at
        db_pr.merged_at = pr.merged_at
        db_pr.mergeable_state = pr.mergeable_state

        if pr.is_merged():
            d = pr.as_dict()
            db_pr.merge_commit_sha = d[u'merge_commit_sha']
            db_pr.additions = d[u'additions']
            db_pr.deletions = d[u'deletions']
            db_pr.changed_files = d[u'changed_files']

        db_pr.user = self.fetch_user(pr.user)

        if pr.merged_by:
            db_pr.merged_by = self.fetch_user(pr.merged_by)
        if pr.assignee:
            db_pr.assignee = self.fetch_user(pr.assignee)

        for comment in pr.issue_comments():
            db_comment = self.fetch_comment(comment)
            db_pr.comments.append(db_comment)

        for review in pr.review_comments():
            db_review = self.fetch_review_comment(review)
            db_pr.review_comments.append(db_review)

        for commit in pr.commits():
            db_commit = self.fetch_commit(commit)
            db_pr.commits.append(db_commit)

        return db_pr

    def fetch_issue_event(self, event):
        db_event = Event()

        e = event.as_dict()

        db_event.event_id = e['id']
        db_event.event = event.event
        db_event.created_at = event.created_at
        db_event.commit_id = event.commit_id
        db_event.actor = self.fetch_user(event.actor)

        if event.event in ('labeled', 'unlabeled'):
            db_event.extra = e['label']['name']
        return db_event

    def fetch_user(self, user):
        if not user:
            return None

        if user.login not in self.USERS_CACHE:
            db_user = User()
            db_user.avatar_url = user.avatar_url
            db_user.login = user.login
            db_user.url = user.url
            db_user.type = user.type

            self.USERS_CACHE[user.login] = db_user
        else:
            db_user = self.USERS_CACHE[user.login]

        return db_user

    def fetch_comment(self, comment):
        db_comment = Comment()
        db_comment.body = comment.body
        db_comment.url = comment.url
        db_comment.created_at = comment.created_at
        db_comment.updated_at = comment.updated_at
        db_comment.user = self.fetch_user(comment.user)
        return db_comment

    def fetch_review_comment(self, review):
        db_review = ReviewComment()
        db_review.body = review.body
        db_review.url = review.url
        db_review.created_at = review.created_at
        db_review.updated_at = review.updated_at
        db_review.user = self.fetch_user(review.user)
        db_review.commit_id = review.commit_id
        db_review.original_commit_id = review.original_commit_id
        return db_review

    def fetch_commit(self, commit):
        db_commit = Commit()
        db_commit.sha = commit.sha
        db_commit.author = self.fetch_user(commit.author)
        db_commit.committer = self.fetch_user(commit.committer)

        d = commit.as_dict()

        ts = d['commit']['author']['date']
        db_commit.author_date = self.unmarshal_timestamp(ts)

        ts = d['commit']['committer']['date']
        db_commit.commit_date = self.unmarshal_timestamp(ts)

        return db_commit

    def unmarshal_timestamp(self, ts):
        # FIXME: store time zone data
        import dateutil.parser
        return dateutil.parser.parse(ts).replace(tzinfo=None)
