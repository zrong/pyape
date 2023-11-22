"""
pyape.db
-------------------

处理 pyape 数据库功能

1. 解决 SQLAlchemy 线程问题
2. 提供多数据库绑定支持
"""
import math
from threading import Lock
from typing import Self, TypeAlias
from collections.abc import Iterable, Callable
from dataclasses import dataclass, field

from collections.abc import Iterable
from sqlalchemy.schema import Table, MetaData
from sqlalchemy import Select, func
from sqlalchemy import orm
from sqlalchemy.engine import Engine, Connection, create_engine, make_url, URL


_URIMaker: TypeAlias = Callable[[int], str]


@dataclass
class PagiPager:
    """指示链接到一页的所有信息。"""

    is_first: bool = False
    """ 是否首页。"""

    is_last: bool = False
    """ 是否末页。"""

    is_current: bool = False
    """ 是否当前页。"""

    uri: str = None
    """ 链接到该页的 URI。"""

    page: int = 0
    """ 该页的页码。"""


@dataclass
class PagiPointer:
    """定义页面指示器，包含一系列 PagiPager 对象。"""

    page: int
    """ 当前页编号，同 Pagination.page。"""

    size: int
    """ 一个页面拥有的记录条数，同 Pagination.size。"""

    pages: int
    """ 所有记录的页面总数，同 Pagination.pages。"""

    total: int
    """ 所有记录总数，同 Pagination.total。"""

    uri_maker: _URIMaker
    """ 创建 uri 的方法。"""

    first: PagiPager = None
    """ 首页。"""

    last: PagiPager = None
    """ 末页。"""

    current: PagiPager = None
    """ 当前页。"""

    prev: PagiPager = None
    """ 前一页。"""

    next: PagiPager = None
    """ 下一页。"""

    pagers: list[PagiPager] = field(default_factory=list)
    """ 所有中间页的列表。"""

    def pager(self, page: int, append: bool = False) -> PagiPager:
        """根据 page 的值创建一个 PagiPager 对象，并填充和完善 self.pagers。"""
        pg = PagiPager(page=page)
        if page == 1:
            pg.is_first = True
            self.first = pg
        if page == self.pages:
            pg.is_last = True
            self.last = pg
        if page == self.page:
            pg.is_current = True
            self.current = pg
        pg.uri = self.uri_maker(page)
        if append:
            self.pagers.append(pg)
        return pg


