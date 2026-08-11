# -*- coding: utf-8 -*-
"""
农历记事本 —— Web Push 后端（用于 iOS / 任意浏览器 PWA 的“关掉软件也推送”）。

能力：
- 托管同一套 PWA 静态文件
- /api/notes  笔记的增删改查（与 EXE 共用 notes.json 格式）
- /api/push/subscribe|unsubscribe  保存浏览器/手机推送订阅
- /api/vapid-public  返回 VAPID 公钥（前端订阅用）
- 定时（每 15 分钟）检查到期提醒，向所有订阅者发送 Web Push

部署：需托管在公网 HTTPS 环境（iOS 的 Web Push 必须是 https 且 PWA 已添加到主屏幕）。
CloudStudio 仅支持静态托管，跑不了本后端；可部署到 Render / Railway / Fly.io / 自有服务器。
"""
import os
import json
import datetime
from flask import Flask, request, jsonify, send_from_directory, Response

import core

ROOT = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__, static_folder=ROOT)

VAPID_FILE = os.path.join(core.data_dir(), "vapid.json")
VAPID_EMAIL = os.environ.get("VAPID_EMAIL", "mailto:admin@example.com")


def get_vapid():
    if os.path.exists(VAPID_FILE):
        with open(VAPID_FILE) as f:
            return json.load(f)
    from py_vapid import Vapid

    v = Vapid()
    v.generate_keys()
    data = {
        "private": v.private_pem().decode(),
        "public": v.public_pem().decode(),
    }
    with open(VAPID_FILE, "w") as f:
        json.dump(data, f)
    return data


VAPID = get_vapid()


# --------------------------------------------------------------------------
# 静态资源
# --------------------------------------------------------------------------
@app.route("/")
def index():
    return send_from_directory(ROOT, "index.html")


@app.route("/<path:p>")
def static_files(p):
    return send_from_directory(ROOT, p)


# --------------------------------------------------------------------------
# 笔记 API
# --------------------------------------------------------------------------
@app.route("/api/notes", methods=["GET"])
def get_notes():
    return jsonify(core.load_notes())


@app.route("/api/notes", methods=["PUT"])
def put_notes():
    notes = request.get_json(force=True)
    core.save_notes(notes)
    return jsonify({"ok": True})


# --------------------------------------------------------------------------
# Web Push 订阅管理
# --------------------------------------------------------------------------
@app.route("/api/vapid-public")
def vapid_public():
    return Response(VAPID["public"], mimetype="text/plain")


def load_subs():
    p = core.subscriptions_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_subs(subs):
    p = core.subscriptions_path()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(subs, f, ensure_ascii=False)
    os.replace(tmp, p)


@app.route("/api/push/subscribe", methods=["POST"])
def subscribe():
    sub = request.get_json(force=True)
    subs = load_subs()
    subs = [s for s in subs if s.get("endpoint") != sub.get("endpoint")]
    subs.append(sub)
    save_subs(subs)
    return jsonify({"ok": True, "count": len(subs)})


@app.route("/api/push/unsubscribe", methods=["POST"])
def unsubscribe():
    sub = request.get_json(force=True)
    subs = [s for s in load_subs() if s.get("endpoint") != sub.get("endpoint")]
    save_subs(subs)
    return jsonify({"ok": True})


def push_to_all(title, body):
    from pywebpush import webpush

    subs = load_subs()
    for s in subs:
        try:
            webpush(
                s,
                data=json.dumps({"title": title, "body": body}),
                vapid_private_key=VAPID["private"],
                vapid_claims={"sub": VAPID_EMAIL},
            )
        except Exception as e:
            print("push error:", e)


# --------------------------------------------------------------------------
# 定时检查并推送
# --------------------------------------------------------------------------
def push_due():
    notes = core.load_notes()
    now = datetime.datetime.now()
    due = core.due_for_now(notes, now)
    changed = False
    for note, occ, trig in due:
        push_to_all(
            "农历提醒：" + (note.get("title") or ""),
            "{} · 公历{}月{}日".format(core.lunar_label(note), occ.month, occ.day),
        )
        core.mark_notified(note, occ, now)
        changed = True
    if changed:
        core.save_notes(notes)


try:
    from apscheduler.schedulers.background import BackgroundScheduler

    sched = BackgroundScheduler()
    sched.add_job(push_due, "interval", minutes=15)
    sched.start()
except Exception as e:
    print("scheduler error:", e)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8731)))
