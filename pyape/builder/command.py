#!/usr/bin/env python
###########################################
# 提供 pyape 初始化的命令行工具
###########################################

import shutil
from pathlib import Path

import click

from pyape.tpl import base_dir as pyape_tpl_dir
from pyape.builder import get_pyape_toml, get_pyape_toml_file, MAIN_CONFIG_FILES, SUPERVISOR_TPL_FILES, MAIN_PROJECT_FILES
from pyape.builder.conf import ConfigReplacer

from fabric.connection import Connection


def check_pyape_toml(cwd: str, ctx: click.Context) -> dict:
    cwd = Path(cwd)
    toml_file = get_pyape_toml_file(cwd)
    if not toml_file.exists():
        ctx.fail(f'Please call "pyape init" to generate file "{toml_file.as_posix()}"')
    succ, pyape_conf = get_pyape_toml(toml_file)
    if not succ:
        ctx.fail(pyape_conf)
    return cwd, pyape_conf


def write_config_file(env_name: str, pyape_conf: dict, tpl_name: str, work_dir: Path, tpl_dir: Path=None, target_postfix: str='') -> None:
    """ 写入配置文件
    :param target_postfix: 配置文件的后缀
    """
    replacer = ConfigReplacer(env_name, pyape_conf, work_dir=work_dir, tpl_dir=tpl_dir)
    replacer.set_writer(tpl_name, target_postfix)



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


#---------------------------- 远程部署相关

def _build_conn(env_name: str, pyape_conf: dict, cwd: Path) -> Connection:
    replacer = ConfigReplacer(env_name, pyape_conf, cwd)
    # 从 pyape.toml 配置中获取服务器地址
    fabric_conf = replacer.get_tpl_value('fabric', merge=False)
    return Connection(**fabric_conf)


@click.command(help='生成并上传配置文件到远程服务器。')
@click.option('--cwd', '-C', type=click.Path(file_okay=False, exists=True), default=Path.cwd(), help='工作文件夹。')
@click.option('--env', '-E', required=True, help='输入支持的环境名称。')
@click.option('--force', '-F', is_flag=True, help='是否强制覆盖已有的配置文件。')
@click.pass_context
def putconf(ctx, cwd, env, force):
    cwd, pyape_conf = check_pyape_toml(cwd, ctx)
    conn = _build_conn(env, pyape_conf, cwd)

    from pyape.builder.fabric import GunicornDeploy as Deploy
    d = Deploy(env, pyape_conf, conn, cwd)
    d.put_config(force=force)


@click.command(help='部署远程服务器的虚拟环境。')
@click.option('--cwd', '-C', type=click.Path(file_okay=False, exists=True), default=Path.cwd(), help='工作文件夹。')
@click.option('--env', '-E', required=True, help='输入支持的环境名称。')
@click.option('--init', '-I', is_flag=True, help='是否初始化虚拟环境。')
@click.argument('upgrade', nargs=-1)
@click.pass_context
def venv(ctx, cwd, env, init: bool, upgrade: tuple):
    cwd, pyape_conf = check_pyape_toml(cwd, ctx)
    conn = _build_conn(env, pyape_conf, cwd)

    from pyape.builder.fabric import GunicornDeploy as Deploy
    d = Deploy(env, pyape_conf, conn, cwd)
    if init:
        d.init_remote_venv()
    if len(upgrade) > 0:
        d.pipupgrade(names=upgrade)
    else:
        d.pipupgrade(all=True)


@click.command(help='部署项目到远程服务器。')
@click.option('--cwd', '-C', type=click.Path(file_okay=False, exists=True), default=Path.cwd(), help='工作文件夹。')
@click.option('--env', '-E', required=True, help='输入支持的环境名称。')
@click.pass_context
def deploy(ctx, cwd, env):
    cwd, pyape_conf = check_pyape_toml(cwd, ctx)
    conn = _build_conn(env, pyape_conf, cwd)

    from pyape.builder.fabric import GunicornDeploy as Deploy
    d = Deploy(env, pyape_conf, conn, cwd)
    d.rsync(exclude=pyape_conf['rsync_exclude'])
    d.put_config(force=True)


@click.command(help='在服务器上启动项目进程。')
@click.option('--cwd', '-C', type=click.Path(file_okay=False, exists=True), default=Path.cwd(), help='工作文件夹。')
@click.option('--env', '-E', required=True, help='输入支持的环境名称。')
@click.pass_context
def start(ctx, cwd, env):
    cwd, pyape_conf = check_pyape_toml(cwd, ctx)
    conn = _build_conn(env, pyape_conf, cwd)

    from pyape.builder.fabric import GunicornDeploy as Deploy
    d = Deploy(env, pyape_conf, conn, cwd)
    d.start()


@click.command(help='在服务器上停止项目进程。')
@click.option('--cwd', '-C', type=click.Path(file_okay=False, exists=True), default=Path.cwd(), help='工作文件夹。')
@click.option('--env', '-E', required=True, help='输入支持的环境名称。')
@click.pass_context
def stop(ctx, cwd, env):
    cwd, pyape_conf = check_pyape_toml(cwd, ctx)
    conn = _build_conn(env, pyape_conf, cwd)

    from pyape.builder.fabric import GunicornDeploy as Deploy
    d = Deploy(env, pyape_conf, conn, cwd)
    d.stop()


@click.command(help='在服务器上重载项目进程。')
@click.option('--cwd', '-C', type=click.Path(file_okay=False, exists=True), default=Path.cwd(), help='工作文件夹。')
@click.option('--env', '-E', required=True, help='输入支持的环境名称。')
@click.pass_context
def reload(ctx, cwd, env):
    cwd, pyape_conf = check_pyape_toml(cwd, ctx)
    conn = _build_conn(env, pyape_conf, cwd)

    from pyape.builder.fabric import GunicornDeploy as Deploy
    d = Deploy(env, pyape_conf, conn, cwd)
    d.reload()


@click.command(help='打印所有的过期的 python package。')
@click.option('--cwd', '-C', type=click.Path(file_okay=False, exists=True), default=Path.cwd(), help='工作文件夹。')
@click.option('--env', '-E', required=True, help='输入支持的环境名称。')
@click.pass_context
def pipoutdated(ctx, cwd, env):
    cwd, pyape_conf = check_pyape_toml(cwd, ctx)
    conn = _build_conn(env, pyape_conf, cwd)

    from pyape.builder.fabric import GunicornDeploy as Deploy
    d = Deploy(env, pyape_conf, conn, cwd)
    d.pipoutdated()


main.add_command(copy)
main.add_command(init)
main.add_command(top)
main.add_command(supervisor)
main.add_command(config)
main.add_command(deploy)
main.add_command(putconf)
main.add_command(start)
main.add_command(stop)
main.add_command(reload)
main.add_command(pipoutdated)


if __name__ == '__main__':
    main()