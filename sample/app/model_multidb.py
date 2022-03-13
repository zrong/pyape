"""
app.model_multidb

"""
import time

from sqlalchemy import Column, INT, VARCHAR

from pyape.app import gdb

Model1 = gdb.Model('db1')
Model2 = gdb.Model('db2')


class User1(Model1):
    __tablename__ = 'user1'

    id = Column(INT, autoincrement=True, primary_key=True)
    name = Column(VARCHAR(100), nullable=False)
    createtime = Column(INT, nullable=False, default=lambda: int(time.time()))


class User2(Model2):
    __tablename__ = 'user2'

    id = Column(INT, autoincrement=True, primary_key=True)
    name = Column(VARCHAR(100), nullable=False)
    createtime = Column(INT, nullable=False, default=lambda: int(time.time()))