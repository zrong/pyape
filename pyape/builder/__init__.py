###########################################
# 提供构建能力
# author: zrong
# created: 2022-02-06
###########################################

from pkg_resources import resource_filename
from pathlib import Path
import toml

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

MAIN_CONFIG_FILES = ['.env', 'uwsgi.ini', 'gunicorn.conf.py', 'config.toml']
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
    