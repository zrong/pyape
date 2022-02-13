#======================
# 处理 pyape 数据库功能
# 
# 1. 解决 SQLAlchemy 线程问题
# 2. 提供多数据库绑定支持
#
# @author zrong
# @created 2022-02-07
#======================

import math
from typing import Iterable, Union
from sqlalchemy.schema import Table, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker, Session, scoped_session, Query
from sqlalchemy.engine import Engine, create_engine


class Pagination(object):
    """ from flask_sqlalchemy
    Internal helper class returned by :meth:`BaseQuery.paginate`.  You
    can also construct it from any other SQLAlchemy query object if you are
    working with other libraries.  Additionally it is possible to pass `None`
    as query object in which case the :meth:`prev` and :meth:`next` will
    no longer work.
    """

    def __init__(self, query: Query, page: int, per_page: int, total: int, items):
        #: the unlimited query object that was used to create this
        #: pagination object.
        self.query = query
        #: the current page number (1 indexed)
        self.page = page
        #: the number of items to be displayed on a page.
        self.per_page = per_page
        #: the total number of items matching the query
        self.total = total
        #: the items for the current page
        self.items = items

    @classmethod
    def paginate(cls, qry: Query, page: int=None, per_page: int=None, max_per_page: int=None):
        """ from flask_sqlalchemy
        Returns ``per_page`` items from page ``page``.

        If ``page`` or ``per_page`` are ``None``, they will be retrieved from
        the request query. If ``max_per_page`` is specified, ``per_page`` will
        be limited to that value. If there is no request or they aren't in the
        query, they default to 1 and 20 respectively.

        Returns a :class:`Pagination` object.
        """

        if page is None or page < 1:
            page = 1

        if per_page is None or per_page < 0:
            per_page = 20

        if max_per_page is not None:
            per_page = min(per_page, max_per_page)

        items = qry.limit(per_page).offset((page - 1) * per_page).all()

        total = qry.order_by(None).count()

        return cls(qry, page, per_page, total, items)

    @property
    def pages(self):
        """The total number of pages"""
        if self.per_page == 0:
            pages = 0
        else:
            pages = int(math.ceil(self.total / float(self.per_page)))
        return pages

    def prev(self):
        """Returns a :class:`Pagination` object for the previous page."""
        assert self.query is not None, 'a query object is required ' \
                                       'for this method to work'
        return self.__class__.paginate(self.query, self.page - 1, self.per_page)

    @property
    def prev_num(self):
        """Number of the previous page."""
        if not self.has_prev:
            return None
        return self.page - 1

    @property
    def has_prev(self):
        """True if a previous page exists"""
        return self.page > 1

    def next(self):
        """Returns a :class:`Pagination` object for the next page."""
        assert self.query is not None, 'a query object is required ' \
                                       'for this method to work'
        return self.__class__.paginate(self.query, self.page + 1, self.per_page)

    @property
    def has_next(self):
        """True if a next page exists."""
        return self.page < self.pages

    @property
    def next_num(self):
        """Number of the next page"""
        if not self.has_next:
            return None
        return self.page + 1

    def iter_pages(self, left_edge=2, left_current=2,
                   right_current=5, right_edge=2):
        """Iterates over the page numbers in the pagination.  The four
        parameters control the thresholds how many numbers should be produced
        from the sides.  Skipped page numbers are represented as `None`.
        This is how you could render such a pagination in the templates:

        .. sourcecode:: html+jinja

            {% macro render_pagination(pagination, endpoint) %}
              <div class=pagination>
              {%- for page in pagination.iter_pages() %}
                {% if page %}
                  {% if page != pagination.page %}
                    <a href="{{ url_for(endpoint, page=page) }}">{{ page }}</a>
                  {% else %}
                    <strong>{{ page }}</strong>
                  {% endif %}
                {% else %}
                  <span class=ellipsis>…</span>
                {% endif %}
              {%- endfor %}
              </div>
            {% endmacro %}
        """
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
               (num > self.page - left_current - 1 and
                num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num


class DBManager(object):
    default_bind_key: str = None
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
            Model = declarative_base(name=name or 'Model')
            Model.bind_key = name
            self.__model_classes[name] = Model
        
    def __set_default_uri(self) -> None:
        if isinstance(self.URI, dict):
            self.default_bind_key = self.URI.keys()[0]

    def get_Model(self, bind_key: str=None):
        return self.__model_classes.get(bind_key or self.default_bind_key)

    def set_Model(self, bind_key: str=None):
        """ 设置并保存一个 Model
        一般在多个数据库共享同一个 Model 的时候使用
        此时使用默认创建的 Model 可能会造成混淆，最好是创建一个新的"""
        if self.__model_classes.get(bind_key):
            raise KeyError(bind_key)
        self.__model_classes[bind_key] = declarative_base(name=bind_key or 'Model')
        return self.__model_classes.get(bind_key or self.default_bind_key)
        
    def get_engine(self, bind_key: str=None) -> Engine:
        return self.__engines.get(bind_key or self.default_bind_key)
    
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
        SF = self.__session_factories.get(bind_key or self.default_bind_key)
        return SF()

    def create_scoped_session(self, bind_key: str=None) -> Session:
        """ 创建一个 scoped session 实例"""
        SF = self.__session_factories.get(bind_key or self.default_bind_key)
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

    def session(self, bind_key: str=None, create_new: bool=False) -> Session:
        """ 获取对应的 session 实例
        :param create_new: 使用独立的 session 实例
        """
        if create_new:
            return self.dbm.create_scoped_session(bind_key) if self.in_flask else self.dbm.create_session(bind_key) 
        return self.__sessions[bind_key]

    def query(self, model_cls) -> Query:
        """ 获取一个 Query 对象
        :param model_cls: 一个 Model对象，该对象在创建的时候一定有定义 bind_key。
        """
        return self.session(model_cls.bind_key).query(model_cls)
        
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
    