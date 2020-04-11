# -*- coding: utf-8 -*-
import pytest
import time

from mjp import config
from mjp.logging import get_logger


@pytest.fixture()
def clear_logfile():
    for file in [config.getdir('logs', 'app.log'), config.getdir('logs', 'test.log')]:
        if file.exists():
            file.unlink()
    yield


@pytest.mark.skip
@pytest.mark.parametrize('fmt', [ ('text',), ('json',), ('raw',) ])
def test_logger_file(client, clear_logfile, conf, fmt):
    """ 测试 file logger 写入
    """
    from mjp.app import logger
    log = get_logger('test', config.getdir(), fmt=fmt)
    log.info('a dict: %s', {'name': 'test.log'})
    logger.info('a dict: %s', {'name': 'app.log'})
    assert True
    

# @pytest.mark.skip
@pytest.mark.parametrize('fmt', [ ('text',), ('json',), ('raw',) ])
def test_logger_zmq(client, conf, fmt):
    """ 测试 ZeroMQ logger 写入
    """
    log = get_logger('zmq', 'tcp://127.0.0.1:5011', type_='zmq', fmt=fmt)
    log.info('a %s dict: %s', fmt, {'name': 'zmq.log'})
    assert True
    