###########################################
# 创建配置文件
# author: zrong
# created: 2022-02-06
###########################################

import os
import json
import jinja2
from pathlib import Path
from typing import Any, Optional

import tomli as tomllib
import tomli_w
from pyape.tpl import base_dir as pyape_tpl_dir


def merge_dict(x: dict, y: dict, z: dict=None) -> dict:
    """ 合并 x 和 y 两个 dict
    1. 用 y 的同 key 值覆盖 x 的值
    2. y 中的新键名（x 中同级不存在）增加到 x 中
    返回一个新的 dict，不修改 x 和 y
    :param x: x 被 y 覆盖
    :param y: y 覆盖 x
    :return: dict
    """
    if z is None:
        z = {}
    # 以 x 的键名为标准，用 y 中包含的 x 键名覆盖 x 中的值
    for xk, xv in x.items():
        yv = y.get(xk, None)
        newv = None
        if isinstance(xv, dict):
            newv = xv.copy()
            # 对于 dict 执行递归替换
            if isinstance(yv, dict):
                z[xk] = {}
                newv = merge_dict(newv, yv, z[xk])
            # 对于 list 直接进行浅复制
            elif isinstance(yv, list):
                newv = yv.copy()
            # 对于标量值（非 None）则直接替换
            elif yv is not None:
                newv = yv
        else:
            newv = xv.copy() if isinstance(xv, list) else xv
            if isinstance(yv, dict) or isinstance(yv, list):
                newv = yv.copy()
            elif yv is not None:
                newv = yv
        z[xk] = newv
    
    # 将 y 中有但 x 中没有的键加入 z
    for yk, yv in y.items():
        if x.get(yk, None) is None:
            z[yk] = yv
    return z


class ConfigWriter(object):
    def __init__(self, tpl_name: str, dst_file: Path, replace_obj: dict, tpl_dir: Optional[Path]) -> None:
        """ 初始化
        :param tplname: 模版名称，不含扩展名
        :param dstname: 目测名称
        """
        self.tpl_name = tpl_name
        self.tpl_filename = tpl_name + '.jinja2'
        self.dst_file = dst_file
        self.replace_obj = replace_obj
        self.tpl_dir = tpl_dir or pyape_tpl_dir

    def _write_by_jinja(self):
        """ 调用 jinja2 直接渲染
        """
        tplenv = jinja2.Environment(loader=jinja2.FileSystemLoader(self.tpl_dir))
        tpl = tplenv.get_template(self.tpl_filename)
        self.dst_file.write_text(tpl.render(self.replace_obj))
    
    def _write_key_value(self):
        """ 输出 key = value 形式的文件
        """
        txt = '\n'.join([f'{k} = {v}' for k, v in self.replace_obj.items()])
        self.dst_file.write_text(txt)

    def write_config_file(self, force: bool=True):
        """ 写入配置文件
        :param force: 若 force 为 False，则仅当文件不存在的时候才写入。
        """
        if not force and self.dst_file.exists():
            return
        if self.tpl_name.endswith('.json'):
            self.dst_file.write_text(json.dumps(self.replace_obj, ensure_ascii=False, indent=4))
        elif self.tpl_name.endswith('.toml'):
            self.dst_file.write_text(tomli_w.dumps(self.replace_obj))
        elif self.tpl_name == '.env':
            self._write_key_value()
        else:
            self._write_by_jinja()


