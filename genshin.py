import hashlib
import json
import os
import random
import string
import time
import uuid
from typing import List

import requests

from notify import *
from settings import *

notify = Notify(notify_class=CONFIG.NOTIFY_CLASS)


def hexdigest(text):
    md5 = hashlib.md5()
    md5.update(text.encode())
    return md5.hexdigest()


class Base(object):
    def __init__(self, cookie: str = None):
        if not isinstance(cookie, str):
            raise TypeError('%s want a %s but got %s' % (
                self.__class__, type(__name__), type(cookie)))
        self._cookie = cookie

    def get_header(self):
        header = {
            'User-Agent': CONFIG.USER_AGENT,
            'Referer': CONFIG.REFERER_URL,
            'Accept-Encoding': 'gzip, deflate, br',
            'Cookie': self._cookie,
        }
        return header

    @staticmethod
    def _ds():
        n = 'h8w582wxwgqvahcdkpvdhbh2w9casgfl'
        i = str(int(time.time()))
        r = ''.join(random.sample(string.ascii_lowercase + string.digits, 6))
        c = hexdigest('salt=' + n + '&t=' + i + '&r=' + r)
        return f'{i},{r},{c}'

    @staticmethod
    def to_python(json_str: str) -> dict:
        return json.loads(json_str)

    @staticmethod
    def to_json(obj):
        return json.dumps(obj, indent=4, ensure_ascii=False)


class GenShin(Base):
    def get_awards(self) -> dict:
        """
        获取签到物品列表
        """
        response = requests.get(CONFIG.AWARD_URL, headers=self.get_header()).text
        awards_obj = self.to_python(response)
        return awards_obj

    def get_role(self) -> dict:
        """
        获取角色信息
        """
        response = requests.get(CONFIG.ROLE_URL, headers=self.get_header()).text
        role_obj = self.to_python(response)
        return role_obj

    def get_header(self):
        header = super(GenShin, self).get_header()
        header.update({
            'x-rpc-device_id': str(uuid.uuid3(uuid.NAMESPACE_URL, self._cookie)).replace('-', '').upper(),
            'x-rpc-client_type': '5',
            'x-rpc-app_version': CONFIG.APP_VERSION,
            'DS': self._ds(),
        })
        return header

    def get_sign_in_info(self) -> List[dict]:
        """
        获取签到信息
        :return: list[dict] [
            {
                'retcode': 0,
                'message': 'OK',
                'data': {
                    'total_sign_day': 14,
                    'today': '2021-01-14',
                    'is_sign': True,
                    'first_bind': False,
                    'is_sub': False,
                    'month_first': False},
                    'region': 'cn_gf01',
                    'region_name': '天空岛',
                    'uid': '146498888'
            }
        ]
        """
        role_obj = self.get_role()
        role_list = role_obj.get('data', {}).get('list', [])

        # 当前账号绑定角色为空
        if not role_list:
            log.warning("当前账号没有角色")
            return []

        role_info = []
        for role in role_list:
            role_info.append({
                'region': role.get('region', 'NA'),
                'region_name': role.get('region_name', 'NA'),
                'uid': role.get('game_uid', 'NA')

            })

        sign_info_list = []
        for sign_info in role_info:
            info_api = CONFIG.INFO_URL.format(sign_info['region'], CONFIG.ACT_ID, sign_info['uid'])
            response = requests.get(info_api, headers=self.get_header()).text
            sign_info_obj = self.to_python(response)
            sign_info_obj.update(sign_info)
            sign_info_list.append(sign_info_obj)
        return sign_info_list

    def sign(self):
        _sign_in_results = {
            'list': [],
            'succ': 0,
            'fail': 0,
            'is_sign': 0
        }
        sign_in_info_list = self.get_sign_in_info()
        if not sign_in_info_list:
            raise RuntimeError("当前账号未有绑定或未创建角色")

        for sign_in_info in sign_in_info_list:
            today = sign_in_info['data']['today']
            total_sign_day = sign_in_info['data']['total_sign_day']
            region_name = sign_in_info['region_name']
            uid = sign_in_info['uid']
            award_list = self.get_awards()['data']['awards']
            award_idx = total_sign_day - 1

            if total_sign_day == 0:
                award_idx = total_sign_day

            sii = {
                'today': today,
                'region_name': region_name,
                'uid': uid[:int(len(uid)/2.0)] + '***' + uid[-int(len(uid)/2.0):],
                'award_name': award_list[award_idx]['name'],
                'award_cnt': award_list[award_idx]['cnt'],
                'total_sign_day': total_sign_day,
                'end': '',
            }
            if sign_in_info['data']['is_sign'] is True:
                sii.update({
                    'status': f"👀 旅行者 {sii['uid']}, 你已经签到过了哦",
                    'sign_in_status': 'is_sign'
                })
                log.info("签到成功 {}".format(CONFIG.MESSGAE_TEMPLATE.format(**sii)))
                _sign_in_results['list'].append(sii)
                _sign_in_results['is_sign'] += 1
                continue
            if sign_in_info['data']['first_bind'] is True:
                sii.update({
                    'status': f"💪 旅行者 {sii[uid]}, 请先前往米游社App手动签到一次",
                    'sign_in_status': 'fail'
                })
                log.info("签到失败 {}".format(CONFIG.MESSGAE_TEMPLATE.format(**sii)))
                _sign_in_results['list'].append(sii)
                _sign_in_results['fail'] += 1
                continue

            payload = {
                'act_id': CONFIG.ACT_ID,
                'region': region_name,
                'uid': uid
            }

            log.info(f"准备为旅行者 {sii['uid']} 签到...")
            response = requests.post(
                CONFIG.SIGN_URL,
                headers=self.get_header(),
                data=json.dumps(payload, ensure_ascii=False)).text
            sign_in_obj = self.to_python(response)

            code = sign_in_obj.get('retcode', -1)
            if code != 0:
                log.warning(f"签到失败 {sign_in_obj['message']}")
                continue

            sii.update({
                'total_sign_day': total_sign_day + 1,
                'status': sign_in_obj['message'],
                'sign_in_status': 'succ'
            })
            _sign_in_results['list'].append(sii)
            _sign_in_results['succ'] += 1
            log.info("签到成功 {}".format(CONFIG.MESSGAE_TEMPLATE.format(**sii)))
        return _sign_in_results


if __name__ == '__main__':
    if not os.environ.get('COOKIE', ''):
        log.info("没有配置COOKIE")
        notify.send("原神签到小助手签到失败", message={
            'msg': "没有配置COOKIE"
        })
        exit(0)

    cookie_list = os.environ['COOKIE'].split('#')
    for ck in cookie_list:
        try:
            sign_in_results = GenShin(cookie=ck).sign()
            msg = f"\n\t签到汇总: 成功({sign_in_results['succ']}) 失败({sign_in_results['fail']}) 已经签到({sign_in_results['is_sign']})"
            for s in sign_in_results.get('list', []):
                msg += CONFIG.MESSGAE_TEMPLATE.format(**s)
            if sign_in_results['fail']:
                notify.send(title="原神签到小助手签到失败", message=msg)
            else:
                notify.send(title="原神签到小助手签到成功", message=msg)
        except Exception as e:
            notify.send(title="原神签到小助手签到失败", message={
                'msg': "请前往执行日志查看详情",
                'err': str(e),
            })
