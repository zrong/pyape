import json
from typing import Any, Callable
import httpx
import asyncio


class ResponseValue:
    """ 封装 HTTP 响应数据。"""
    error: bool = False
    code: int = 200
    message: str = None

    value: dict = None
    httpx_response: httpx.Response = None
    request_value = None

    def __init__(self,
                 message: str = None,
                 *,
                 error: bool = None,
                 code: int = None,
                 value: dict = None,
                 httpx_response: httpx.Response = None,
                 request_value=None,
                 **kwargs) -> None:
        self.message = message
        # 不提供 message，也不提供 error，就是无错误 error=False, code=200
        if self.message is None:
            self.error = False if error is None else error
            self.code = 200 if code is None else code
        else:
            self.error = error
            self.code = code
        if self.error is None:
            self.error = True
        if self.code is None:
            self.code = 444

        self.value = value or {}
        self.httpx_response = httpx_response
        self.request_value = request_value
        if kwargs:
            self.value.update(kwargs)

    @property
    def text(self) -> str:
        if self.httpx_response:
            return self.httpx_response.text
        return None

    @property
    def content(self) -> bytes:
        if self.httpx_response:
            return self.httpx_response.content
        return None

    @property
    def headers(self) -> bytes:
        if self.httpx_response:
            return self.httpx_response.headers
        return None

    def get_value(self, key: str) -> Any:
        """ 获取 values 对象中保存的数据。"""
        if not self.value:
            return None
        return self.value.get(key)

    def to_dict(self,
                plain_value: bool = False,
                value_keyname: str = 'value',
                include_request_value: bool = False) -> dict:
        """ 将 ResponeValue 的数据作为 dict 导出。

        :param plain_value: 将 value 的值拉平。
        :param value_keyname: 指示 ResponseValue 中的 value 对象，在 dict 中的键名。
            若 plain_value 为 True，则这个值无效。
        """
        d = {
            'error': self.error,
            'code': self.code,
        }
        if self.message:
            d['message'] = self.message
        if self.value:
            if plain_value:
                d.update(self.value)
            else:
                d[value_keyname] = self.value
        if self.request_value and include_request_value:
            d['request_value'] = self.request_value.request_args
        return d

    def parse_and_merge_json(self,
                             *,
                             data_keyname: str = 'data',
                             code_keyname: str = 'code',
                             message_keyname: str = 'msg',
                             success_code_values: tuple[Any] = (0, 200, None),
                             value_keyname: str = 'value',
                             plain_value: bool = False) -> dict:
        """ 解析 http 响应中的 json 返回，将其中的有效数据合并到 ResponseValue 中。

        json 中一般会封装一个键名用于表现数据。以抖音 API 的返回为例：
        https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/server/interface-request-credential/get-access-token/
        >>> {
        >>>    "err_no": 40017,
        >>>    "err_tips": "bad secret",
        >>>    "data": {
        >>>             "access_token": "",
        >>>             "expires_in": 0
        >>>    }
        >>> }
        在上例中，data_keyname=data, code_keyname=err_no, message_keyname=err_tips。

        根据微信 API 文档，success_code_values 应该包含 None 这个值。
        > 注意：当API调用成功时，部分接口不会返回 errcode 和 errmsg，只有调用失败时才会返回。
        https://developers.weixin.qq.com/minigame/dev/guide/base-ability/backend-api.html

        :param data_keyname: api 返回的数据键名。
        :param code_keyname: api 返回的错误码键名。
        :param message_keyname: api 返回的错误消息键名。
        :param success_code_values: 哪些错误码代表调用成功。默认值为 (0, 200, None)。
        :param value_keyname: 同 to_dict() 定义。
        :param plain_value: 同 to_dict() 定义。
        """
        try:
            parsed_json = self.httpx_response.json()
            if parsed_json.get(code_keyname) is not None:
                self.code = parsed_json.get(code_keyname)
            # 代表上一步请求的 http 调用错误，也可能是解析后的 json 中有错误码
            if not self.code in success_code_values:
                self.error = True
                if parsed_json.get(message_keyname):
                    self.message = parsed_json.get(message_keyname)
            if data_keyname is None or parsed_json.get(data_keyname) is None:
                self.value = parsed_json
            else:
                self.value = parsed_json.get(data_keyname)
            return self.to_dict(plain_value=plain_value,
                                value_keyname=value_keyname)
        except Exception as e:
            self.error = True
            self.code = 500
            self.message = f'{e=}, {self.httpx_response.text=}' if self.httpx_response else str(
                e)

        return self.to_dict(plain_value=True)

    def __repr__(self) -> str:
        return f'<mjp.http.ResponseValue>{self.to_dict()}'


