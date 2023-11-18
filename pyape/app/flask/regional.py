"""
pyape.app.flask.regional
~~~~~~~~~~~~~~~~~~~

对 Regional 的操作封装
"""

import time

import tomllib
from flask import jsonify
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql.expression import or_
from sqlalchemy.orm import Session

from pyape.app import gdb, logger
from pyape.util.func import parse_int

from .re2 import responseto


def regional_add(regional_cls, r, name, value, status):
    """增加一个 regional"""
    if r is None or name is None or value is None:
        return responseto('Param please!', code=401)
    try:
        tomllib.loads(value)
    except tomllib.TOMLDecodeError as e:
        msg = f'value is not a TOML string: {e!s}'
        logger.error(msg)
        return responseto(msg, code=401)

    now = int(time.time())
    robj = regional_cls(
        r=r,
        name=name,
        value=value,
        status=status,
        createtime=now,
        updatetime=now,
    )
    dbs: Session = gdb.session()
    try:
        dbs.add(robj)
        dbs.commit()
        dbs.refresh(robj)
    except SQLAlchemyError as e:
        return jsonify({'error': True, 'message': str(e), 'code': 500})
    return responseto(regional=robj, code=200)


def regional_edit(regional_cls, r, name, value, status):
    """修改一个 regional"""
    status = parse_int(status, 1)
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
    """删除一个 regional"""
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
