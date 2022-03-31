"""
pyape.app.models.regional
~~~~~~~~~~~~~~~~~~~

与 regional 表相关的方法
"""
import time
import tomli as tomllib
from sqlalchemy.orm import Query, Session
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.types import Enum, SMALLINT, VARCHAR, INTEGER, FLOAT, TEXT, TIMESTAMP
from sqlalchemy import  Column, ForeignKey

from pyape.app import gdb, logger
from pyape.config import RegionalConfig
from pyape.util.func import parse_int


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


def get_regional_qry(regional_cls, kindtype=None, rtype=None, status=None) -> Query:
    """ 获取排序过的 Regional 项目，可以根据 kindtype/rtype/status 筛选
    :param kindtype:
    :param rtype:
    :param status:
    :return:
    """
    cause = []
    if kindtype is not None:
        cause.append(regional_cls.kindtype == kindtype)
    if status is not None:
        cause.append(regional_cls.status == status)
    if rtype is not None:
        if rtype == 1000:
            cause.append(regional_cls.r.between(1000, 1999))
        elif rtype == 2000:
            cause.append(regional_cls.r.between(2000, 2999))
        else:
            cause.append(regional_cls.r.between(5000, 5999))
    return gdb.query(regional_cls).\
            filter(*cause).\
            order_by(regional_cls.status, regional_cls.createtime.desc())


def make_regional_table_cls(table_name: str='regional', bind_key: str=None):
    """ Regional 配置
    """
    def _merge(self):
        """ 合并数据库中的其他字段到 value 配置中
        """
        parsed_dict = {}
        if self.value is not None:
            parsed_dict = tomllib.loads(self.value)
        parsed_dict['name'] = self.name
        parsed_dict['r'] = self.r
        parsed_dict['kindtype'] = self.kindtype
        parsed_dict['status'] = self.status
        parsed_dict['createtime'] = self.createtime
        parsed_dict['updatetime'] = self.updatetime
        parsed_dict['rtype'] = r2type(self.r)
        return parsed_dict

    attributes = \
        dict(
            __tablename__ = table_name,

            # 以下的属性是是数据表列
            r = Column(SMALLINT, primary_key=True, index=True, autoincrement=False), # Regional 配置的主键序号
            name = Column(VARCHAR(100), nullable=False), # Regional 名称
            value = Column(TEXT, nullable=True), # Regional 的具体配置， TOML 字符串
            kindtype = Column(SMALLINT, nullable=False, index=True), # 对 regional 的一种分类法，其值应为 typeid
            status = Column(SMALLINT, nullable=False, default=1), # Regional 的状态，值为在 TypeID 中的整数，1正常，5 禁用
            # createtime = gdb.Column(gdb.TIMESTAMP(True), server_default=text('CURRENT_TIMESTAMP'))
            # updatetime = gdb.Column(gdb.TIMESTAMP(True), nullable=True,
            #                        server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
            # 改用时间戳，将格式化完全交给客户端来处理
            createtime = Column(INTEGER, nullable=False),
            updatetime = Column(INTEGER, nullable=True),

            # 下面的属性是方法
            merge=_merge,

            # 下面的属性是普通属性
            REGIONAL_TYPES = [1000, 2000, 5000], # 1000测试 2000审核 5000正式
            bind_key=bind_key
        )
    return type(table_name, (gdb.Model(bind_key), ), attributes)



def get_regional_config(regional_cls, status=None):
    """ 从数据库中读取 regional 的配置，转换成 RegionalConfig
    """
    # 取出数据库中所有启用的 Regional
    qry = gdb.query(regional_cls)
    if isinstance(status, int):
        qry = qry.filter_by(status=status)
    regional_list = [ritem.merge() for ritem in qry.all()]
    return RegionalConfig(regional_list)


def check_regional(regional_cls, r: int, ignore_zero: bool=False):
    """ 检查 regional 是否有效，同时返回数据库中查询到的 regional 配置
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


def check_regionals(regional_cls, rs: list[int], ignore_zero=False):
    """ 判断数据库中是否包含所有的 rs
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


def init_regional(regional_cls):
    """ 初始化 regional0 这是必须存在的一条
    """
    dbs: Session = gdb.session()
    r0 = dbs.get(regional_cls, 0)
    if r0 is not None:
        raise ValueError('The regional 0 is exists!')

    now = int(time.time())
    r0 = regional_cls(r=0, name='0', kindtype=0, status=1, createtime=now, updatetime=now)
    try:
        dbs.add(r0)
        dbs.commit()
    except SQLAlchemyError as e:
        raise SQLAlchemyError(f'Init regional table error: {e!s}')