#======================
# 处理 pyape 数据库功能
# 
# 1. 解决 SQLAlchemy 线程问题
# 2. 提供多数据库绑定支持
#
# @author zrong
# @created 2022-02-07
#======================

from typing import Iterable, Union
from sqlalchemy.schema import Table, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker, Session, scoped_session, Query
from sqlalchemy.engine import Engine, create_engine


class DBManager(object):
    default_uri: str = None
    URI: Union[dict, str] = None
    # 保存 engines 对象
    __engines: dict = None
    # 保存 Session 生成器
    __session_factories: dict = None
    # 保存所有的 Model class
    __model_classes: dict = None

    def __init__(self, URI: Union[dict, str], **kwargs: dict) -> None:
        """ 管理 SQL 连接，可单独使用，也可以结合 SQLAlchemy 使用"""
        self.__engines = {}
        self.__session_factories = {}
        self.__model_classes = {}
        self.URI = URI
        self.__set_default_uri()
        self.__build_dbs()

    @property
    def Models(self) -> Iterable:
        return self.__model_classes.values()
        
    @property
    def bind_keys(self) -> Iterable:
        return self.__model_classes.keys()
        
    def __build_dbs(self) -> None:
        view = None
        if isinstance(self.URI, str):
            view = {None: self.URI}.items()
        else:
            view = self.URI.items()
        # 下面的三个引擎只需要创建一遍，在初始化的时间创建
        for name, uri in view:
            engine = create_engine(uri)
            # 保存 engine
            self.__engines[name] = engine
            # 保存 session factory
            self.__session_factories[name] = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            # 保存 Model class
            self.__model_classes[name] = declarative_base(name=name or 'Model')
        
    def __set_default_uri(self) -> None:
        if isinstance(self.URI, dict):
            self.default_uri = self.URI.keys()[0]

    def get_Model(self, bind_key: str=None):
        return self.__model_classes.get(bind_key or self.default_uri)

    def set_Model(self, bind_key: str=None):
        """ 设置并保存一个 Model
        一般在多个数据库共享同一个 Model 的时候使用
        此时使用默认创建的 Model 可能会造成混淆，最好是创建一个新的"""
        if self.__model_classes.get(bind_key):
            raise KeyError(bind_key)
        self.__model_classes[bind_key] = declarative_base(name=bind_key or 'Model')
        return self.__model_classes.get(bind_key or self.default_uri)
        
    def get_engine(self, bind_key: str=None) -> Engine:
        return self.__engines.get(bind_key or self.default_uri)
    
    def create_sessions(self, is_scoped: bool=False) -> dict[Session]:
        """ 根据 URI 的定义创建所有需要的 session 实例"""
        sessions: dict[Session] = {}
        for bind_key, SF in self.__session_factories.items():
            if is_scoped:
                sessions[bind_key] = self.create_scoped_session(bind_key)
            else:
                sessions[bind_key] = self.create_session(bind_key)
        return sessions
    
    def create_session(self, bind_key: str=None) -> Session:
        """ 创建一个 session 实例"""
        SF = self.__session_factories.get(bind_key or self.default_uri)
        return SF()

    def create_scoped_session(self, bind_key: str=None) -> Session:
        """ 创建一个 scoped session 实例"""
        SF = self.__session_factories.get(bind_key or self.default_uri)
        import flask
        return scoped_session(SF, scopefunc=flask._app_ctx_stack.__ident_func__)
        

