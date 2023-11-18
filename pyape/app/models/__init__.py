"""
pyape.app.models
~~~~~~~~~~~~~~~~~~~

包含公用的 models 定义
"""

import time
from sqlalchemy.types import VARCHAR, INTEGER
from sqlalchemy.sql.schema import ForeignKey, Column


default_timestamp = lambda: str(int(time.time()))
""" 返回一个UNIX时间戳的字符串形态"""

foreign_key = lambda c: ForeignKey(c, ondelete='CASCADE', onupdate='CASCADE')
""" 外键定义，使用 delte/update CASCADE 约束"""

column_primary = lambda: Column(INTEGER, primary_key=True, autoincrement=True)
""" 主键列，自增"""

column_timestamp = lambda *, nullable=False, default=None: Column(
    VARCHAR(12), nullable=nullable, default=default
)
""" 使用 12位字符串存储秒级的 Unix 时间戳，足够用到公元 33658 年"""