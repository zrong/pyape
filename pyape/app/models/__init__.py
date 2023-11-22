"""
pyape.app.models
~~~~~~~~~~~~~~~~~~~

包含公用的 models 定义
"""

import time
from datetime import datetime, timedelta
from sqlalchemy.types import VARCHAR, INTEGER, Integer
from sqlalchemy.sql import or_, and_, Select
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


from pyape.util.date import DateRange


def select_by_date_range(date_text: str, timestamp_column: Column, stmt: Select):
    """根据 date_text 字符串，获取对应的 date_range，
    与 timestamp_column 中提供的时间戳做比较，
    返回新的 Select 对象。
    """
    # timestamp_column 的类型有可能是整数时间戳字符串
    # SMALLINT/BIGINT/INTEGER 的父类都是 Integer，
    # 这里不考虑浮点数，保存在 timestamp 列的只能是字符串或者整数
    is_int = isinstance(timestamp_column.type, Integer)
    real_column = timestamp_column if is_int else timestamp_column.cast(INTEGER)

    date_range = DateRange(date_text)
    # 筛选日期，注意结束的日期需要加上一天以保证包含当天的时间，比较的时候使用小于。
    if date_range.is_range:
        stmt = stmt.where(
            and_(
                real_column >= int(date_range.range_start(datetime).timestamp()),
                real_column
                < int((date_range.range_end(datetime) + timedelta(days=1)).timestamp()),
            )
        )
    else:
        where_cause = []
        for d in date_range:
            range_start = datetime.strptime(str(d), DateRange.DATE_FMT)
            range_end = range_start + timedelta(days=1)
            where_cause.append(
                and_(
                    real_column >= int(range_start.timestamp()),
                    real_column < int(range_end.timestamp()),
                )
            )
        stmt = stmt.where(or_(*where_cause))
    return stmt
