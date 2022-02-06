#!/usr/bin/env python
###########################################
# 提供 pyape 初始化的命令行工具
###########################################

import os
import json
import shutil
from pathlib import Path
from typing import Any, Optional

from pkg_resources import resource_filename
import toml
import jinja2
import click

from pyape.tpl import base_dir as pyape_tpl_dir


# pyape 安装所在的文件夹
# module_dir = Path(resource_filename('pyape', '__init__.py')).parent
# 找到 tpl 文件夹所在地
# tpl_dir = module_dir.joinpath('tpl')

MAIN_PROJECT_FILES = {
    'fabfile': 'fabfile.py',
    'wsgi': 'wsgi.py',
    'readme': 'README.md',
    'pyape': 'pyape.toml',
    'gitignore': '.gitignore',
}

MAIN_CONFIG_FILES = ['.env', 'uwsgi.ini', 'gunicorn.conf.py', 'PYAPE']
SUPERVISOR_TPL_FILES = ['supervisor_program.conf', 'supervisord.service', 'supervisord.conf']
REPLACE_ENVIRON = ['ADMIN_NAME', 'ADMIN_PASSWORD', 'SECRET_KEY', 'SQLALCHEMY_DATABASE_URI']


def get_pyape_toml_file(cwd: Path=None) -> Path:
    cwd = cwd or Path.cwd()
    return cwd.joinpath('pyape.toml')


def get_pyape_toml(pyape_toml: Path) -> tuple[bool, dict]:
    """ 获取主配置文件 pyape.toml 并进行简单的检测
    """
    err = None
    try:
        pyape_conf = toml.load(pyape_toml)
        pyape_conf['rsync_exclude']
        pyape_conf['name']
        pyape_conf['pye']
        pyape_conf['deploy_dir']
        return True, pyape_conf
    except FileNotFoundError:
        err = 'Please call "pyape init" to generate a "pyape.toml" file.'
    except toml.TomlDecodeError as e:
        err = f'Decode {pyape_toml.resolve()} error: {e}'
    except KeyError as e:
        err = f'Key error: {e.args[0]}'
    return False, err
    

def check_pyape_toml(cwd: str, ctx: click.Context) -> dict:
    cwd = Path(cwd)
    toml_file = get_pyape_toml_file(cwd)
    if not toml_file.exists():
        ctx.fail(f'Please call "pyape init" to generate file "{toml_file.as_posix()}"')
    succ, pyape_conf = get_pyape_toml(toml_file)
    if not succ:
        ctx.fail(pyape_conf)
    return cwd, pyape_conf


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

    def write_config_file(self):
        if self.tpl_name.endswith('.json'):
            self.dst_file.write_text(json.dumps(self.replace_obj, ensure_ascii=False, indent=4))
        elif self.tpl_name.endswith('.toml'):
            self.dst_file.write_text(toml.dumps(self.replace_obj))
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

    def __init__(self, env_name, pyape_conf, work_dir: Path, tpl_dir: Path=None):
        """ 初始化
        """
        self.env_name = env_name
        self.pyape_conf = pyape_conf
        self.envs = pyape_conf['ENV']
        self.work_dir = work_dir
        self.tpl_dir = tpl_dir or pyape_tpl_dir
        self.pye = pyape_conf['pye']

        self.check_env_name()
        self._set_name_and_deploy_dir()

    def check_env_name(self):
        if self.env_name is None:
            raise ValueError('Please provide a env.')
        keys = self.envs.keys()
        if not self.env_name in self.envs: 
            raise ValueError('env must be in follow values: \n\n{}'.format('\n'.join(keys)))
        
    def _set_name_and_deploy_dir(self):
        """ name 和 deploy_dir 的值允许作为替换值使用，但这两个值中也可能包含替换值，因此需要先固化下来"""
        self.pyape_name = self.get_tpl_value('name', merge=False)
        # 获取被 env 合并后的值
        deploy_dir = self.get_tpl_value('deploy_dir', merge=False)
        # 如果包含 {NAME} 或者环境变量的替换值，需要替换
        deploy_dir = self.replace(deploy_dir)
        self.deploy_dir = Path(deploy_dir)

    def get_tpl_value(self, tpl_name: str, merge: bool=True, wrap_key: str=None) -> Any:
        """ 获取配置模版中的值
        :param tpl_name: 配置模版的键名
        :param merge: 是否合并，对于已知的标量，应该选择不合并
        :param wrap_key: 是否做一个包装。如果提供，则会将提供的值作为 key 名，在最终值之上再包装一层
        """
        print('='* 20)
        print(f'get_tpl_value pyape_conf: {json.dumps(self.pyape_conf)}')
        print(f'get_tpl_value env_name: {self.env_name}')
        base_obj = self.pyape_conf.get(tpl_name, None)
        update_obj = self.get_env_value(tpl_name)
        repl_obj = None
        print(f'get_tpl_value tpl_name: {tpl_name}')
        print(f'get_tpl_value base_obj: {base_obj}')
        print(f'get_tpl_value update_obj: {update_obj}')
        if merge:
            repl_obj = merge_dict(base_obj or {}, update_obj or {})
        else:
            repl_obj = update_obj or base_obj
        print(f'get_tpl_value repl_obj: {repl_obj}')
        return {wrap_key: repl_obj} if wrap_key else repl_obj

    def replace(self, value: str) -> str:
        """ 替换 value 中的占位符
        """
        # 替换 {NAME} 和 {WORK_DIR}
        replace_obj = {
            'NAME': self.pyape_name,
            'WORK_DIR': self.work_dir.as_posix(),
        }
        # 增加 {DEPLOY_DIR} 的值进行替换
        if isinstance(self.deploy_dir, Path):
            replace_obj['DEPLOY_DIR'] = self.deploy_dir.as_posix()
        # 获取环境变量中的替换值
        environ_keys = {}
        for n in REPLACE_ENVIRON:
            # PYAPE_LOCAL_NAME
            environ_key = f'{self.pyape_name.upper()}_{self.env_name.upper()}_{n}'
            environ_keys[n] = environ_key
            environ_value = os.environ.get(environ_key)
            if environ_value is not None:
                replace_obj[n] = environ_value
        try:
            new_value = value.format_map(replace_obj)
            return new_value
        except KeyError as e:
            # 抛出对应的 environ key 的错误
            raise KeyError(environ_keys.get(e.args[0]))
            

    def get_env_value(self, key=None, default_value=None):
        value = self.envs.get(self.env_name)
        if value and key is not None:
            return value.get(key, default_value)
        return value


