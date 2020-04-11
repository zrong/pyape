
# -*- coding: utf-8 -*-
"""
pyape.app.models.regional
~~~~~~~~~~~~~~~~~~~

Regional 表
"""
import toml
from sqlalchemy.sql.expression import text

from pyape.app import gdb, logger


class Admin(gdb.Model):
    """ 保存管理员账号，不区分区服
    """
    __tablename__ = 'admin'

    # 管理员账号 uid
    adminuid = gdb.Column(gdb.INT, primary_key=True, autoincrement=True)

    # 加密后的密码
    password = gdb.Column(gdb.CHAR(32), nullable=True)

    # 值为 TypeID 中的整数，暂未使用。为了性能不使用外键
    usertype = gdb.Column(gdb.SMALLINT, nullable=False, default=0)

    # 账户的状态，值为在 TypeID 中的整数
    status = gdb.Column(gdb.SMALLINT, nullable=False, default=1)

    # 使用 JSON 字符串的方式保存管理员的权限，例如相关的渠道 channel ，还有可以管理的区服 r
    scheme = gdb.Column(gdb.TEXT, nullable=True)

    # 用户名
    username = gdb.Column(gdb.VARCHAR(20), index=True, unique=True, nullable=True)

    # openid
    wxopenid = gdb.Column(gdb.VARCHAR(34), index=True, nullable=True)

    # unionid
    wxunionid = gdb.Column(gdb.VARCHAR(34), index=True, nullable=True)

    # 账号昵称
    nickname = gdb.Column(gdb.VARCHAR(64), nullable=False)

    # 账号创建时间
    createtime = gdb.Column(gdb.TIMESTAMP(True), nullable=False, server_default=text('NOW()'))

    # 账号的信息更新时间
    updatetime = gdb.Column(gdb.TIMESTAMP(True), nullable=True,
                           server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    # 账户备注
    note = gdb.Column(gdb.VARCHAR(100), nullable=True)

    @property
    def is_identify(self):
        """
        是否有足够的信息可以鉴别这个 User
        拥有 unionid+openid 或者 拥有 password+mobile/email
        :return:
        """
        return (self.wxunionid and self.wxopenid) or (self.password and self.username)

    def set_scheme(self, scheme):
        """
        将提供的 scheme 转换成为 JSON 字符串
        """
        self.scheme = toml.dumps(scheme)

    def get_scheme(self):
        """
        将 scheme 中的字符串转换成为 dict
        """
        if self.scheme:
            try:
                return toml.loads(self.scheme)
            except Exception as e:
                return None
        return None