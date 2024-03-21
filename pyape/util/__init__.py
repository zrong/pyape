"""
pyape.util
------------------

封装的小工具
"""

__all__ = ['encrypt', 'func', 'gen', 'date', 'warning']

import hashlib
import base64


def md5txt(txt: str | bytes) -> str:
    """
    计算 MD5 字符串散列
    :param txt:
    :return:
    """
    md5obj = hashlib.md5()
    if isinstance(txt, str):
        txt = txt.encode('utf-8')
    md5obj.update(txt)
    return md5obj.hexdigest()


def md5base64(txt: str | bytes) -> bytes:
    """md5(base64) 算法
    验证工具： http://www.cmd5.com/hash.aspx
    """
    m = hashlib.md5()
    if isinstance(txt, str):
        txt = txt.encode('utf-8')
    m.update(txt)
    return base64.encodebytes(m.digest())[:-1].decode('utf8')