def write_config_file(env_name: str, pyape_conf: dict, tpl_name: str, work_dir: Path, tpl_dir: Path=None, target_postfix: str='') -> None:
    """ 写入配置文件
    :param target_postfix: 配置文件的后缀
    """
    replacer = ConfigReplacer(env_name, pyape_conf, work_dir=work_dir, tpl_dir=tpl_dir)
    replace_obj = replacer.get_tpl_value(tpl_name)
    print(f'write_config_file {tpl_name} {replace_obj}')
    replace_str = toml.dumps(replace_obj)
    # 将 obj 转换成 toml 字符串，进行一次替换，然后再转换回 obj
    # 采用这样的方法可以不必处理复杂的层级关系
    replace_obj = toml.loads(replacer.replace(replace_str))
    # 如果 tpl_name 是 pyape，代表要生成 config.toml
    if tpl_name.lower() == 'pyape':
        tpl_name = 'config.toml'
    writer = ConfigWriter(tpl_name, work_dir.joinpath(f'{tpl_name}{target_postfix}'), replace_obj, tpl_dir)
    writer.write_config_file()


def copytplfile(srcdir, dstdir, keyname, filename, force=False, rename=False):
    """ 复制文件到目标文件夹
    :param srcdir: 源文件夹
    :param dstdir: 目标文件夹
    :param keyname: 文件 key 名称，files 的 key
    :param filename: 文件名称，files 的 value
    :param force: 是否强制覆盖已存在文件
    :param rename: 若文件已存在是否重命名
    """
    split_path = keyname.split('/')
    dstfiledir = dstdir
    srcfiledir = srcdir
    while len(split_path) > 1:
        # 检测是否拥有中间文件夹，若有就创建它
        dstfiledir = dstfiledir.joinpath(split_path[0])
        srcfiledir = srcfiledir.joinpath(split_path[0])
        if not dstfiledir.exists():
            dstfiledir.mkdir()
        split_path = split_path[1:]

    srcfile = srcfiledir / filename
    dstfile = dstfiledir / filename

    if dstfile.exists():
        if force:
            shutil.copyfile(srcfile, dstfile)
            click.echo('复制 {0} 到 {1}'.format(srcfile, dstfile))
        elif rename:
            dstbak = dstfile.parent.joinpath(dstfile.name + '.bak')
            if dstbak.exists():
                st = click.style('备份文件 {0} 已存在！请先删除备份文件。'.format(dstbak), fg='red')
                click.echo(st, err=True)
            else:
                shutil.move(dstfile, dstbak)
                st = click.style('备份文件 {0} 到 {1}'.format(dstfile, dstbak), fg='yellow')
                click.echo(st)
                shutil.copyfile(srcfile, dstfile)
                click.echo('复制 {0} 到 {1}'.format(srcfile, dstfile))
        else:
            st = click.style('文件 {0} 已存在！'.format(dstfile), fg='red')
            click.echo(st, err=True)
    else:
        shutil.copyfile(srcfile, dstfile)
        click.echo('复制 {0} 到 {1}'.format(srcfile, dstfile))


