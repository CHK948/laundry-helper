"""
桌面通知封装：抢单成功后弹出 Windows 提示。
按优先级回退：winotify (Win10 toast) → plyer → tkinter.messagebox。
同时播放一次提示音（winsound）。
所有调用都是非阻塞的，封装在后台线程里跑，不会卡住抢单主循环。
"""
import sys
import threading


def _play_sound():
    """播放一次系统提示音。"""
    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
        return
    except Exception:
        pass
    # 终端 bell 兜底（一般用不到）
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        pass


def _toast(title, message):
    """Win10/11 原生 toast（需要 winotify）。非阻塞。"""
    try:
        from winotify import Notification, audio
        toast = Notification(
            app_id="浣熊先生洗衣助手",
            title=title,
            msg=message,
            duration="long",
        )
        toast.set_audio(audio.Default, loop=False)
        toast.show()
        return True
    except Exception as e:
        print(f"[notify] winotify 失败: {e}", file=sys.stderr)
        return False


def _plyer(title, message):
    """plyer 跨平台通知（需要 plyer 包）。非阻塞。"""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="浣熊先生洗衣助手",
            timeout=10,
        )
        return True
    except Exception as e:
        print(f"[notify] plyer 失败: {e}", file=sys.stderr)
        return False


def _messagebox(title, message):
    """tkinter 弹窗（Python 自带，无外部依赖）。阻塞，直到用户点确定。"""
    try:
        import tkinter as tk_mod
        from tkinter import messagebox
        root = tk_mod.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        messagebox.showinfo(title, message)
        root.destroy()
        return True
    except Exception as e:
        print(f"[notify] tkinter 弹窗失败: {e}", file=sys.stderr)
        return False


def notify(title, message, sound=True):
    """抢单成功/异常时调用，自动选最佳方式展示。

    非阻塞，会在后台线程里执行，不会卡住调用方。
    """
    def _run():
        delivered = (
            _toast(title, message)
            or _plyer(title, message)
            or _messagebox(title, message)
        )
        if sound:
            _play_sound()
        if not delivered:
            print(f"[NOTIFY-FAIL] {title} :: {message}", file=sys.stderr)

    threading.Thread(target=_run, daemon=True).start()