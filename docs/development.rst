开发
================

.. _sample_app:

一个最小化的 app
---------------------------

下面的工作完成后，项目文件夹结构将如下所示： ::

    sample
    ├── app
    │   ├── __init__.py
    │   ├── main.py
    │   └── user.py
    ├── config.toml
    ├── .gitignore
    ├── .env
    ├── pyape.toml
    └── wsgi.py


使用 :ref:`cli_pyape_init` 创建项目后，我们需要给项目增加内容使其可以工作。
下面以创建一个在本地调试的 app 为例，描述项目搭建过程。

创建 ``app`` 文件夹，在其中加入 ``__init__.py`` 文件使其成为标准的 python 模块。

创建两个子模块 ``app/main.py`` 和 ``app/user.py``。

.. _sample_app_main_py:

``main.py`` 的内容如下：

.. code-block:: python
   
    from flask import Blueprint

    main = Blueprint('main', __name__)

    @main.get('/')
    def home():
        return 'HELLO WORLD

.. _sample_app_user_py:

``user.py`` 的内容如下：

.. code-block:: python

    from flask import Blueprint

    user = Blueprint('user', __name__)

    @user.get('/friend')
    def friend():
        return 'HELLO MY FRIEND'
        
在 :ref:`pyape_toml` 中创建 ``local`` 环境，进行如下配置： ::
    
    [ENV.local.'.env']
    FLASK_ENV = 'development'
    FLASK_RUN_PORT = 5001

    [ENV.local.'config.toml'.PATH]
    STATIC_URL_PATH = '/static'

    [ENV.local.'config.toml'.PATH.modules]
    main = ''
    user = '/user'

使用 :ref:`cli_pyape_config` 生成配置文件，由于我们的目标是在本地环境调试运营，
因此只需要生成 ``config.toml`` 和 ``.env``： ::

    pyape config --env local --force config.toml .env

.. warning::

    在生成 ``config.toml`` 之前，在环境变量中必须包含 ``SAMPLE_LOCAL_SECRET_KEY`` 
    这个环境变量。详情请阅读 :ref:`gen_secret_key` 。
    
生成的 ``.env`` 文件内容为： ::

    FLASK_APP = wsgi:sample_app
    FLASK_ENV = development
    FLASK_RUN_PORT = 5001
    
生成的 ``config.toml`` 文件内容为： ::

    [FLASK]
    SECRET_KEY = "HK-VHH4C0ijLjOYBYrO7L2ACsmxcx9UClph-Q8lu3Hk="

    [SQLALCHEMY]
    URI = "sqlite:///sample/sample.sqlite"

    [PATH]
    STATIC_URL_PATH = "/static"
    STATIC_FOLDER = "dist"
    TEMPLATE_FOLDER = "dist/template"

    [SQLALCHEMY.ENGINE_OPTIONS]
    pool_timeout = 10
    pool_recycle = 3600

    [PATH.modules]
    main = ""
    user = "/user"
    
参照 :ref:`wsgi_py` 对已有文件进行修改。

执行 ``flask run`` 启动开发服务器。

测试页面访问： ::

    $ curl http://127.0.0.1:5001/
    HELLO WORLD
    $ curl http://127.0.0.1:5001/user/friend
    HELLO MY FRIEND%

完整的 sample 项目请访问 `sample <https://github.com/zrong/pyape/tree/develop/sample>`_ 。

.. _wsgi_py:

wsgi.py
-------------

``wsgi.py`` 是 Flask 项目的入口文件。执行 :ref:`cli_pyape_init` 后，项目文件夹中会自动生成这个文件。
我们需要修改这个文件，使其符合我们自己项目的需要。

最简单的 ``wsgi.py`` 内容如下：

.. code-block:: python

    import pyape.app
    from pyape.flask_extend import PyapeFlask

    pyape_app: PyapeFlask = pyape.app.init()

.. note::

    在 :ref:`pyape_toml_dotenv` 中要设置 ``FLASK_APP = wsgi:pyape_app`` 。

    在使用 Gunicorn 部署时，要确保 :ref:`pyape_toml_gunicorn_conf_py` 中的 ``wsgi_app = 'wsgi:pyape_app'`` 。

    在使用 uWSGI 部署时，要确保 :ref:`pyape_toml_uwsgi_ini` 中的 ``callable = 'wsgi:pyape_app'``。

.. _wsgi_py_more:

wsgi.py 加强版
-----------------

为了方便理解，我们可以做得更多一些。

导入必要的模块：

.. code-block:: python

    from pathlib import Path
    from functools import partial

    import pyape.app
    import pyape.config
    from pyape.flask_extend import PyapeFlask, PyapeRespons
    
明确指定主配置文件：

.. code-block:: python

    work_dir = Path(__file__).parent.resolve()
    gconfig = pyape.config.GlobalConfig(work_dir, 'config.toml')

