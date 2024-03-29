"""
pyape.builder.fabric.deploy
~~~~~~~~~~~~~~~~~~~

同步 fabric 进行远程部署。
"""

import re
import json
from datetime import datetime

from pathlib import Path
from invoke import runners
from invoke.exceptions import Exit
from fabric import Connection

from pyape.builder import MAIN_CONFIG_FILES
from pyape.builder.conf import  ConfigReplacer

from . import logger, rsync


class Deploy(object):
    env_name: str = None
    pyape_conf: dict = None
    envs: dict = None
    work_dir: Path = None
    conn: Connection = None
    pye: str = None
    replacer: ConfigReplacer = None

    def __init__(self, env_name, pyape_conf, conn, work_dir: Path=None):
        """ 初始化
        """
        self.env_name = env_name
        self.pyape_conf = pyape_conf
        self.envs = pyape_conf['ENV']
        self.conn = conn
        self.work_dir = Path(work_dir)
        self.pye = pyape_conf['PYE']
        self.replacer = ConfigReplacer(env_name, pyape_conf, self.work_dir)

        try:
            self.replacer.check_env_name()
        except Exception as e:
            raise Exit(e)

    def check_remote_conn(self):
        """ 确保当前提供的 conn 是远程版本
        """
        if not isinstance(self.conn, Connection):
            raise Exit('Use -H to provide a host!')

    def get_remote_path(self, *args) -> str:
        return self.replacer.deploy_dir.joinpath(*args).as_posix()

    def remote_exists(self, file):
        """ 是否存在远程文件 file
        """
        self.check_remote_conn()
        # files.exists 仅接受字符串
        if isinstance(file, Path):
            file = file.resolve().as_posix()
        command = f'test -e "$(echo {file})"'
        logger.info(f'{command=}')
        return self.conn.run(command, hide=True, warn=True).ok

    def make_remote_dir(self, *args):
        """ 创建部署文件夹
        """
        self.check_remote_conn()
        remotedir = self.get_remote_path(*args)
        if not self.remote_exists(remotedir):
            command = 'mkdir %s' % remotedir
            logger.info('创建远程文件夹 %s', command)
            self.conn.run(command)

    def cat_remote_file(self, *args):
        """ 使用 cat 命令获取远程文件的内容
        """
        f = self.get_remote_path(*args)
        logger.info('cat_remote_file %s', f)
        if not self.remote_exists(f):
            return None
        result = self.conn.run('cat ' + f, warn=False, hide=True)
        return result.stdout

    def get_remote_pid(self, host=None, port=None):
        """ 利用命令行查找某个端口运行进程的 pid
        :param host: IP 地址
        :param port: 端口号
        """
        self.check_remote_conn()
        address = None
        if host:
            address = host
        if port:
            p = ':' + str(port)
            if address:
                address += '@' + p
            else:
                address = p
        if not address:
            raise Exit('需要 host 或 port 配置。')
        # command = 'lsof -i :2004 | tail -1'
        command_fmt = 'lsof -i {} | tail -1'
        command = command_fmt.format(address)
        result = self.conn.run(command, warn=False, hide=True)
        if result.stdout == '':
            return None
        return re.split(r'\s+', result.stdout)[1]

    def init_remote_dir(self, deploy_dir):
        """ 创建远程服务器的运行环境
        """
        deploy_dir_path = Path(deploy_dir)
        for d in [ self.replacer.deploy_dir,
            deploy_dir,
            deploy_dir_path.joinpath('logs'),
            deploy_dir_path.joinpath('output') ]:
            self.make_remote_dir(d)

    def source_venv(self):
        remote_venv_dir = self.get_remote_path('venv')
        if not self.remote_exists(remote_venv_dir):
            raise Exit('venv 还没有创建！请先执行 init_remote_venv')
        return 'source {}/bin/activate'.format(remote_venv_dir)

    def init_remote_venv(self, req_path: str='requirements.txt'):
        """ 创建虚拟环境
        """
        remote_venv_dir = self.get_remote_path('venv')
        if not self.remote_exists(remote_venv_dir):
            self.conn.run(f'{self.pye} -m venv {remote_venv_dir}')
        with self.conn.prefix(f'source {remote_venv_dir}/bin/activate'):
            self.conn.run('pip install -U pip')
            self.conn.run(f'pip install -r {self.get_remote_path(req_path)}')

    def piplist(self, format='columns'):
        """ 获取虚拟环境中的所有安装的 python 模块
        :@param format: columns (default), freeze, or json
        """
        with self.conn.prefix(self.source_venv()):
            result = self.conn.run('pip list --format ' + format)
            return result.stdout

    def pipoutdated(self, format='columns'):
        """ 查看过期的 python 模块
        :@param format: columns (default), freeze, or json
        """
        with self.conn.prefix(self.source_venv()):
            result = self.conn.run('pip list --outdated --format ' + format)
            return result.stdout

    def pipupgrade(self, names=None, all=False):
        """ 更新一个 python 模块
        """
        with self.conn.prefix(self.source_venv()):
            mod_names = []
            if all:
                result = self.conn.run('pip list --outdated --format json')
                if result.ok:
                    mod_names = [item['name'] for item in json.loads(result.stdout)]
            elif names:
                mod_names = [name for name in names]
            if mod_names:
                self.conn.run('pip install -U ' + ' '.join(mod_names))

    def put_tpl(self, tpl_name, force=False):
        """ 基于 jinja2 模板生成配置文件，根据 env 的值决定是否上传
        """
        # 创建远程文件夹
        self.make_remote_dir()
        # 获取远程文件的绝对路径
        target_remote = self.get_remote_path(tpl_name)
        tpltarget_remote_exists = self.remote_exists(target_remote)
        if force and tpltarget_remote_exists:
            logger.warning('delete %s', target_remote)
            remoter = self.conn.run(f'rm -f {target_remote}')
            if remoter.ok:
                logger.warning(f'删除远程配置文件 {target_remote}')
            tpltarget_remote_exists = False
        
        # 本地创建临时文件后上传
        if force or not tpltarget_remote_exists:
            # 创建一个临时文件用于上传，使用后缀
            _, final_file = self.replacer.set_writer(tpl_name, force=force, target_postfix=f'.{self.env_name}')
            self.conn.put(final_file, target_remote)
            logger.warning('覆盖远程配置文件 %s', target_remote)
            localrunner = runners.Local(self.conn)
            # 删除本地的临时配置文件
            localr = localrunner.run(f'rm -f {final_file.as_posix()}')
            if localr.ok:
                logger.warning(f'删除本地临时文件 {final_file.as_posix()}')
            
    def put_config(self, force: bool=False) -> None:
        for tpl_name in MAIN_CONFIG_FILES:
            self.put_tpl(tpl_name, force)

    def rsync(self, exclude=[], is_windows=False):
        """ 部署最新程序到远程服务器
        """
        if is_windows:
            # 因为 windows 下面的 rsync 不支持 windows 风格的绝对路径，转换成相对路径
            pdir = str(self.work_dir.relative_to('.').resolve())
        else:
            pdir = str(self.work_dir.resolve())
        if not pdir.endswith('/'):
            pdir += '/'
        deploy_dir = self.get_remote_path()
        self.init_remote_dir(deploy_dir)
        rsync(self.conn, pdir, deploy_dir, exclude=exclude)
        logger.warn('RSYNC [%s] to [%s]', pdir, deploy_dir)

    def get_logs(self, extras=[]):
        """ 下载远程 logs 到本地
        """
        log_files = ['app.log', 'error.log', 'access.log']
        time_string = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
        for f in log_files + extras:
            logf = self.get_remote_path('logs/{}'.format(f))
            if not self.remote_exists(logf):
                logger.warning('找不到远程 log 文件 %s', logf)
                continue
            logp = Path(logf)
            local_file = self.work_dir.joinpath('logs', '{name}_{basename}_{times}{extname}'.format(name=self.env_name, times=time_string, basename=logp.name, extname=logp.suffix))
            self.conn.get(logf, local=local_file)