class Pagination:
    """from flask_sqlalchemy
    Internal helper class returned by :meth:`BaseQuery.paginate`.  You
    can also construct it from any other SQLAlchemy query object if you are
    working with other libraries.  Additionally it is possible to pass `None`
    as query object in which case the :meth:`prev` and :meth:`next` will
    no longer work.
    """

    dbs: orm.Session = None
    query: Select = None

    page: int = 1
    size: int = 1
    total: int = 0

    def __init__(
        self,
        query: Select,
        dbs: orm.Session,
        page: int,
        size: int,
        total: int,
        items,
    ):
        #: the unlimited query object that was used to create this
        #: pagination object.
        self.query = query
        self.dbs = dbs
        #: the current page number (1 indexed)
        self.page = page
        #: the number of items to be displayed on a page.
        self.size = size
        #: the total number of items matching the query
        self.total = total
        #: the items for the current page
        self.items = items

    @classmethod
    def paginate(
        cls,
        qry: Select,
        dbs: orm.Session,
        page: int = None,
        size: int = None,
        max_size: int = None,
    ) -> Self:
        """from flask_sqlalchemy
        Returns ``size`` items from page ``page``.

        If ``page`` or ``size`` are ``None``, they will be retrieved from
        the request query. If ``max_size`` is specified, ``size`` will
        be limited to that value. If there is no request or they aren't in the
        query, they default to 1 and 20 respectively.

        Returns a :class:`Pagination` object.
        """

        if page is None or page < 1:
            page = 1

        if size is None or size < 0:
            size = 20

        if max_size is not None:
            size = min(size, max_size)

        items = dbs.scalars(qry.limit(size).offset((page - 1) * size)).all()
        total = dbs.scalar(
            qry.with_only_columns(func.count(), maintain_column_froms=True)
        )
        return cls(qry, dbs, page, size, total, items)

    @property
    def pages(self) -> int:
        """The total number of pages"""
        if self.size == 0:
            pages = 0
        else:
            pages = int(math.ceil(self.total / float(self.size)))
        return pages

    def prev(self) -> Self:
        """Returns a :class:`Pagination` object for the previous page."""
        assert self.query is not None, (
            "a query object is required " "for this method to work"
        )
        return self.__class__.paginate(self.query, self.dbs, self.page - 1, self.size)

    @property
    def prev_page(self) -> int:
        """Number of the previous page."""
        if not self.has_prev:
            return None
        return self.page - 1

    @property
    def has_prev(self) -> bool:
        """True if a previous page exists"""
        return self.page > 1

    def next(self) -> Self:
        """Returns a :class:`Pagination` object for the next page."""
        assert self.query is not None, (
            "a query object is required " "for this method to work"
        )
        return self.__class__.paginate(self.query, self.dbs, self.page + 1, self.size)

    @property
    def has_next(self) -> bool:
        """True if a next page exists."""
        return self.page < self.pages

    @property
    def next_page(self) -> int:
        """Number of the next page"""
        if not self.has_next:
            return None
        return self.page + 1

    def iter_pages(
        self,
        left_edge: int = 2,
        left_current: int = 2,
        right_current: int = 5,
        right_edge: int = 2,
    ) -> Iterable[int]:
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
            if (
                num <= left_edge
                or (
                    num > self.page - left_current - 1
                    and num < self.page + right_current
                )
                or num > self.pages - right_edge
            ):
                if last + 1 != num:
                    yield None
                yield num
                last = num

    def point(
        self,
        uri_maker: _URIMaker,
        left_edge: int = 2,
        left_current: int = 2,
        right_current: int = 5,
        right_edge: int = 2,
    ) -> PagiPointer:
        """返回一个分页指针对象。"""
        pointer = PagiPointer(self.page, self.size, self.pages, self.total, uri_maker)
        for page in self.iter_pages(left_edge, left_current, right_current, right_edge):
            if page is None:
                pointer.pagers.append(None)
            else:
                pointer.pager(page, append=True)
                if self.has_next:
                    pointer.next = pointer.pager(self.next_page, append=False)
                if self.has_prev:
                    pointer.prev = pointer.pager(self.prev_page, append=False)
        return pointer

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} total={self.total} page={self.page}, size={self.size}, pages={self.pages}>'


class BindMetaMixin(type):
    def __init__(cls, name: str, bases, d):
        bind_key = d.pop("__bind_key__", None) or getattr(cls, "__bind_key__", None)
        super(BindMetaMixin, cls).__init__(name, bases, d)
        if bind_key is not None and getattr(cls, "__table__", None) is not None:
            cls.__table__.info["bind_key"] = bind_key


class DefaultMeta(BindMetaMixin, orm.DeclarativeMeta):
    pass


