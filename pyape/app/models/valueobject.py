"""
pyape.app.models.valueobject
~~~~~~~~~~~~~~~~~~~

与 vo 表相关的方法
vo = ValueObject 用于存储所有量不大的值对象
例如 Version/Token
"""

import json
import tomli as tomllib
import tomli_w

from sqlalchemy.sql.expression import or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.types import Enum, SMALLINT, VARCHAR, INTEGER, FLOAT, TEXT, TIMESTAMP
from sqlalchemy import  Column, ForeignKey

from pyape.app import gdb, logger


def dump_value(value, type_='json'):
    """ 将提供的 value 转换成为 TOML 或者 JSON 字符串
    :return:
    """
    if type_ == 'toml':
        # toml 不支持 list 格式，对于之前 json list 格式的配置文件，加入一个顶级的 ROOTLIST 键
        if isinstance(value, list):
            return tomli_w.dumps({'ROOTLIST': value})
        return tomli_w.dumps(value)
    return json.dumps(value, ensure_ascii=False)


def load_value(value, type_=None):
    """ 将 value 字符串转换成为 dict 或者 list
    首先检测是否为 json 格式
    然后考虑 toml 格式
    :return:
    """
    # logger.info('ValueObject.load_value %s, type: %s', value, type_)
    def toml_loads(value):
        tobj = tomllib.loads(value, dict)
        # toml 不支持 list 格式，对于之前 json list 格式的配置文件，加入一个顶级的 ROOTLIST 键
        # 若存在这个键且其值为 list，则仅返回这个 list
        rootlist = tobj.get('ROOTLIST')
        # logger.info('toml_loads tobj %s', tobj)
        # 使用 pickle 处理 loads 后的对象时，会出现下面的错误
        # TomlDecoder.get_empty_inline_table.<locals>.DynamicInlineTableDict
        # 因此使用 json 转换一遍
        if isinstance(rootlist, list):
            jstr = json.dumps(rootlist, ensure_ascii=False)
        else:
            jstr = json.dumps(tobj, ensure_ascii=False)
        return json.loads(jstr)

    if type_ is None:
        try:
            return json.loads(value)
        except Exception as e:
            logger.warning('valueobject.load_value, value is not json: %s', e)
            try:
                return toml_loads(value)
            except Exception:
                return None
    elif type_ == 'toml':
        try:
            return toml_loads(value)
        except Exception:
            return None
    else:
        try:
            return json.loads(value)
        except Exception:
            return None


