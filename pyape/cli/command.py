#!/usr/bin/env python
###########################################
# 提供 pyape 初始化的命令行工具
###########################################

from dataclasses import replace
import os
import json
import shutil
from pathlib import Path
from typing import Any, Optional

from pkg_resources import resource_filename
import toml
import jinja2
import click

from pyape.tpl import create_from_jinja, base_dir as pyape_tpl_dir


# pyape 安装所在的文件夹
# module_dir = Path(resource_filename('pyape', '__init__.py')).parent
# 找到 tpl 文件夹所在地
# tpl_dir = module_dir.joinpath('tpl')

files = {
    'dotenv': '_env.jinja2',
    'uwsgi': 'uwsgi_ini.jinja2',
    'gunicorn': 'gunicorn_conf_py.jinja2',
    'gunicorn_nginx': 'gunicorn_nginx.conf.jinja2',
    'fabfile': 'fabfile.py',
    'wsgi': 'wsgi.py',
    'readme': 'README.md',
}


REPLACE_ENVIRON = ['ADMIN_NAME', 'ADMIN_PASSWORD', 'SECRET_KEY', 'SQLALCHEMY_DATABASE_URI']


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

    def create_from_jinja(self):
        """ 调用 jinja2 直接渲染
        """
        tplenv = jinja2.Environment(loader=jinja2.FileSystemLoader(self.tpl_dir))
        tpl = tplenv.get_template(self.tpl_filename)
        self.dst_file.write_text(tpl.render(self.replace_obj))

    def write_config_file(self):
        if self.tpl_name.endswith('.json'):
            self.dst_file.write_text(json.dumps(self.replace_obj, ensure_ascii=False, indent=4))
        elif self.tpl_name.endswith('.toml'):
            self.dst_file.write_text(toml.dumps(self.replace_obj))
        else:
            self.create_from_jinja()


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
        base_obj = self.pyape_conf.get(tpl_name, None)
        update_obj = self.get_env_value(tpl_name)
        repl_obj = None
        if merge:
            repl_obj = merge_dict(base_obj or {}, update_obj or {})
        else:
            repl_obj = update_obj or base_obj
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
        for n in REPLACE_ENVIRON:
            # PYAPE_LOCAL_NAME
            environ_key = f'{self.pyape_name.upper()}_{self.env_name.upper()}_{n}'
            environ_value = os.environ.get(environ_key)
            if environ_value is not None:
                replace_obj[n] = environ_value
        new_value = value.format_map(replace_obj)
        return new_value

    def get_env_value(self, key=None, default_value=None):
        value = self.envs.get(self.env_name)
        if value and key is not None:
            return value.get(key, default_value)
        return value


def write_config_file(env_name: str, pyape_conf: dict, tpl_name: str, work_dir: Path, tpl_dir: Path=None) -> None:
    replacer = ConfigReplacer(env_name, pyape_conf, work_dir=work_dir, tpl_dir=tpl_dir)
    replace_obj = replacer.get_tpl_value(tpl_name)
    replace_str = toml.dumps(replace_obj)
    # 将 obj 转换成 toml 字符串，进行一次替换，然后再转换回 obj
    # 采用这样的方法可以不必处理复杂的层级关系
    replace_obj = toml.loads(replacer.replace(replace_str))
    # 如果 tpl_name 是 pyape，代表要生成 config.toml
    if tpl_name.lower() == 'pyape':
        tpl_name = 'config.toml'
    writer = ConfigWriter(tpl_name, work_dir.joinpath(tpl_name), replace_obj, tpl_dir)
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



@click.command(help='test')
def test():
    pass


@click.command(help='复制 pyape 配置文件到当前项目中')
@click.option('--all', '-A', default=False, is_flag=True, help='复制所有模版')
@click.option('--dst', '-D', help='指定复制目标文件夹')
@click.option('--force', '-F', default=False, is_flag=True, help='覆盖已存在的文件')
@click.option('--rename', '-R', default=False, is_flag=True, help='若目标文件存在则重命名')
@click.argument('name', nargs=-1)
def copy(all, name, dst, force, rename):
    if dst is None:
        dst = Path.cwd()
    else:
        dst = Path(dst)
    if all:
        for key, tplfile in files.items():
            copytplfile(pyape_tpl_dir, dst, key, tplfile, force, rename)
    else:
        for key in name:
            if not key in files.keys():
                st = click.style('仅支持以下名称： {0}'.format(' '.join(files.keys())), fg='red')
                click.echo(st, err=True)
                continue
            copytplfile(pyape_tpl_dir, dst, key, files[key], force, rename)


