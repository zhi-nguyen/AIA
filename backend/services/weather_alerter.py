"""
weather_alerter.py — Weather analysis, cancel email templates, and WebSocket push.
Dùng bởi cả Celery ETA task (per-event) và Observer (hourly fetch).
"""

import json
from datetime import datetime, timezone, timedelta

# ── Ngưỡng thời tiết xấu ──────────────────────────────────────────────────

BAD_WEATHER_KEYWORDS = [
    "thunder", "storm", "heavy rain", "torrential",
    "flood", "blizzard", "hurricane", "typhoon",
    "mưa lớn", "bão", "dông", "lốc", "ngập",
]

RAIN_THRESHOLD = 60       # chance_of_rain >= 60%
EXTREME_TEMP_C  = 40      # temp_c >= 40°C


def analyze_hour_weather(hourly_entry: dict) -> dict:
    """
    Phân tích 1 entry từ forecast.forecastday[].hour[].
    Trả về {"is_bad": bool, "reason": str, "details": str}
    """
    reasons = []

    chance_of_rain = hourly_entry.get("chance_of_rain", 0)
    will_it_rain = hourly_entry.get("will_it_rain", 0)
    temp_c = hourly_entry.get("temp_c", 25)
    condition_text = (hourly_entry.get("condition", {}).get("text", "") or "").lower()
    wind_kph = hourly_entry.get("wind_kph", 0)
    humidity = hourly_entry.get("humidity", 0)

    # Check mưa
    if int(chance_of_rain) >= RAIN_THRESHOLD or int(will_it_rain) == 1:
        reasons.append(f"Mưa ({chance_of_rain}%)")

    # Check bão/sấm sét/ngập
    for kw in BAD_WEATHER_KEYWORDS:
        if kw in condition_text:
            reasons.append(f"Cảnh báo: {condition_text}")
            break

    # Check nắng cực đoan
    if temp_c >= EXTREME_TEMP_C:
        reasons.append(f"Nắng cực đoan ({temp_c}°C)")

    is_bad = len(reasons) > 0

    details = (
        f"Nhiệt độ {temp_c}°C, "
        f"mưa {chance_of_rain}%, "
        f"gió {wind_kph}km/h, "
        f"độ ẩm {humidity}%"
        f"{', ' + condition_text if condition_text else ''}"
    )

    return {
        "is_bad": is_bad,
        "reason": " | ".join(reasons) if reasons else "Thời tiết tốt",
        "details": details,
    }


def scan_24h_for_bad_windows(weather_data: dict) -> list[dict]:
    """
    Quét toàn bộ forecast 24h, trả về list khung giờ thời tiết xấu.
    Mỗi entry: {"hour": "2026-04-02 14:00", "reason": "...", "details": "..."}
    List rỗng = 24h tới OK → Observer không cần query DB.
    """
    bad_windows = []

    forecast_days = weather_data.get("forecast", {}).get("forecastday", [])
    for day in forecast_days:
        for hour_entry in day.get("hour", []):
            result = analyze_hour_weather(hour_entry)
            if result["is_bad"]:
                bad_windows.append({
                    "hour": hour_entry.get("time", ""),         # "2026-04-02 14:00"
                    "epoch": hour_entry.get("time_epoch", 0),
                    "reason": result["reason"],
                    "details": result["details"],
                })

    return bad_windows


def find_matching_bad_window(bad_windows: list[dict], proposed_time: datetime) -> dict | None:
    """
    Tìm khung giờ xấu trùng với proposed_time của event.
    Match bằng hour string (YYYY-MM-DD HH:00).
    """
    if not proposed_time:
        return None

    vn_tz = timezone(timedelta(hours=7))
    if proposed_time.tzinfo is None:
        proposed_time = proposed_time.replace(tzinfo=vn_tz)

    event_hour_str = proposed_time.astimezone(vn_tz).strftime("%Y-%m-%d %H:00")

    for window in bad_windows:
        if window["hour"] == event_hour_str:
            return window

    return None


def generate_cancel_email(event: dict, weather_reason: str) -> dict:
    """
    Tạo mẫu email huỷ/hoãn lịch hẹn, user có thể tuỳ chỉnh trước khi gửi.
    """
    title = event.get("title", "cuộc hẹn")
    proposed_time = event.get("proposed_time")
    participants = event.get("participants", [])

    # Format time
    time_str = "thời gian chưa xác định"
    if proposed_time:
        if isinstance(proposed_time, str):
            try:
                proposed_time = datetime.fromisoformat(proposed_time)
            except (ValueError, TypeError):
                pass
        if isinstance(proposed_time, datetime):
            vn_tz = timezone(timedelta(hours=7))
            time_str = proposed_time.astimezone(vn_tz).strftime("%H:%M ngày %d/%m/%Y")

    subject = f"[Thông báo] Hoãn lịch hẹn: {title}"
    body = (
        f"Xin chào,\n\n"
        f"Do dự báo thời tiết sắp tới ({weather_reason}), "
        f"tôi xin phép hoãn/huỷ cuộc hẹn \"{title}\" "
        f"vào lúc {time_str}.\n\n"
        f"Mong bạn thông cảm. Tôi sẽ sắp xếp lại lịch hẹn sớm nhất có thể.\n\n"
        f"Trân trọng."
    )

    return {
        "subject": subject,
        "body": body,
        "recipients": participants,
    }


def build_weather_alert_payload(event: dict, weather_info: dict, proposal_id: str) -> dict:
    """
    Xây dựng payload WEATHER_ALERT để push qua WebSocket.
    Cấu trúc tương thích với useProposals → ProposalSidebar.
    """
    cancel_email = generate_cancel_email(event, weather_info["reason"])

    return {
        "type": "WEATHER_ALERT",
        "source": "weather_system",
        "user_id": str(event["user_id"]),
        "data": {
            "db_id": proposal_id,
            "event_id": str(event.get("id", "")),
            "event_title": event.get("title", ""),
            "proposed_time": (
                event["proposed_time"].isoformat()
                if isinstance(event.get("proposed_time"), datetime)
                else str(event.get("proposed_time", ""))
            ),
            "participants": event.get("participants", []),
            "weather_reason": weather_info["reason"],
            "weather_details": weather_info["details"],
            "suggested_actions": [
                {
                    "action_type": "cancel_event",
                    "label": "Huỷ lịch & gửi email thông báo",
                    "payload": cancel_email,
                },
                {
                    "action_type": "ignore",
                    "label": "Bỏ qua cảnh báo",
                },
            ],
        },
    }


async def push_weather_alert(user_id: str, event: dict, weather_info: dict, proposal_id: str):
    """
    Push WEATHER_ALERT qua Redis PubSub → FastAPI → WebSocket → Frontend.
    """
    import redis.asyncio as aioredis
    from celery_app import redis_url

    payload = build_weather_alert_payload(event, weather_info, proposal_id)

    try:
        r = aioredis.from_url(redis_url)
        await r.publish("aia_ws_messages", json.dumps(payload, ensure_ascii=False, default=str))
        print(f"[WeatherAlerter] ✓ Pushed alert for event={str(event.get('id', '?'))[:8]} user={str(user_id)[:8]}")
    except Exception as e:
        print(f"[WeatherAlerter] ✗ Redis publish error: {e}")
