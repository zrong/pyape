"""
pyape.fastapi
----------------------

对 Fastapi 框架进行扩展。
"""
import logging
from pathlib import Path

from fastapi import FastAPI, APIRouter
from fastapi.staticfiles import StaticFiles
from pyape.application import CreateArgument, PyapeApp
from pyape.config import GlobalConfig


_default_create_arg = CreateArgument(
    FrameworkAppClass=FastAPI,
)


class PyapeAppFastAPI(PyapeApp):
    def __init__(
        self,
        gconf: GlobalConfig,
        create_arg: CreateArgument = None,
        package_name: str = 'pyape.app',
    ) -> None:
        super().__init__(gconf, create_arg, package_name)

        if self.create_arg is None:
            self.create_arg = CreateArgument(_default_create_arg)
        else:
            merge_args = CreateArgument(_default_create_arg)
            merge_args.update(self.create_arg)
            self.create_arg = merge_args

        print(f'{self.create_arg=}')

        self.framework_app = self.create_app()

        self.init_db()
        self.init_redis()
        self.init_cache()
        self.init_logger()

        if self.create_arg and self.create_arg.init_app_method:
            self.create_arg.init_app_method(self)

        # Router 要 import gdb，因此要在 gdb 之后注册
        self.register_routers()

    @property
    def debug(self) -> bool:
        return self.app.debug

    def create_app(self) -> FastAPI:
        FastAPIClass = self.create_arg.FrameworkAppClass
        print(f'create_app {self.create_arg=}')
        app: FastAPI = FastAPIClass()

        # 挂载静态文件，设置默认名称
        # 若没有提供文件夹设置，文件夹名称也使用相同的名称
        default_static_name = 'static'
        static_url_path = self.gconf.getcfg('PATH', 'STATIC_URL_PATH')
        static_folder = self.gconf.getcfg(
            'PATH', 'STATIC_FOLDER', default_value=default_static_name
        )
        if static_url_path is not None:
            app.mount(
                static_url_path,
                StaticFiles(directory=Path(static_folder)),
                name=default_static_name,
            )
        return app

    def register_a_router(self, router_obj: APIRouter, url_prefix: str):
        app: FastAPI = self.app
        app.include_router(router_obj, prefix=url_prefix)

    def get_loggers(self) -> list[logging.Logger]:
        from fastapi.logger import logger
        # del logger.handlers[:]
        return [logger]