class UwsgiDeploy(Deploy):
    """ 使用 uWSGI 来部署服务
    """
    def __init__(self, env_name, pyape_conf, conn, work_dir: Path=None):
        super().__init__(env_name, pyape_conf, conn, work_dir)

    def get_fifo_file(self):
        """ 使用 master-fifo 来管理进程
        http://uwsgi-docs-zh.readthedocs.io/zh_CN/latest/MasterFIFO.html
        """
        fifofile = self.get_remote_path('uwsgi.fifo')
        if self.remote_exists(fifofile):
            return fifofile
        return None

    def get_pid_file(self):
        """ 使用 pidfile 来判断进程是否启动
        """
        pidfile = self.get_remote_path('uwsgi.pid')
        if self.remote_exists(pidfile):
            return pidfile
        return None

    def get_uwsgi_exe(self):
        """ 获取 venv 中 uwsgi 的可执行文件绝对路径
        """
        uwsgi_exe = self.get_remote_path('venv/bin/uwsgi')
        if not self.remote_exists(uwsgi_exe):
            raise Exit('没有找到 uwsgi 可执行文件！请先执行 init_remote_venv')
        return uwsgi_exe

    def start(self):
        """ 启动服务进程
        """
        pidfile = self.get_pid_file()
        if pidfile is not None:
            raise Exit('进程不能重复启动！')
        self.conn.run(self.get_uwsgi_exe() + ' ' + self.get_remote_path('uwsgi.ini'))

    def stop(self):
        """ 停止 API 进程
        """
        fifofile = self.get_fifo_file()
        if fifofile is not None:
            self.conn.run('echo q > %s' % fifofile)
        pidfile = self.get_pid_file()
        # 删除 pidfile 以便下次启动
        if pidfile is not None:
            self.conn.run('rm %s' % pidfile)

    def reload(self):
        """ 优雅重载 API 进程
        """
        fifofile = self.get_fifo_file()
        if fifofile is None:
            raise Exit('进程还没有启动！')
        self.conn.run('echo r > %s' % fifofile)


