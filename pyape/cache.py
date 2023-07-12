"""
pyape.cache
~~~~~~~~~~~~~~~~~~~
提供全局缓存的读取和写入
"""
import warnings
import pickle
from typing import Any
from redis.client import Redis
from pyape import uwsgiproxy
from pathlib import Path
import tomllib, tomli_w
import json
import time


class Cache(object):
    """ 处理缓存。
    """
    ctype: str = None
    """ 保存缓存的类型，目前支持三种缓存： uwsgi/dict/redis。"""
    def __init__(self, ctype: str):
        self.ctype = ctype


class DictCache(Cache):
    """ 使用一个 Python Dict 保存缓存
    仅用于测试，应该在 单线程/单进程 本地环境使用
    """
    def __init__(self):
        super().__init__('dict')
        self.__g = {}
        warnings.warn(f'GlobalCache USE {self!s}')

    def __getitem__(self, name):
        return self.__g.get(name)

    def __setitem__(self, name, value):
        self.__g[name] = value

    def __str__(self) -> str:
        return f'{self.__class__.__name__} {id(self.__g)}'


class FileCache(Cache):
    """  使用一个本地文件作为缓存。"""

    ftype: str = '.toml'
    """ 默认的本地文件类型，支持 toml/json/pickle"""

    fpath: Path = None

    def __init__(self, fpath: Path, ftype: str = None):
        super().__init__('file')
        self.fpath = fpath
        self.ftype = ftype or fpath.suffix
        if self.fpath is None:
            raise ValueError('FileCache need a file!')
        warnings.warn(f'GlobalCache USE {self!s}')
        self.get_cache()

    def get_cache(self) -> dict:
        if not self.fpath.exists():
            self.fpath.touch()
            return {'@cache_created': time.time()}
        if self.ftype == '.toml':
            return tomllib.loads(self.fpath.read_text(encoding='utf-8'))
        elif self.ftype == '.json':
            return json.loads(self.fpath.read_text(encoding='utf-8'))
        elif self.ftype == '.pickle':
            return pickle.loads(self.fpath.read_bytes(), encoding='utf-8')
        raise ValueError('FileCache.get_cache only supports .toml/.json/.pickle!')

    def set_cache(self, cache_data: dict) -> int:
        if self.ftype == '.toml':
            return self.fpath.write_text(tomli_w.dumps(cache_data), encoding='utf-8')
        elif self.ftype == '.json':
            return self.fpath.write_text(json.dumps(cache_data), encoding='utf-8')
        elif self.ftype == '.pickle':
            return self.fpath.write_bytes(pickle.dumps(cache_data, pickle.HIGHEST_PROTOCOL))
        raise ValueError('FileCache.set_cache only supports .toml/.json/.pickle!')

    def __getitem__(self, name):
        return self.get_cache().get(name)

    def __setitem__(self, name, value):
        c = self.get_cache()
        c['@cache_updated'] = time.time()
        c[name] = value
        self.set_cache(c)

    def __str__(self) -> str:
        return f'{self.__class__.__name__} {self.fpath.as_posix()} ftype: {self.ftype}'


class UwsgiCache(Cache):
    def __init__(self):
        super().__init__('uwsgi')
        warnings.warn(f'GlobalCache USE {self!s}')

    def __getitem__(self, name):
        """
        获取 UWSGI 缓存
        :param name: 真实的 name，带有 regional 信息
        :return: 序列化之后的 python 对象
        """
        raw_value = uwsgiproxy.cache_get(name)
        # print('_getuwsgicache:', raw_value)
        if raw_value is not None:
            return pickle.loads(raw_value, encoding='utf8')
        return None

    def __setitem__(self, name, value):
        """
        设置 UWSGI 缓存
        :param name: 设置名称
        :param value:
        :return:
        """
        if value is None:
            uwsgiproxy.cache_del(name)
            return
        raw_value = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        # print('_setuwsgicache:', raw_value)
        if uwsgiproxy.cache_exists(name):
            uwsgiproxy.cache_update(name, raw_value)
        else:
            uwsgiproxy.cache_set(name, raw_value)

    def __str__(self) -> str:
        return f'{self.__class__.__name__}'