def make_value_object_table_cls(table_name: str='vo', bind_key: str=None):
    """ 所有量不大的值对象放在这里，例如 Version/Token
    动态创建一个 vo 表，需要提供 bind_key 以指定 Model
    """
    def _set_value(self, value, type_='json'):
        """
        将提供的 value 转换成为 ValueObject 需要的 JSON 字符串
        :return:
        """
        self.value = dump_value(value, type_)

    def _get_value(self, type_=None):
        """
        将 ValueObject 中的 value 字符串转换成为 dict
        首先检测是否为 toml 格式
        然后考虑 json 格式
        :return:
        """
        valueobj = load_value(self.value, type_)
        # logger.info('get_value %s', valueobj)
        return valueobj

    def _merge(self, includes=['votype', 'createtime', 'updatetime', 'note', 'status'], type_=None):
        """
        将 ValueObject 对象转换成为一个 dict ，合并 createtime/updatetime/vid/typeid 到 value 代表的 JSON 对象中
        :param includes: 需要包含的字段
        :return:
        """
        voobj = self.get_value(type_)
        if isinstance(voobj, dict):
            pass
        elif voobj is None:
            voobj = {}
        else:
            voobj = {'value': voobj}
        voobj['vid'] = self.vid
        voobj['name'] = self.name
        voobj['index'] = self.index
        if includes:
            for k in includes:
                try:
                    v = getattr(self, k)
                    # 2021-01-10 使用时间戳，不再需要 isoformat
                    # if isinstance(v, datetime):
                    #     v = v.isoformat()
                    voobj[k] = v
                except AttributeError:
                    pass
        return voobj

    attributes = \
        dict(
            __tablename__ = table_name,

            # 以下的属性是是数据表列
            vid = Column(INTEGER, primary_key=True, autoincrement=True),
            r = Column(SMALLINT, nullable=False, default=0), # 区服编号，对应 regional
            name = Column(VARCHAR(32), nullable=False, unique=True, index=True), # VO 的名称
            value = Column(TEXT, nullable=False), # VO 的值，一般使用 JSON/TOML 字符串
            votype = Column(SMALLINT, index=True, nullable=False, default=307), # VO 的类型，详见 typeid
            index = Column(SMALLINT, nullable=False, default=0), # 排序索引
            status = Column(SMALLINT, index=True, nullable=False, default=1), # VO 是 1启用 还是 5禁用

            # createtime = Column(TIMESTAMP(True), server_default=text('CURRENT_TIMESTAMP'))
            # updatetime = Column(TIMESTAMP(True), nullable=True,
            #                        server_default=text('CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'))
            # updatetime = Column(TIMESTAMP(True), nullable=True)
            # 2021-01-10 改用时间戳，将格式化完全交给客户端来处理
            createtime = Column(INTEGER, nullable=False),
            updatetime = Column(INTEGER, nullable=True),
            note = Column(VARCHAR(512), nullable=True),
            
            # 下面的属性是普通属性
            bind_key=bind_key,

            # 下面的属性是普通方法
            get_value=_get_value,
            set_value=_set_value,
            merge=_merge
        )
    return type(table_name, (gdb.Model(bind_key), ), attributes)


def get_vo_fullname(r, name):
    """ 由于 vo 的 name 是 unique 的，需要给所有 name 加上 r 前缀
    """
    return 'r%s_%s' % (r, name)


def get_vo_by_fullname(vo_cls, fullname: str, type_=None, merge=None, bind_key: str=None):
    """ 获取一个 vo，此处提供的 name 完整名称
    """
    vo = gdb.query(vo_cls).filter_by(name=fullname, status=1).first()
    if vo is not None:
        if isinstance(merge, list):
            return vo.merge(merge, type_)
        return vo.get_value(type_)
    return None


def get_vo_by_name(vo_cls, r:int, name: str, type_=None, merge=None, bind_key: str=None):
    """ 获取一个 vo，此处提供的 name 是不含 r 前缀的名称
    """
    fullname = get_vo_fullname(r, name)
    return get_vo_by_fullname(vo_cls, fullname, type_, merge, bind_key=bind_key)


def get_vo_query(vo_cls, r: int, votype: int=None, status=None):
    """ 获取排序过的 ValueObject 项目，可以根据 usertype 和 status 筛选
    :param votype:
    :param status:
    :return:
    """
    cause = [vo_cls.r == r]
    if votype is not None:
        cause.append(vo_cls.votype == votype)
    if status is not None:
        cause.append(vo_cls.status == status)
    return gdb.query(vo_cls).filter(*cause).\
            order_by(vo_cls.status, vo_cls.index, vo_cls.createtime.desc())


def get_vos_vidname(vo_cls, votype: int):
    vos = gdb.query(votype).filter_by(votype=votype, status=1).\
        with_entities(vo_cls.vid, vo_cls.name).\
        all()
    return vos


def del_vo_vidname(vo_cls, vid: int, name: str):
    """ 通过 vid 或者 name 删除一个 vo
    """
    try:
        dbs = gdb.session(vo_cls.bind_key)
        dbs.query(vo_cls).filter(or_(vo_cls.vid==vid, vo_cls.name==name)).delete()
        dbs.commit()
    except SQLAlchemyError as e:
        msg = 'valueobject.del_vo_vidname error: ' + str(e)
        dbs.rollback()
        logger.error(msg)
        return msg
    return None
