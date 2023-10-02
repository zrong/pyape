#!/usr/bin/env python
"""
pyape 命令行工具
"""

import shutil
from dataclasses import dataclass
from typing import Annotated, TYPE_CHECKING
from pathlib import Path

import click
import typer
from rich.console import Console

from invoke.exceptions import Exit

from pyape.tpl import base_dir as pyape_tpl_dir
from pyape.builder import (
    get_pyape_toml,
    get_pyape_toml_file,
    MainConfigFile,
    SupervisorTplFile,
    MainProjectFile,
)
from pyape.error import ErrorCode, ConfigError
from pyape.builder.conf import ConfigReplacer

from fabric.connection import Connection

if TYPE_CHECKING:
    from pyape.builder.fabric.deploy import Deploy


@dataclass
class GlobalState:
    cwd: Path = None
    env: str = None
    force: bool = False
    pyape_conf: dict = None


global_state = GlobalState()
console: Console = Console()


def check_pyape_toml(ctx: typer.Context) -> dict:
    toml_file = get_pyape_toml_file(global_state.cwd)
    if not toml_file.exists():
        ctx.fail(f'Please call "pyape init" to generate file "{toml_file.as_posix()}"')
    succ, pyape_conf = get_pyape_toml(toml_file)
    if not succ:
        ctx.fail(pyape_conf)
    global_state.pyape_conf = pyape_conf
    return pyape_conf


def write_config_file(
    ctx: typer.Context,
    pyape_conf: dict,
    tpl_name: str,
    /,
    tpl_dir: Path = None,
    target_postfix: str = '',
    force: bool = True,
) -> None:
    """写入配置文件

    :param target_postfix: 配置文件的后缀
    """
    try:
        replacer = ConfigReplacer(
            global_state.env, pyape_conf, work_dir=global_state.cwd, tpl_dir=tpl_dir
        )
        replacer.set_writer(tpl_name, force, target_postfix)
        if not force and replacer.writer.exists_before_write:
            st = click.style(
                f'文件 {replacer.writer.dst_file.as_uri()} 已存在。可使用 --force 参数强制覆盖。',
                fg='red',
            )
            click.echo(st)
    except ConfigError as e:
        if e.code == ErrorCode.ENV_NAME:
            ctx.fail(f'{e.message} 使用 pyape --env 指定一个存在的名称！')
        ctx.fail(e.message)
    except Exception as e:
        ctx.fail(str(e))


