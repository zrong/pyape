# -*- coding: utf-8 -*-
"""
pyape.app.models.regional
~~~~~~~~~~~~~~~~~~~

Regional 表
"""

import toml
from sqlalchemy.sql.expression import text

from pyape.app import gdb, logger
from pyape.config import RegionalConfig
from pyape.util.func import parse_int


class Regional(gdb.Model):
    """ Regional 配置
    """
    __tablename__ = 'regional'

    # 1000测试 2000审核 5000正式
    REGIONAL_TYPES = [1000, 2000, 5000]

    # Regional 配置的主键序号
    r = gdb.Column(gdb.SMALLINT, primary_key=True, index=True)

    # Regional 名称
    name = gdb.Column(gdb.VARCHAR(100), nullable=False)

    # Regional 的具体配置， TOML 字符串
    value = gdb.Column(gdb.TEXT, nullable=False)

    # 用于这个 Regional 登录时候使用的加密秘钥编号。编号就是 Valueobject 的 vid
    secretvid = gdb.Column(gdb.SMALLINT, nullable=False, index=True)

    # 对 regional 的一种分类法，其值应为 typeid
    kindtype = gdb.Column(gdb.SMALLINT, nullable=False, index=True)

    # Regional 的状态，值为在 TypeID 中的整数，1正常，5 禁用
    status = gdb.Column(gdb.SMALLINT, nullable=False, default=1)

    createtime = gdb.Column(gdb.TIMESTAMP(True), server_default=text('NOW()'))
    updatetime = gdb.Column(gdb.TIMESTAMP(True), nullable=True,
                           server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))

    @staticmethod
    def r2type(r):
        """ 将 r 转换成数字表示的 mjptype
        """
        if r >= 1000 and r < 2000:
            return 1000
        elif r >= 2000 and r < 3000:
            return 2000
        elif r >= 5000:
            return 5000
        return None

    @classmethod
    def get_all_by_type_qry(cls, type_):
        """ 根据 type 查询 r 的列表，返回一个查询对象
        """
        if type_ == 1000:
            return cls.query.filter(cls.r.between(1000, 1999))
        elif type_ == 2000:
            return cls.query.filter(cls.r.between(2000, 2999))
        return cls.query.filter(cls.r.between(5000, 5999))

    def merge_value(self):
        """ 合并数据库中的其他字段到 value 配置中
        """
        parsed_dict = {}
        if self.value is not None:
            parsed_dict = toml.loads(self.value)
        parsed_dict['name'] = self.name
        parsed_dict['r'] = self.r
        parsed_dict['secretvid'] = self.secretvid
        parsed_dict['kindtype'] = self.kindtype
        parsed_dict['status'] = self.status
        parsed_dict['createtime'] = self.createtime.isoformat()
        parsed_dict['updatetime'] = self.updatetime.isoformat()
        parsed_dict['rtype'] = Regional.r2type(self.r)
        return parsed_dict


def get_regional_config(status=None):
    """ 从数据库中读取 regional 的配置，转换成 RegionalConfig
    """
    # 取出数据库中所有启用的 Regional
    qry = Regional.query
    if isinstance(status, int):
        qry = qry.filter_by(status=status)
    regional_list = [ritem.merge_value() for ritem in qry.all()]
    # logger.info('regionals %s', regional_list)
    return RegionalConfig(regional_list)


def get_regional(r, *args):
    ritem = Regional.query.filter_by(status=1).first()


def check_regional(r, ignore_zero=False):
    """ 检查 regional 是否有效，同时返回数据库中查询到的 regional 配置
    :param ignore_zero: 值为真，则允许 r 值为 0。0 是一个特殊的 r 值，代表全局 r
    :return: 已经转换成整数的 regional 值，以及数据库中查到的 regional 配置
    """
    r = parse_int(r)
    if r is None:
        return None, None
    if ignore_zero:
        if r == 0:
            return 0, Regional.query.filter_by(status=1, r=0).first()
    # 从数据库中的启用的 regional 中查找
    regional = Regional.query.filter_by(status=1, r=r).first()
    if regional is None:
        return None, None
    return r, regional


def check_regionals(rs, ignore_zero=False):
    """ 判断数据库中是否包含所有的 rs
    :param ignore_zero: 值为真，则允许 rs 值为 [0]。0 是一个特殊的 r 值，代表全局 r
    """
    lenrs = len(rs)
    if ignore_zero:
        # 传递 0 的时候， rs 只能拥有 1 个项： 0
        if lenrs == 1 and parse_int(rs[0]) == 0:
            return True
    regionals = Regional.query.filter_by(status=1).filter(Regional.r.in_(rs)).all()
    return len(regionals) == lenrs