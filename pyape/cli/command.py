# -*- coding: utf-8 -*-
#!/usr/bin/env python
###########################################
# 提供 pyape 初始化的命令行工具
###########################################

import shutil
from pathlib import Path
from pkg_resources import resource_filename

import click


basedir = Path(resource_filename('pyape', '__init__.py')).parent
# 找到 tpl 文件夹所在地
tpldir = basedir.joinpath('tpl')
fabconfig = Path('fabconfig')
files = {
    'dotenv': '_env.jinja2',
    'uwsgi': 'uwsgi_ini.jinja2',
    'fabfile': 'fabfile.py',
    'fabconfig/init': '__init__.py',
    'fabconfig/local': 'env_local.py',
    'fabconfig/prod': 'env_prod.py',
    'fabconfig/test': 'env_test.py',
    'wsgi': 'wsgi.py',
    'run': 'run.sh',
    'readme': 'README.md',
}


@click.group(help='初始化 pyape 项目')
def main():
    pass


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
        for tplfile in files.values():
            copytplfile(tplfile, dst, force, rename)
    else:
        for key in name:
            if not key in files.keys():
                st = click.style('仅支持以下名称： {0}'.format(' '.join(files.keys())), fg='red')
                click.echo(st, err=True)
                continue
            copytplfile(tpldir, dst, key, files[key], force, rename)


@click.command(help='初始化 pyape 项目')
@click.option('--force', '-F', default=False, is_flag=True, help='覆盖已存在的文件')
def init(force):
    dst = Path.cwd()
    for keyname, filename in files.items():
        copytplfile(tpldir, dst, keyname, filename, force, False)


@click.command(help='展示 uwsgi 的运行情况。')
@click.option('--frequency', '-F', default=1, type=int, help='Refresh frequency in seconds')
@click.argument('address', nargs=1)
def top(address, frequency):
    import pyape.uwsgitop
    pyape.uwsgitop.call(address, frequency)


main.add_command(copy)
main.add_command(init)
main.add_command(top)


if __name__ == '__main__':
    main()