from celery_app import celery_app
import asyncio
from agents.graph import get_compiled_graph
from langchain_core.messages import HumanMessage
import traceback


def get_or_create_eventloop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop


# ── System tasks ──────────────────────────────────────────────────────────────
@celery_app.task(name="tasks.save_token_usage_task", ignore_result=True)
def save_token_usage_task(user_id: str, period: str, tokens_in: int, tokens_out: int):
    try:
        from services.db_service import add_token_usage
        loop = get_or_create_eventloop()
        loop.run_until_complete(add_token_usage(user_id, period, tokens_in, tokens_out))
    except Exception as e:
        print(f"[Tokens] Task record error: {e}")

# ── Chat task ──────────────────────────────────────────────────────────────
@celery_app.task(bind=True, name="tasks.process_chat")
def process_chat(self, user_id: str, message: str, doc_context: str, image_context: str, image_filename: str):
    from llm.gemini_client import current_user_id
    current_user_id.set(user_id)
    try:
        combined_context = doc_context
        if image_context:
            combined_context += f"\n\n[Ảnh đã upload: {image_filename}]\n{image_context}"

        initial_state = {
            "messages": [HumanMessage(content=message)],
            "user_id": user_id,
            "user_context": "",
            "route": "",
            "route_reasoning": "",
            "tool_results": "",
            "final_response": "",
            "document_context": combined_context,
            "error": "",
        }

        loop = get_or_create_eventloop()
        graph = get_compiled_graph()
        result = loop.run_until_complete(graph.ainvoke(initial_state))

        response_payload = {
            "response": result.get("final_response", "Xin lỗi, tôi không thể xử lý yêu cầu này.") or "Xin lỗi, tôi không thể xử lý.",
            "route": result.get("route"),
            "route_reasoning": result.get("route_reasoning"),
        }

        # Publish result back via Redis PubSub
        try:
            import redis
            import json
            from celery_app import redis_url
            r = redis.from_url(redis_url)
            pub_data = {**response_payload, "user_id": user_id, "type": "chat_response", "task_id": self.request.id}
            r.publish("aia_ws_messages", json.dumps(pub_data))
        except Exception as redis_e:
            print(f"[Celery] Redis publish error: {redis_e}")

        return response_payload
    except Exception as e:
        traceback.print_exc()
        raise Exception(f"Chat processing error: {str(e)}")


# ── TTS task ───────────────────────────────────────────────────────────────
@celery_app.task(bind=True, name="tasks.generate_tts")
def generate_tts(self, user_id: str, text: str):
    try:
        from services.tts_service import synthesize_speech
        import base64
        import redis
        import json
        from celery_app import redis_url

        audio_bytes = synthesize_speech(text)
        base64Str = base64.b64encode(audio_bytes).decode("utf-8")

        payload = {
            "type": "tts_response",
            "task_id": self.request.id,
            "user_id": user_id,
            "audio_base64": base64Str,
        }

        try:
            r = redis.from_url(redis_url)
            r.publish("aia_ws_messages", json.dumps(payload))
        except Exception as redis_e:
            print(f"[Celery] Redis publish error for TTS: {redis_e}")

        return {"audio_base64": base64Str}

    except Exception as e:
        traceback.print_exc()
        try:
            import redis
            import json
            from celery_app import redis_url
            r = redis.from_url(redis_url)
            payload = {
                "type": "tts_response",
                "task_id": self.request.id,
                "user_id": user_id,
                "error": str(e),
            }
            r.publish("aia_ws_messages", json.dumps(payload))
        except Exception:
            pass
        raise Exception(f"TTS generation error: {str(e)}")


# ── Email Assistant task (on-demand — triggered by Gmail Watch Pub/Sub) ─────
# Không còn chạy theo Celery Beat. Thay vào đó, gmail_watch.py gọi trực tiếp
# async qua FastAPI event loop khi nhận push notification từ Google Pub/Sub.
# Task Celery này giữ lại như fallback nếu cần gọi thủ công từ CLI/API.