class RequestValue:
    """ 封装 HTTP 请求数据。"""

    method: str = None
    """ 请求方法。"""

    url: str = None
    """ 请求路径。"""

    url_map: dict = None
    """ 若存在，执行 url = url.format_map(url_map) 。"""

    value: dict = None
    """ 请求值，在 GET 的时候作为 params，在 post 的时候作为 data。"""

    headers: dict = None
    """ 请求头。"""

    is_json: bool = False
    """ 代表这次使用 json 请求。"""

    check_response: Callable[[httpx.Response], ResponseValue] = None
    """ check_response 接收一个 httpx.Response 参数，返回 ResponseValue，用于下一步处理。"""

    after_response: Callable = None
    """ after_response 保存期待在获得 ResponseValue 之后再调用的方法。
    check_response 可以修改原始的 httpx.Respone，
    而 after_response 更加灵活，对参数和返回值都不做限制。
    """

    kwargs: dict = None

    def __init__(self,
                 *,
                 url: str,
                 method: str = 'GET',
                 value: dict = None,
                 url_map: dict = None,
                 headers: dict = None,
                 is_json: bool = False,
                 check_response: Callable[[httpx.Response],
                                          ResponseValue] = None,
                 after_response: Callable = None,
                 **kwargs) -> None:
        self.url = url
        self.url_map = url_map
        self.value = value
        self.method = method
        self.headers = headers
        self.is_json = is_json
        self.check_response = check_response
        self.after_response = after_response

        # 支持更多数据
        self.kwargs = kwargs
        self.check_validity()

    def check_validity(self):
        if None in (self.method, self.url):
            raise ValueError(
                f'{self.__class__.__name__} [url={self.url}, method={self.method}] is necessary.'
            )

    @property
    def request_args(self) -> dict:
        """ 获取 httpx.request 的请求参数。
        
        注意，当进行 json 请求的时候，不要使用 api 提供的 httpx.post(json=...)，
        而是使用 httpx.post(content=..., headers={'Content-Type': 'application/json'})。
        因为其默认使用 ensure_ascii=True，会导致中文变成 unicode 编码。
        见： httpx._content.encode_json 被 encode_request 调用。注意，requests 库亦如此。
        在这种情况下，微信 API 会报错：
        {'errcode': 40033, 'errmsg': 'invalid charset. please check your request, if include \\uxxxx will create fail! hint: [I1T390898vr29]', 'error': True, 'code': 502, 'message': '40033(invalid charset. please check your request, if include \\uxxxx will create fail! hint: [I1T390898vr29])'}

        原因可能如下，转换成 ascii 码之后，实际的 byte 是不同的。
        
        >>> name = 'zrong曾嵘'
        >>> json.dumps(name, ensure_ascii=False).encode('utf-8')
        >>> b'"zrong\xe6\x9b\xbe\xe5\xb5\x98"'
        >>> json.dumps(name, ensure_ascii=True).encode('utf-8')
        >>> b'"zrong\\u66fe\\u5d58"'
        >>> json.dumps(name, ensure_ascii=True)
        >>> '"zrong\\u66fe\\u5d58"'
        """
        p = {
            'method': self.method,
            'url': self.url,
            'headers': self.headers,
        }
        if isinstance(self.url_map, dict):
            p['url'] = self.url.format_map(self.url_map)
        if self.method == 'GET':
            p['params'] = self.value
        elif self.is_json:
            headers = {'Content-Type': 'application/json'}
            if self.headers:
                self.headers.update(headers)
            else:
                self.headers = headers
            p['content'] = json.dumps(self.value, ensure_ascii=False)
            p['headers'] = self.headers
        else:
            p['data'] = self.value
        if self.kwargs:
            for k, v in self.kwargs.items():
                p[k] = v
        return p

    def __repr__(self) -> str:
        return f'<mjp.http.RequestValue>{self.request_args}'


