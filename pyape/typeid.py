"""
pyape.typeid
~~~~~~~~~~~~~~~~~~~

使用 typeid 定义
"""
from enum import IntEnum


class TypeID(IntEnum):
    # 保存初始化的 type
    # 0 默认状态，用于所有默认值，例如默认账号类型
    # 1-9 账户的状态
    # 10-49 特殊账户权限
    # 50-99 一般账户权限
    # 100-199 行为
    # 200-299 暂未使用
    # 300-399 数据库表 vo 的类型区分
    # 400-499 平台类型
    # 1001-xxxx 历史记录类型

    def __new__(cls, value: int, phrase: str, desc: str=''):
        obj = int.__new__(cls, value)
        obj._value_ = value

        obj.phrase = phrase
        obj.desc = desc
        return obj

    DEFAULT = 0, '默认', 'default'
    ACTIVE = 1, '可用', 'active'
    LOCK = 5, '锁定', 'lock'
    VO_TOKEN = 302, 'Token', 'Token Value Object'
    VO_FREQUENCY = 306, '频繁访问的配置', '不分类的需要频繁访问，写入内存缓存的配置'
    VO_COMMON = 307, '通用配置', '通用配置，不区分类型'