def copytplfile(srcdir, dstdir, keyname, filename, force=False, rename=False):
    """复制文件到目标文件夹

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
            console.print(f'复制 [red]{srcfile}[/] 到 [red]{dstfile}[/]')
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


def build_deploy_conn(ctx: typer.Context) -> 'Deploy':
    """创建一个远程部署连接。"""
    try:
        pyape_conf = check_pyape_toml(ctx)
        replacer = ConfigReplacer(global_state.env, pyape_conf, global_state.cwd)
        # 从 pyape.toml 配置中获取服务器地址
        fabric_conf = replacer.get_tpl_value('FABRIC', merge=False)

        from pyape.builder.fabric.deploy import GunicornDeploy

        d = GunicornDeploy(
            global_state.env,
            global_state.pyape_conf,
            Connection(**fabric_conf),
            global_state.cwd,
        )
        return d
    except ConfigError as e:
        if e.code == ErrorCode.ENV_NAME:
            ctx.fail(f'{e.message} 使用 pyape --env 指定一个存在的名称！')
        ctx.fail(e.message)
    except Exception as e:
        ctx.fail(str(e))


# ---------------------------- 创建命令行对象
main: typer.Typer = typer.Typer()

sub_gen: typer.Typer = typer.Typer(name='gen', help='「本地」生成器，生成常用字符串。')
sub_conf: typer.Typer = typer.Typer(name='conf', help='「本地/远程」处理配置文件。')
sub_uwsgi: typer.Typer = typer.Typer(name='uwsgi', help='「远程」处理远程服务器上的 uWSGI 相关功能。')
sub_venv: typer.Typer = typer.Typer(name='venv', help='「远程」处理远程服务器上的 Python 虚拟环境。')
sub_server: typer.Typer = typer.Typer(name='server', help='「远程」操作远程服务器进程。')

main.add_typer(sub_gen)
main.add_typer(sub_conf)
main.add_typer(sub_uwsgi)
main.add_typer(sub_venv)
main.add_typer(sub_server)


# ---------------------------- 根命令
@main.callback()
def main_callback(
    env: Annotated[str, typer.Option(help='支持的环境名称。')] = None,
    cwd: Annotated[
        Path, typer.Option(file_okay=False, exists=True, help='本地工作文件夹。')
    ] = Path.cwd(),
):
    global_state.cwd = cwd
    global_state.env = env
    console.print(f'main_callback {global_state=}')


@main.command('init')
def main_init():
    """「本地」初始化 pyape 项目。"""
    for keyname, filename in MainProjectFile.__members__.items():
        copytplfile(
            pyape_tpl_dir,
            global_state.cwd,
            keyname,
            filename.value,
            global_state.force,
            False,
        )


@main.command('setup')
def main_setup(ctx: typer.Context):
    """「本地」创建 pyape 项目运行时必须的环境，例如数据库建立等。需要自行在项目根文件夹创建 setup.py。"""
    cwd = global_state.cwd
    for filename in MainProjectFile.__members__.values():
        if not cwd.joinpath(filename.value).exists():
            ctx.fail('Please call "pyape init" to generate project files.')
    setup_py = cwd.joinpath('setup.py')
    if not cwd.joinpath(setup_py).exists():
        ctx.fail('Please create a file named "setup.py" in project root directory.')
    import sys

    sys.path.insert(0, cwd.as_posix())
    from importlib.util import spec_from_file_location, module_from_spec

    spec = spec_from_file_location('pyape.setup', setup_py)
    mod = module_from_spec(spec)
    spec.loader.exec_module(mod)


# ---------------------------- 子命令 venv
@sub_venv.command('update')
def venv_update(
    ctx: typer.Context,
    name: Annotated[list[str], typer.Argument(help='指定希望更新的 pip 包名称。')] = None,
    init: Annotated[bool, typer.Option(help='是否初始化虚拟环境。')] = False,
    requirements: Annotated[
        str, typer.Option(help='指定 requirements.txt 的相对路径。')
    ] = 'requirements.txt',
):
    """「远程」部署远程服务器的虚拟环境。"""
    d = build_deploy_conn(ctx)
    if init:
        d.init_remote_venv(req_path=requirements)
    if len(name) > 0:
        d.pipupgrade(names=name)
    else:
        d.pipupgrade(all=True)


@sub_venv.command('outdated')
def venv_outdated(ctx: typer.Context):
    """「远程」打印所有的过期的 python package。"""
    d = build_deploy_conn(ctx)
    d.pipoutdated()



# ---------------------------- 子命令 uwsgi
@sub_uwsgi.command('top')
def uwsgi_top(
    address: Annotated[str, typer.Argument(help='uWSGI address.')],
    frequency: Annotated[int, typer.Option(help='Refresh frequency in seconds.')] = 1,
):
    """「远程」展示 uwsgi 的运行情况。"""
    import pyape.uwsgitop

    pyape.uwsgitop.call(address, frequency)



# ---------------------------- 子命令 conf

@sub_conf.callback()
def conf_main_callback(
    force: Annotated[bool, typer.Option(help='覆盖已存在的文件。')] = False,
):
    global_state.force = force


@sub_conf.command('make')
def conf_make(
    ctx: typer.Context,
    file: Annotated[
        list[MainConfigFile], typer.Argument(help='提供支持的配置文件名称。', show_default=False)
    ],
    env_postfix: Annotated[bool, typer.Option(help='在生成的配置文件名称末尾加上环境名称后缀。')] = False,
):
    """「本地」生成配置文件。"""
    pyape_conf = check_pyape_toml(ctx)
    # 若没有提供参数就生成所有的配置文件
    config_files = file if len(file) > 0 else MainConfigFile.__members__.values()
    for tpl_name in config_files:
        write_config_file(
            ctx,
            pyape_conf,
            tpl_name.value,
            target_postfix=f'.{global_state.env}' if env_postfix else '',
            force=global_state.force,
        )


@sub_conf.command('copy')
def conf_copy(
    name: Annotated[list[str], typer.Argument(help='待处理的配置文件名称。')] = None,
    rename: Annotated[bool, typer.Option(help='若目标文件存在则重命名')] = False,
):
    """「本地」复制 pyape 配置文件到当前项目中"""
    if len(name) == 0:
        for key, tplfile in MainConfigFile.__members__.items():
            copytplfile(
                pyape_tpl_dir,
                global_state.cwd,
                key,
                tplfile.value,
                global_state.force,
                rename,
            )
    else:
        for key in name:
            if not key in MainConfigFile.__members__.keys():
                st = click.style(
                    '仅支持以下名称： {0}'.format(' '.join(MainConfigFile.__members__.keys())),
                    fg='red',
                )
                click.echo(st, err=True)
                continue
            copytplfile(
                pyape_tpl_dir,
                global_state.cwd,
                key,
                MainConfigFile[key],
                global_state.force,
                rename,
            )


@sub_conf.command('supervisor')
def conf_supervisor(
    ctx: typer.Context,
):
    """「本地」生成 Supervisor 需要的配置文件。"""
    pyape_conf = check_pyape_toml(ctx)
    for tpl_name in SupervisorTplFile.__members__.values():
        write_config_file(ctx, pyape_conf, tpl_name.value, force=global_state.force)


@sub_conf.command('put')
def conf_put(
    ctx: typer.Context,
):
    """「远程」生成并上传配置文件到远程服务器。"""
    d = build_deploy_conn(ctx)
    d.put_config(force=global_state.force)



# ---------------------------- 子命令 gen

@sub_gen.command('password')
def gen_password(
    password: Annotated[str, typer.Argument(help='提供密码。', show_default=False)],
    salt: Annotated[
        str,
        typer.Argument(help='提供密码盐值。', show_default=False),
    ],
):
    """返回加盐之后的 PASSWORD。"""
    from pyape.util import gen

    console.print(gen.gen_password(password, salt))


@sub_gen.command('secret')
def gen_secret():
    """生成一个 Flask 可用的 SECRET_KEY。"""
    from pyape.util import gen

    console.print(gen.gen_secret_key())


@sub_gen.command('nonce')
def gen_once(length: Annotated[int, typer.Argument(help='字符串位数。')] = 8):
    """根据提供的位数，返回 nonce 字符串。"""
    from pyape.util import gen

    console.print(gen.gen_nonce(k=length))



# ---------------------------- 子命令 server

@sub_server.command('deploy')
def server_deploy(ctx: typer.Context):
    """「远程」部署项目到远程服务器。"""
    d = build_deploy_conn(ctx)
    d.rsync(exclude=global_state.pyape_conf['RSYNC_EXCLUDE'])
    d.put_config(force=True)


@sub_server.command(help='start')
def server_start(ctx: typer.Context):
    """「远程」在服务器上启动项目进程。"""
    try:
        d = build_deploy_conn(ctx)
        d.start()
    except Exit as e:
        ctx.fail(e.message)


@sub_server.command('stop')
def server_stop(ctx: typer.Context):
    """「远程」在服务器上停止项目进程。"""
    d = build_deploy_conn(ctx)
    d.stop()


@sub_server.command('reload')
def server_reload(ctx: typer.Context):
    """「远程」在服务器上重载项目进程。"""
    d = build_deploy_conn(ctx)
    d.reload()


@sub_server.command('dar')
def server_dar(ctx: typer.Context):
    """「远程」在服务器上部署代码，然后执行重载。也就是 deploy and reload 的组合。"""
    try:
        d = build_deploy_conn(ctx)
        d.rsync(exclude=global_state.pyape_conf['RSYNC_EXCLUDE'])
        d.put_config(force=True)
        d.reload()
    except Exception as e:
        ctx.fail(str(e))


if __name__ == '__main__':
    main()
