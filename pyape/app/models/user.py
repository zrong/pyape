
# -*- coding: utf-8 -*-
"""
pyape.app.models.user
~~~~~~~~~~~~~~~~~~~

用户表
"""
from datetime import datetime, timezone
from sqlalchemy.sql.expression import text
from sqlalchemy.exc import SQLAlchemyError

from pyape.app import gdb, logger
from pyape.app.queryfun import commit_and_response_error


def make_user_model(tablename, bind_key=None):
    """ User 表是每个 regional 一个，需要动态创建
    """
    attributes = \
        dict(  
            __table_name=tablename,
            # __table_args__ = {'extend_existing': True} ,
            __bind_key__=bind_key,
            # uid
            uid = gdb.Column(gdb.INT, primary_key=True, autoincrement=True),
            # 用户所属的 regional。值为 0 代表默认的用户
            r = gdb.Column(gdb.SMALLINT, index=True, nullable=True),
            # 用户的状态，值为在 TypeID 中的整数
            status = gdb.Column(gdb.SMALLINT, nullable=False, default=1),
            # 昵称，可以覆盖 account 中的昵称
            nickname = gdb.Column(gdb.VARCHAR(64), nullable=True),
            # 头像地址，可以覆盖 account 中的头像
            headimg = gdb.Column(gdb.TEXT, nullable=True),
            # 用户创建时间
            createtime = gdb.Column(gdb.TIMESTAMP(True), nullable=False, server_default=text('CURRENT_TIMESTAMP')),
            # 更新时间
            updatetime = gdb.Column(gdb.TIMESTAMP(True), nullable=False),
            #  用户备注
            note = gdb.Column(gdb.VARCHAR(100), nullable=True)
        )

    return type(tablename, (gdb.Model,), attributes)


def init_user(rconfig):
    gdb.build_regional_tables('user', make_user_model, rconfig)
    # 创建所有的 User 表
    gdb.create_all()
    # 选择默认的 User 表
    User = gdb.get_regional_table('user', 0, make_user_model, rconfig)
    if User is None:
        raise TypeError('No table user0!')
    # 获取 1 号用户，也就是 root 用户
    u1 = User.query.get(1)
    if u1 is not None:
        raise TypeError('The user %s is exists!' % u1.uid)

    u1 = User(r=0, nickname='根管理员', status=1, updatetime=datetime.now(timezone.utc))
    resp = commit_and_response_error(u1, return_dict=True)
    if resp is not None:
        raise SQLAlchemyError('Add root user error: %s' % resp['message'])