"""
.. _pyape_config:

pyape.config
----------------------------

解析 config.toml 配置文件
提供配置文件相关的读取和写入方法
"""

from pathlib import Path
import json
import time
from typing import Any, Union
import tomli as tomllib
import tomli_w

from pyape.util.encrypt import Encrypt


# 根据平台中的配置字符串，确定属于哪个平台
PlATFORMS = {
    'BAIDU_SMARTPROGRAM': 'baidu',
    'BYTEDANCE_MICROAPP': 'bytedance',
    'WECHAT_MINIAPP': 'wechat',
    'QQ_MINIGAME': 'qq2',
}


class PYConf(dict):
    """基于 Python dict 的配置文件。

    dict 默认不适合当作配置文件对象使用。如要有下面几点不便：

    #. 对于不存在的 key，会 raise KeyError 错误；
    #. dict不能使用 ``.`` 语法访问。

    :class:`PYConf` 解决了这些问题，还另外提供了一些方法在使用上更加方便。

    """

    def __missing__(self, key):
        return None

    def __getattr__(self, name):
        return self[name]

    def __setattr__(self, name, value):
        self[name] = value

    def __delattr__(self, name):
        del self[name]

    def copy_from_dict(self, adict: dict, parent=None) -> None:
        """从一个已经存在的 dict 中复制所有的值。

        :param adict: 被复制的 dict。
        :type adict: dict
        :param parent:  复制到哪个父对象。
                        若为 None 则复制到 self 。
        :type parent: PYConf

        """
        if not parent:
            parent = self
        for k,v in adict.items():
            if isinstance(v, dict):
                vconf = PYConf(v)
                self.copy_from_dict(v, vconf)
                parent[k] = vconf
            else:
                parent[k] = v


class RegionalConfig(object):
    """ 为 Regional 机制提供的配置文件，用于解析 Regional 配置。
    """
    rlist = None
    rdict = None
    rids = None

    def __init__(self, rlist):
        self.rlist = rlist
        self.rdict = {}
        self.rids = []
        if not isinstance(self.rlist, list) or len(self.rlist) == 0:
            raise ValueError('REGIONAL is unavailable!')
        for regional in self.rlist:
            r = regional.get('r')
            if r is None:
                raise KeyError('REGIONALS 配置必须包含 r key!')
            self.rids.append(r)
            self.rdict[r] = regional

    def get_regional(self, r):
        """ 获取一个 regional 配置
        :param int r: r 值
        :rtype: dict
        """
        return self.rdict.get(r)

    def check_regional(self, r, ignore_zero=False):
        """ 检查 regional 是否有效
        :param ignore_zero: 值为真，则允许 r 值为 0。0 是一个特殊的 r 值，代表全局 r
        :return: 已经转换成整数的 regional 值
        """
        try:
            r = int(r)
        except:
            r = None
        if r is None:
            return None, None
        if ignore_zero:
            if r == 0:
                return 0, None
        regional = self.get_regional(r)
        if regional is None:
            return None, None
        return r, regional

    def get_platform_conf(self, r):
        """ 根据 regional 中的配置，获取平台的类型和配置
        在返回的数据中包含 pfvalue/pfkey
        若获取不到则返回 None
        """
        robj = self.get_regional(r)
        for key in PlATFORMS.keys():
            conf = robj.get(key)
            if conf is not None:
                pfconf = {}
                pfconf.update(conf)
                pfconf['pfkey'] = key
                pfconf['pfvalue'] = PlATFORMS[key]
                return pfconf
        return None


