"""
浣熊先生洗衣助手 - Web 服务
功能：短信/手动登录、查看洗衣机状态、等待空闲后自动下单、运行日志。
提示：token 仅在服务端内存中保存，重启后需重新登录。
"""
import hashlib
import json
import os
import threading
import time
from collections import deque
from datetime import datetime
from urllib.parse import unquote

from flask import Flask, jsonify, render_template, request, session

from client import RaccoonClient
from notifier import notify

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")


def load_config(path="config.json"):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# -------------- 全局状态 --------------
# 服务器端会话：key = session cookie id，value = {phone, token, created_at}
accounts = {}
client = RaccoonClient(load_config())

poll_thread = None
poll_stop = threading.Event()
poll_status = {"running": False, "target": None, "started_at": None}
operation_logs = deque(maxlen=200)


def _session_id():
    sid = request.cookies.get("session")
    if not sid:
        sid = session.get("_sid")
    return sid


def _current_account():
    sid = _session_id()
    return accounts.get(sid)


def _mask_phone(phone):
    if not phone or len(phone) < 7:
        return phone
    return phone[:3] + "****" + phone[-2:]


def _token_id(token):
    if not token:
        return None
    return hashlib.sha256(token.encode()).hexdigest()[:12]


def _account_info():
    acc = _current_account()
    if not acc:
        return None
    return {
        "phone": _mask_phone(acc.get("phone", "")),
        "tokenId": _token_id(acc.get("token")),
        "loggedIn": True,
    }


def _log(message, level="info"):
    entry = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "level": level,
        "message": message,
    }
    operation_logs.appendleft(entry)
    print(f"[{entry['time']}] [{level}] {message}")


def _get_token():
    acc = _current_account()
    if not acc:
        raise RuntimeError("未登录，请先获取 token")
    return acc["token"]


# -------------- 页面 --------------
@app.route("/")
def index():
    return render_template("index.html")


# -------------- 配置 --------------
@app.route("/api/config")
def api_config():
    return jsonify({
        "baseUrl": client.cfg.get("base_url"),
        "loginSendEndpoint": client.cfg.get("login_send_endpoint"),
        "loginVerifyEndpoint": client.cfg.get("login_verify_endpoint"),
    })


# -------------- 账号/登录 --------------
@app.route("/api/account")
def api_account():
    return jsonify(success=True, data=_account_info() or {"loggedIn": False})


@app.route("/api/send_code", methods=["POST"])
def api_send_code():
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "").strip()
    if not phone:
        return jsonify(success=False, msg="请输入手机号"), 400
    try:
        result = client.send_sms_code(phone)
        _log(f"发送验证码到 {phone}: {result.get('msg', 'OK')}")
        return jsonify(success=True, data=result)
    except Exception as e:
        _log(f"发送验证码失败: {e}", "error")
        return jsonify(success=False, msg=f"发送验证码失败: {e}"), 500


@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    phone = data.get("phone", "").strip()
    code = data.get("code", "").strip()
    manual_token = data.get("token", "").strip()

    if not phone:
        return jsonify(success=False, msg="请输入手机号"), 400

    sid = _session_id()
    if not sid:
        import uuid
        sid = uuid.uuid4().hex
        session["_sid"] = sid

    token = None
    if manual_token:
        token = manual_token
        if not client.test_token(token):
            return jsonify(success=False, msg="手动填入的 token 无效或已过期"), 400
    else:
        if not code:
            return jsonify(success=False, msg="请输入验证码或手动粘贴 token"), 400
        try:
            result, token = client.login_by_sms(phone, code)
        except Exception as e:
            _log(f"登录接口异常: {e}", "error")
            return jsonify(success=False, msg=f"登录接口异常: {e}"), 500
        if not token:
            msg = result.get("msg") if isinstance(result, dict) else str(result)
            return jsonify(success=False, msg=f"登录失败：{msg}"), 400

    accounts[sid] = {
        "phone": phone,
        "token": token,
        "created_at": time.time(),
    }
    _log(f"账号 {phone} 登录成功，tokenId={_token_id(token)}")
    return jsonify(success=True, data=_account_info())


@app.route("/api/logout", methods=["POST"])
def api_logout():
    sid = _session_id()
    acc = accounts.pop(sid, None)
    if acc:
        _log(f"账号 {_mask_phone(acc.get('phone',''))} 已登出")
    return jsonify(success=True)


# -------------- 洗衣机/宿舍 --------------
@app.route("/api/washers")
def api_washers():
    try:
        token = _get_token()
    except RuntimeError as e:
        return jsonify(success=False, msg=str(e)), 401
    try:
        result = client.get_washers(token)
        if not result.get("success"):
            return jsonify(success=False, msg=result.get("msg", "获取失败")), 400
        return jsonify(success=True, data=result.get("data", []))
    except Exception as e:
        _log(f"获取洗衣机失败: {e}", "error")
        return jsonify(success=False, msg=str(e)), 500


@app.route("/api/set_dormitory", methods=["POST"])
def api_set_dormitory():
    try:
        token = _get_token()
    except RuntimeError as e:
        return jsonify(success=False, msg=str(e)), 401
    profile = request.get_json(silent=True) or {}
    if not profile:
        return jsonify(success=False, msg="请提供宿舍信息"), 400
    try:
        result = client.set_dormitory(token, profile)
        _log(f"切换宿舍到 {profile.get('dormitoryName')} {profile.get('floorName')}")
        return jsonify(success=True, data=result)
    except Exception as e:
        _log(f"切换宿舍失败: {e}", "error")
        return jsonify(success=False, msg=str(e)), 500


