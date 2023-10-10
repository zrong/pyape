"""
pyape.util.warning
~~~~~~~~~~~~~~~~~~~

提供调用警告接口，或者记录重要历史消息。
"""
import logging
from collections.abc import Callable

from datetime import datetime
from pyape.config import GlobalConfig
from pyape.cache import GlobalCache
from pyape.http import HTTPxMixIn, ResponseValue
from pyape.error import ConfigError, ErrorCode


class SendWarning(HTTPxMixIn):
    """发送报警消息。支持飞书机器人，企业微信机器人，企业微信自建应用。"""

    appname: str = None
    botname: str = None

    logger: logging.Logger = None
    gconfig: GlobalConfig = None
    gcache: GlobalCache = None

    def __init__(
        
        self,
        logger: logging.Logger,
        gconf: GlobalConfig,
        gcache: GlobalCache,
        *,
        appname: str = 'FEISHU',
        botname: str = 'OPT_ALARM',
        is_async: bool = True,
    ) -> None:
        # 使用异步调用 http
        super().__init__(is_async)
        self.logger = logger
        self.gconfig = gconf
        self.gcache = gcache

        self.appname = appname
        self.botname = botname

    def send2_webhook(
        self,
        content: dict,
        url_map: dict = None,
        callback: Callable[[ResponseValue], None] = None,
    ) -> ResponseValue | None:
        api_url = self.gconfig.getcfg('WEBHOOK', self.appname, self.botname)
        if self.is_async:
            self.post_async(
                api_url, content, url_map=url_map, is_json=True, callback=callback
            )
            return None
        return self.post(api_url, content, url_map=url_map, is_json=True)

    def send2_feishu_bot(
        self,
        content: str | dict,
        msgtype: str = 'text',
        callback: Callable[[ResponseValue], None] = None,
    ) -> ResponseValue | None:
        """向飞书群自定义机器人发送消息。

        https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
        https://open.feishu.cn/document/tools-and-resources/message-card-builder

        :param msg_type: test/post/template 其中 template 就是 interactive 的模板支持。
            当 msg_type 为 template 时， content 必须为 dict，格式如下
            >>> {
            >>>     "template_id":"ctp_xxxxxxxxxxxx",//卡片id，参数必填。可在搭建工具中通过“复制卡片ID”获取
            >>>     "template_variable":
            >>>     {
            >>>         //卡片中绑定的变量的取值。如没有绑定变量，可不填此字段。
            >>>     }
            >>> }
        :param content: 可能为 str 或者 dict，根据 msg_type 有不同的值。
        """
        title: str = None
        data: dict = None
        match msgtype:
            case 'text':
                data = {
                    'msg_type': msgtype,
                    'content': {
                        'text': content.get('content')
                        if isinstance(content, dict)
                        else content
                    },
                }
            case 'post':
                content_field = []
                if isinstance(content, str):
                    content_field.append([{"tag": "text", "text": content}])
                    title = 'MJP2飞书机器人消息'
                elif isinstance(content, dict):
                    title = content.get('title')
                    c = content.get('content')
                    if isinstance(c, str):
                        content_field.append([{"tag": "text", "text": c}])
                    elif isinstance(c, list):
                        content_field.extend(c)
                    else:
                        raise ValueError(
                            f'post 消息 content 键类型应为 str/list，当前为 {type(c)=}。'
                        )
                else:
                    raise ValueError('post 消息类型仅支持 str/dict。')
                content_field.append(
                    [
                        {
                            'tag': 'text',
                            'text': datetime.now().isoformat(),
                        }
                    ]
                )
                data = {
                    'msg_type': 'post',
                    "content": {
                        "post": {"zh_cn": {"title": title, "content": content_field}}
                    },
                }
            case 'template':
                if not isinstance(content, dict) or not 'template_id' in content.keys():
                    raise ValueError(
                        'template 消息必须为包含 template_id 和 template_variable 的 dict！'
                    )
                data = {
                    'msg_type': 'interactive',
                    'card': {'type': "template", 'data': content},
                }
        if data is None:
            raise ValueError('data 未构建。')
        return self.send2_webhook(data, callback=callback)

    def send2_workwechat_bot(
        self,
        content: str,
        mentioned_list: list = ['@all'],
        msgtype: str = 'text',
    ) -> ResponseValue | None:
        """向企业微信机器人发送消息。

        调用返回的格式如下：
        {
            "errcode": 0,
            "errmsg": "ok"
        }

        @deprated 2023-05-04 zrong 不再使用企业微信机器人。
        """
        data = {
            'msgtype': msgtype,
            msgtype: {
                'content': datetime.now().isoformat() + '\n' + content,
                'mentioned_list': mentioned_list,
            },
        }
        return self.send2_webhook(data)


def send_warning(
    content: dict,
    logger: logging.Logger,
    gconf: GlobalConfig,
    gcache: GlobalCache,
    callback: Callable[[ResponseValue], None] = None,
):
    default_webhook = gconf.getcfg('WEBHOOK', 'DEFAULT')
    if isinstance(default_webhook, dict):
        for k in ('APP_NAME', 'BOT_NAME', 'IS_ASYNC'):
            if not k in default_webhook.keys():
                raise ConfigError(
                    f'需要在 WEBHOOK.DEFAULT 下同时提供 APP_NAME, BOT_NAME, IS_ASYNC 配置！', ErrorCode.WEBHOOK
                )
    else:
        raise ConfigError(f'必须提供 WEBHOOK.DEFAULT 配置！', ErrorCode.WEBHOOK)

    msgtype = content.pop('msgtype', 'text')

    appname = content.pop('appname', None)
    botname = content.pop('botname', None)
    is_async = content.pop('is_async', None)
    if appname is None:
        appname = default_webhook['APP_NAME']
    if botname is None:
        botname = default_webhook['BOT_NAME']
    if is_async is None:
        is_async = default_webhook['IS_ASYNC']
        # 测试调用机器人数据
        # is_async = False
    sw = SendWarning(
        logger, gconf, gcache, appname=appname, botname=botname, is_async=is_async
    )
    # print(f'send_warning {appname=} {botname=} {msgtype=} {content=}')
    match (appname):
        case 'FEISHU':
            succ = sw.send2_feishu_bot(content, msgtype, callback)
            # 若 is_async 为 True，这里返回总是 None
            # print(f'{succ.to_dict(include_request_value=True)=}')
            return succ
        case 'WORK_WECHAT':
            mentioned_list = content.pop('mentioned_list', ['@all'])
            return sw.send2_workwechat_bot(
                content['content'], mentioned_list, msgtype
            )
        case 'DEFAULT':
            url_map = content.pop('url_map', None)
            return sw.send2_webhook(content, url_map, callback)
    return None
