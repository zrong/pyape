命令行
=================

参考 :ref:`install` 安装最新版本，使用下面的命令行进行操作。

pyape
-------------------
::
    
    Usage: pyape [OPTIONS] COMMAND [ARGS]...

      管理和部署使用 pyape 构建的项目。

    Options:
      --help  Show this message and exit.

    Commands:
      config       「本地」生成配置文件。
      copy         「本地」复制 pyape 配置文件到当前项目中
      dar          「远程」在服务器上部署代码，然后执行重载。也就是 deploy and reload 的组合。
      deploy       「远程」部署项目到远程服务器。
      gen          「本地」生成器，生成一个 Flask 可用的 SECRET_KEY，一个 NONCE 字符串，和一个加盐密码。
      init         「本地」初始化 pyape 项目
      pipoutdated  「远程」打印所有的过期的 python package。
      putconf      「远程」生成并上传配置文件到远程服务器。
      reload       「远程」在服务器上重载项目进程。
      setup        「本地」创建 pyape 项目运行时必须的环境，例如数据库建立等。需要自行在项目根文件夹创建 setup.py。
      start        「远程」在服务器上启动项目进程。
      stop         「远程」在服务器上停止项目进程。
      supervisor   「本地」生成 Supervisor 需要的配置文件。
      top          「远程」展示 uwsgi 的运行情况。
      venv         「远程」部署远程服务器的虚拟环境。

.. _cli_pyape_init:

pyape init
--------------------

::
    
    Usage: pyape init [OPTIONS]

      「本地」初始化 pyape 项目

    Options:
      -C, --cwd DIRECTORY  工作文件夹。
      -F, --force          覆盖已存在的文件
      --help               Show this message and exit.

.. _cli_pyape_config:

pyape config
-------------------

::
    
    Usage: pyape config [OPTIONS]
                              [[.env|uwsgi.ini|gunicorn.conf.py|config.toml]]...

      「本地」生成配置文件。

    Options:
      -C, --cwd DIRECTORY  工作文件夹。
      -E, --env TEXT       输入支持的环境名称。  [required]
      -P, --env_postfix    在生成的配置文件名称末尾加上环境名称后缀。
      -F, --force          是否强制替换已存在的文件。
      --help               Show this message and exit.
      
.. _cli_pyape_copy:

pyape copy
-------------------

::
      
    Usage: pyape copy [OPTIONS] [NAME]...

      「本地」复制 pyape 配置文件到当前项目中

    Options:
      -C, --cwd DIRECTORY  工作文件夹，也就是复制目标文件夹。
      -F, --force          覆盖已存在的文件
      -R, --rename         若目标文件存在则重命名
      --help               Show this message and exit.
      
.. _cli_pyape_deploy:

pyape deploy
------------------

::
    
    Usage: pyape deploy [OPTIONS]

      「远程」部署项目到远程服务器。

    Options:
      -C, --cwd DIRECTORY  工作文件夹。
      -E, --env TEXT       输入支持的环境名称。  [required]
      --help               Show this message and exit.

.. _cli_pyape_venv:

pyape venv
-------------------

::

    Usage: pyape venv [OPTIONS] [UPGRADE]...

      「远程」部署远程服务器的虚拟环境。

    Options:
      -C, --cwd DIRECTORY  工作文件夹。
      -E, --env TEXT       输入支持的环境名称。  [required]
      -I, --init           是否初始化虚拟环境。
      --help               Show this message and exit.
      
.. _cli_pyape_start:

pyape start
-----------------

::

    Usage: pyape start [OPTIONS]

      「远程」在服务器上启动项目进程。

    Options:
      -C, --cwd DIRECTORY  工作文件夹。
      -E, --env TEXT       输入支持的环境名称。  [required]
      --help               Show this message and exit.


.. _cli_pyape_stop:

pyape stop
---------------

::

    Usage: pyape stop [OPTIONS]

      「远程」在服务器上停止项目进程。

    Options:
      -C, --cwd DIRECTORY  工作文件夹。
      -E, --env TEXT       输入支持的环境名称。  [required]
      --help               Show this message and exit.

.. _cli_pyape_reload:

pyape reload
---------------

::

    Usage: pyape reload [OPTIONS]

      「远程」在服务器上重载项目进程。

    Options:
      -C, --cwd DIRECTORY  工作文件夹。
      -E, --env TEXT       输入支持的环境名称。  [required]
      --help               Show this message and exit.
