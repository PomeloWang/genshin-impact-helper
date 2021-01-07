import abc
import json
import os
import sys

import requests
from requests.exceptions import *

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
    def send(self, title, status, message):
        """please implemente in subclass"""


class ServerJiang(Sender):
    def send(self, title, status, message):
        message = CONFIG.MESSGAE_TEMPLATE.format(**message)

        secret = os.environ.get('SCKEY', '')
        if isinstance(message, list) or isinstance(message, dict):
            message = self.to_json(message)
        log.info('签到{}: {}'.format(status, message))

        if secret.startswith('SC'):
            log.info('准备推送通知...')
            url = 'https://sc.ftqq.com/{}.send'.format(secret)
            data = {'text': '原神签到小助手 签到{}'.format(status), 'desp': message}
            try:
                response = self.to_python(requests.Session().post(url, data=data).text)
            except Exception as e:
                log.error(e)
                raise HTTPError
            else:
                errmsg = response['errmsg']
                if errmsg == 'success':
                    log.info('推送成功')
                else:
                    log.error('{}: {}'.format('推送失败', response))
        else:
            log.info('未配置SCKEY,正在跳过推送')
        return log.info('任务结束')


class Notify(object):
    default_notify_class = "ServerJiang"

    def __new__(cls, *args, **kwargs):
        notify_class = kwargs.get('notify_class', cls.default_notify_class)

        this_mod = sys.modules[__name__]
        notify_class = getattr(this_mod, notify_class, None)

        if notify_class is None:
            raise ModuleNotFoundError("not found {}.{}".format(this_mod, notify_class))
        return notify_class()
