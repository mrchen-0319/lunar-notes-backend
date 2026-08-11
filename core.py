# -*- coding: utf-8 -*-
"""农历记事本 —— 跨进程共用的核心逻辑（EXE 守护进程 / Web Push 后端 都复用此文件）。

职责：
- 数据持久化（notes.json 共享文件，EXE 与后台守护进程同读同写）
- 农历 <-> 公历换算（borax，已验证：2026 八月十五 = 2026-09-25）
- 计算“下一次公历日期 / 提醒触发时间 / 是否已到提醒点”
"""
import os
import json
import datetime
from borax.calendars.lunardate import LunarDate

# ---------------------------------------------------------------------------
# 存储
# ---------------------------------------------------------------------------
def data_dir():
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "lunar-notes")
    else:
        d = os.path.expanduser("~/.lunar-notes")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def notes_path():
    return os.path.join(data_dir(), "notes.json")


def subscriptions_path():
    return os.path.join(data_dir(), "subscriptions.json")


def load_notes():
    p = notes_path()
    if not os.path.exists(p):
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def save_notes(notes):
    p = notes_path()
    # 直接写入目标文件（避免 os.replace 在冻结环境中触发文件操作拦截而卡死）；
    # ensure_ascii=True 让 json 走纯 ASCII 路径，规避冻结后非 ASCII 编码异常。
    with open(p, "w", encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=True, indent=2)


# ---------------------------------------------------------------------------
# 农历换算
# ---------------------------------------------------------------------------
def lunar_to_solar(year, month, day, leap):
    """返回 datetime.date。"""
    ld = LunarDate(year, month, day, 1 if leap else 0)
    return ld.to_solar_date()


def solar_to_lunar(d):
    """d: datetime.date -> (year, month, day, leap)"""
    ld = LunarDate.from_solar_date(d.year, d.month, d.day)
    return (ld.year, ld.month, ld.day, ld.leap)


def next_occurrence(month, day, leap, from_date):
    """从 from_date(含) 起，找第一个农历为 (month,day,leap) 的公历日期。"""
    d = from_date
    for _ in range(800):  # ~2.2 年，足够覆盖绝大多数情况（含闰月 ~19 年兜底）
        y, m, dd, lp = solar_to_lunar(d)
        if m == month and dd == day and lp == (1 if leap else 0):
            return d
        d = d + datetime.timedelta(days=1)
    return None


# ---------------------------------------------------------------------------
# 提醒触发逻辑
# ---------------------------------------------------------------------------
def trigger_datetime(note, occ_date):
    """提醒触发时刻 = 公历纪念日 - 提前天数，固定在设定时间点。"""
    remind = note.get("remind") or {}
    adv = int(remind.get("advance", 1) or 1)
    hh, mm = (remind.get("time") or "09:00").split(":")
    t = datetime.datetime(occ_date.year, occ_date.month, occ_date.day, int(hh), int(mm))
    t = t - datetime.timedelta(days=adv)
    return t


def due_for_now(notes, now=None):
    """返回当前应当推送的 [(note, occ_date, trigger_dt)]，且过滤掉本年度已推送过的。

    字段约定（与前端 index.html 完全一致）：
      note.month / note.day / note.leap
      note.remind = { advance:int(0=不提醒), time:"HH:MM" }
      note.notified = { "<公历年份>": "<ISO 时间戳>" }
    """
    now = now or datetime.datetime.now()
    today = now.date()
    out = []
    for note in notes:
        remind = note.get("remind") or {}
        adv = int(remind.get("advance", 0) or 0)
        if adv <= 0:
            continue
        month = int(note["month"])
        day = int(note["day"])
        leap = bool(note.get("leap", False))
        occ = next_occurrence(month, day, leap, today)
        if not occ:
            continue
        trig = trigger_datetime(note, occ)
        notified = note.get("notified", {}) or {}
        if trig <= now and str(occ.year) not in notified:
            out.append((note, occ, trig))
    return out


def mark_notified(note, occ, now):
    note.setdefault("notified", {})
    note["notified"][str(occ.year)] = now.isoformat()


def lunar_label(note):
    m = int(note["month"])
    d = int(note["day"])
    return "农历{}月{}{}日".format(m, "闰" if note.get("leap") else "", d)


if __name__ == "__main__":
    # 自测
    print("2026 八月十五 ->", lunar_to_solar(2026, 8, 15, False))
    print("2023 闰二月初一 ->", lunar_to_solar(2023, 2, 1, True))
    n = {"month": 8, "day": 15, "leap": False, "remind": {"advance": 3, "time": "09:00"}}
    occ = next_occurrence(8, 15, False, datetime.date(2026, 1, 1))
    print("next occ:", occ, "trigger:", trigger_datetime(n, occ))
