"""
pyape.config
~~~~~~~~~~~~~~~~~~~

解析 config.json 配置文件
提供配置文件相关的读取和写入方法
"""

from pathlib import Path
import json
from typing import Any, Union
import toml


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
    # 全局变量，用于保存 config.json 载入的配置
    cfg_data = None
    regional = None

    def __init__(self, work_dir=None, cfg_file='config.toml'):
        self.__work_dir = work_dir
        if cfg_file:
            self.cfg_data = self.read(cfg_file, throw_error=True)
        # self.cfg_json 可能是个 {}
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
                return toml.load(conf_file)
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
            toml.dump(data_dict, conf_file)
        elif filename.endswith('.json'):
            json.dump(data_dict, conf_file,  ensure_ascii=False, indent=2)
            
    def getdir(self, *args, work_dir: Path=None) -> Path:
        """ 基于当前项目的运行文件夹，返回一个 pathlib.Path 对象
        如果传递 basedir，就基于这个 basedir 创建路径
        """
        if work_dir is not None:
            return Path(work_dir, *args)
        if self.__work_dir is None:
            raise ValueError('please set work_dir first!')
        return Path(self.__work_dir, *args)

    def getcfg(self, *args, default_value: Any=None, data: Union[str, dict]='cfg_file') -> Any:
        """
        递归获取 dict 中的值
        如果不提供 data，默认使用 cfg 中的值
        注意，getcfg 不仅可用于读取 config.yaml 的值，还可以通过传递 data 用于读取任何字典的值
        :param args:
        :param data:
        :return:
        """
        if data is None:
            return None
        elif data == 'cfg_file':
            data = self.cfg_data
        if args:
            if isinstance(data, dict):
                return self.getcfg(*args[1:], data=data.get(args[0], default_value), default_value=default_value)
            return data
        return data

    def init_regionals(self, data: Union[str, dict]='cfg_file') -> None:
        rlist = self.getcfg('REGIONALS', data=data)
        if isinstance(rlist, list):
            self.regional = RegionalConfig(rlist)
