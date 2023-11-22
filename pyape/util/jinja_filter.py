"""
pyape.util.jinja_filter
~~~~~~~~~~~~~~~~~~~

自定义 jinja filter

@author zrong
@created 2023-11-22
"""

from typing import Any
from datetime import datetime


def _jinja_filter_check_int_str(value: Any) -> Any:
    """ 检测 value 如果是 None 或者空字符串，就返回空字符串。"""
    if value is None:
        return None
    if isinstance(value, str) and len(value.strip()) == 0:
        return None
    return value


def jinja_filter_strftimestamp(ts: float | int | str | None, fmt: str = None):
    """将 timestamp 转换成为字符串。"""
    # fmt = '%Y-%m-%d'
    ts = _jinja_filter_check_int_str(ts)
    if ts is None:
        return ''
    ts = float(ts)
    if ts <= 0:
        return ''
    dt = datetime.fromtimestamp(ts)
    if fmt is None:
        return dt.isoformat()
    return dt.strftime(fmt)


_KB: int = 1024
_MB: int = 1048576
_GB: int = 1073741824
def jinja_filter_filesize(size: int | str | None) -> Any:
    """ 将文件大小（字节）转换为人类可读的形式。"""
    size = _jinja_filter_check_int_str(size)
    if size is None:
        return ''
    size = int(size)
    if size > _GB:
        return f'{size/_GB:.2f} GB'
    elif size > _MB:
        return f'{size/_MB:.2f} MB'
    elif size > _KB:
        return f'{size/_KB:.1f} KB'
    return f'{size} Byte'