@click.group(help='初始化 pyape 项目')
def main():
    pass


@click.command(help='复制 pyape 配置文件到当前项目中')
@click.option('--all', '-A', default=False, is_flag=True, help='复制所有模版')
@click.option('--cwd', '-C', type=click.Path(file_okay=False, exists=True), default=Path.cwd(), help='工作文件夹，也就是复制目标文件夹。')
@click.option('--force', '-F', default=False, is_flag=True, help='覆盖已存在的文件')
@click.option('--rename', '-R', default=False, is_flag=True, help='若目标文件存在则重命名')
@click.argument('name', nargs=-1)
def copy(all, name, cwd, force, rename):
    cwd = Path(cwd)
    if all:
        for key, tplfile in MAIN_PROJECT_FILES.items():
            copytplfile(pyape_tpl_dir, cwd, key, tplfile, force, rename)
    else:
        for key in name:
            if not key in MAIN_PROJECT_FILES.keys():
                st = click.style('仅支持以下名称： {0}'.format(' '.join(MAIN_PROJECT_FILES.keys())), fg='red')
                click.echo(st, err=True)
                continue
            copytplfile(pyape_tpl_dir, cwd, key, MAIN_PROJECT_FILES[key], force, rename)


@click.command(help='初始化 pyape 项目')
@click.option('--cwd', '-C', type=click.Path(file_okay=False, exists=True), default=Path.cwd(), help='工作文件夹。')
@click.option('--force', '-F', default=False, is_flag=True, help='覆盖已存在的文件')
def init(cwd, force):
    for keyname, filename in MAIN_PROJECT_FILES.items():
        copytplfile(pyape_tpl_dir, Path(cwd), keyname, filename, force, False)


@click.command(help='展示 uwsgi 的运行情况。')
@click.option('--frequency', '-F', default=1, type=int, help='Refresh frequency in seconds')
@click.argument('address', nargs=1)
def top(address, frequency):
    import pyape.uwsgitop
    pyape.uwsgitop.call(address, frequency)


@click.command(help='生成配置文件。')
@click.option('--cwd', '-C', type=click.Path(file_okay=False, exists=True), default=Path.cwd(), help='工作文件夹。')
@click.option('--env', '-E', required=True, help='输入支持的环境名称。')
@click.option('--env_postfix', '-P', is_flag=True, help='在生成的配置文件名称末尾加上环境名称后缀。')
@click.argument('files', nargs=-1, type=click.Choice(MAIN_CONFIG_FILES))
@click.pass_context
def config(ctx: click.Context, env: str, cwd: str, env_postfix: bool, files: tuple):
    cwd, pyape_conf = check_pyape_toml(cwd, ctx)
    # 若没有提供参数就生成所有的配置文件
    config_files = files if len(files) > 0 else MAIN_CONFIG_FILES
    for tpl_name in config_files:
        write_config_file(env, pyape_conf, tpl_name, work_dir=cwd, target_postfix=f'.{env}' if env_postfix else '')
        


@click.command(help='生成 Supervisor 需要的配置文件。')
@click.option('--cwd', '-C', type=click.Path(file_okay=False, exists=True), default=Path.cwd(), help='工作文件夹。')
@click.option('--env', '-E', required=True, help='输入支持的环境名称。')
@click.pass_context
def supervisor(ctx, cwd, env):
    cwd, pyape_conf = check_pyape_toml(cwd, ctx)
    for tpl_name in SUPERVISOR_TPL_FILES:
        write_config_file(env, pyape_conf, tpl_name, work_dir=cwd)


main.add_command(copy)
main.add_command(init)
main.add_command(top)
main.add_command(supervisor)
main.add_command(config)


if __name__ == '__main__':
    main()