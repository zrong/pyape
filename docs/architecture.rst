架构
================

.. _multi_db:

多数据库支持原理
--------------------------------

在设计多数据库支持时， `Flask-SQLAlchemy <https://flask-sqlalchemy.palletsprojects.com/binds/>`_ 的设计给了我很大启发，
但我并不太喜欢这种设计。原因有 2：

1. ``SQLAlchemy`` 自身就建立了 binds 机制，已经支持不同的 mapper 使用不同的 bind，
但 Flask-SQLAlchemy 并没有使用这套机制，这让我感到混乱。

2. ``Flask-SQLAlchemy`` 仅使用了一个 Model，通过在 Model 中设置
``__bind_key__`` 这个巧妙的方式来让不同的 Table 绑定到不同的数据库。
而我认为直接使用多个 Model，在定义 Table 的时候通过 Model 来区分，更容易理解。

``Flask-SQLAlchemy`` 对 Metadata 做了一些手脚，自动加入 ``__bind_key__`` 属性。

.. code-block:: python

    class BindMetaMixin(type):
        def __init__(cls, name, bases, d):
            bind_key = (
                d.pop('__bind_key__', None)
                or getattr(cls, '__bind_key__', None)
            )

            super(BindMetaMixin, cls).__init__(name, bases, d)

            if bind_key is not None and getattr(cls, '__table__', None) is not None:
                cls.__table__.info['bind_key'] = bind_key

然后，通过重写 ``Session.get_bind`` 方法，让 Query 可以通过 ``__bind_key__`` 来找到对应的 Engine： 

.. code-block:: python

    def get_bind(self, mapper=None, clause=None):
        """Return the engine or connection for a given model or
        table, using the ``__bind_key__`` if it is set.
        """
        # mapper is None if someone tries to just get a connection
        if mapper is not None:
            try:
                # SA >= 1.3
                persist_selectable = mapper.persist_selectable
            except AttributeError:
                # SA < 1.3
                persist_selectable = mapper.mapped_table

            info = getattr(persist_selectable, 'info', {})
            bind_key = info.get('bind_key')
            if bind_key is not None:
                state = get_state(self.app)
                return state.db.get_engine(self.app, bind=bind_key)
        return SessionBase.get_bind(self, mapper, clause)

pyape 采用了另一种方法。下面截取 :ref:`pyape.db.DBManager <pyape.db.DBManager>` 的一部分代码来说明：

.. code-block:: python

    class DBManager(object):

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

        def set_Model(self, bind_key: str=None):
            """ 设置并保存一个 Model。

            :param bind_key: 详见 
                :ref:`pyape.db.DBManager.set_bind <pyape.db.DBManager>` 中的说明。
            """
            if self.__model_classes.get(bind_key):
                raise KeyError(bind_key)

            Model = declarative_base(name=bind_key or 'Model', metaclass=DefaultMeta)
            Model.bind_key = bind_key
            self.__model_classes[bind_key] = Model
            return Model

DBManager 在初始化时自动调用 ``__build_binds`` 方法，创建必须的 ``__Session_Factory`` 和 ``Model``。
Model 是根据 :ref:`pyape_toml` 中的 ``[SQLALCHEMY.URI]`` 的值进行创建的。
若 ``URI`` 值为 dict，代表使用多个数据库， dict 的 key 就是 ``bind_key``，使用这个 key 就可以获取到不同的 Engine。
若 ``URI`` 为 str，那么默认的 ``bind_key`` 就是 ``None``，这也是一个合法的值。

在创建 ``__Session_Factory`` 时，使用 SQLAlchemy 提供的标准 ``binds`` 机制，将 mapper(即 Model) 和 Engine 对应起来。

要获取到不同数据库 Model，只需要使用 ``get_Model(bind_key)`` 即可。
若要获取到对应的 Engine，也可以直接使用 ``get_engine(bind_key)``。
这简化了使用，也降低了理解成本。

具体案例请查看： :ref:`multi_db_sample`。
