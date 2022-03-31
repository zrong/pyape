import sys
from pathlib import Path

import tomli as tomllib
import pytest

from pyape.config import GlobalConfig
from pyape.flask_extend import PyapeFlask

# 加入 sample 的路径以便测试
sample_path: Path = Path(__file__).parent.parent.joinpath('sample').resolve()
sys.path.insert(0, sample_path.as_posix())

config_toml: str = """
[FLASK]
SECRET_KEY = 'CWbqhvnx5_g49n0Keq0zlSvC5PARJEsGOLlGUkd-1sc='
[SQLALCHEMY.URI]
s1 = 'sqlite:///{WORK_DIR}/s1.sqlite'
s2 = 'sqlite:///{WORK_DIR}/s2.sqlite'
"""


@pytest.fixture(scope='session')
def global_config():
    global config_toml
    work_dir = Path(__file__).parent
    config_toml = config_toml.format(WORK_DIR=work_dir.as_posix())
    config_dict = tomllib.loads(config_toml)
    return GlobalConfig(work_dir, config_dict)


@pytest.fixture(scope='session')
def sample_local_app():
    from wsgi import sample_app, gconfig
    sample_app.config.update({
        "TESTING": True,
    })
    sample_app._gdb.create_all()

    yield sample_app

    # 删除测试过程中创建的数据库
    URI = gconfig.getcfg('SQLALCHEMY', 'URI')
    f: Path = gconfig.getdir(URI[10:])
    f.unlink()


@pytest.fixture(scope='session')
def sample_local_client(sample_local_app: PyapeFlask):
    return sample_local_app.test_client()


@pytest.fixture(scope='session')
def sample_multidb_app():
    from wsgi import sample_app, gconfig
    sample_app.config.update({
        "TESTING": True,
    })
    sample_app._gdb.create_all()

    yield sample_app

    # 删除测试过程中创建的数据库
    URI: dict = gconfig.getcfg('SQLALCHEMY', 'URI')
    for s in URI.values():
        f: Path = gconfig.getdir(s[10:])
        f.unlink()


@pytest.fixture(scope='session')
def sample_multidb_client(sample_multidb_app: PyapeFlask):
    return sample_multidb_app.test_client()
