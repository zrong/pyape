from pathlib import Path
import toml
import pytest

from pyape.config import GlobalConfig


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
    config_dict = toml.loads(config_toml)
    return GlobalConfig(work_dir, config_dict)