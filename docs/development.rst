开发
================

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

wsgi.py 加强版2
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
    

使用 Blueprint 创建访问 URL 
---------------------------

使用 SQLAlchemy 操作数据库
--------------------------------