# -*- coding: utf-8 -*-
"""
pyape.app.models.account
~~~~~~~~~~~~~~~~~~~

帐号表，所有的账号存入这个表，不区分 Regional
"""
import json
from datetime import datetime ,timezone
from sqlalchemy.sql.expression import text
from sqlalchemy.exc import SQLAlchemyError

from pyape.app import gdb
from pyape.util.gen import gen_password
from pyape.app.queryfun import commit_and_response_error


class Account(gdb.Model):
    """ 保存帐号信息
    """
    __tablename__ = 'account'

    # 帐号 ID
    aid = gdb.Column(gdb.INT, primary_key=True, autoincrement=True)

    # 登录号称
    loginname = gdb.Column(gdb.VARCHAR(50), index=True, unique=True, nullable=True)

    # 加密后的密码
    password = gdb.Column(gdb.CHAR(32), nullable=True)

    # 账户的状态，值为在 TypeID 中的整数
    status = gdb.Column(gdb.SMALLINT, nullable=False, default=1)

    # 移动电话
    mobile = gdb.Column(gdb.VARCHAR(26), index=True, unique=True, nullable=True)

    # 电子邮件
    email = gdb.Column(gdb.VARCHAR(100), index=True, unique=True, nullable=True)

    # openid
    openid = gdb.Column(gdb.VARCHAR(100), index=True, nullable=True)

    # unionid
    unionid = gdb.Column(gdb.VARCHAR(100), index=True, nullable=True)

    # 昵称
    nickname = gdb.Column(gdb.VARCHAR(64), nullable=False)

    # 头像地址
    headimg = gdb.Column(gdb.TEXT, nullable=True)

    # 性别，0 未设置 1 男 2 女
    gender = gdb.Column(gdb.SMALLINT, nullable=False, default=0)

    # 创建时间
    createtime = gdb.Column(gdb.TIMESTAMP(True), nullable=False, server_default=text('CURRENT_TIMESTAMP'))

    # 更新时间
    updatetime = gdb.Column(gdb.TIMESTAMP(True), nullable=False)

    # 帐号备注
    note = gdb.Column(gdb.VARCHAR(100), nullable=True)

    def is_identify(self):
        """ 是否有足够的信息可以鉴别这个 Account
        拥有 unionid 或 openid 或 password+mobile/email/loginname
        :return:
        """
        return self.unionid or self.openid or \
                (self.password and (self.loginname or self.mobile or self.email))

    def shrink(self, *args):
        """ 去除 user 表中的敏感信息
        :param args: 除了默认的数据，需要增加一些键名
        """
        shrink_info = {
            'aid': self.aid,
            'loginname': self.username,
            'nickname': self.nickname,
            'status': self.status,
            'mobile': self.mobile,
            'email': self.email,
            'headimg': self.headimg,
            'gender': self.gender,
            'createtime': self.createtime.isoformat(),
            'updatetime': self.updatetime.isoformat(),
            'openid': self.wxopenid,
            'unionid': self.wxunionid,
            'note': self.note,
        }
        for key in args:
            value = getattr(self, key, None)
            if value is not None and key.endswith('time'):
                value = value.isoformat()
            shrink_info[key] = value
        return shrink_info


def init_account(root_password, root_loginname='root'):
    """ 初始化 regional0 这是必须存在的一条

    :param root_loginname: 根用户登录名称
    :param root_password: 根用户密码
    """
    if root_loginname is None or root_password is None:
        raise TypeError('Need root_loginname and root_password!')
    a1 = Account.query.get(1)
    if a1 is not None:
        raise TypeError('The root account %s is exists!' % a1.loginname)

    a1 = Account(loginname=root_loginname, nickname='根管理员', status=1, updatetime=datetime.now(timezone.utc))
    resp = commit_and_response_error(a1, refresh=True, return_dict=True)
    if resp is not None:
        raise SQLAlchemyError('Add root Account error: %s' % resp['message'])
    a1.password = gen_password(root_password, a1.aid)
    resp = commit_and_response_error(a1, refresh=True)
    if resp is not None:
        raise SQLAlchemyError('Update root Account error: %s' % resp['message'])
        
