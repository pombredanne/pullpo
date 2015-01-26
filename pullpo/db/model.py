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

from sqlalchemy import Column, Boolean, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship


Base = declarative_base()


class UniqueObject(object):

    @classmethod
    def unique_filter(cls, query, *arg, **kw):
        raise NotImplementedError

    @classmethod
    def as_unique(cls, session, *arg, **kw):
        return _unique(
                    session,
                    cls,
                    cls.unique_filter,
                    cls,
                    arg, kw
               )


class User(UniqueObject, Base):
    __tablename__ = 'people'

    id = Column(Integer, primary_key=True)
    name = Column(String(256))
    email = Column(String(256))
    login = Column(String(128))
    url = Column(String(256))
    avatar_url = Column(String(256))
    type = Column(String(32))

    __table_args__ = {'mysql_charset': 'utf8'}

    @classmethod
    def unique_filter(cls, query, login):
        return query.filter(User.login == login)


class Repository(UniqueObject, Base):
    __tablename__ = 'repositories'

    id = Column(Integer, primary_key=True)
    owner = Column(String(128))
    repository = Column(String(128))
    name = Column(String(128))
    url = Column(String(256))

    prs = relationship('PullRequest', backref='repositories',
                       cascade="save-update, merge, delete")

    __table_args__ = {'mysql_charset': 'utf8'}

    @classmethod
    def unique_filter(cls, query, owner, repository):
        return query.filter(Repository.owner == owner,
                            Repository.repository == repository)


class PullRequest(UniqueObject, Base):
    __tablename__ = 'pull_requests'

    id = Column(Integer, primary_key=True)
    number = Column(Integer)
    github_id = Column(Integer)
    title = Column(String(256))
    body = Column(Text())
    created_at = Column(DateTime(timezone=False))
    updated_at = Column(DateTime(timezone=False))
    closed_at = Column(DateTime(timezone=False))
    merged_at = Column(DateTime(timezone=False))
    state = Column(String(32))
    merged = Column(Boolean(), default=False)
    mergeable_state = Column(String(32))
    merge_commit_sha = Column(String(256))
    additions = Column(Integer)
    deletions = Column(Integer)
    changed_files = Column(Integer)

    repo_id = Column(Integer,
                     ForeignKey('repositories.id', ondelete='CASCADE'))

    user_id = Column(Integer,
                     ForeignKey('people.id', ondelete='CASCADE'),)
    assignee_id = Column(Integer,
                         ForeignKey('people.id', ondelete='CASCADE'),)
    merged_by_id = Column(Integer,
                          ForeignKey('people.id', ondelete='CASCADE'),)

    repository = relationship('Repository', backref='pull_requests')

    comments = relationship('Comment',
                            lazy='joined', cascade="save-update, merge, delete")
    review_comments = relationship('ReviewComment',
                                   lazy='joined', cascade="save-update, merge, delete")
    commits = relationship('Commit',
                           lazy='joined', cascade="save-update, merge, delete")
    events = relationship('Event',
                          lazy='joined', cascade="save-update, merge, delete")

    user = relationship('User', foreign_keys=[user_id])
    assignee = relationship('User', foreign_keys=[assignee_id])
    merged_by = relationship('User', foreign_keys=[merged_by_id])

    __table_args__ = {'mysql_charset': 'utf8'}

    @classmethod
    def unique_filter(cls, query, github_id):
        return query.filter(PullRequest.github_id == github_id)


class Comment(UniqueObject, Base):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True)
    body = Column(Text())
    url = Column(String(256))
    created_at = Column(DateTime())
    updated_at = Column(DateTime())
    pull_request_id = Column(Integer,
                             ForeignKey('pull_requests.id', ondelete='CASCADE'),)
    user_id = Column(Integer,
                     ForeignKey('people.id', ondelete='CASCADE'),)

    pull_request = relationship('PullRequest')
    user = relationship('User', foreign_keys=[user_id])

    __table_args__ = {'mysql_charset': 'utf8'}

    @classmethod
    def unique_filter(cls, query, pull_request_id, user_id, created_at):
        return query.filter(Comment.pull_request_id == pull_request_id,
                            Comment.user_id == user_id,
                            Comment.created_at == created_at)


class ReviewComment(UniqueObject, Base):
    __tablename__ = 'review_comments'

    id = Column(Integer, primary_key=True)
    body = Column(Text())
    url = Column(String(256))
    commit_id = Column(String(256))
    original_commit_id = Column(String(256))
    created_at = Column(DateTime())
    updated_at = Column(DateTime())
    pull_request_id = Column(Integer,
                             ForeignKey('pull_requests.id', ondelete='CASCADE'),)
    user_id = Column(Integer,
                     ForeignKey('people.id', ondelete='CASCADE'),)

    pull_request = relationship('PullRequest')
    user = relationship('User', foreign_keys=[user_id])

    __table_args__ = {'mysql_charset': 'utf8'}

    @classmethod
    def unique_filter(cls, query, pull_request_id, commit_id, user_id, created_at):
        return query.filter(ReviewComment.pull_request_id == pull_request_id,
                            ReviewComment.commit_id == commit_id,
                            ReviewComment.user_id == user_id,
                            ReviewComment.created_at == created_at)


class Commit(UniqueObject, Base):
    __tablename__ = 'commits'

    id = Column(Integer, primary_key=True)
    sha = Column(String(256))
    author_date = Column(DateTime())
    commit_date = Column(DateTime())
    author_id = Column(Integer,
                       ForeignKey('people.id', ondelete='CASCADE'),)
    committer_id = Column(Integer,
                          ForeignKey('people.id', ondelete='CASCADE'),)
    pull_request_id = Column(Integer,
                             ForeignKey('pull_requests.id', ondelete='CASCADE'),)

    pull_request = relationship('PullRequest')
    author = relationship('User', foreign_keys=[author_id])
    committer = relationship('User', foreign_keys=[committer_id])

    __table_args__ = {'mysql_charset': 'utf8'}

    @classmethod
    def unique_filter(cls, query, pull_request_id, sha):
        return query.filter(Commit.pull_request_id == pull_request_id,
                            Commit.sha == sha)


class Event(UniqueObject, Base):
    __tablename__ = 'events'

    id = Column(Integer, primary_key=True)
    event = Column(String(64))
    event_id = Column(Integer())
    created_at = Column(DateTime())
    commit_id = Column(String(256))
    extra = Column(String(256))
    actor_id = Column(Integer,
                      ForeignKey('people.id', ondelete='CASCADE'),)
    pull_request_id = Column(Integer,
                             ForeignKey('pull_requests.id', ondelete='CASCADE'),)
    pull_request = relationship('PullRequest')
    actor = relationship('User')

    __table_args__ = {'mysql_charset': 'utf8'}

    @classmethod
    def unique_filter(cls, query, event_id):
        return query.filter(Event.event_id == event_id)


def _unique(session, cls, queryfunc, constructor, arg, kw):
    with session.no_autoflush:
        q = session.query(cls)
        q = queryfunc(q, *arg, **kw)

        obj = q.first()

        if not obj:
            obj = constructor(*arg, **kw)

        session.add(obj)
    return obj