class GlobalConfig(object):
    """ 全局配置文件，对应 config.toml """

    cfg_data: dict = None
    """ 全局变量，用于保存 config.toml/config.json 中载入的配置。"""

    regional: RegionalConfig = None
    """ 如果 Pyape 框架启用了 Regional 机制，则保存 Regional 配置实例。"""

    encrypter: Encrypt = None
    """ 用于 Fernet 加解密对象。"""

    def __init__(self, work_dir: Path=None, cfg: Union[dict, str]='config.toml'):
        """ 初始化全局文件
        :param Path work_dir: 工作文件夹
        :param str|dict cfg: 相对于工作文件夹的配置文件地址，或者配置内容本身
        """
        self.__work_dir = work_dir
        if isinstance(cfg, dict):
            self.cfg_data = cfg
        else:
            self.cfg_data = self.read(cfg, throw_error=True)
        if self.cfg_data:
            self.init_regionals(data=self.cfg_data)

    def read(self, filename: str, work_dir: Path=None, throw_error: bool=False) -> Union[list, dict]:
        """ 读取一个配置文件，支持 .json 和 .toml 扩展名。

        :param filename: 文件名
        :param work_dir: str
        :param throw_error: boolean 若值为 True，则当文件不存在的时候抛出异常
        :returns: 解析后的 dict
        :rtype: dict
        """
        conf_file = self.getdir(filename, work_dir=work_dir)
        if conf_file.exists():
            if filename.endswith('.toml'):
                with conf_file.open(mode='rb') as f:
                    return tomllib.load(f)
            elif filename.endswith('.json'):
                return json.load(conf_file)
            elif throw_error:
                raise ValueError(f'{conf_file.as_posix()} is not supported!')
        if throw_error:
            raise FileNotFoundError(f'{conf_file.as_posix()} is not found!')
        return {}

    def write(self, filename: str, data_dict: Union[list, dict], work_dir: Path=None) -> None:
        """ 将一个 dict 写入成为配置文件，支持 .toml 和 .json 后缀。

        :param data_dict: 要写入的配置信息
        """
        conf_file = self.getdir(filename, work_dir=work_dir)
        if filename.endswith('.toml'):
            with conf_file.open(mode='wb') as f:
                tomli_w.dump(data_dict, f)
        elif filename.endswith('.json'):
            json.dump(data_dict, conf_file,  ensure_ascii=False, indent=2)
            
    def getdir(self, *args, work_dir: Path=None) -> Path:
        """ 基于当前项目的运行文件夹，返回一个 pathlib.Path 对象
        如果传递 basedir，就基于这个 basedir 创建路径
        
        :param args: 传递路径
        :param Path work_dir: 工作文件夹
        """
        if work_dir is not None:
            return Path(work_dir, *args)
        if self.__work_dir is None:
            raise ValueError('Please set work_dir first!')
        return Path(self.__work_dir, *args)

    def getcfg(self, *args, default_value: Any=None, data: Union[str, dict]='cfg_file') -> Any:
        """ 递归获取 conf 中的值。getcfg 不仅可用于读取 config.toml 的值，还可以通过传递 data 用于读取任何字典的值。

        :param args: 需要读取的参数，支持多级调用，若级不存在，不会报错。
        :param default_value: 找不到这个键就提供一个默认值。
        :param data: 提供一个 dict，否则使用 cfg_data。
        :return: 获取的配置值
        """
        if data == 'cfg_file':
            data = self.cfg_data
        if args and isinstance(data, dict):
            cur_data = data.get(args[0], default_value)
            return self.getcfg(*args[1:], default_value=default_value, data=cur_data)
        return data
    
    def setcfg(self, *args, value: Any, data: Union[str, dict]='cfg_file') -> None:
        """ 递归设置 conf 中的值。setcfg 不仅可用于设置 config.toml 的值，还可以通过传递 data 用于读取任何字典的值。

        :param args: 需要设置的参数，支持多级调用，若级不存在，会自动创建一个内缪的 dict。
        :param data: 提供一个 dict，否则使用 cfg_data。
        :param value: 需要设置的值。
        """
        if data == 'cfg_file':
            data = self.cfg_data
        if args and isinstance(data, dict):
            arg0 = args[0]
            if len(args) > 1:
                cur_data = data.get(arg0)
                if cur_data is None:
                    cur_data = {}
                    data[arg0] = cur_data
                self.setcfg(*args[1:], value=value, data=cur_data)
            else:
                data[arg0] = value

    def encode_token(self, expire: int=86400, ts: int=None, **values: dict) -> str:
        """ 使用 Fernet 算法加密一组值为 token 用于鉴权。

        :param expire: 过期时间，单位秒。 3600*24 = 86400。
        :param ts: 过期时间戳，单位秒。若不提供则使用 当前时间+expire。

        >>> encode_token(r=0, uid=1, nickname='超级管理员', usertype=50)
        'b929a9f08a7ba1a01578ec5a8ecd75b7a06431b18866f1132a56aca667c3b33c'
        """
        if ts is None:
            ts = int(time.time()) + expire
        if self.encrypter is None:
            self.encrypter = Encrypt(self.getcfg('FLASK', 'SECRET_KEY'))
        values['ts'] = ts
        return self.encrypter.encrypt(json.dumps(values))

    def decode_token(self, token: str) -> PYConf:
        """ 解密使用 encode_token 加密的字符串。

        :param token: 需要解密的 token 字符串。

        >>> decode_token('b929a9f08a7ba1a01578ec5a8ecd75b7a06431b18866f1132a56aca667c3b33c')
        {'r': 0, 'uid': 0, 'usertype': 50, 'status': 1, 'expires': False}
        """
        if self.encrypter is None:
            self.encrypter = Encrypt(self.getcfg('FLASK', 'SECRET_KEY'))
        tokenobj = json.loads(self.encrypter.decrypt(token))
        # 指示是否过期
        tokenobj['expires'] = tokenobj.get('ts') < int(time.time())
        return PYConf(tokenobj)

    def init_regionals(self, data: Union[str, dict]='cfg_file') -> None:
        rlist = self.getcfg('REGIONALS', data=data)
        if isinstance(rlist, list):
            self.regional = RegionalConfig(rlist)
