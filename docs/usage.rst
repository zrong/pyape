使用
================

pyape 支持 python3.9 及以上版本。

.. _install:

安装
----------

安装开发版
^^^^^^^^^^^^^

国内::

    pip install git+https://gitee.com/zrong/pyape@develop

全球::

    pip install git+https://github.com/zrong/pyape@develop
    
安装稳定版
^^^^^^^^^^^^^^

由于架构变更，请使用 pyape 开发版。

::

    pip install pyape
    
    
.. _create_project:

创建项目
----------------

创建项目文件夹，项目名称以 project 为例：

::

    mkdir project
    cd project
    python -m venv venv
    source venv/bin/activate
    pip install git+https://github.com/zrong/pyape@develop
    
    # or

    pip install pyape
    

初始化项目
-----------

进入虚拟环境，执行初始化命令，在项目文件夹下生成 4 个文件： ``README.md/wsgi.py/pyape.toml/.gitignore``。

亦可以用 ``-C`` 参数指定项目文件夹。详情见 :ref:`cli_pyape_init`。

::

    (venv) cd project
    (venv) pyape init

.. note::

    这里创建的是一个空项目，需要在这个项目的基础上进行进一步开发。开发遵循 Flask 程序的标准。

进一步阅读：

- 进一步完善项目，请阅读： :ref:`sample_app`；
- 配置 :ref:`wsgi_py` 作为项目入口；
- 对 :ref:`pyape_toml` 进行详细配置；
- 阅读 :doc:`development` 文档。

部署项目
-------------

若配置文件中存在 ``prod`` 这个环境，可以使用 pyape deploy 命令将项目部署到远程服务器。

远程服务器配置参见配置文件中的 :ref:`pyape_toml_fabric` 段落。

::

    (venv) pyape deploy --env prod
    
启动项目/停止项目/重载项目
-------------------------------------

下面的命令使用 gunicorn 作为服务器。

::

    # 启动项目
    (venv) pyape start --env prod --server gunicorn
    
    # 停止项目
    (venv) pyape stop --env prod --server gunicorn

    # 优雅重载项目
    (venv) pyape reload --env prod --server gunicorn

部署并重载项目
----------------

在调试时经常需要部署并重载项目，使用 pyape dar 来执行这个操作。

dar = Deploy And Reload

下面的命令使用 gunicorn 作为服务器。

::

    (venv) pyape dar --env prod --server gunicorn


.. _gen_secret_key:

生成 SECRET_KEY
--------------------

``SECRET_KEY`` 是 Flask 程序必须包含的配置。
使用 :ref:`cli_pyape_gen` 命令可以生成一个标准的 ``SECRET_KEY``。

不带参数执行命令，可以生成 ``secret-key``： ::

    pyape gen
    {'secret-key': 'HK-VHH4C0ijLjOYBYrO7L2ACsmxcx9UClph-Q8lu3Hk=', 'nonce': 'ZmtcOPhm'}

生成后，将 ``secret-key`` 的值设置为环境变量。
如果项目名称为 ``sample``，开发环境为 ``local``，那么应该设置环境变量 ``SAMPLE_LOCAL_SECRET_KEY``： ::

    export SAMPLE_LOCAL_SECRET_KEY='HK-VHH4C0ijLjOYBYrO7L2ACsmxcx9UClph-Q8lu3Hk='

阅读 :ref:`pyape_toml_substitution` 了解 pyape 的环境变量替换机制。