class HTTPxMixIn:
    """ 需要 http 请求功能的类，可以混合这个类，以提供自己的 http 请求功能。
    当然也可以使用继承或者组合的方式使用。支持异步和同步调用。

    比较几种回调的区别：

    - RequestValue.check_response(httpx.Response)
        在 **每次** HTTP 请求成功之后调用。传递的参数是 httpx.Response 对象。
        这里的请求成功代表的是 HTTP 请求成功(http_status=200)，
        而非实际语义上 API 的调用成功（因为可能存在参数错误等等）
        异步和同步调用，均可在 RequestValue 中包含这个回调方法。

        在同步调用时，HTTPxMixIn.get 和 HTTPxMixIn.post 只有一次请求，
        可以通过对同步方法返回的 ResponseValue.httpx_response 对象进行处理代替对 httpx.Response 的处理。
        因此在 HTTPxMixIn.get 和 HTTPxMixIn.post 中没有包含 check_response 参数传递。

    - HTTPxMixIn *_async(callback) 中的 callback
        在 **每组** 异步 HTTP 请求成功之后调用。传递的参数是 ResponseValue 或者 list[ResponseValue]。
        同步 HTTP 方法不支持 callback，因为直接使用 return 更高效（request_once_sync/request_sync就是这么做的） 。
        注意在使用 request_once_async_wait_run 进行调用的时候（也就是 get_async 和 post_async 采用的方法），
        传递给 callback 的参数是 ResponseValue，因为即使是异步，也只有一次 http 调用。
        使用 request_async_wait_run 进行调用的时候，传递的参数是 list[ResponseValue]。

    - RequestValue.after_response(ResponseValue)
        一般在 HTTPxMixIn *_async(callback) 的 callback 中调用。
        亦可在获得 Respone 之后的任何时刻调用，这取决于使用场景。

        下面是一个场景：

        在 **一组** 异步调用完成之后，可能需要一些对于请求的清理工作。
        check_response 并不适合做这个清理工作，因为它的参数是 httpx.Respone，此时还没有对 http 返回的值做分析。
        after_response 可以在分析完毕之后再处理，它更加灵活，对参数和返回值都不做限制。
        在一组异步请求之后，如果需要分析这一组返回的信息，并于其他信息进行比较，用 after_response 更合适。
    

    如何选择回调方式：

        check_response 是在 **一次 http 请求** 完成后回调，而 callback 是在 **一组 http 请求** 完成之后回调。
        可以根据回调执行的及时性来决定使用哪一种。

        check_response 是在异步线程中执行的。在这里处理，无法与其它处理结果进行比较。
        callback 则返回到主线程执行。因为已经获取了所有的返回，方便整体处理。
        此时在 callback 中调用 after_response 就是一个合理的选择。
    """
    _client_sync: httpx.Client = None
    """ 同步版本的 client。"""

    _request_values: list[RequestValue] = None

    is_async: bool = False

    method: str = None
    """ 公用方法，若请求不提供 method 则使用这个值。"""

    url: str = None
    """ 公用 url，若请求不提供 url 则使用这个值。"""

    url_map: dict = None
    """ 用于替换 url 中的 map 占位符。"""

    headers: dict = None

    def __init__(self,
                 is_async: bool = False,
                 *,
                 url: str = None,
                 method: str = 'GET',
                 url_map: dict = None,
                 headers: dict = None) -> None:
        self.is_async = is_async
        self.url = url
        self.method = method
        self.url_map = url_map
        self.headers = headers
        self._request_values = []

        if not self.is_async:
            self._client_sync = httpx.Client()

    def clear_request_values(self):
        """ 清除保存的请求队列。"""
        self._request_values = []

    def build_request_value(self,
                            rv: RequestValue = None,
                            *,
                            url: str = None,
                            method: str = None,
                            value: dict = None,
                            url_map: dict = None,
                            headers: dict = None,
                            is_json: bool = False,
                            check_response: Callable[[httpx.Response],
                                                     ResponseValue] = None,
                            after_response: Callable = None,
                            insert_to_list: bool = False,
                            **kwargs):
        """ 返回一个 RequestValue 对象。

        :param insert_to_list: 是否插入请求队列，默认值为 true。
        """
        if isinstance(rv, RequestValue):
            # 传入的参数还要再检查一次数据可用性。
            rv.check_validity()
        else:
            method = method or self.method
            url = url or self.url
            url_map = url_map or self.url_map
            headers = headers or self.headers
            rv = RequestValue(url=url,
                              value=value,
                              method=method,
                              url_map=url_map,
                              is_json=is_json,
                              check_response=check_response,
                              after_response=after_response,
                              **kwargs)
        if insert_to_list:
            self._request_values.append(rv)
        return rv

    def request_once_sync(self, rv: RequestValue) -> ResponseValue:
        """ 同步请求一次。"""
        try:
            http_resp = self._client_sync.request(**rv.request_args)
            # 同步请求很少会使用 check_response，更多是接受返回的 ResponseValue，
            # 然后对其 httpx_response 属性进一步处理。
            if rv.check_response is None:
                return ResponseValue(httpx_response=http_resp, request_value=rv)
            else:
                return rv.check_response(http_resp)
        except httpx.HTTPStatusError as e:
            return ResponseValue(message=str(e),
                                 error=True,
                                 code=e.response.status_code,
                                 httpx_response=e.response,
                                 request_value=rv)
        except httpx.HTTPError as e:
            return ResponseValue(message=str(e),
                                 error=True,
                                 code=400,
                                 request_value=rv)
        except Exception as e:
            return ResponseValue(message=str(e),
                                 error=True,
                                 code=500,
                                 request_value=rv)

    def request_sync(self) -> list[ResponseValue]:
        """ 同步请求队列，返回调用结果 list。"""
        resp_data = []
        for rv in self._request_values:
            resp_data.append(self.request_once_sync(rv))
        return resp_data

    def get(self,
            url: str = None,
            value: dict = None,
            *,
            url_map: dict = None,
            headers: dict = None,
            **kwargs) -> ResponseValue:
        """ 发送一次同步 get 请求。"""
        if self.is_async:
            raise ValueError(
                f'{self.__class__.__name__}.get cannot use in async mode!')
        rv = self.build_request_value(url=url,
                                      value=value,
                                      url_map=url_map,
                                      method='GET',
                                      headers=headers,
                                      is_json=False,
                                      insert_to_list=False,
                                      **kwargs)
        return self.request_once_sync(rv)

    def post(self,
             url: str = None,
             value: dict = None,
             *,
             url_map: dict = None,
             headers: dict = None,
             is_json: bool = True,
             **kwargs) -> ResponseValue:
        """ 发送一次同步 post 请求。"""
        if self.is_async:
            raise ValueError(
                f'{self.__class__.__name__}.post cannot use in async mode!')
        rv = self.build_request_value(url=url,
                                      value=value,
                                      url_map=url_map,
                                      headers=headers,
                                      method='POST',
                                      is_json=is_json,
                                      insert_to_list=False,
                                      **kwargs)
        return self.request_once_sync(rv)

    async def request_once_async(self, client: httpx.AsyncClient,
                                 rv: RequestValue) -> ResponseValue:
        """ 异步请求一次。"""
        try:
            http_resp = await client.request(**rv.request_args)
            if rv.check_response is None:
                return ResponseValue(httpx_response=http_resp, request_value=rv)
            else:
                return rv.check_response(http_resp)
        except httpx.HTTPStatusError as e:
            return ResponseValue(message=str(e),
                                 error=True,
                                 code=e.response.status_code,
                                 httpx_response=e.response,
                                 request_value=rv)
        except httpx.HTTPError as e:
            return ResponseValue(message=str(e),
                                 error=True,
                                 code=400,
                                 request_value=rv)
        except Exception as e:
            return ResponseValue(message=str(e),
                                 error=True,
                                 code=300,
                                 request_value=rv)

    async def request_async_wait_run(self,
                                     callback: Callable[[list[ResponseValue]],
                                                        None] = None):
        """ 异步请求队列，使用 callback 来处理一组 http 响应。"""
        async with httpx.AsyncClient() as client:
            tasks = []
            for rv in self._request_values:
                tasks.append(
                    asyncio.ensure_future(self.request_once_async(client, rv)))

            response_values = await asyncio.gather(*tasks)
            if callback:
                callback(response_values)

    async def request_once_async_wait_run(self,
                                          rv: RequestValue,
                                          callback: Callable[[ResponseValue],
                                                             None] = None):
        """ 异步请求一次，使用 callback 来处理这一次 http 响应。"""
        async with httpx.AsyncClient() as client:
            response_value = self.request_once_async(client, rv)
            if callback:
                callback(response_value)

    def request_async(self,
                      callback: Callable[[list[ResponseValue]], None] = None):
        """ 批量调用异步请求，并传递一个 callback 用于处理 http 响应。"""
        asyncio.run(self.request_async_wait_run(callback))

    def post_async(self,
                   url: str = None,
                   value: dict = None,
                   *,
                   url_map: dict = None,
                   headers: dict = None,
                   is_json: bool = True,
                   callback: Callable[[ResponseValue], None] = None,
                   **kwargs):
        """ 发送一次异步 post 请求。"""
        if not self.is_async:
            raise ValueError(
                f'{self.__class__.__name__}.post_async cannot use in sync mode!'
            )
        rv = self.build_request_value(url=url,
                                      method='POST',
                                      value=value,
                                      url_map=url_map,
                                      headers=headers,
                                      is_json=is_json,
                                      insert_to_list=False,
                                      **kwargs)
        asyncio.run(self.request_once_async_wait_run(rv, callback))

    def get_async(self,
                  url: str = None,
                  value: dict = None,
                  *,
                  url_map: dict = None,
                  headers: dict = None,
                  callback: Callable[[ResponseValue], None] = None,
                  **kwargs):
        """ 发送一次异步 get 请求。"""
        if not self.is_async:
            raise ValueError(
                f'{self.__class__.__name__}.get_async cannot use in sync mode!'
            )
        rv = self.build_request_value(url=url,
                                      method='GET',
                                      value=value,
                                      url_map=url_map,
                                      headers=headers,
                                      is_json=False,
                                      insert_to_list=False,
                                      **kwargs)
        asyncio.run(self.request_once_async_wait_run(rv, callback))
