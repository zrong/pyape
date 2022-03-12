from sqlalchemy import inspect, Integer, Column, select, insert
from sqlalchemy.orm import Session
from pyape.config import GlobalConfig
from pyape.db import DBManager, SQLAlchemy


def test_build_db(global_config: GlobalConfig):
    URI = global_config.getcfg('SQLALCHEMY', 'URI')
    sql = SQLAlchemy(URI=URI)
    
    class A(sql.Model('s2')):
        __tablename__ = 'a'
        id = Column(Integer, primary_key=True)
        
    sql.create_all()
    a1 = A(id=10)
    s = sql.session()
    s.add(a1)
    s.commit()
    
    print(s.get(A, 3).id)
    print(s.scalars(select(A).order_by(A.id.desc())).first().id)
