"""
pyape.fastapi
----------------------

对 Fastapi 框架进行扩展。
"""
import logging
import warnings
from pathlib import Path
from typing import Any, NoReturn
from collections.abc import Iterable

from fastapi import FastAPI, APIRouter, Request
from fastapi.templating import Jinja2Templates
from starlette.templating import pass_context
from fastapi.staticfiles import StaticFiles
from starlette.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.cors import CORSMiddleware

from .error import ErrorCode, ConfigError
from .application import CreateArgument, PyapeApp
from .config import GlobalConfig
from .util.jinja_filter import jinja_filter_strftimestamp, jinja_filter_filesize


_default_create_arg = CreateArgument(
    FrameworkAppClass=FastAPI,
)


class PyapeAppFastAPI(PyapeApp):
    templates: Jinja2Templates = None

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

        self.framework_app = self.create_app()
        self.templates = self.create_templates()

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
        debug = self.gconf.getcfg('FASTAPI', 'DEBUG')
        warnings.warn(f'{self.create_arg=} {debug=}')
        app: FastAPI = FastAPIClass(debug=debug, title='pyape')

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
            warnings.warn(
                f'Mount StaticFiles {static_url_path=}, {static_folder=}, {default_static_name=}'
            )

        secret_key = self.gconf.getcfg(
            'FASTAPI', 'SECRET_KEY', default_value=self.gconf.getcfg('SECRET_KEY')
        )

        if not secret_key:
            raise ConfigError(
                'SECRET_KEY or FASTAPI.SECRET_KEY is not in config.toml!',
                ErrorCode.REQUIRED_CONF,
            )

        app.add_middleware(SessionMiddleware, secret_key=secret_key)
        warnings.warn(f'Add SessionMiddleware {secret_key=}')

        # 处理跨域
        cors = self.gconf.getcfg('CORS')
        if isinstance(cors, dict):
            lower_cors = {k.lower():v for k, v in cors.items()}
            app.add_middleware(CORSMiddleware, **lower_cors)

        return app

    def create_templates(self) -> Jinja2Templates:
        template_folder = self.gconf.getcfg(
            'PATH', 'TEMPLATE_FOLDER', default_value='template'
        )
        warnings.warn(f'create_templates {template_folder=}')

        jt = Jinja2Templates(directory=template_folder)

        @pass_context
        def get_flashed_messages(
            context: dict,
            with_categories: bool = False,
            category_filter: Iterable[str] = (),
        ) -> list[str] | list[tuple[str, str]]:
            """MIGRATE FROM FLASK

            Pulls all flashed messages from the session and returns them.
            Further calls in the same request to the function will return
            the same messages.  By default just the messages are returned,
            but when `with_categories` is set to ``True``, the return value will
            be a list of tuples in the form ``(category, message)`` instead.

            Filter the flashed messages to one or more categories by providing those
            categories in `category_filter`.  This allows rendering categories in
            separate html blocks.  The `with_categories` and `category_filter`
            arguments are distinct:

            * `with_categories` controls whether categories are returned with message
            text (``True`` gives a tuple, where ``False`` gives just the message text).
            * `category_filter` filters the messages down to only those matching the
            provided categories.

            See :doc:`/patterns/flashing` for examples.

            .. versionchanged:: 0.3
            `with_categories` parameter added.

            .. versionchanged:: 0.9
                `category_filter` parameter added.

            :param with_categories: set to ``True`` to also receive categories.
            :param category_filter: filter of categories to limit return values.  Only
                                    categories in the list will be returned.
            """
            session = context['request'].session
            flashes = session.pop("_flashes") if "_flashes" in session else []
            if category_filter:
                flashes = list(filter(lambda f: f[0] in category_filter, flashes))
            if not with_categories:
                return [x[1] for x in flashes]
            return flashes

        # 将 flask 的 get_flashed_messages 方法移植过来
        jt.env.globals[get_flashed_messages.__name__] = get_flashed_messages
        # 加入 strftimestamp filter
        jt.env.filters['strftimestamp'] = jinja_filter_strftimestamp
        jt.env.filters['filesize'] = jinja_filter_filesize
        return jt

    def flash(
        self, request: Request, message: str, category: str = "message"
    ) -> NoReturn:
        """MIGRATE FROM FLASK

        Flashes a message to the next request.  In order to remove the
        flashed message from the session and to display it to the user,
        the template has to call :func:`get_flashed_messages`.

        .. versionchanged:: 0.3
        `category` parameter added.

        :param message: the message to be flashed.
        :param category: the category for the message.  The following values
                        are recommended: ``'message'`` for any kind of message,
                        ``'error'`` for errors, ``'info'`` for information
                        messages and ``'warning'`` for warnings.  However any
                        kind of string can be used as category.
        """
        # Original implementation:
        #
        #     session.setdefault('_flashes', []).append((category, message))
        #
        # This assumed that changes made to mutable structures in the session are
        # always in sync with the session object, which is not true for session
        # implementations that use external storage for keeping their keys/values.
        flashes = request.session.get("_flashes", [])
        flashes.append((category, message))
        request.session["_flashes"] = flashes

    def render_template(
        self,
        template_name: str,
        status_code: int = 200,
        /,
        **context: Any,
    ) -> str:
        """Render a template by name with the given context.

        :param template_name: The name of the template to render.
        :param context: The variables to make available in the template.
        """
        return self.templates.TemplateResponse(
            template_name, context, status_code=status_code
        )

    def register_a_router(self, router_obj: APIRouter, url_prefix: str):
        app: FastAPI = self.app
        app.include_router(router_obj, prefix=url_prefix)

    def add_middleware(self, middleware_class: type, **options: Any) -> None:
        self.app.add_middleware(middleware_class, **options)

    def append_middleware(self, middleware_class: type, **options: Any) -> None:
        fast_app: FastAPI = self.app
        if fast_app.middleware_stack is not None:  # pragma: no cover
            raise RuntimeError("Cannot add middleware after an application has started")
        fast_app.user_middleware.append(Middleware(middleware_class, **options))

    def get_loggers(self) -> list[logging.Logger]:
        from fastapi.logger import logger

        # del logger.handlers[:]
        return [logger]
