"""
pyape.db
-------------------

处理 pyape 数据库功能

1. 解决 SQLAlchemy 线程问题
2. 提供多数据库绑定支持
"""
import math
from threading import Lock

from typing import Iterable, Union
from sqlalchemy.schema import Table, MetaData
from sqlalchemy.orm import DeclarativeMeta, declarative_base, sessionmaker, Session, scoped_session, Query
from sqlalchemy.engine import Engine, create_engine, Result


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


class BindMetaMixin(type):
    def __init__(cls, name: str, bases, d):
        bind_key = (
            d.pop('__bind_key__', None)
            or getattr(cls, '__bind_key__', None)
        )
        super(BindMetaMixin, cls).__init__(name, bases, d)
        if bind_key is not None and getattr(cls, '__table__', None) is not None:
            cls.__table__.info['bind_key'] = bind_key


class DefaultMeta(BindMetaMixin, DeclarativeMeta):
    pass


class DBManager(object):
    """ 管理 SQL 连接，创建和管理数据库 Engine，Session，Model
    
    :param URI: 提供数据库地址
    :param dict kwargs: 提供数据库连接参数
    """
    default_bind_key: str = None
    URI: Union[dict, str] = None
    __engine_lock: Lock = Lock()
    # 保存 engines 对象
    __engines: dict = None
    # 保存 sessionmaker 需要的 binds 参数
    __binds: dict = None
    # 保存 Session 生成器
    __Session_Factory = None
    # 保存所有的 Model class
    __model_classes: dict = None

    def __init__(self, URI: Union[dict, str], **kwargs: dict) -> None:
        self.__engines = {}
        self.__binds = {}
        self.__model_classes = {}
        self.URI = URI
        self.__build_binds()

    @property
    def Models(self) -> Iterable:
        return self.__model_classes.values()
        
    @property
    def bind_keys(self) -> Iterable:
        return self.__model_classes.keys()
        
    def __build_binds(self) -> None:
        view = None
        if isinstance(self.URI, str):
            view = {None: self.URI}.items()
            self.default_bind_key = None
        else:
            view = self.URI.items()
            self.default_bind_key = list(self.URI.keys())[0]
            
        # 下面的三个引擎只需要创建一遍，在初始化的时间创建
        for name, uri in view:
            self.__add_bind(name, uri)

        self.__Session_Factory = sessionmaker(
            binds=self.__binds,
            autoflush=False,
            future=True
        )
        
    def __add_bind(self, bind_key: str, uri: str) -> bool:
        Model = self.set_Model(bind_key)
        if self.__binds.get(Model) is None:
            engine = self.__set_engine(bind_key, uri)
            self.__binds[Model] = engine
            return True
        return False
        
    def __set_engine(self, bind_key: str, uri: str) -> None:
        engine = create_engine(uri, future=True)
        # 保存 engine
        self.__engines[bind_key] = engine
        return engine

    def set_bind(self, bind_key: str, uri: str):
        succ = self.__add_bind(bind_key, uri)
        # 因为增加了 bind，所以也要同时更新 __Session_Factory，
        # 以便新创建的 Session 实例包含新的 bind
        # 对于已经创建的实例，需要调用 Session.bind_mapper 进行绑定
        if succ:
            self.__Session_Factory.configure(binds=self.__binds)
            return
        raise KeyError(f'bind_key {bind_key} is duplicated!')

    def get_Model(self, bind_key: str=None):
        return self.__model_classes.get(bind_key or self.default_bind_key)

    def set_Model(self, bind_key: str=None):
        """ 设置并保存一个 Model
        一般在多个数据库共享同一个 Model 的时候使用
        此时使用默认创建的 Model 可能会造成混淆，最好是创建一个新的
        """
        if self.__model_classes.get(bind_key):
            raise KeyError(bind_key)

        Model = declarative_base(name=bind_key or 'Model', metaclass=DefaultMeta)
        Model.bind_key = bind_key
        self.__model_classes[bind_key] = Model
        return Model
        
    def get_engine(self, bind_key: str=None) -> Engine:
        return self.__engines.get(bind_key or self.default_bind_key)

    def create_session(self) -> Session:
        return self.__Session_Factory()

    def create_scoped_session(self, in_flask: bool=False) -> Session:
        """ 创建一个 scoped session 实例"""
        if in_flask:
            import flask
            return scoped_session(self.__Session_Factory, scopefunc=flask._app_ctx_stack.__ident_func__)
        return scoped_session(self.__Session_Factory)
        

class SQLAlchemy(object):
    """ 创建一个用 sqlalchemy 管理数据库的对象。
    封装常用的高级功能，例如 table 和 query 操作。

    :param dbm: DBManager 的实例。
    :param URI: 若不提供 dbm 则使用 URI 数据新建 DBManager。
    :param is_scoped: 为线程安全，使用 scoped session。
    :param in_flask: 是否在 Flask 框架内部。若在 Flask 内部使用，创建 Session 实例的时候会使用 scoped_session。
    """
    dbm: DBManager = None
    is_scoped: bool = True
    in_flask: bool = True
    __session: Session = None

    def __init__(self,
        dbm: DBManager=None,
        URI: dict=None,
        is_scoped: bool=True,
        in_flask: bool=False,
        **kwargs: dict) -> None:

        if dbm is None:
            dbm = DBManager(URI, **kwargs)
        self.dbm = dbm
        self.in_flask = in_flask
        # 若 in_flask 为真，则 is_scoped 一定为真
        self.is_scoped = True if in_flask else is_scoped
        self.__session = self.__build_session()

    def __build_session(self) -> Session:
        return self.dbm.create_scoped_session(self.in_flask) \
            if self.is_scoped else self.dbm.create_session() 

    def Model(self, bind_key: str=None):
        """ 获取对应的 Model Factory class
        """
        return self.dbm.get_Model(bind_key)

    def isModel(self, instance, bind_key: str=None):
        """ 判断一个实例是否是 Model 的实例
        """
        Model = self.Model(bind_key=bind_key)
        return isinstance(instance, Model)

    def session(self, create_new: bool=False) -> Session:
        """ 获取对应的 session 实例
        :param create_new: 使用独立的 session 实例
        """
        if create_new:
            return self.__build_session()
        return self.__session

    def query(self, model_cls) -> Query:
        """ 获取一个 Query 对象
        :param model_cls: 一个 Model对象
        """
        return self.session().query(model_cls)
        
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

    def execute(self, sql, use_session: bool=False, bind_key: str=None) -> Result:
        # 使用下面的语法会报错 sqlite3.ProgrammingError: Cannot operate on a closed database.
        # with engine.connect() as connection:
        #     return connection.execute(sql)
        result: Result = None
        if use_session:
            return self.session().execute(sql)
        return self.engine(bind_key).connect().execute(sql)
