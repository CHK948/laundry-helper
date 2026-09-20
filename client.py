"""
浣熊先生洗衣助手 - API 客户端
基于开源项目 Lide4Code/Hxxy 的接口逻辑整理，仅用于个人学习/自动化自己的账号。
"""
import json
import time
from urllib.parse import quote
import requests


DEFAULT_CONFIG = {
    "base_url": "https://hxxs.mrrac.com",
    # 真实接口（从小程序 wxf3d088fc4d192e93 源码逆向，GET + URL 参数）
    "login_send_endpoint": "/sendCode",
    "login_verify_endpoint": "/login",
    "category": "1",
    "channel_map": {
        "1799": 2
    },
    "default_channel": 3,
    "user_agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
        "MicroMessenger/7.0.20.1781(0x6700143B) NetType/WIFI "
        "MiniProgramEnv/Windows WindowsWechat/WMPF "
        "WindowsWechat(0x63090a1b)XWEB/11275"
    ),
    "referer": "https://servicewechat.com/wxf3d088fc4d192e93/179/page-frame.html"
}


class RaccoonClient:
    def __init__(self, config=None):
        self.cfg = {**DEFAULT_CONFIG, **(config or {})}
        self.session = requests.Session()

    def _headers(self, token=None):
        h = {
            "Host": self._host(),
            "Connection": "keep-alive",
            "xweb_xhr": "1",
            "from-agent": "wxmini",
            "api-version": "1.0.0",
            "User-Agent": self.cfg["user_agent"],
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "*/*",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Referer": self.cfg["referer"],
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if token:
            h["token"] = token
        return h

    def _host(self):
        return self.cfg["base_url"].replace("https://", "").replace("http://", "")

    def _url(self, path):
        if path.startswith("http"):
            return path
        base = self.cfg["base_url"].rstrip("/")
        return base + path

    def send_sms_code(self, phone, is_retry=0):
        """发送短信验证码。真实接口：GET /sendCode?mobile=xxx&isRetry=0"""
        ep = self.cfg["login_send_endpoint"]
        if not ep:
            raise RuntimeError("未配置短信发送接口 (login_send_endpoint)")
        url = self._url(ep)
        # 小程序原生请求方式：GET + URL 查询参数
        resp = self.session.get(
            url, params={"mobile": phone, "isRetry": is_retry},
            headers=self._headers(), timeout=15,
        )
        resp.encoding = "utf-8"
        try:
            return resp.json()
        except Exception:
            return {"success": False, "msg": f"非 JSON 响应: {resp.text[:200]}"}

    def login_by_sms(self, phone, code):
        """短信验证码登录，返回 (完整响应, token)。
        真实接口：GET /login?mobile=xxx&code=xxx&floorRoomId=&workerId=&random=
        响应 data 里含 hxUser / token / userSelfVO / isActivityUser
        """
        ep = self.cfg["login_verify_endpoint"]
        if not ep:
            raise RuntimeError("未配置短信登录接口 (login_verify_endpoint)")
        url = self._url(ep)
        resp = self.session.get(
            url,
            params={
                "mobile": phone, "code": code,
                "floorRoomId": "", "workerId": "", "random": "",
            },
            headers=self._headers(), timeout=15,
        )
        resp.encoding = "utf-8"
        try:
            data = resp.json()
        except Exception:
            return {"success": False, "msg": f"非 JSON 响应: {resp.text[:200]}"}, None
        # 兼容两种返回：直接 data 是 token，或 data.token
        token = None
        if isinstance(data, dict):
            if isinstance(data.get("data"), str):
                token = data["data"]
            elif isinstance(data.get("data"), dict):
                token = data["data"].get("token") or data["data"].get("accessToken")
        return data, token

    def set_dormitory(self, token, profile):
        """
        切换洗衣房/宿舍。
        profile 示例：
        {
            "id": 1666260,
            "sex": 1,
            "graduationYear": 2027,
            "communityId": "10136",
            "communityName": "华南农业大学",
            "dormitoryId": 2673,
            "dormitoryName": "3号楼",
            "floorId": 15402,
            "floorName": "1层",
            "dormitoryNo": "118",
            "nickname": "hx_xxxx"
        }
        """
        obj = quote(json.dumps(profile, ensure_ascii=False, separators=(",", ":")))
        url = self._url(f"/user/saveUserSelf?obj={obj}")
        resp = self.session.post(url, headers=self._headers(token), timeout=15)
        resp.encoding = "utf-8"
        return resp.json()

    def get_washers(self, token, category=None):
        cat = category if category is not None else self.cfg["category"]
        url = self._url(f"/home/loadHomeWashList?category={cat}")
        resp = self.session.get(url, headers=self._headers(token), timeout=15)
        resp.encoding = "utf-8"
        try:
            return resp.json()
        except Exception:
            return {"success": False, "msg": f"非 JSON 响应: {resp.text[:200]}"}

    def channel_for(self, washer):
        """根据 washRoomId 推断 channel，可配置。"""
        rid = str(washer.get("washRoomId", ""))
        return self.cfg["channel_map"].get(rid, self.cfg["default_channel"])

    def place_order(self, token, wash_id, bucket_number, way, channel=None):
        url = self._url("/order/saveDorOrder")
        data = {
            "bucketNumber": bucket_number,
            "channel": channel if channel is not None else self.cfg["default_channel"],
            "washId": wash_id,
            "washTypeCode": way,
        }
        resp = self.session.post(url, headers=self._headers(token), json=data, timeout=15)
        resp.encoding = "utf-8"
        try:
            return resp.json()
        except Exception:
            return {"success": False, "msg": f"非 JSON 响应: {resp.text[:200]}"}

    def test_token(self, token):
        """用 get_washers 测试 token 是否有效。"""
        r = self.get_washers(token)
        return r.get("success") and isinstance(r.get("data"), list)


if __name__ == "__main__":
    c = RaccoonClient()
    # 示例：直接填入 token 与桶编号即可测试
    import sys
    if len(sys.argv) >= 3:
        tok, bucket = sys.argv[1], sys.argv[2]
        print(c.get_washers(tok))
        # print(c.place_order(tok, 8050, bucket, "QUICK_WASH"))
    else:
        print("用法: python client.py <token> <bucket_number>")