@celery_app.task(bind=True, name="tasks.process_user_emails")
def process_user_emails(self, user_id: str):
    """
    On-demand: Kéo email mới cho MỘT user cụ thể.
    Được gọi khi Gmail Watch Pub/Sub phát hiện email mới,
    hoặc khi admin muốn trigger thủ công.
    """
    import asyncio
    import traceback
    from llm.gemini_client import current_user_id

    current_user_id.set(user_id)

    async def _run():
        from tools.email_tools import fetch_unread_emails, check_gmail_authorized
        from agents.email_agent import process_email_intent

        if not await check_gmail_authorized(user_id):
            print(f"[EmailTask] User {user_id[:8]}… chưa cấp phép Gmail")
            return

        emails = await fetch_unread_emails(user_id=user_id, limit=10)
        print(f"[EmailTask] user={user_id[:8]}… → {len(emails)} email qua bộ lọc")

        for email_data in emails:
            try:
                await process_email_intent(user_id=user_id, email_data=email_data)
            except Exception as email_err:
                print(f"[EmailTask] intent error for {email_data.get('id')}: {email_err}")
                traceback.print_exc()

    loop = get_or_create_eventloop()
    loop.run_until_complete(_run())


# ── Weather Fetch task (Celery Beat — every 1 hour) + OBSERVER ─────────────

@celery_app.task(bind=True, name="tasks.fetch_weather_for_events")
def fetch_weather_for_events(self):
    """
    1) Lấy dữ liệu thời tiết cho tất cả tỉnh/thành phố có lịch hẹn weather_dependent.
    2) OBSERVER: Sau khi cào xong, quét 24h forecast tìm khung giờ xấu.
       Chỉ khi phát hiện thời tiết xấu → query DB tìm events bị ảnh hưởng → batch alert.
    """
    import asyncio
    import traceback
    import requests
    import json

    async def _run():
        from services.db_service import (
            get_weather_dependent_locations, save_weather_data,
            get_events_in_bad_weather_window, mark_event_weather_alerted,
        )
        from services.weather_alerter import (
            scan_24h_for_bad_windows, find_matching_bad_window,
            push_weather_alert,
        )
        from services.db_service import create_pending_proposal
        from config import get_settings

        settings = get_settings()
        locations = await get_weather_dependent_locations()

        if not locations:
            print("[WeatherTask] Không có location nào cần lấy thời tiết.")
            return

        print(f"[WeatherTask] Tìm thấy {len(locations)} location(s) cần lấy thời tiết.")

        for loc in locations:
            lat = loc["lat"]
            lon = loc["lon"]
            province = loc.get("province", f"{lat},{lon}")

            try:
                url = (
                    f"http://api.weatherapi.com/v1/forecast.json"
                    f"?key={settings.weather_api_key}"
                    f"&q={lat},{lon}"
                    f"&days=1"
                    f"&aqi=no"
                    f"&alerts=yes"
                )
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                data = resp.json()

                await save_weather_data(
                    location_name=province,
                    lat=lat,
                    lon=lon,
                    data=data,
                )
                print(f"[WeatherTask] ✓ {province} ({lat},{lon}) — "
                      f"temp={data.get('current', {}).get('temp_c', '?')}°C")

                # ═══ OBSERVER PHASE ═══
                bad_windows = scan_24h_for_bad_windows(data)

                if not bad_windows:
                    print(f"[WeatherObserver] {province}: 24h OK — skip DB query")
                    continue

                print(f"[WeatherObserver] {province}: {len(bad_windows)} bad hour(s) detected!")
                bad_hours = [w["hour"] for w in bad_windows]

                # Chỉ khi có khung giờ xấu → query events bị ảnh hưởng
                affected_events = await get_events_in_bad_weather_window(
                    bad_hours=bad_hours,
                    province=province,
                )

                if not affected_events:
                    print(f"[WeatherObserver] {province}: No events in bad windows")
                    continue

                print(f"[WeatherObserver] {province}: {len(affected_events)} event(s) affected!")

                # Batch dispatch alerts
                for event in affected_events:
                    matching_window = find_matching_bad_window(bad_windows, event.get("proposed_time"))
                    if not matching_window:
                        continue

                    weather_info = {
                        "reason": matching_window["reason"],
                        "details": matching_window["details"],
                    }

                    # Tạo proposal trong DB
                    from services.weather_alerter import build_weather_alert_payload
                    proposal_payload = build_weather_alert_payload(event, weather_info, "")
                    proposal_id = await create_pending_proposal(
                        user_id=event["user_id"],
                        gmail_id=None,
                        payload=proposal_payload.get("data", {}),
                    )

                    # Push alert qua WebSocket
                    await push_weather_alert(
                        user_id=event["user_id"],
                        event=event,
                        weather_info=weather_info,
                        proposal_id=proposal_id,
                    )

                    # Đánh dấu đã cảnh báo
                    await mark_event_weather_alerted(str(event["id"]))
                    print(f"[WeatherObserver] ✓ Alert sent for event={str(event['id'])[:8]}")

            except Exception as e:
                print(f"[WeatherTask] ✗ {province}: {e}")
                traceback.print_exc()

    loop = get_or_create_eventloop()
    loop.run_until_complete(_run())


