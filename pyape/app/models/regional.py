"""
pyape.app.models.regional
~~~~~~~~~~~~~~~~~~~

与 regional 表相关的方法
"""
import time
import tomllib
from typing import Any
from sqlalchemy.orm import Query, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.types import VARCHAR, INTEGER, TEXT
from sqlalchemy import Column, ForeignKey, select

from pyape.app import gdb, logger
from pyape.config import RegionalConfig
from pyape.util.func import parse_int

from . import column_primary, column_timestamp, default_timestamp


def get_regional_select(regional_cls: type, status: int = None) -> Query:
    """获取排序过的 Regional 项目，可以根据 status 筛选
    :param status:
    :return:
    """
    s = select(regional_cls)
    if status is not None:
        s = s.where(regional_cls.status == status)
    return s.order_by(regional_cls.status, regional_cls.createtime.desc())


def make_regional_table_cls(
    table_name: str = "regional", Model: Any = None, bind_key: str = None
):
    """创建 Regional 表。

    :param table_name: 表名称。
    :param Model: 提供一个 Model 对象。若不提供则使用 gdb.Model(bind_key) 创建对象。
    :param bind_key: 提供 bind_key。
    """

    def _merge(self):
        """合并数据库中的其他字段到 value 配置中"""
        parsed_dict = {}
        if isinstance(self.value, str) and self.value.strip():
            parsed_dict = tomllib.loads(self.value)
        parsed_dict["name"] = self.name
        parsed_dict["r"] = self.r
        parsed_dict["status"] = self.status
        parsed_dict["createtime"] = self.createtime
        parsed_dict["updatetime"] = self.updatetime
        return parsed_dict

    attributes = dict(
        __tablename__=table_name,
        # 以下的属性是是数据表列
        r=column_primary(),  # Regional 配置的主键序号
        name=Column(VARCHAR(100), nullable=False),  # Regional 名称
        value=Column(TEXT, nullable=True),  # Regional 的具体配置， TOML 字符串
        status=Column(
            INTEGER, nullable=False, default=1
        ),  # Regional 的状态，值为在 TypeID 中的整数，1正常，5 禁用
        createtime=column_timestamp(default=default_timestamp),
        updatetime=column_timestamp(nullable=True),
        # 下面的属性是方法
        merge=_merge,
        # 下面的属性是普通属性
        bind_key=bind_key,
    )
    return type(table_name, (Model or gdb.Model(bind_key),), attributes)


def get_regional_config(regional_cls: type, status: int = None):
    """从数据库中读取 regional 的配置，转换成 RegionalConfig"""
    # 取出数据库中所有启用的 Regional
    qry = gdb.query(regional_cls)
    if isinstance(status, int):
        qry = qry.filter_by(status=status)
    regional_list = [ritem.merge() for ritem in qry.all()]
    return RegionalConfig(regional_list)


def check_regional(regional_cls: type, r: int, ignore_zero: bool = False):
    """检查 regional 是否有效，同时返回数据库中查询到的 regional 配置
    :param ignore_zero: 值为真，则允许 r 值为 0。0 是一个特殊的 r 值，代表全局 r
    :return: 已经转换成整数的 regional 值，以及数据库中查到的 regional 配置
    """
    qry = gdb.query(regional_cls)
    r = parse_int(r)
    if r is None:
        return None, None
    if ignore_zero:
        if r == 0:
            return 0, qry.filter_by(status=1, r=0).first()
    # 从数据库中的启用的 regional 中查找
    regional = qry.filter_by(status=1, r=r).first()
    if regional is None:
        return None, None
    return r, regional


def check_regionals(regional_cls: type, rs: list[int], ignore_zero: bool = False):
    """判断数据库中是否包含所有的 rs
    :param ignore_zero: 值为真，则允许 rs 值为 [0]。0 是一个特殊的 r 值，代表全局 r
    """
    lenrs = len(rs)
    qry = gdb.query(regional_cls)
    if ignore_zero:
        # 传递 0 的时候， rs 只能拥有 1 个项： 0
        if lenrs == 1 and parse_int(rs[0]) == 0:
            return True
    regionals = qry.filter_by(status=1).filter(regional_cls.r.in_(rs)).all()
    return len(regionals) == lenrs


def init_regional(regional_cls: type, value: str = ''):
    """初始化 regional 0。
    regional 0 一般用于保存全局配置。
    """
    with gdb.session() as dbs, dbs.begin():
        r0 = dbs.get(regional_cls, 0)
        if r0 is None:
            now = str(int(time.time()))
            r0 = regional_cls(
                r=0, name="0", status=1, value=value, createtime=now, updatetime=now
            )
            dbs.add(r0)
