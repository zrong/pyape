
# -*- coding: utf-8 -*-
"""
pyape.app.models.role
~~~~~~~~~~~~~~~~~~~

角色管理
"""
import json
from sqlalchemy.sql.expression import text
from sqlalchemy.exc import SQLAlchemyError

from pyape.app import gdb
from pyape.app.queryfun import commit_and_response_error


class Role(gdb.Model):
    """ 权限权限
    """
    __tablename__ = 'role'

    # 角色 uid
    rid = gdb.Column(gdb.INT, primary_key=True, autoincrement=True)

    # 角色所属的 regional。值为 0 代表通用角色
    r = gdb.Column(gdb.SMALLINT, index=True, nullable=True)

    # 角色名称
    name = gdb.Column(gdb.VARCHAR(50), index=True, unique=True, nullable=True)

    # JSON 字符串
    permissions = gdb.Column(gdb.TEXT, nullable=False)

    # 创建时间
    createtime = gdb.Column(gdb.TIMESTAMP(True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))

    # 角色备注
    note = gdb.Column(gdb.VARCHAR(100), nullable=True)

    def merge(self):
        parsed_dict = {}
        parsed_dict['rid'] = self.rid
        parsed_dict['permissions'] = json.loads(self.value)
        parsed_dict['name'] = self.name
        parsed_dict['r'] = self.r
        parsed_dict['createtime'] = self.createtime.isoformat()
        return parsed_dict


class UserRole(gdb.Model):
    """ 用户和角色的关系
    """
    __tablename__ = 'userrole'

    # uid
    uid = gdb.Column(gdb.INT, primary_key=True)

    # 角色 uid
    rid = gdb.Column(gdb.INT, primary_key=True)

    # 角色和用户所属的 regional
    r = gdb.Column(gdb.SMALLINT, primary_key=True)

    # 创建时间
    createtime = gdb.Column(gdb.TIMESTAMP(True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))


def init_userrole():
    role1 = Role(r=0, name='根权限', permissions='["*"]')
    resp = commit_and_response_error(role1, return_dict=True)
    if resp is not None:
        raise SQLAlchemyError('Add role 1 error: %s' % resp['message'])
    userrole = UserRole(r=0, uid=1, rid=1)
    resp = commit_and_response_error(userrole, return_dict=True)
    if resp is not None:
        raise SQLAlchemyError('Add userrole 1 error: %s' % resp['message'])
