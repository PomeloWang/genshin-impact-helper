import abc
import json
import os
import sys

import requests

from settings import *

__all__ = ['Notify']


class Sender(abc.ABC):
    @staticmethod
    def to_python(json_str: str):
        return json.loads(json_str)

    @staticmethod
    def to_json(obj):
        return json.dumps(obj, indent=4, ensure_ascii=False)

    @abc.abstractmethod
    def send(self, title, message):
        """please implemente in subclass"""


class ServerChan(Sender):
    def send(self, title, message):
        secret = os.environ.get('SCKEY', '')
        if not secret:
            log.info("未配置SCKEY,正在跳过推送")
            return

        if isinstance(message, list) or isinstance(message, dict):
            message = self.to_json(message)

        log.info("准备推送通知...")

        server_chan_api = f'https://sc.ftqq.com/{secret}.send'
        payload = {'text': f'{title}', 'desp': message}

        response = self.to_python(requests.Session().post(server_chan_api, data=payload).text)
        errmsg = response.get('errmsg', "未获取到msg")
        if errmsg == "success":
            log.info('推送成功')
        else:
            log.error(f"推送失败: {errmsg}")

        log.info('任务结束')


class Notify(object):
    default_notify_class = "ServerChan"

    def __new__(cls, *args, **kwargs):
        notify_class = kwargs.get('notify_class', cls.default_notify_class)

        this_mod = sys.modules[__name__]
        notify_class = getattr(this_mod, notify_class, None)

        if notify_class is None:
            raise ModuleNotFoundError(f"not found {this_mod}.{notify_class}")
        return notify_class()
