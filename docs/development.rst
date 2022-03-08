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

``main.py`` 的内容如下：

.. code-block:: python
   
    from flask import Blueprint

    main = Blueprint('main', __name__)

    @main.get('/')
    def home():
        return 'HELLO WORLD

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
    
使用 SQLAlchemy 操作数据库
--------------------------------