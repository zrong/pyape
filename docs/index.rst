.. PYAPE documentation master file, created by
   sphinx-quickstart on Wed Mar  2 11:27:16 2022.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

PYAPE 文档
================================

PYAPE ``[paɪp]`` = A Application Programming Environment of Python.

Pyape 是我在开发 Flask 应用程序过程中积累的一个开发框架。准确的说，这不算一个框架，而是一组集合。
我将开发 Web 以及 API 应用程序过程中积累的一些好用的工具和常用功能进行了简单的封装，整合在一起，
方便快速启动一个新项目。

**Pyape 的特点如下：**

集成命令行
---------------

通过对 `Fabric`_ 的集成，使用统一的命令行工具来实现如下功能：

#. 生成配置文件
#. 将程序部署到远程服务器
#. 控制远程服务器的运行

详细说明请阅读： :doc:`command`。

多环境支持
-------------

可配置多套开发环境，方便同时支持本地开发、局域网开发、互联网测试和正式服部署。

详细说明请阅读： :doc:`configuration`。

模版支持与配置合并
----------------------------

pyape 的命令行工具支持多级配置合并，方便在多个配置中共用数据，不必重复输入配置。

pyape 允许自定义配置生成模版。

环境变量支持
-----------------

pyape 的配置文件模版机制支持从环境变量中获取实际值，这样可以避免将敏感信息写入配置文件提交到 CVS 造成安全隐患。

SQLAlchemy 支持
-----------------------

Pyape 集成了 `SQLAlchemy`_ 支持。与 `Flask-SQLAlchemy`_ 不同，Pyape 直接使用标准的 SQLAlchemy 语法。
这更加方便升级到未来的 SQLAlchemy 2.0 版本。

`Use Flask and SQLalchemy, not Flask-SQLAlchemy <https://towardsdatascience.com/use-flask-and-sqlalchemy-not-flask-sqlalchemy-5a64fafe22a4?gi=dd7c37dae9bf>`_ 
这篇文章的观点，我也是赞同的。

Redis 支持
---------------

基于 `flask-redis <https://github.com/underyx/flask-redis>`_ 修改，使其支持多个 Redis 数据库。

Logging 集成
---------------

支持 ZeroMQHandler、RedisHandler，
提供 get_logger 和 get_logging_handler 方便从配置中直接生成 Logger 和 Handler 对象。
详情参见 :ref:`pyape_logging` 。


.. toctree::
   :maxdepth: 2
   :caption: 目录:
   
   usage
   command
   development
   dependent
   architecture
   configuration
   deploy
   reference

   
.. _SQLAlchemy: https://www.sqlalchemy.org/
.. _FLASK-SQLAlchemy: https://flask-sqlalchemy.palletsprojects.com/
.. _Fabric: https://www.fabfile.org/