class DBManager:
    """管理 SQL 连接，创建和管理数据库 Engine，Session，Model。

    :param URI: 提供数据库地址。
    :param dict kwargs: 提供数据库连接参数。
    """

    default_bind_key: str = None
    """ 默认的 bind_key 必须存在，它的默认值就是 ``None``，这是一个有效的 bind_key。"""

    URI: dict | str = None
    """ 从配置文件中解析出的 URI 值，可能是 str 或者 dict。"""

    ENGINE_OPTIONS: dict = None
    """ 从配置文件中解析出的 ENGINE_OPTION 值。用于数据库引擎的配置。"""

    Session_Factory = None
    """ Session 工厂类，使用 orm.sessionmaker 生成。"""

    __engine_lock: Lock = Lock()
    # 保存 engines 对象
    __engines: dict = None
    # 保存 orm.sessionmaker 需要的 binds 参数
    __binds: dict = None
    # 保存所有的 Model class
    __model_classes: dict = None

    def __init__(
        self, URI: dict | str, ENGINE_OPTIONS: dict = None, **kwargs: dict
    ) -> None:
        self.__engines = {}
        self.__binds = {}
        self.__model_classes = {}
        self.URI = URI
        self.ENGINE_OPTIONS = ENGINE_OPTIONS
        self.__build_binds()

    @property
    def Models(self) -> Iterable:
        """使用 set 形式返回所有的 Model。"""
        return self.__model_classes.values()

    @property
    def bind_keys(self) -> Iterable:
        """使用 set 形式返回所有的 bind_key。若只有一个数据库，
        返回的是 ``(None,)`` 。
        """
        return self.__model_classes.keys()

    def __build_binds(self) -> None:
        view = None
        if isinstance(self.URI, str):
            view = {None: self.URI}.items()
            self.default_bind_key = None
        else:
            view = self.URI.items()
            self.default_bind_key = list(self.URI.keys())[0]

        for name, uri in view:
            self.__add_bind(name, uri)

        self.Session_Factory = orm.sessionmaker(
            binds=self.__binds, autoflush=False, future=True
        )

    def __add_bind(self, bind_key: str, uri: str) -> bool:
        Model = self.set_Model(bind_key)
        if self.__binds.get(Model) is None:
            engine = self.__set_engine(bind_key, uri)
            self.__binds[Model] = engine
            return True
        return False

    def __set_engine(self, bind_key: str, uri: str) -> None:
        sa_url: URL = make_url(uri)

        options: dict = self.ENGINE_OPTIONS or {}
        options.setdefault("future", True)

        if sa_url.drivername.startswith("mysql"):
            # 加入 charset 设置，用于 utf8mb4 这种 charset
            query = dict(sa_url.query)
            query.setdefault("charset", "utf8")
            sa_url = sa_url.set(query=query)

            if sa_url.drivername != "mysql+gaerdbms":
                # 对于 MySQL 来说，设置 pool_recycle 是必须的，原因如下：
                # pymysql.err.OperationalError: (2013, 'Lost connection to MySQL server during query')
                # 连接池连接mysql数据库失败，应该是mysql数据库连接超时，mysql数据库配置文件存在以下两个参数，是负责管理连接超时的。
                # 1. interactive_timeout：针对交互式连接
                # 2. wait_timeout：针对非交互式连接。
                # 所谓的交互式连接，即在mysql_real_connect()函数中使用了CLIENT_INTERACTIVE选项。
                # 说得直白一点，通过mysql客户端连接数据库是交互式连接，通过jdbc连接数据库是非交互式连接。
                # 这两个参数在腾讯云 MySQL 中默认都是 3600 秒，也就是超过1小时的连接就会自动失效。这本身并没什么问题，真正的问题是：
                # 我们做项目一般使用数据库连接池来获取连接，连接池里的连接可能会较长时间不关闭，等待被使用，这就与mysql连接超时机制起了冲突。
                # 当超过8个小时没有新的数据库请求的时候，数据库连接就会断开，
                # 如果我们连接池的配置是用不关闭或者关闭时间超过8小时，
                # 这个时候连接池没有回收并且还认为连接池与数据库之间的连接还存在，
                # 就会继续连接，但是数据库连接断开了，就会报错 2013: Lost connection to MySQL server during query.
                # pool_recycle 回收时间（就是一定时间内不使用就会回收），修改这个参数的值，不要大于wait_timeout的值即可。下面的设置意味着每隔 7200 秒就回收一次连接线程池。

                options.setdefault("pool_size", 10)
                options.setdefault("pool_recycle", 7200)

        elif sa_url.drivername == "sqlite":
            pool_size = options.get("pool_size")
            detected_in_memory = False
            if sa_url.database in (None, "", ":memory:"):
                detected_in_memory = True

                from sqlalchemy.pool import StaticPool

                options["poolclass"] = StaticPool
                if "connect_args" not in options:
                    options["connect_args"] = {}
                # https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#using-a-memory-database-in-multiple-threads
                options["connect_args"]["check_same_thread"] = False

                # we go to memory and the pool size was explicitly set
                # to 0 which is fail.  Let the user know that
                if pool_size == 0:
                    raise RuntimeError(
                        "SQLite in memory database with an "
                        "empty queue not possible due to data "
                        "loss."
                    )
            # if pool size is None or explicitly set to 0 we assume the
            # user did not want a queue for this sqlite connection and
            # hook in the null pool.
            elif not pool_size:
                from sqlalchemy.pool import NullPool

                options["poolclass"] = NullPool

        engine = create_engine(sa_url, **options)

        if sa_url.drivername == "sqlite":
            # 强制 SQLITE 支持支持外键
            # https://docs.sqlalchemy.org/en/14/dialects/sqlite.html#foreign-key-support
            from sqlalchemy import event

            @event.listens_for(engine, "connect")
            def set_sqlite_pragma(dbapi_connection, connection_record):
                # print(f'ffff {dbapi_connection=} {connection_record=}')
                cursor = dbapi_connection.cursor()
                cursor.execute("PRAGMA foreign_keys=ON;")
                cursor.close()

        # options['poolclass'] = StaticPool
        # if 'connect_args' not in options:
        #     options['connect_args'] = {}
        # options['connect_args']['check_same_thread'] = False
        # 保存 engine
        self.__engines[bind_key] = engine
        return engine

    def set_bind(self, bind_key: str, uri: str):
        """利用 SQLAlchemy 提供的 binds 机制，
        将 bind_key 与数据库连接绑定起来。

        :param bind_key: 数据库的 bind_key，在 :ref:`pyape_toml` 中定义，
            值为 ``[SQLALCHEMY.URI]`` 中的键名。
            若 URI 为 str 而非 dict，则 bind_key 值为 ``None`` 。
        """
        succ = self.__add_bind(bind_key, uri)
        # 因为增加了 bind，所以也要同时更新 __Session_Factory，
        # 以便新创建的 Session 实例包含新的 bind
        # 对于已经创建的实例，需要调用 Session.bind_mapper 进行绑定
        if succ:
            self.Session_Factory.configure(binds=self.__binds)
            return
        raise KeyError(f"bind_key {bind_key} is duplicated!")

    def get_Model(self, bind_key: str = None):
        return self.__model_classes.get(bind_key or self.default_bind_key)

    def set_Model(self, bind_key: str = None):
        """设置并保存一个 Model。

        :param bind_key: 详见
            :ref:`pyape.db.DBManager.set_bind <pyape.db.DBManager>` 中的说明。
        """
        if self.__model_classes.get(bind_key):
            raise KeyError(bind_key)

        Model = orm.declarative_base(name=bind_key or "Model", metaclass=DefaultMeta)
        Model.bind_key = bind_key
        self.__model_classes[bind_key] = Model
        return Model

    def get_engine(self, bind_key: str = None) -> Engine:
        """获取一个 Engine 对象。

        :param bind_key:
            详见 :ref:`pyape.db.DBManager.set_bind <pyape.db.DBManager>` 中的说明。
        """
        return self.__engines.get(bind_key or self.default_bind_key)

    def create_new_session(self) -> orm.Session:
        """创建一个 Session 对象。"""
        return self.Session_Factory()

    def create_scoped_session(self, use_greenlet: bool = False) -> orm.scoped_session:
        """创建一个 orm.scoped_session 代理。

        :param use_greenlet: 是否使用 greenlet。
        """
        if use_greenlet:
            try:
                from greenlet import getcurrent as _get_ident
            except ImportError:
                from threading import get_ident as _get_ident
            return orm.scoped_session(self.Session_Factory, scopefunc=_get_ident)
        return orm.scoped_session(self.Session_Factory)