测试期间，可以用继承 ``PyapeRespone`` 的方式来实现跨域：

.. code-block:: python

    class CustomResponse(PyapeResponse):
        @property
        def cors_config(self):
            return PyapeResponse.CORS_DEFAUL
            
创建一个 app 实例，使用支持跨域的 Response：

.. code-block:: python

    pyape_app: PyapeFlask = pyape.app.init(gconfig, create_app, cls_config={'ResponseClass': CustomResponse})

加强版的完整内容 ``wsgi.py``：

.. code-block:: python

    from pathlib import Path

    import pyape.app
    import pyape.config
    from pyape.flask_extend import PyapeFlask, PyapeRespons

    work_dir = Path(__file__).parent.resolve()
    gconfig = pyape.config.GlobalConfig(work_dir, 'config.toml')

    class CustomResponse(PyapeResponse):
        @property
        def cors_config(self):
            return PyapeResponse.CORS_DEFAUL

    pyape_app: PyapeFlask = pyape.app.init(gconfig, None, cls_config={'ResponseClass': CustomResponse})

.. _wsgi_py_more_more:

wsgi.py 加加强版
-----------------

基于加强版，可以做更多事。
例如增加可以在 `flask shell <https://flask.palletsprojects.com/en/2.0.x/cli/?highlight=shell#open-a-shell>`_ 环境中调用的上下文方法。
以及对数据库进行初始化： 

.. code-block:: python

    from pathlib import Path
    from functools import partial

    import pyape.app
    import pyape.config
    from pyape.flask_extend import PyapeFlask, PyapeRespons

    work_dir = Path(__file__).parent.resolve()
    gconfig = pyape.config.GlobalConfig(work_dir, 'config.toml')

    class CustomResponse(PyapeResponse):
        @property
        def cors_config(self):
            return PyapeResponse.CORS_DEFAUL
            

    def setup_app(pyape_app: PyapeFlask, **kwargs):
    """ 初始化 app 项目，这个方法被嵌入 flask shell 上下文中执行，可以使用 kwargs 传递参数
    """
    # 在这里可以进行数据库的初始化工作
    # pyape_app._gdb.create_all()
    return pyape_app
    

    def create_app(pyape_app: PyapeFlask):
        """ 被 pyape.app.init 调用，用于处理 app 初始化
        """
        # 加入上下文处理器
        pyape_app.shell_context_processor(lambda: {
            'gdb': pyape_app._gdb,
            # 这里可以传递更多促使给 setup_app
            'setup': partial(setup_app, pyape_app),
        })
        pyape.app.logger.info(pyape_app.config)

    pyape_app: PyapeFlask = pyape.app.init(gconfig, create_app, cls_config={'ResponseClass': CustomResponse})
    
.. _sqlalchemy:

使用 SQLAlchemy 操作数据库
--------------------------------

在使用 :ref:`wsgi_py` 初始化框架的时候，数据库会自动创建。可以在 ``pyape.app.init_db`` 中找到创建代码：

.. code-block:: python

    def init_db(pyape_app: PyapeFlask):
    """ 初始化 SQLAlchemy
    """
        sql_uri = pyape_app._gconf.getcfg('SQLALCHEMY', 'URI')
        if sql_uri is None:
            return
        global gdb
        if gdb is not None:
            raise ValueError('gdb 不能重复定义！')
        gdb = PyapeDB(app=pyape_app)
        pyape_app._gdb = gdb

.. note::

    ``pyape.flask_extend.PyapeDB`` 是 :ref:`pyape.db.SQLAlchemy <pyape.db.SQLAlchemy>` 的子类。


pyape 默认使用 SQLAlchemy 的 ORM 模式工作。让我们构建一个 Model 用于创建 Table。

.. _app_model_py:

创建子模块 ``app/model.py`` 用于 Table 定义。

.. code-block:: python

    # app/model.py
    import time
    from sqlalchemy import Column, INT, VARCHAR
    from pyape.app import gdb

    Model = gdb.Model()

    class User(Model):
        __tablename__ = 'user'

        id = Column(INT, autoincrement=True, primary_key=True)
        name = Column(VARCHAR(100), nullable=False)
        createtime = Column(INT, nullable=False, default=lambda: int(time.time()))


在模块 :ref:`app/user.py <sample_app_user_py>` 中增加两个方法，用于读写数据库。

.. note::

    涉及到 webargs 用法，请参考其 `官方文档 <https://webargs.readthedocs.io/en/latest/>`_。

    SQLAlchemy 语法基于最新的 SQLAlchemy 2.0，请阅读 `SQLAlchemy 2.0 Tutorial <https://docs.sqlalchemy.org/en/20/tutorial/index.html>`_。
    若你是 SQLAlchemy 1.x 用户，请阅读 `Migrating to SQLAlchemy 2.0 <https://docs.sqlalchemy.org/en/20/changelog/migration_20.html>`_。

