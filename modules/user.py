import json
import time
import requests
import urllib.parse

class UserFetcher:
    def __init__(self, cookie_str):
        self.cookies = self._parse_cookie_string(cookie_str)
        self.real_name = None
        self.uuid = None
        self.user_id = None

        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "application/x-www-form-urlencoded",
            "Pragma": "no-cache",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36 Edg/121.0.0.0",
            "sec-ch-ua": "Not",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "Windows"
        }

    def _parse_cookie_string(self, cookie_str):
        cookies = {}
        if not cookie_str:
            return cookies
        items = cookie_str.split(';')
        for item in items:
            item = item.strip()
            if '=' in item:
                key, value = item.split('=', 1)
                key = key.strip()
                value = value.strip()
                cookies[key] = value
        return cookies

    def get_real_name(self):
        headers = {
            "Origin": "https://studyvideoh5.zhihuishu.com",
            "Referer": "https://studyvideoh5.zhihuishu.com/",
        }
        headers.update(self.headers)
        url = "https://studyservice-api.zhihuishu.com/gateway/f/v1/login/getLoginUserInfo"
        params = {"dateFormate": str(int(time.time() * 1000))}
        
        try:
            response = requests.get(url, cookies=self.cookies, params=params, headers=headers)
            response.raise_for_status()
            json_data = response.json()
            real_name = json_data["data"]["realName"]
            self.uuid = json_data["data"].get("uuid", "")
            if real_name:
                self.real_name = real_name
                return real_name
        except:
            pass
        
        try:
            caslogc = self.cookies.get("CASLOGC", "")
            if caslogc:
                decoded = urllib.parse.unquote(caslogc)
                cas_data = json.loads(decoded)
                real_name = cas_data.get("realName", "")
                self.user_id = cas_data.get("userId", "")
                self.uuid = cas_data.get("uuid", "")
                if real_name:
                    self.real_name = real_name
                    return real_name
        except:
            pass
        return None

def user_value(user_cookie_one):
    fetcher = UserFetcher(user_cookie_one)
    real_name = fetcher.get_real_name()
    if real_name:
        fetcher.Write_Log = lambda msg: None
        fetcher.Write_Log(f"欢迎你{real_name}")
    return {
        "realName": real_name,
        "uuid": fetcher.uuid,
        "userId": fetcher.user_id
    }