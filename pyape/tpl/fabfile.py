# -*- coding: utf-8 -*-
"""
部署 pyape 项目
~~~~~~~~~~~~~~~~~~~

默认使用 uWSGI 部署。

查看所有可用的环境(env)，请调用：

fab envs

对于一个全新的未部署的项目，请调用：

fab new -env [env] 

然后需要登录服务器进入 flask shell 初始化数据库

fab start --env [env] 

日常更新功能：

fab deploy --env [role] 
fab reload --env [role] 

更新配置文件 config.json+uwsgi.ini+.env：

fab putjson --env [role] 
fab putini --env [role] 
fab putenv --env [role] 
"""

from pathlib import Path

from invoke import task
from invoke.exceptions import Exit

from pyape.cli.fabric import logger, UwsgiDeploy as Deploy

from fabconfig import rsync_exclude, uwsgi_ini, config_json, _env, enviroments


basedir = Path(__file__).parent


@task
def envs(c):
    """ 查看支持哪些环境
    """
    logger.info('可用的环境(env): \n\n%s\n', '\n'.join(enviroments.keys()))


@task
def putjson(c, env, local=False):
    """ 生成 config.json 并上传
    """
    d = Deploy(env, enviroments, c, basedir)
    d.put_tpl('config_json', config_json, dstname='config.json', force=True, local=local)


@task
def putini(c, env, local=False):
    """ 生成 uwsgi.ini 并上传
    """
    d = Deploy(env, enviroments, c, basedir)
    d.put_tpl('uwsgi_ini', uwsgi_ini, dstname='uwsgi.ini', force=True, local=local)


@task
def putenv(c, env, local=False):
    """ 生成 .env 或上传
    """
    d = Deploy(env, enviroments, c, basedir)
    d.put_tpl('_env', _env, dstname='.env', wrapkey='options', force=True, local=local)


@task
def putcfiles(c, env, local=False):
    """ 根据tpl文件生成配置文件并上传
    """
    d = Deploy(env, enviroments, c, basedir)
    d.put_tpl('uwsgi_ini', uwsgi_ini, dstname='uwsgi.ini', force=True, local=local)
    d.put_tpl('config_json', config_json, dstname='config.json', force=True, local=local)
    d.put_tpl('_env', _env, dstname='.env', wrapkey='options', force=True, local=local)

@task
def venv(c, env):
    """ 创建虚拟环境
    """
    d = Deploy(env, enviroments, c, basedir)
    d.init_remote_venv()


@task
def deploy(c, env):
    """ 部署最新程序到远程服务器
    """
    d = Deploy(env, enviroments, c, basedir)
    d.rsync(exclude=rsync_exclude)
    d.put_tpl('uwsgi_ini', uwsgi_ini, dstname='uwsgi.ini', force=True)
    d.put_tpl('config_json', config_json, dstname='config.json', force=True)
    d.put_tpl('_env', _env, dstname='.env', wrapkey='options', force=True)


@task
def dar(c, env, venv=None):
    """ 部署并重载
    """
    d = Deploy(env, enviroments, c, basedir)
    if venv:
        d.init_remote_venv()
    d.deploy()
    d.reload()


@task
def new(c, env):
    """ 在服务器上创建一个全新的 API 环境
    """
    d = Deploy(env, enviroments, c, basedir)
    d.deploy()
    d.venv()