.. code-block:: python

    from flask import Blueprint, abort
    from webargs.flaskparser import use_args
    from webargs import fields

    from pyape.app import gdb, logger
    from app.model import User


    @user.get('/get')
    @use_args({'id': fields.Int(required=True)}, location='query')
    def get_user(args):
        id = args['id']
        userobj = gdb.session().get(User, id)
        if userobj is None:
            logger.warning(f'user {id} is not found.')
            abort(404)
        return f'User id: {userobj.id}, name: {userobj.name}'


    @user.post('/set')
    @use_args({'id': fields.Int(required=True), 'name': fields.Str(required=True)}, location='form')
    def set_user(args):
        userobj = User(**args)
        gdb.session().add(userobj)
        gdb.session().commit()
        return f'User id: {userobj.id}, name: {userobj.name}'

.. _test_sample_local:

测试 Sample 项目的 local 环境（单数据库支持）
----------------------------------------------

若 pyape 项目位于 ``~/storage/pyape``： ::

    # 进入虚拟环境
    cd ~/storage/pyape
    python3 -m venv venv
    source venv/bin/active

    # 安装当前环境下的 pyape
    (venv) pip install -e .

    # 创建本地配置文件，使用 local 环境
    (venv) pyape config -FE local config.toml .env

    # 运行单元测试
    (venv) pytest tests/test_sample_env_local.py

.. _multi_db_sample:

多数据库支持范例
--------------------------------

:ref:`sqlalchemy` 仅包含单数据库支持，得益于 SQLAlchemy 的良好设计
以及 :ref:`pyape_toml` 的多环境支持，我们可以非常容易让不同环境支持不同的数据库。

要理解多数据库支持的原理，请查看： :ref:`multi_db`。

在 ``sample/pyape.toml`` 中已经包含了多数据库范例的支持。让我们看看 ``multidb`` 环境的配置，
我们使用 :ref:`app.user_multidb <sample_app_user_multidb_py>` 模块替代 :ref:`app.user <sample_app_user_py>`。 ::

    [ENV.multidb.'config.toml'.PATH.modules]
    main = ''
    user_multidb = '/user2'

    [ENV.multidb.'config.toml'.SQLALCHEMY.URI]
    # 多数据库配置，直接覆盖默认配置
    db1 = 'sqlite:///{WORK_DIR}/sample_db1.sqlite'
    db2 = 'sqlite:///{WORK_DIR}/sample_db2.sqlite'

.. _sample_app_model_multidb_py:

创建子模块 ``app/model_multidb.py`` 用于 Table 定义。
在这里，可以使用 `Model()` 方法，传递 ``bind_key`` 参数来获取对应不同数据库的 Model。
下面的 ``User1`` 和 ``User2`` 两个 Table 分别位于不同的数据库。

.. code-block:: python

    # app/model_multidb.py
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

.. _sample_app_user_multidb_py:

创建子模块 ``app/user_multidb.py`` 提供数据库访问方法。
这里的范例简单传递 ``bind_key`` 参数用来指定写入不同的数据库。

.. code-block:: python

    from flask import Blueprint, abort
    from webargs.flaskparser import use_args
    from webargs import fields
    from sqlalchemy import select

    from pyape.app import gdb, logger
    from app.model_multidb import User1, User2


    user_multidb = Blueprint('user_multidb', __name__)


    @user_multidb.get('/get')
    @use_args({'id': fields.Int(required=True), 'bind_key': fields.Str(required=True)}, location='query')
    def get_user_db1(args):
        id = args['id']
        bind_key = args['bind_key']
        User = User1 if bind_key == 'db1' else User2
        userobj = gdb.session().get(User, id)
        if userobj is None:
            logger.warning(f'user {id} is not found in {bind_key}.')
            abort(404)
        return f'User in {bind_key} id: {userobj.id}, name: {userobj.name}'


    @user_multidb.post('/set')
    @use_args({'id': fields.Int(required=True), 'name': fields.Str(required=True), 'bind_key': fields.Str(required=True)}, location='form')
    def set_user(args):
        bind_key = args['bind_key']
        User = User1 if bind_key == 'db1' else User2
        userobj = User(**args)
        gdb.session().add(userobj)
        gdb.session().commit()
        return f'User in {bind_key} id: {userobj.id}, name: {userobj.name}'

.. _test_sample_multidb:

测试 Sample 项目的 multidb 环境（多数据库支持）
------------------------------------------------------------

若 pyape 项目位于 ``~/storage/pyape``： ::

    # 进入虚拟环境
    cd ~/storage/pyape
    python3 -m venv venv
    source venv/bin/active

    # 安装当前环境下的 pyape
    (venv) pip install -e .

    # 创建本地配置文件，使用 multidb 环境
    (venv) pyape config -FE multidb config.toml .env

    # 运行单元测试
    (venv) pytest tests/test_sample_env_multidb.py
