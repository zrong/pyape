###########################################
# 提供构建能力
# author: zrong
# created: 2022-02-06
###########################################

from pathlib import Path
import tomllib
from enum import StrEnum


class MainProjectFile(StrEnum):
    wsgi = 'wsgi.py'
    readme = 'README.md'
    pyape = 'pyape.toml'
    gitignore = '.gitignore'


class MainConfigFile(StrEnum):
    config = 'config.toml'
    env = '.env'
    uwsgi = 'uwsgi.ini'
    gunicorn = 'gunicorn.conf.py'
    gunicorn_nginx = 'gunicorn_nginx.conf'


class SupervisorTplFile(StrEnum):
    PROGRAM = 'supervisor_program.conf'
    SERVICE = 'supervisord.service'
    CONF = 'supervisord.conf'


def get_pyape_toml_file(cwd: Path=None) -> Path:
    cwd = cwd or Path.cwd()
    return cwd.joinpath('pyape.toml')


def get_pyape_toml(pyape_toml: Path) -> tuple[bool, dict]:
    """ 获取主配置文件 pyape.toml 并进行简单的检测
    """
    err = None
    try:
        pyape_conf = tomllib.loads(pyape_toml.read_text())
        pyape_conf['RSYNC_EXCLUDE']
        pyape_conf['NAME']
        pyape_conf['PYE']
        pyape_conf['DEPLOY_DIR']
        pyape_conf['REPLACE_ENVIRON']
        return True, pyape_conf
    except FileNotFoundError:
        err = 'Please call "pyape init" to generate a "pyape.toml" file.'
    except tomllib.TOMLDecodeError as e:
        err = f'Decode {pyape_toml.resolve().as_posix()} error: {e}'
    except KeyError as e:
        err = f'Key error: {e.args[0]}'
    return False, err
    