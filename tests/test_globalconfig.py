from pyape.config import GlobalConfig

def test_setcfg():
    d = dict()
    gconf = GlobalConfig(cfg_file=None)
    gconf.setcfg('a', 'b', value='c', data=d)
    assert gconf.getcfg('a', 'b', data=d) == 'c'
    gconf.setcfg('a', 'b', value=1, data=d)
    assert gconf.getcfg('a', 'b', data=d) == 1