# ── ETA Task: Check weather 1h before a specific event ─────────────────────

@celery_app.task(bind=True, name="tasks.check_weather_before_event")
def check_weather_before_event(self, event_id: str, user_id: str):
    """
    Chạy đúng 1h trước event (scheduled via ETA).
    Kiểm tra thời tiết tại location của user → nếu xấu → push alert.
    """
    import asyncio
    import traceback
    import requests
    import json

    async def _run():
        from services.db_service import (
            get_event_by_id, get_user_address,
            get_weather_data_for_location, save_weather_data,
            create_pending_proposal, mark_event_weather_alerted,
        )
        from services.weather_alerter import (
            analyze_hour_weather, push_weather_alert,
            build_weather_alert_payload,
        )
        from config import get_settings
        from datetime import datetime, timezone, timedelta

        # 1. Lấy event — verify vẫn active
        event = await get_event_by_id(event_id)
        if not event:
            print(f"[WeatherETA] Event {event_id[:8]} not found — skip")
            return
        if event.get("status") not in ("pending", "confirmed"):
            print(f"[WeatherETA] Event {event_id[:8]} status={event.get('status')} — skip")
            return
        if event.get("weather_alerted"):
            print(f"[WeatherETA] Event {event_id[:8]} already alerted — skip")
            return

        # 2. Lấy user address
        addr = await get_user_address(user_id)
        if not addr or not addr.get("address_province"):
            print(f"[WeatherETA] User {user_id[:8]} has no address — skip")
            return

        province = addr["address_province"]
        lat = addr["address_lat"]
        lon = addr["address_lon"]

        # 3. Lấy weather_data từ DB (nếu không có → call API → save)
        weather_data = await get_weather_data_for_location(province)

        if not weather_data:
            print(f"[WeatherETA] No cached weather for {province} — fetching...")
            settings = get_settings()
            try:
                url = (
                    f"http://api.weatherapi.com/v1/forecast.json"
                    f"?key={settings.weather_api_key}"
                    f"&q={lat},{lon}"
                    f"&days=1&aqi=no&alerts=yes"
                )
                resp = requests.get(url, timeout=15)
                resp.raise_for_status()
                weather_data = resp.json()
                await save_weather_data(province, lat, lon, weather_data)
            except Exception as e:
                print(f"[WeatherETA] ✗ API error for {province}: {e}")
                return

        # 4. Tìm hourly forecast cho giờ của event
        vn_tz = timezone(timedelta(hours=7))
        proposed_time = event.get("proposed_time")
        if proposed_time and proposed_time.tzinfo is None:
            proposed_time = proposed_time.replace(tzinfo=vn_tz)

        event_hour_str = proposed_time.astimezone(vn_tz).strftime("%Y-%m-%d %H:00") if proposed_time else None

        hourly_match = None
        for day in weather_data.get("forecast", {}).get("forecastday", []):
            for hour_entry in day.get("hour", []):
                if hour_entry.get("time") == event_hour_str:
                    hourly_match = hour_entry
                    break

        if not hourly_match:
            print(f"[WeatherETA] No hourly data for {event_hour_str} — skip")
            return

        # 5. Phân tích thời tiết
        result = analyze_hour_weather(hourly_match)

        if not result["is_bad"]:
            print(f"[WeatherETA] Event {event_id[:8]}: Weather OK at {event_hour_str}")
            return

        print(f"[WeatherETA] ⚠ Event {event_id[:8]}: BAD WEATHER — {result['reason']}")

        # 6. Tạo proposal + push alert
        weather_info = {"reason": result["reason"], "details": result["details"]}

        event_dict = dict(event)
        event_dict["user_id"] = user_id

        proposal_payload = build_weather_alert_payload(event_dict, weather_info, "")
        proposal_id = await create_pending_proposal(
            user_id=user_id,
            gmail_id=None,
            payload=proposal_payload.get("data", {}),
        )

        await push_weather_alert(user_id, event_dict, weather_info, proposal_id)
        await mark_event_weather_alerted(event_id, self.request.id)

    loop = get_or_create_eventloop()
    try:
        loop.run_until_complete(_run())
    except Exception:
        traceback.print_exc()

