#!/usr/bin/env python3
"""
Rain Alert — 检查未来几小时是否下雨，通过 Bark / Pushover 推送到 iPhone。

中国大陆用户推荐使用 Bark（App Store 搜 "Bark" 免费安装）。
境外用户可用 Pushover。

依赖：无需第三方库，仅用 Python 标准库
运行：python3 check_rain.py

测试推送：python3 check_rain.py --test
"""

import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# ── 基本配置（根据你的情况修改）──────────────────────
LAT = 39.9516          # 纬度
LON = 116.7131         # 经度
FORECAST_HOURS = 12     # 往前看几小时
RAIN_THRESHOLD_MM = 0.1 # 降水量阈值（mm），超过即视为下雨
# ──────────────────────────────────────────────────────

# 通过环境变量选择通知方式
# NOTIFY_METHOD=bark    → Bark（中国大陆推荐，免费）
# NOTIFY_METHOD=pushover → Pushover（境外用户）
NOTIFY_METHOD = os.environ.get("NOTIFY_METHOD", "bark")

# Bark 配置：从 Bark App 里复制设备 key
BARK_KEY = os.environ.get("BARK_KEY", "")

# Pushover 配置：在 https://pushover.net 注册获取
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_TOKEN", "")
PUSHOVER_USER = os.environ.get("PUSHOVER_USER", "")


# ── 天气查询 ──────────────────────────────────────────

def get_forecast():
    """调用 Open-Meteo API（免费，无需 API Key）获取逐时降水数据。"""
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": "precipitation_probability,precipitation",
        "forecast_days": 1,
        "timezone": "auto",
    }
    url = "https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "rain-alert/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def will_rain(data):
    """判断未来 FORECAST_HOURS 小时内是否可能下雨。"""
    times = data["hourly"]["time"]
    probs = data["hourly"]["precipitation_probability"]
    precips = data["hourly"]["precipitation"]

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
    now_idx = None
    for i, t in enumerate(times):
        if t >= now_iso:
            now_idx = i
            break
    if now_idx is None:
        return False, "no forecast data"

    end_idx = min(now_idx + FORECAST_HOURS, len(times))
    for i in range(now_idx, end_idx):
        prob = probs[i] if probs[i] is not None else 0
        prec = precips[i] if precips[i] is not None else 0
        if prob >= 50 or prec >= RAIN_THRESHOLD_MM:
            return True, f"{times[i]} 降水概率 {prob}%，降水量 {prec}mm"
    return False, "no rain expected"


# ── 推送通知 ──────────────────────────────────────────

def send_via_bark(message):
    """通过 Bark 推送到 iPhone（中国大陆推荐，免费）。"""
    if not BARK_KEY:
        print("❌ 缺失 BARK_KEY 环境变量", file=sys.stderr)
        print("  请安装 Bark App → 复制设备 key → 设为 BARK_KEY", file=sys.stderr)
        sys.exit(1)

    title = "🌂 带伞提醒"
    url = f"https://api.day.app/{BARK_KEY}/{urllib.parse.quote(title)}/{urllib.parse.quote(message)}"
    url += "?isArchive=1&level=timeSensitive"

    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def send_via_pushover(message):
    """通过 Pushover 推送到 iPhone。"""
    if not PUSHOVER_TOKEN or not PUSHOVER_USER:
        print("❌ 缺失 PUSHOVER_TOKEN 或 PUSHOVER_USER 环境变量", file=sys.stderr)
        sys.exit(1)

    data = urllib.parse.urlencode({
        "token": PUSHOVER_TOKEN,
        "user": PUSHOVER_USER,
        "title": "🌂 带伞提醒",
        "message": message,
        "sound": "persistent",
        "priority": 1,
    }).encode()

    req = urllib.request.Request(
        "https://api.pushover.net/1/messages.json",
        data=data,
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def send_notification(message):
    """根据配置选择推送渠道。"""
    if NOTIFY_METHOD == "pushover":
        return send_via_pushover(message)
    return send_via_bark(message)


# ── 主流程 ────────────────────────────────────────────

def send_test_notification():
    """发送一条测试通知，验证推送通道是否正常。"""
    msg = "🔔 带伞提醒 · 测试通知\n推送系统正常工作 ✅\n"
    msg += f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
    msg += "未来下雨时将自动收到带伞提醒 🌂"
    print(f"☔ 发送测试通知...")
    send_notification(msg)
    print("✅ 已推送，请查看手机")


def main():
    print(f"🌤 查询天气预报（方式: {NOTIFY_METHOD}）...")
    try:
        data = get_forecast()
    except Exception as e:
        print(f"❌ 查询天气失败: {e}", file=sys.stderr)
        sys.exit(1)

    raining, detail = will_rain(data)
    if raining:
        msg = f"预计未来 {FORECAST_HOURS} 小时内有雨。{detail} 出门记得带伞 🌂"
        print(f"☔ {msg}")
        send_notification(msg)
        print("✅ 已推送通知")
    else:
        print(f"☀️ {detail}，不需要推送")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        send_test_notification()
    else:
        main()
# 测试模式：通过环境变量 TEST_MODE=true 触发（用于 GitHub Actions 手动运行）
TEST_MODE = os.environ.get("TEST_MODE", "").lower() == "true"

# Bark 配置：从 Bark App 里复制设备 key
if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        send_test_notification()
    elif TEST_MODE:
        send_test_notification()
    else:
        main()