@click.command(help='初始化 pyape 项目')
@click.option('--force', '-F', default=False, is_flag=True, help='覆盖已存在的文件')
def init(force):
    dst = Path.cwd()
    for keyname, filename in files.items():
        copytplfile(pyape_tpl_dir, dst, keyname, filename, force, False)


@click.command(help='展示 uwsgi 的运行情况。')
@click.option('--frequency', '-F', default=1, type=int, help='Refresh frequency in seconds')
@click.argument('address', nargs=1)
def top(address, frequency):
    import pyape.uwsgitop
    pyape.uwsgitop.call(address, frequency)


GEN_SUPE_HELP = '在当前文件夹下生成 supervisord.conf 配置文件'

@click.command(help=GEN_SUPE_HELP)
@click.option('-p', '--path', required=False, type=click.Path(), help='提供一个路径，配置中和路径相关的内容都放在这个路径下')
@click.option('--unix-http-server-file', required=False, type=str)
@click.option('--supervisord-logfile', required=False, type=str)
@click.option('--supervisord-pidfile', required=False, type=str)
@click.option('--supervisord-user', required=False, type=str)
@click.option('--supervisord-directory', required=False, type=str)
@click.option('--supervisorctl-serverurl', required=False, type=str)
@click.option('--include-files', required=False, type=str)
def gensupe(**kwargs):
    try:
        replaceobj = {}
        path = kwargs.get('path')
        if path is not None:
            path = Path(path)
            replaceobj['unix_http_server_file'] = str(path.joinpath('run', 'supervisord.sock').resolve())
            replaceobj['supervisorctl_serverurl'] = 'unix://%s' % str(path.joinpath('run', 'supervisord.sock').resolve())
            replaceobj['include_files'] = str(path.joinpath('conf.d').resolve()) + '/*.conf'
            replaceobj['supervisord_logfile'] = str(path.joinpath('log', 'supervisord.log').resolve())
            replaceobj['supervisord_pidfile'] = str(path.joinpath('run', 'supervisord.pid').resolve())
            replaceobj['supervisord_directory'] = str(path.resolve())
            
        for k, v in kwargs.items():
            if v is not None:
                replaceobj[k] = v
        name = 'supervisord'
        cwdpath = Path().cwd()
        create_from_jinja(name, cwdpath, replaceobj)
    except Exception as e:
        click.echo(click.style('生成错误：%s' % e, fg='red'), err=True)
        raise click.Abort()


GEN_SYS_HELP = '在当前文件夹下生成 systemd 需要的 supervisord.service 配置文件'

@click.command(help=GEN_SYS_HELP)
@click.option('--supervisord-exec', required=False, type=str)
@click.option('--supervisorctl-exec', required=False, type=str)
@click.option('--supervisord-conf', required=False, type=str)
def gensys(**kwargs):
    try:
        replaceobj = {}
        for k, v in kwargs.items():
            if v is not None:
                replaceobj[k] = v
        name = 'systemd'
        cwdpath = Path().cwd()
        create_from_jinja(name, cwdpath, replaceobj)
    except Exception as e:
        click.echo(click.style('生成错误：%s' % e, fg='red'), err=True)
        raise click.Abort()


GEN_PROGRAM_CONF_HELP = '生成 supervisord 的 program 配置文件'

@click.command(help=GEN_PROGRAM_CONF_HELP)
@click.option('-n', '--name', required=True, type=str, help='Supervisor program 名称')
@click.option('-u', '--user', required=False, type=str, help='Supervisor program 的 user')
@click.option('-c', '--app-module', default='wsgi:pyape_app', type=str, help='Supervisor 启动的 flask 进程之 app_module')
def genprog(name, app_module, user):
    try:
        cwdpath = Path().cwd()
        replaceobj = {
            'cwd': cwdpath.resolve(),
            'name': name,
            'app_module': app_module,
        }
        if user is not None:
            replaceobj['user'] = user
        create_from_jinja('program', cwdpath.joinpath(name + '.conf'), replaceobj)
    except Exception as e:
        click.echo(click.style('生成错误 %s' % e, fg='red'), err=True)
        raise click.Abort()


main.add_command(copy)
main.add_command(init)
main.add_command(top)
main.add_command(gensupe)
main.add_command(gensys)
main.add_command(genprog)


if __name__ == '__main__':
    main()