class SQLAlchemy(object):
    dbm: DBManager = None
    in_flask: bool = True

    def __init__(self, dbm: DBManager=None, URI: dict=None, in_flask: bool=True, **kwargs: dict) -> None:
        """ 创建一个用 sqlalchemy 管理数据库的对象
        :param dbm: DBManager 的实例
        :param URI: 若不提供 dbm 则使用 URI 数据新建 DBManager
        :param in_flask: 是否在 flask 内部使用。创建 Session 实例的时候会使用 scoped_session
        """
        if dbm is None:
            dbm = DBManager(URI, **kwargs)
        self.dbm = dbm
        self.in_flask = in_flask
        self.__sessions = self.dbm.create_sessions(is_scoped=in_flask)

    def Model(self, bind_key: str=None):
        """ 获取对应的 Model Factory class
        """
        return self.dbm.get_Model(bind_key)

    def isModel(self, instance, bind_key: str=None):
        """ 判断一个实例是否是 Model 的实例
        """
        Model = self.Model(bind_key=bind_key)
        return isinstance(instance, Model)

    def session(self, bind_key: str=None) -> Session:
        """ 获取对应的 session 实例
        """
        return self.__sessions[bind_key]

    def query(self, model_cls, bind_key: str=None) -> Query:
        return self.session(bind_key).query(model_cls)
        
    def metadata(self, bind_key: str=None) -> MetaData:
        """ 获取对应 Model 的 metadata 实例
        """
        return self.Model(bind_key).metadata

    def engine(self, bind_key: str=None) -> Engine:
        """ 从 DBManager 中获取对应的 engine 实例
        """
        return self.dbm.get_engine(bind_key)

    def create_tables(self, table_names: list[str]=None, bind_key: str=None) -> None:
        """ 创建 table 
        """
        engine = self.engine(bind_key)
        metadata = self.metadata(bind_key)
        if table_names:
            tables = [metadata.tables[tn] for tn in table_names]
            metadata.create_all(bind=engine, tables=tables, checkfirst=True)
        else:
            metadata.create_all(bind=engine, checkfirst=True)

    def drop_tables(self, table_names: list[str]=None, bind_key: str=None) -> None:
        """ 移除 table
        """
        engine = self.engine(bind_key)
        metadata = self.metadata(bind_key)
        if table_names:
            tables = [metadata.tables[tn] for tn in table_names]
            metadata.drop_all(bind=engine, tables=tables, checkfirst=True)
        else:
            metadata.drop_all(bind=engine, checkfirst=True)
    
    def create_all(self) -> None:
        """ 创建所有数据库中的所有表"""
        for bind_key in self.dbm.bind_keys:
            metadata = self.metadata(bind_key)
            metadata.create_all(bind=self.engine(bind_key), checkfirst=True)
        
    def drop_all(self) -> None:
        """ 删除所有数据库中的所有表"""
        for bind_key in self.dbm.bind_keys:
            metadata = self.metadata(bind_key)
            metadata.drop_all(bind=self.engine(bind_key), checkfirst=True)

    def get_table(self, name: str, bind_key: str=None) -> Table:
        return self.metadata(bind_key).tables[name]

    def execute(self, sql, use_session: bool=False, bind_key: str=None):
        # 使用下面的语法会报错 sqlite3.ProgrammingError: Cannot operate on a closed database.
        # with engine.connect() as connection:
        #     return connection.execute(sql)
        if use_session:
            return self.session(bind_key).execute(sql)
        return self.engine(bind_key).connect().execute(sql)
    
    def sall(self, sql, one_entity: bool=True, bind_key: str=None) -> list:
        """ 基于 session 获取所有数据
        :param is_entity: 若为实体，则需要取第一项 https://docs.sqlalchemy.org/en/14/tutorial/data_select.html
        """
        rows = self.execute(sql, use_session=True, bind_key=bind_key).fetchall()
        if one_entity:
            return [item[0] for item in rows]
        return rows

    def sone(self, sql, one_entity: bool=True, bind_key: str=None) -> list:
        """ 基于 session 获取一条数据
        :param is_entity: 若为实体，则需要取第一项 https://docs.sqlalchemy.org/en/14/tutorial/data_select.html
        """
        row = self.execute(sql, use_session=True, bind_key=bind_key).fetchone()
        if one_entity:
            return row[0]
        return row
