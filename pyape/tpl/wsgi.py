# -*- coding: utf-8 -*-

from pathlib import Path
import pyape 


appdir = Path(__file__).parent.resolve()

@pyape.init_decorator(basedir=appdir)
def create_app(pyape_app, gdb):
    # 在这里导入 app.models
    # import app.models
    # 创建用户数据库的 Model
    # app.models.create_user_tables()
    # 创建所有数据库
    # gdb.create_all()
    # pyape_app.shell_context_processor(lambda: {'gdb': gdb})
    return pyape_app