class RedisCache(Cache):
    redis_uri: str = None

    def __init__(self, redis_client: Redis, redis_uri: str=None):
        super().__init__('redis')
        self.redis_uri = redis_uri
        self.__client = redis_client
        if not isinstance(self.__client, Redis):
            raise ValueError(f'{self!s} redis_client must be a Redis instance!')
        warnings.warn(f'GlobalCache USE {self!s}')

    def __getitem__(self, name: str):
        raw_value = self.__client.get(name)
        if raw_value is None:
            return None
        try:
            return pickle.loads(raw_value, encoding='utf8')
        except pickle.UnpicklingError as e:
            warnings.warn(f'{self!s}.pickle.loads {name=} error: {e!s}')
            return None

    def __setitem__(self, name: str, value: Any):
        raw_value = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        self.__client.set(name, raw_value)

    def mset(self, nvs):
        """ 批量设置
        """
        self.__client.mset(nvs)

    def __str__(self) -> str:
        return f'{self.__class__.__name__} {self.redis_uri}'


class GlobalCache(object):
    """ 创建一个唯一的全局 Cache 方便使用
    注意这个全局代表同进程全局，因此在使用 DictCache 和 UwsgiCache 的时候，需要自行同步
    """
    def __init__(self, cache):
        self.cache = cache

    @classmethod
    def from_config(cls, ctype: str, **kwargs):
        """ 获取一个 Cache 实例
        """
        if ctype == 'uwsgi':
            return cls(UwsgiCache())
        elif ctype == 'file':
            fpath = kwargs.get('fpath')
            ftype = kwargs.get('ftype')
            return cls(FileCache(fpath, ftype))
        elif ctype == 'redis':
            # 优先确认 redis_client 参数
            redis_client = kwargs.get('redis_client')
            redis_uri = kwargs.get('redis_uri')
            if redis_client is None:
                # 将 grc 参数作为 PyapeRedis 实例对待
                grc = kwargs.get('grc')
                if grc and getattr(grc, 'get_client', None):
                    # 获取名称为 cache 的 redis 定义，作为 cache 的源。
                    bind_key = 'cache'
                    redis_client = grc.get_client(bind_key, miss_default=True)
                    redis_uri = grc.get_uri(bind_key, miss_default=True)
            # redis 模式下，redis_client 必须存在
            if redis_client is None:
                raise ValueError('redis_client must be existence!')
            return cls(RedisCache(redis_client, redis_uri))
        return cls(DictCache())

    @property
    def ctype(self) -> str:
        return self.cache.ctype

    def keyname(self, r: int, name: str):
        return f'{r}_{name!s}'

    def getg(self, name, r=0):
        """ 默认使用 0 这个r值，代表不区分 r
        """
        if r is None or name is None:
            return None
        return self.cache[self.keyname(r, name)]

    def setg(self, name, value, r=0):
        """ 默认使用 0 这个r值，代表不区分 r
        """
        if r is not None and name is not None and value is not None:
            self.cache[self.keyname(r, name)] = value

    def msetg(self, nvs, r=0):
        """ 设置一组缓存
        """
        # 若提供了 setall 方法则直接调用
        newkey_nvs = {}
        for n, v in nvs.items():
            newkey_nvs[self.keyname(r, n)] = v
        if getattr(self.cache, 'mset', None):
            self.cache.mset(newkey_nvs)
        else:
            for n2, v2 in newkey_nvs.items():
                self.cache[n2] = v2

    def delg(self, name, r=0):
        """ 默认使用 0 这个r值，代表不区分 r
        """
        if r is not None and name is not None:
            self.cache[self.keyname(r, name)] = None
