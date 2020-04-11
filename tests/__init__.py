import attr

@attr.s
class TestConf(object):
    r = attr.ib(default=1000)
    sagiuid = attr.ib(default=100001)
