# -*- coding: utf-8 -*-
"""
pyape.app.vofun
~~~~~~~~~~~~~~~~~~~

对 ValueObject 的操作封装
"""

from flask import abort

from pyape.util.func import parse_int
from pyape import gconfig
from pyape.app import gdb, gcache, logger
from pyape.app.models.valueobject import ValueObject, get_vo_query
from pyape.app.models.typeid import TypeID
from pyape.app.re2fun import get_request_values, responseto, get_page_response
from pyape.app.queryfun import commit_and_response_error


# @checker.request_checker('votype', 'status', 'mergevo', defaultvalue={'mergevo': 1, 'status': 1}, request_key='args', parse_int_params=['mergevo', 'status', 'votype'])
def valueobject_get_more(r, page, per_page, votype, status, mergevo):
    """ 分页获取指定 votype 下的 ValueObject 信息
    """
    if mergevo > 0:
        return_method = lambda vos: [vo.mergevo() for vo in vos] 
    else:
        return_method = 'model'
    qry = get_vo_query(r, votype, status)
    rdata = get_page_response(qry, page, per_page, 'vos', return_method)
    return responseto(data=rdata)


# @checker.request_checker('votype', 'status', 'mergevo', defaultvalue={'mergevo': 0, 'status': 1}, request_key='args', parse_int_params=['mergevo', 'status', 'votype'])
def valueobject_get_all(r, votype, status, mergevo):
    """ 获取指定 votype 下所有 ValueObject 信息
    """
    vos = get_vo_query(r, votype, status).all()
    if mergevo > 0:
        return responseto(vos=[vo.mergevo() for vo in vos])
    return responseto(vos=vos)


def valueobject_save(r, value, vid=None, name=None, votype=None, status=None, index=None, note=None, valuetype=None):
    """ 保存一个 VO ，支持增加和更新
    """
    if vid is not None:
        vid = parse_int(vid)
        if vid is None:
            return dict(message='vid 必须是整数!', code=401, error=True)
    if status is not None:
        status = parse_int(status)
        if status is None:
            return dict(message='status 必须是整数!', code=401, error=True)
    if index is not None:
        index = parse_int(index)
    if isinstance(value, str):
        # 检测字符串是否正常解析
        vobj = ValueObject.load_value(value, valuetype)
        if vobj is None:
            return dict(message='value 无法正常解析！请检查。', code=401, error=True)
    else:
        value = ValueObject.dump_value(value, valuetype)
    voitem = None
    if vid is not None:
        # 提供 vid 代表是修改 vo
        voitem = ValueObject.query.get(vid)
        if not voitem:
            return dict(message='找不到 vid 为 %s 的纪录!' % vid, code=404, error=True)
    elif name is not None:
        # 没有提供 vid 但提供了 name 也代表是修改 vo
        voitem = ValueObject.query.filter_by(name=name).first()
    if voitem is not None:
        # 只有明确提供了 status 才设置它
        # 不处理 votype/r ，因为已经创建了的 VO 不允许修改这些关键分类的值
        if name is not None:
            voitem.name = name
        if status is not None:
            voitem.status = status
        if note is not None:
            voitem.note = note
        if index is not None:
            voitem.index = index
    else:
        # 找不到 voitem，代表新增 vo。必须提供 votype 和 name
        if name is None:
            return dict(message='name please!', code=401, error=True)
        votype = parse_int(votype)
        if votype is None:
            return dict(message='请提供 votype!', code=401, error=True)
        voitem = ValueObject(name=name,
            status=status if status is not None else 1,
            index=index if index is not None else 0,
            r=r,
            votype=votype,
            note=note)
    # vo已经是检测过的字符串了
    voitem.value = value

    resp = commit_and_response_error(voitem, refresh=True, return_dict=True)
    if resp is not None:
        return resp
    return dict(vo=gdb.to_response_data(voitem), error=False, code=200)


def _get_vo_by_cache(r, name):
    """ 从缓存中查询 vo 的 value
    若缓存中不存在，则从数据库中查询并将其写入缓存
    """
    valueobj = gcache.getg(name, r)
    if valueobj is None:
        vo = ValueObject.query.filter_by(name=name).first()
        if vo is not None:
            valueobj = vo.get_value()
            gcache.setg(name, valueobj, r)
    return valueobj


# @checker.request_checker('vid', 'name', 'mergevo', defaultvalue={'mergevo': 1, 'withcache': 0}, request_key='args', parse_int_params=['mergevo', 'withcache'])
def valueobject_get(r, vid, name, mergevo, withcache):
    """ 获取单个 ValueObject 信息，支持通过  vid 和 name
    """
    if withcache > 0:
        if name is None:
            return responseto('请提供 name!', code=401)
        value_in_cache = _get_vo_by_cache(r, name)
        if value_in_cache is None:
            return responseto('no vo like this.', code=404)
        return responseto(vo=value_in_cache)

    # 从数据库中查询
    vo = None
    if vid is not None:
        vo = ValueObject.query.get(vid)
    elif name is not None:
        vo = ValueObject.query.filter_by(name=name).first()
    else:
        return responseto('vid or name please!', code=401)
    if vo is None:
        return responseto('no vo like this.', code=404)
    if mergevo > 0:
        vo = vo.mergevo()
    return responseto(vo=vo)


def valueobject_set(r, vodict, withcache):
    """ 增加或者编辑 ValueObject 信息
    """
    rdata = valueobject_save(r, **vodict)
    if rdata.get('error'):
        return responseto(data=rdata)
    # 将 valueobj 写入缓存
    if withcache > 0:
        valueobj = ValueObject.load_value(rdata['vo']['value'])
        gcache.setg(rdata['vo']['name'], valueobj, r)
    return responseto(data=rdata)


def valueobject_del(vid, name):
    """ 删除一个 vo，优先使用 vid，然后考虑 name
    """
    vo = None
    if vid is not None:
        vo = ValueObject.query.get(vid)
    elif name is not None:
        vo = ValueObject.query.filter_by(name=name).first()
    else:
        return responseto('vid or name please!', code=401)
    if vo is None:
        return responseto('no vo like this.', code=404)

    r = vo.r
    name = vo.name

    resp = commit_and_response_error(vo, delete=True)
    if resp is not None:
        return resp
    gcache.delg(name, r)

    return responseto()


def update_cache_all(votype):
    """ 数据库中配置信息更新，需要更新所有的数据库
    """
    if gconfig.regional_ids:
        for r in config.regional_ids:
            update_cache(votype, r)


def update_cache(votype, r):
    """ 从数据库中获取 vo 数据，将其写入缓存中
    这个配置需要被客户端频繁调用，因此不应该去查询数据库
    每次增加或者修改服务器配置的时候，必须调用一次更新内存
    """
    allcache = {}
    for vo in get_vo_query(r, votype, 1).all():
        if vo.value is not None:
            # logger.info('vofun.update_cache %s', vo.get_value())
            allcache[vo.name] = vo.get_value()
    gcache.mset(allcache, r)