class ConfigReplacer(object):
    env_name: str = None
    pyape_name: str = None
    pyape_conf: dict = None
    envs: dict = None
    work_dir: Path = None
    tpl_dir: Path = None
    deploy_dir: Path = None
    pye: str = None
    replace_environ: list[str] = None
    writer: ConfigWriter = None

    def __init__(self, env_name, pyape_conf, work_dir: Path, tpl_dir: Path=None):
        """ 初始化
        """
        self.env_name = env_name
        self.pyape_conf = pyape_conf
        self.envs = pyape_conf['ENV']
        self.work_dir = work_dir
        self.tpl_dir = tpl_dir or pyape_tpl_dir
        self.pye = pyape_conf['PYE']

        self.check_env_name()
        self._set_replace_keys()

    def check_env_name(self):
        if self.env_name is None:
            raise ValueError('Please provide a env.')
        keys = self.envs.keys()
        if not self.env_name in self.envs: 
            raise ValueError('env must be in follow values: \n\n{}'.format('\n'.join(keys)))
        
    def _set_replace_keys(self):
        """ name 和 deploy_dir 的值允许作为替换值使用，但这两个值中也可能包含替换值，因此需要先固化下来"""
        self.pyape_name = self.get_tpl_value('NAME', merge=False)
        # 获取被 env 合并后的值
        deploy_dir = self.get_tpl_value('DEPLOY_DIR', merge=False)
        # 如果包含 {NAME} 或者环境变量的替换值，需要替换
        deploy_dir = self.replace(deploy_dir)
        self.deploy_dir = Path(deploy_dir)
        if not self.deploy_dir.is_absolute():
            raise ValueError('DEPLOY_DIR must be a absolute path!')
        self.replace_environ = self.get_tpl_value('REPLACE_ENVIRON', merge=False)

    def get_tpl_value(self, tpl_name: str, merge: bool=True, wrap_key: str=None) -> Any:
        """ 获取配置模版中的值
        :param tpl_name: 配置模版的键名
        :param merge: 是否合并，对于已知的标量，应该选择不合并
        :param wrap_key: 是否做一个包装。如果提供，则会将提供的值作为 key 名，在最终值之上再包装一层
        """
        # print('='* 20)
        # print(f'get_tpl_value pyape_conf: {json.dumps(self.pyape_conf)}')
        # print(f'get_tpl_value env_name: {self.env_name}')
        base_obj = self.pyape_conf.get(tpl_name, None)
        update_obj = self.get_env_value(tpl_name)
        repl_obj = None
        # print(f'get_tpl_value tpl_name: {tpl_name}')
        # print(f'get_tpl_value base_obj: {base_obj}')
        # print(f'get_tpl_value update_obj: {update_obj}')
        if merge:
            repl_obj = merge_dict(base_obj or {}, update_obj or {})
        else:
            repl_obj = update_obj or base_obj
        # print(f'get_tpl_value repl_obj: {repl_obj}')
        return {wrap_key: repl_obj} if wrap_key else repl_obj

    def replace(self, value: str) -> str:
        """ 替换 value 中的占位符
        """
        # 环境变量替换用
        environ_keys = {}
        # 替换 {NAME} 和 {WORK_DIR}
        replace_obj = {
            'NAME': self.pyape_name,
            'WORK_DIR': self.work_dir.resolve().as_posix(),
        }
        # 增加 {DEPLOY_DIR} 的值进行替换
        if isinstance(self.deploy_dir, Path):
            replace_obj['DEPLOY_DIR'] = self.deploy_dir.as_posix()
        # 获取环境变量中的替换值
        if self.replace_environ is not None:
            for n in self.replace_environ:
                # PYAPE_LOCAL_NAME
                environ_key = f'{self.pyape_name.upper()}_{self.env_name.upper()}_{n}'
                environ_keys[n] = environ_key
                environ_value = os.environ.get(environ_key)
                if environ_value is not None:
                    replace_obj[n] = environ_value
        try:
            # print(f'replace format_map {value=} {replace_obj=}')
            templ: jinja2.Template = jinja2.Template(value)
            # new_value = value.format_map(replace_obj)
            new_value = templ.render(replace_obj)
            return new_value
        except KeyError as e:
            # 抛出对应的 environ key 的错误
            error_key = e.args[0]
            raise ValueError(f'''error_key: {error_key}
environ_keys: {environ_keys}
replace_obj: {replace_obj}.''')

    def get_env_value(self, key=None, default_value=None):
        value = self.envs.get(self.env_name)
        if value and key is not None:
            return value.get(key, default_value)
        return value
    
    def set_writer(self, tpl_name: str, force=True, target_postfix: str='', immediately: bool=True) -> tuple[Path, Path]:
        """ 写入配置文件"""
        replace_obj = self.get_tpl_value(tpl_name)
        # print(f'write_config_file {tpl_name} {replace_obj}')
        replace_str = tomli_w.dumps(replace_obj)
        # 将 obj 转换成 toml 字符串，进行一次替换，然后再转换回 obj
        # 采用这样的方法可以不必处理复杂的层级关系
        replace_obj = tomllib.loads(self.replace(replace_str))
        # 不加后缀的文件路径
        target = self.work_dir.joinpath(tpl_name)
        # 加入后缀的文件路径，大部分情况下雨 target 相同
        final_target = self.work_dir.joinpath(f'{tpl_name}{target_postfix}')
        self.writer = ConfigWriter(tpl_name, final_target, replace_obj, self.tpl_dir)
        if immediately:
            self.writer.write_config_file(force)
        return target, final_target