# -------------- 下单 --------------
@app.route("/api/order", methods=["POST"])
def api_order():
    try:
        token = _get_token()
    except RuntimeError as e:
        return jsonify(success=False, msg=str(e)), 401

    data = request.get_json(silent=True) or {}
    wash_id = data.get("washId")
    bucket = data.get("bucketNumber", "").strip()
    way = data.get("way", "QUICK_WASH")
    channel = data.get("channel")

    if not wash_id or not bucket:
        return jsonify(success=False, msg="缺少 washId 或桶编号"), 400

    try:
        result = client.place_order(token, wash_id, bucket, way, channel)
        if result.get("success"):
            _log(f"下单成功 washId={wash_id}, way={way}, 返回={result.get('data')}")
        else:
            _log(f"下单失败 washId={wash_id}: {result.get('msg')}", "warning")
        return jsonify(success=True, data=result)
    except Exception as e:
        _log(f"下单异常: {e}", "error")
        return jsonify(success=False, msg=str(e)), 500


# -------------- 轮询抢单 --------------
def _polling_worker(token, bucket, way, interval, selected_wash_id=None):
    _log("开始监控洗衣机空闲状态")
    consecutive_errors = 0
    while not poll_stop.is_set():
        try:
            result = client.get_washers(token)
            if not result.get("success"):
                _log(f"查询洗衣机失败: {result.get('msg')}", "warning")
                consecutive_errors += 1
                if consecutive_errors > 10:
                    _log("连续失败次数过多，已自动停止监控", "error")
                    break
                time.sleep(min(interval, 5))
                continue
            consecutive_errors = 0
            washers = result.get("data", [])
            target = None
            for w in washers:
                if selected_wash_id is not None:
                    if w.get("washId") != selected_wash_id:
                        continue
                if w.get("stateName") == "可用":
                    target = w
                    break

            if not target:
                _log("暂无空闲洗衣机，继续监控...")
                poll_stop.wait(interval)
                continue

            info = target.get("washAllInfo", f"washId={target.get('washId')}")
            _log(f"发现空闲洗衣机：{info}，准备下单")
            channel = client.channel_for(target)
            order_result = client.place_order(
                token, target.get("washId"), bucket, way, channel
            )
            if order_result.get("success"):
                _log(f"下单成功：{info}")
                notify(
                    "🎉 洗衣下单成功！",
                    f"机器：{info}\n请尽快前往投放衣物。",
                )
                poll_status.update({"running": False, "target": None})
                break
            else:
                msg = order_result.get("msg", "未知错误")
                _log(f"下单失败：{msg}，将继续监控", "warning")
                # 该机器可能刚被抢，跳过一小段时间
                poll_stop.wait(2)
        except Exception as e:
            _log(f"监控异常: {e}", "error")
            consecutive_errors += 1
            if consecutive_errors > 10:
                break
            poll_stop.wait(2)

    if poll_stop.is_set():
        _log("监控已手动停止")
        notify(
            "监控已停止",
            "你主动停止了抢单监控。",
            sound=False,
        )
    else:
        _log("监控已结束")
        # 走到这里通常意味着下单成功（已在上面 notify）或连续错误自动停止
        if poll_status.get("target") is None and not poll_status.get("running"):
            pass  # 成功路径已通知
        else:
            notify(
                "⚠️ 抢单监控异常停止",
                "连续请求失败超过上限，已自动停止。请检查网络或 token 是否过期。",
            )
    poll_status["running"] = False


@app.route("/api/poll/start", methods=["POST"])
def api_poll_start():
    global poll_thread, poll_stop
    data = request.get_json(silent=True) or {}
    try:
        token = _get_token()
    except RuntimeError as e:
        return jsonify(success=False, msg=str(e)), 401

    bucket = data.get("bucketNumber", "").strip()
    way = data.get("way", "QUICK_WASH")
    interval = int(data.get("interval", 8))
    selected_wash_id = data.get("washId")
    if selected_wash_id is not None:
        selected_wash_id = int(selected_wash_id)

    if not bucket:
        return jsonify(success=False, msg="请填写桶编号"), 400

    # 停止已有的
    if poll_thread and poll_thread.is_alive():
        poll_stop.set()
        poll_thread.join(timeout=3)

    poll_stop.clear()
    poll_status.update({
        "running": True,
        "target": selected_wash_id,
        "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    })
    poll_thread = threading.Thread(
        target=_polling_worker,
        args=(token, bucket, way, interval, selected_wash_id),
        daemon=True,
    )
    poll_thread.start()
    _log(f"启动监控：桶={bucket}, 模式={way}, 间隔={interval}s, 目标={selected_wash_id or '任意空闲'}")
    return jsonify(success=True)


@app.route("/api/poll/stop", methods=["POST"])
def api_poll_stop():
    global poll_thread, poll_stop
    poll_stop.set()
    if poll_thread:
        poll_thread.join(timeout=3)
    poll_status.update({"running": False, "target": None})
    return jsonify(success=True)


@app.route("/api/poll/status")
def api_poll_status():
    return jsonify(success=True, data=poll_status)


# -------------- 日志 --------------
@app.route("/api/logs")
def api_logs():
    return jsonify(success=True, data=list(operation_logs))


if __name__ == "__main__":
    # 重新加载配置，确保 client 使用最新 config.json
    cfg = load_config()
    if cfg:
        client = RaccoonClient(cfg)
    app.run(host="127.0.0.1", port=8090, debug=False)
