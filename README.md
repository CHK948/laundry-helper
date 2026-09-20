# 浣熊先生洗衣助手

一个本地运行的浣熊先生共享洗衣机自动下单助手，界面参考下图设计：

- 短信/手动方式登录，token 仅在服务端内存保存
- 查看洗衣机实时状态
- 选择目标洗衣机，空闲后自动提交一次订单
- 不自动付款，下单后需在微信小程序完成支付

> 声明：本项目基于开源项目 [Lide4Code/Hxxy](https://github.com/Lide4Code/Hxxy) 的接口逻辑整理，仅供学习交流，请仅用于自己的账号。

## 快速开始

### 一键启动（Windows）

双击 `start.bat` 即可：脚本会自动检测 Python、生成 `config.json`、创建虚拟环境 `.venv`、安装依赖并启动服务，随后自动打开浏览器。

> 首次运行需联网安装依赖，稍慢；之后再启动会直接复用 `.venv`。

### 手动启动

#### 1. 安装依赖

```bash
cd raccoon-laundry-helper
pip install -r requirements.txt
```

### 2. 配置接口

```bash
copy config.example.json config.json
```

如果你的学校/公寓需要切换宿舍，请把对应的 `communityId`、`dormitoryId`、`floorId` 等参数填到 `client.py` 或自行调用 `/api/set_dormitory`。

### 3. 启动服务

```bash
python app.py
```

浏览器打开 http://127.0.0.1:8090 即可使用。

## 登录方式

### 方式一：短信验证码登录（推荐）

需要在 `config.json` 里填入从抓包得到的短信接口：

```json
{
  "login_send_endpoint": "/user/sendSmsCode",
  "login_verify_endpoint": "/user/loginBySms"
}
```

> 具体路径因版本/学校可能不同，请使用之前抓包的方法获取。如果不知道，先用方式二。

### 方式二：手动粘贴 Token

在登录弹窗最下方可直接粘贴从 Charles / Reqable / mitmproxy 抓到的 token，后端会校验 token 是否有效。

## 使用流程

1. 登录账号
2. 填写「我的专属桶」编号、选择洗衣模式、轮询间隔
3. 点击「立即刷新」加载洗衣机列表，单选一台目标洗衣机
4. 点击「洗衣机空闲后下单」开始监控
5. 程序检测到该机器 `stateName == '可用'` 时自动调用 `/order/saveDorOrder` 下单一次
6. 下单成功后自动停止监控，并弹出 Windows 桌面通知（toast + 提示音）
7. 去微信小程序完成支付

## 桌面通知

- 下单成功、监控异常停止时，会自动通过 Windows 通知中心发 toast 提示（依赖 `winotify`）
- 如果 winotify 不可用，自动降级到 tkinter 弹窗（不需要额外依赖）
- 提示音通过 `winsound.MessageBeep` 播放
- 如需关闭通知，编辑 `notifier.py`，把 `notify(...)` 调用注释掉即可

## 常见问题

**Q：抓取到的 token 怎么粘贴？**  
在微信开发者工具 / Charles 的登录响应里复制 `token` 字段的值，整段粘贴到登录弹窗的「手动粘贴 Token」框。

**Q：洗衣机列表为空？**  
检查 token 是否过期；不同学校需要切换宿舍（调用 `/api/set_dormitory`），宿舍 ID 需从抓包获取。

**Q：下单失败？**  
可能是 `channel` 参数不匹配。可在 `config.json` 的 `channel_map` 里按 `washRoomId` 配置对应 channel，或检查 `washTypeCode`（洗衣模式）是否合法。
