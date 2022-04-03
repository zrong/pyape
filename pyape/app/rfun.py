"""
pyape.app.rfun
~~~~~~~~~~~~~~~~~~~

对 Regional 的操作封装
"""

import time

import tomli as tomllib
from flask import jsonify
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.expression import or_
from sqlalchemy.orm import Session

from pyape.app.re2fun import responseto, get_page_response
from pyape.app import gdb, logger
from pyape.util.func import parse_int

from pyape.app.models.regional import get_regional_qry


def regional_get_more(regional_cls, page, per_page, kindtype, status, merge):
    """ 分页获取指定 votype 下的 ValueObject 信息
    """
    if merge > 0:
        return_method = lambda vos: [vo.merge() for vo in vos] 
    else:
        return_method = 'model'
    qry = get_regional_qry(regional_cls, kindtype=kindtype, status=status)
    rdata = get_page_response(qry, page, per_page, 'regionals', return_method)
    return responseto(data=rdata)


def regional_get(regional_cls, r, merge):
    """ 获得一个 regional 项目
    :param merge: 若 merge 为 0，则直接返回原始数据；
                    若 merge 为 1，执行 Regional 中的 merge 方法
    """
    if r is None:
        return responseto('Param please!', code=401)
    robj = gdb.session().get(regional_cls, r)
    if robj is None:
        return responseto('No regional %s!' % r, code=404)

    if merge > 0:
        return responseto(regional=robj.merge(), code=200)
    return responseto(regional=robj, code=200)


def regional_get_all(regional_cls, kindtype, rtype, merge):
    """ 获得多个 regional 项目
    """
    rtype = parse_int(rtype)
    kindtype = parse_int(kindtype)

    if rtype is not None:
        if not rtype in regional_cls.REGIONAL_TYPES:
            return responseto('The rtype of regional %s is unavailable!' % rtype, code=401)

    regionals = get_regional_qry(regional_cls, kindtype=kindtype, rtype=rtype).all()
    if merge > 0:
        regionals = [regional.merge() for regional in regionals] 
    return responseto(regionals=regionals, code=200)


def regional_get_all_trim(regional_cls, kindtype, rtype, rformat):
    """ 获得多个 regional 项目，仅包含 r 和 name

    :param kindtype:
    :param rtype: 1000/2000/5000
    :param rformat: 0 代表返回 json 格式的 list，1 代表仅仅返回 r 的 list
    """
    if rtype is not None and not rtype in regional_cls.REGIONAL_TYPES:
        return responseto('The rtype of regional %s is unavailable!' % rtype, code=401)
    qry = get_regional_qry(regional_cls, kindtype=kindtype, rtype=rtype, status=1)
    regionals = qry.with_entities(regional_cls.r, regional_cls.name, regional_cls.createtime).all()
    if rformat == 1:
        regionals = [ritem.r for ritem in regionals]
    return responseto(regionals=regionals, code=200)


def regional_add(regional_cls, r, name, value, kindtype, status):
    """ 增加一个 regional
    """
    if r is None or name is None or value is None:
        return responseto('Param please!', code=401)
    kindtype = parse_int(kindtype, 0)
    try:
        tomllib.loads(value)
    except tomllib.TOMLDecodeError as e:
        msg = 'value is not a TOML string: %s' % str(e)
        logger.error(msg)
        return responseto(msg, code=401)

    now = int(time.time())
    robj = regional_cls(r=r, name=name, value=value, status=status, kindtype=kindtype, createtime=now, updatetime=now)
    dbs: Session = gdb.session()
    try:
        dbs.add(robj)
        dbs.commit()
        dbs.refresh(robj)
    except SQLAlchemyError as e:
        return jsonify({'error': True, 'message': str(e), 'code': 500})
    return responseto(regional=robj, code=200)
    

def regional_edit(regional_cls, r, name, value, kindtype, status):
    """ 修改一个 regional
    """
    status = parse_int(status, 1)
    kindtype = parse_int(kindtype)
    if r is None:
        return responseto('Param please!', code=401)
    robj = gdb.session().get(regional_cls, r)
    if robj is None:
        return responseto('找不到 regional %s!' % r, code=404)
    if name is not None:
        robj.name = name
    if value is not None:
        try:
            tomllib.loads(value)
            robj.value = value
        except tomllib.TOMLDecodeError as e:
            msg = 'value is not a TOML string: %s' % str(e)
            logger.error(msg)
            return responseto(msg, code=401)
    if kindtype is not None:
        robj.kindtype = kindtype
    if status is not None:
        robj.status = status
    robj.updatetime = int(time.time())
    dbs: Session = gdb.session()
    try:
        dbs.add(robj)
        dbs.commit()
        dbs.refresh(robj)
    except SQLAlchemyError as e:
        return jsonify({'error': True, 'message': str(e), 'code': 500})
    return responseto(regional=robj, code=200)
    

def regional_del(regional_cls, valueobject_cls, r):
    """  删除一个 regional
    """
    if r is None:
        return responseto('Param please!', code=401)
    # 必须先删除所有的与这个 Regional 相关的关系
    dbs: Session = gdb.session()
    vo = dbs.execute(select(valueobject_cls).filter_by(r=r)).scalar()
    if vo is not None:
        return responseto(f'Please delete valueobjet of {r} first!', code=403)

    robj = dbs.execute(select(regional_cls).filter_by(r=r)).scalar()
    try:
        dbs.delete(robj)
        dbs.commit()
    except SQLAlchemyError as e:
        return jsonify({'error': True, 'message': str(e), 'code': 500})
    return responseto(regional=robj, code=200)