class GunicornDeploy(Deploy):
    """ 使用 Gunicorn 来部署服务
    """
    def __init__(self, env_name, pyape_conf, conn, work_dir: Path=None):
        super().__init__(env_name, pyape_conf, conn, work_dir)

    def get_pid_file(self):
        """ 使用 pidfile 来判断进程是否启动
        """
        pidfile = self.get_remote_path('gunicorn.pid')
        if self.remote_exists(pidfile):
            return pidfile
        return None

    def get_pid_value(self, *args):
        """ 获取远程 pid 文件中的 pid 值
        """
        pid_value = self.cat_remote_file('gunicorn.pid')
        if pid_value is None:
            raise Exit('gunicorn.pid 没有值！')
        return pid_value.strip()

    def get_gunicorn_exe(self):
        """ 获取 venv 中 uwsgi 的可执行文件绝对路径
        """
        gunicorn_exe = self.get_remote_path('venv/bin/gunicorn')
        if not self.remote_exists(gunicorn_exe):
            raise Exit('没有找到 gunicorn 可执行文件！请先执行 init_remote_venv')
        return gunicorn_exe

    def start(self, wsgi_app=None, daemon=None):
        """ 启动服务进程
        :@param wsgi_app: 传递 wsgi_app 名称
        :@param daemon: 若值为 True，则强制加上 -D 参数
        """
        pidfile = self.get_pid_file()
        if pidfile is not None:
            raise Exit('进程不能重复启动！')
        conf = self.get_remote_path('gunicorn.conf.py')
        cmd = self.get_gunicorn_exe() + ' --config ' + conf
        if daemon == True:
            cmd += ' -D'
        if wsgi_app is not None:
            cmd += ' ' + wsgi_app
        self.conn.run(cmd)

    def stop(self):
        """ 停止 API 进程
        """
        pidvalue = self.get_pid_value()
        killr = self.conn.run('kill -s TERM ' + pidvalue)
        if killr.ok:
            logger.warning('优雅关闭 %s', pidvalue)
            # 删除 pidfile 以便下次启动
            self.conn.run('rm %s' % self.get_pid_file())
        else:
            logger.warning('关闭 %s 失败', pidvalue)

    def reload(self):
        """ 优雅重载 API 进程
        """
        pidvalue = self.get_pid_value()
        killr = self.conn.run('kill -s HUP ' + pidvalue)
        if killr.ok:
            logger.warning('优雅重载 %s', pidvalue)
        else:
            logger.warning('重载 %s 失败', pidvalue)


class SupervisorGunicornDeploy(Deploy):
    """ 使用 Supervisor + Gunicorn(非 daemon 模式) 来部署服务
    """
    def __init__(self, env_name, pyape_conf, conn, work_dir: Path=None):
        super().__init__(env_name, pyape_conf, conn, work_dir)

    def get_pid_file(self):
        """ 使用 pidfile 来判断进程是否启动
        """
        pidfile = self.get_remote_path('gunicorn.pid')
        if self.remote_exists(pidfile):
            return pidfile
        return None

    def start(self):
        """ 启动服务进程
        """
        pidfile = self.get_pid_file()
        if pidfile is not None:
            raise Exit('进程不能重复启动！')
        pass
        # self.conn.run('uwsgi ' + self.get_remote_path('uwsgi.ini'))

    def stop(self):
        """ 停止 API 进程
        """
        pidfile = self.get_pid_file()
        # 删除 pidfile 以便下次启动
        if pidfile is not None:
            self.conn.run('rm %s' % pidfile)

    def reload(self):
        """ 优雅重载 API 进程
        """
        pass