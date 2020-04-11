from pathlib import Path

import pytest
import flask

import mjp
import mjp.app
import mjp.config

from . import TestConf


class TestConfig(mjp.app.FlaskConfig):
    DEBUG = False
    TESTING = True


def create_mjpapp(mjpapp, db):
    from mjp.app.queryfun import VO2Cache
    mjpapp.vo2cache = VO2Cache()


@pytest.fixture(scope='session')
def mjpapp():
    appdir = Path(__file__).parent.parent.resolve()
    mjp.init(appdir, initr=False)
    appmodules = mjp.config.getcfg('PATH', 'modules')
    app = mjp.app.create_app(ConfigClass=TestConfig)

    with app.app_context():
        mjp.app.init_app(app, 'app', appmodules, create_mjpapp, before_first_request=False)
    yield app


@pytest.fixture(scope='session')
def client(mjpapp):
    return mjpapp.test_client()


@pytest.fixture(scope='session')
def conf():
    return TestConf()