# ── News Scraping Task ────────────────────────────────────────────────────────
@celery_app.task(bind=True, name="tasks.fetch_and_index_news_task")
def fetch_and_index_news_task(self):
    """
    Quét tin tức theo cấu hình của người dùng. Tải và đẩy lên Vertex Store.
    """
    import asyncio
    import traceback
    import hashlib

    async def _run():
        from services.db_service import get_db_pool
        from memory.user_context import get_user_profile
        from tools.news_tools import fetch_rss_news, search_google_news, push_to_vertex_search

        pool = await get_db_pool()
        async with pool.acquire() as conn:
            # Thu thập toàn bộ danh sách user (Mockup: query sessions hoặc events proxy user_id)
            rows = await conn.fetch("SELECT user_id::text FROM user_sessions")
            user_ids = list(set([row["user_id"] for row in rows if row["user_id"]]))
            if "default_user" not in user_ids:
                user_ids.append("default_user")

        processed_urls = set()
        total_pushed = 0

        for uid in user_ids:
            profile = await get_user_profile(uid)
            if not profile: continue
            
            interests = profile.interests or []
            urls = profile.preferred_news_sources or []
            if not interests and not urls:
                continue
                
            articles = []
            
            # 1. Fetch bằng URLs Custom (dùng rss fallback)
            for url in urls:
                try:
                    res = fetch_rss_news(url, source_name="Feed", limit=5)
                    for a in res:
                        if a["url"] not in processed_urls:
                            a["tag"] = "Nguồn yêu thích"
                            articles.append(a)
                            processed_urls.add(a["url"])
                except Exception as e:
                    print(f"[NewsTask] URL {url} err: {e}")
                    
            # 2. Ngôn từ sở thích (Google News)
            for tag in interests:
                try:
                    res = search_google_news(tag, limit=3, lang="vi")
                    for a in res:
                        if a["url"] not in processed_urls:
                            a["tag"] = tag
                            articles.append(a)
                            processed_urls.add(a["url"])
                except Exception as e:
                    print(f"[NewsTask] Interest {tag} err: {e}")

            # Push vào Vertex Search
            for a in articles:
                doc_id = hashlib.md5(a["url"].encode()).hexdigest()
                doc = {
                    "id": doc_id,
                    "title": a["title"],
                    "content": a.get("summary", "") or a["title"],
                    "metadata": {
                        "source": a["source"],
                        "url": a["url"],
                        "published": a.get("published", ""),
                        "tag": a.get("tag", "Chung"),
                    }
                }
                success = push_to_vertex_search(doc)
                if success:
                    total_pushed += 1

        print(f"[NewsTask] Completed. Pushed {total_pushed} new documents to Vertex DB.")

    loop = get_or_create_eventloop()
    try:
        loop.run_until_complete(_run())
    except Exception:
        traceback.print_exc()
