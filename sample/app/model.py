"""
app.model

"""
import time

from sqlalchemy import Column, INT, VARCHAR

from pyape.app import gdb

Model = gdb.Model()


class User(Model):
    __tablename__ = 'user'

    id = Column(INT, autoincrement=True, primary_key=True)
    name = Column(VARCHAR(100), nullable=False)
    createtime = Column(INT, nullable=False, default=lambda: int(time.time()))