class SQLAlchemy:
    """创建一个用 sqlalchemy 管理数据库的对象。
    封装常用的高级功能，例如 table 和 query 操作。

    :param dbm: DBManager 的实例。
    :param URI: 若不提供 dbm 则使用 URI 数据新建 DBManager。
    :param is_scoped: 为线程安全，使用 scoped session。
    :param in_flask: 是否在 Flask 框架内部。若在 Flask 内部使用，
        创建 Session 实例的时候会使用 scoped_session。
    """

    dbm: DBManager = None
    is_scoped: bool = True
    use_greenlet: bool = False

    Session: orm.sessionmaker | orm.scoped_session = None
    """ 根据 is_scoped 的值，保存 orm.sessionmaker 或者 orm.scoped_session 的结果对象。"""

    def __init__(
        self,
        dbm: DBManager = None,
        URI: dict | str = None,
        ENGINE_OPTIONS: dict = None,
        is_scoped: bool = True,
        use_greenlet: bool = False,
        **kwargs: dict,
    ) -> None:
        if dbm is None:
            dbm = DBManager(URI, ENGINE_OPTIONS, **kwargs)
        self.dbm = dbm
        self.use_greenlet = use_greenlet
        # 若 use_greenlet 为真，则 is_scoped 一定为真
        self.is_scoped = True if use_greenlet else is_scoped
        if self.is_scoped:
            self.Session = self.dbm.create_scoped_session(self.use_greenlet)
        else:
            self.Session = self.dbm.Session_Factory

    def Model(self, bind_key: str = None):
        """获取对应的 Model Factory class。

        :param bind_key:
            详见 :ref:`pyape.db.DBManager.set_bind <pyape.db.DBManager>` 中的说明。
        """
        return self.dbm.get_Model(bind_key)

    def isModel(self, instance, bind_key: str = None):
        """判断一个实例是否是 Model 的实例。

        :param bind_key:
            详见 :ref:`pyape.db.DBManager.set_bind <pyape.db.DBManager>` 中的说明。
        """
        Model = self.Model(bind_key=bind_key)
        return isinstance(instance, Model)

    def engine(self, bind_key: str = None) -> Engine:
        """从 DBManager 中获取对应的 engine 实例。

        :param bind_key:
            详见 :ref:`pyape.db.DBManager.set_bind <pyape.db.DBManager>` 中的说明。
        """
        return self.dbm.get_engine(bind_key)

    def connection(self, bind_key: str = None) -> Connection:
        """调用 Engine 的 connect 放来了获取一个 connection 对象。"""
        return self.engine(bind_key).connect()

    def session(self) -> orm.Session:
        """获取一个 Session 对象。"""
        return self.Session()

    def metadata(self, bind_key: str = None) -> MetaData:
        """获取对应 Model 的 metadata 实例"""
        return self.Model(bind_key).metadata

    def create_tables(
        self, table_names: list[str] = None, bind_key: str = None
    ) -> None:
        """创建 table。

        :param table_names: 提供 table 名称列表。
        :param bind_key:
            详见 :ref:`pyape.db.DBManager.set_bind <pyape.db.DBManager>` 中的说明。
        """
        engine = self.engine(bind_key)
        metadata = self.metadata(bind_key)
        if table_names:
            tables = [metadata.tables[tn] for tn in table_names]
            metadata.create_all(bind=engine, tables=tables, checkfirst=True)
        else:
            metadata.create_all(bind=engine, checkfirst=True)

    def drop_tables(self, table_names: list[str] = None, bind_key: str = None) -> None:
        """移除 table。

        :param table_names: 提供 table 名称列表。
        :param bind_key:
            详见 :ref:`pyape.db.DBManager.set_bind <pyape.db.DBManager>` 中的说明。
        """
        engine = self.engine(bind_key)
        metadata = self.metadata(bind_key)
        if table_names:
            tables = [metadata.tables[tn] for tn in table_names]
            metadata.drop_all(bind=engine, tables=tables, checkfirst=True)
        else:
            metadata.drop_all(bind=engine, checkfirst=True)

    def recreate_table(self, *table_names: str, bind_key: str = None) -> None:
        """重建 table，支持单个或者多个名称。"""
        self.drop_tables(table_names=table_names, bind_key=bind_key)
        self.create_tables(table_names=table_names, bind_key=bind_key)

    def create_all(self) -> None:
        """创建所有数据库中的所有表。"""
        for bind_key in self.dbm.bind_keys:
            metadata = self.metadata(bind_key)
            metadata.create_all(bind=self.engine(bind_key), checkfirst=True)

    def drop_all(self) -> None:
        """删除所有数据库中的所有表。"""
        for bind_key in self.dbm.bind_keys:
            metadata = self.metadata(bind_key)
            metadata.drop_all(bind=self.engine(bind_key), checkfirst=True)

    def get_table(self, name: str, bind_key: str = None) -> Table:
        """获取一个 Table。

        :param name: Table 名称。
        :param bind_key:
            详见 :ref:`pyape.db.DBManager.set_bind <pyape.db.DBManager>` 中的说明。
        """
        return self.metadata(bind_key).tables[name]
