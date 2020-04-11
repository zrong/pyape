# -*- coding: utf-8 -*-
"""
pyape.app.rfun
~~~~~~~~~~~~~~~~~~~

对 Regional 的操作封装
"""

import toml
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.expression import or_

from pyape.app.re2fun import get_request_values, responseto
from pyape.app.queryfun import commit_and_response_error
from pyape.app import gdb, logger
from pyape.util.func import parse_int

from pyape.app.models.valueobject import ValueObject, get_vos_vidname, del_vo_vidname
from pyape.app.models.regional import Regional


def regional_loginkey_get_all():
    """ 获得所有可用的 loginkey 的名称和编号
    """
    vos = get_vos_vidname(501)
    return responseto(loginkeys=vos, code=200)


def regional_loginkey_add(names, value):
    """ 增加一个 loginkey
    """
    if name is None or value is None:
        return responseto('Param please!', code=401)
    robj = ValueObject(r=0, votype=501, name=name, value=value, status=1)
    resp = commit_and_response_error(robj, refresh=True)
    if resp is not None:
        return resp
    return responseto(loginkey={'vid':robj.vid, 'name':robj.name}, code=200)


def regional_loginkey_del(vid, name):
    """  删除一个 loginkey
    """
    if vid is None and name is None:
        return responseto('Param please!', code=401)
    msg = del_vo_vidname(vid, name)
    if msg is not None:
        return responseto(msg, code=500)
    return responseto(code=200)
    

def regional_get(r, mergevo):
    """ 获得一个 regional 项目
    :param mergevo: 若 mergevo 为 0，则直接返回原始数据；
                    若 mergevo 为 1，执行 Regional 中的 mergevo 方法
    """
    if r is None:
        return responseto('Param please!', code=401)
    robj = Regional.query.get(r)
    if robj is None:
        return responseto('No regional %s!' % r, code=404)

    logger.info('mergevo %s', mergevo)
    if mergevo == 1:
        return responseto(regional=robj.merge_value(), code=200)
    return responseto(regional=robj, code=200)


def regional_get_all(type_):
    """ 获得多个 regional 项目
    与 /cf/regional/all/ 不同的是，这里获取的直接是数据库项目内容，value 是 TOML 字符串
    """
    if type_ is None:
        return responseto(regionals=Regional.query.all(), code=200)
    if not type_ in Regional.REGIONAL_TYPES:
        return responseto('The type of regional %s is unavailable!' % type_, code=401)
    return responseto(regionals=Regional.get_all_by_type_qry(type_).all(), code=200)


def regional_get_all_trim(type_, format_):
    """ 获得多个 regional 项目，仅包含 r 和 name

    :param type: 1000/2000/5000
    :param format: 0 代表返回 json 格式的 list，1 代表仅仅返回 r 的 list
    """
    qry = None
    if type_ is None:
        qry = Regional.query
    else:
        if not type_ in Regional.REGIONAL_TYPES:
            return responseto('The type of regional %s is unavailable!' % type_, code=401)
        qry = Regional.get_all_by_type_qry(type_)
    regionals = qry.filter_by(status=1).with_entities(Regional.r, Regional.name, Regional.createtime).all()
    if format_ == 1:
        regionals = [ritem.r for ritem in regionals]
    return responseto(regionals=regionals, code=200)


def regional_add(r, name, value, loginkey, kindtype, status):
    """ 增加一个 regional
    """
    if r is None or name is None or value is None or loginkey is None or pftype is None:
        return responseto('Param please!', code=401)
    try:
        toml.loads(value)
    except toml.TomlDecodeError as e:
        msg = 'value is not a TOML string: %s' % str(e)
        logger.error(msg)
        return responseto(msg, code=401)
    if ValueObject.query.get(loginkey) is None:
        return responseto('No loginkey %s!' % loginkey, code=401)

    robj = Regional(r=r, name=name, value=value, status=status, loginkey=loginkey, kindtype=kindtype)
    resp = commit_and_response_error(robj, refresh=True)
    if resp is not None:
        return resp
    return responseto(regional=robj, code=200)
    

def regional_edit(r, name, value, loginkey, kindtype, status):
    """ 修改一个 regional
    """
    status = parse_int(status, 1)
    loginkey = parse_int(loginkey)
    kindtype = parse_int(kindtype)
    if r is None:
        return responseto('Param please!', code=401)
    robj = Regional.query.get(r)
    if name is not None:
        robj.name = name
    if value is not None:
        try:
            toml.loads(value)
            robj.value = value
        except toml.TomlDecodeError as e:
            msg = 'value is not a TOML string: %s' % str(e)
            logger.error(msg)
            return responseto(msg, code=401)
    if loginkey is not None:
        if ValueObject.query.get(loginkey) is None:
            return responseto('No loginkey %s!' % loginkey, code=401)
        robj.loginkey = loginkey
    if kindtype is not None:
        robj.kindtype = kindtype
    if status is not None:
        robj.status = status
    resp = commit_and_response_error(robj, refresh=True)
    if resp is not None:
        return resp
    return responseto(regional=robj, code=200)
    

def regional_del(r):
    """  删除一个 regional
    """
    if r is None:
        return responseto('Param please!', code=401)
    # 必须先删除所有的与这个 Regional 相关的关系
    if ValueObject.query.filter_by(r=r).first() is not None:
        return responseto('Please delete valueobjet of %s first!' % r, code=403)
    try:
        Regional.query.filter_by(r=r).delete()
        db.session.commit()
    except SQLAlchemyError as e:
        msg = 'regiona_del error: ' + str(e)
        logger.error(msg)
        return responseto(msg, code=500)
    return responseto(code=200)
    