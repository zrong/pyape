"""
pyape.app.queryfun
~~~~~~~~~~~~~~~~~~~

查询常用方法封装
"""
from flask import jsonify
from sqlalchemy import func

from pyape.app import gdb, logger


def sql_from_unixtime(dtfield, dtformat='%Y-%m-%d'):
    """
    返回一个 FROM_UINXTIME 的查询对象
    :param dtfield: 用于转换的记录名称，必须是 datetime 或者 timestamp 类型
    :param dtformat: 对应与 FROM_UNIXTIME 的第二个参数
    :return:
    """
    return func.from_unixtime(func.unix_timestamp(dtfield), dtformat)


def get_total_value(query, sum_field):
    """
    返回总计的值
    :param query: 要计数的查询
    :param sum_field: 要计数的字段
    :param label_name: 计数字段的label名称
    :return:
    """
    total_value_entry = query.with_entities(func.sum(sum_field).label('total_value')).first()
    if total_value_entry is None:
        return 0
    return 0 if total_value_entry.total_value is None else int(total_value_entry.total_value)


def commit_and_response_error(inst, refresh=False, delete=False, return_dict=False, bind_key: str=None):
    """ 将提交一个 instance 并返回错误响应，封装成一个操作
    """
    try:
        session = gdb.session(bind_key)
        if delete:
            session.delete(inst)
        else:
            session.add(inst)
        session.commit()
        if refresh:
            session.refresh(inst)
        return None
    except Exception as e:
        msg = str(e)
        logger.error(msg)
        session.rollback()
        resp_dict = {'error': True, 'message': msg, 'code': 500}
        if return_dict:
            return resp_dict
        return jsonify(resp_dict)