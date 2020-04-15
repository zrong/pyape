# -*- coding: utf-8 -*-
"""
pyape.app.models
~~~~~~~~~~~~~~~~~~~

包含公用的 models 定义
"""

from .typeid import TypeID
from .regional import init_regional
from .valueobject import init_valueobject


def init_models():
    """ 初始化 models
    执行所有 models 的初始化数据库的方法
    """
    init_regional()
    init_valueobject()