__all__ = ['encrypt', 'func']

import hashlib

def md5txt(txt):
    """
    计算 MD5 字符串散列
    :param txt:
    :return:
    """
    md5obj = hashlib.md5()
    md5obj.update(txt.encode('utf-8'))
    return md5obj.hexdigest()