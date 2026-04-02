/**
 * WeatherSidebar.tsx - Sidebar hiển thị thời tiết
 * Slide-in panel với glassmorphism design
 */

"use client";

import { useState, useEffect } from "react";
import { getWeather } from "@/lib/api";
import {
  X,
  CloudRain,
  Sun,
  Cloud,
  Wind,
  Droplets,
  Thermometer,
  Eye,
  MapPin,
  RefreshCw,
  CloudSnow,
  CloudLightning,
  CloudDrizzle,
  CloudFog,
} from "lucide-react";

interface WeatherSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

// Map weather condition code to icon
function getWeatherIcon(code: number, isDay: number) {
  if (code === 1000) return isDay ? <Sun size={32} /> : <Sun size={32} />;
  if (code === 1003) return <Cloud size={32} />;
  if ([1006, 1009].includes(code)) return <Cloud size={32} />;
  if ([1030, 1135, 1147].includes(code)) return <CloudFog size={32} />;
  if ([1063, 1150, 1153, 1180, 1183, 1186, 1189, 1192, 1195, 1240, 1243, 1246].includes(code))
    return <CloudRain size={32} />;
  if ([1066, 1069, 1114, 1117, 1210, 1213, 1216, 1219, 1222, 1225, 1255, 1258].includes(code))
    return <CloudSnow size={32} />;
  if ([1087, 1273, 1276, 1279, 1282].includes(code)) return <CloudLightning size={32} />;
  if ([1072, 1168, 1171, 1198, 1201].includes(code)) return <CloudDrizzle size={32} />;
  return <Cloud size={32} />;
}

function getWeatherIconSmall(code: number, isDay: number) {
  if (code === 1000) return isDay ? <Sun size={16} /> : <Sun size={16} />;
  if (code === 1003) return <Cloud size={16} />;
  if ([1006, 1009].includes(code)) return <Cloud size={16} />;
  if ([1063, 1150, 1153, 1180, 1183, 1186, 1189, 1192, 1195, 1240, 1243, 1246].includes(code))
    return <CloudRain size={16} />;
  if ([1066, 1069, 1114, 1117, 1210, 1213, 1216, 1219, 1222, 1225, 1255, 1258].includes(code))
    return <CloudSnow size={16} />;
  if ([1087, 1273, 1276, 1279, 1282].includes(code)) return <CloudLightning size={16} />;
  return <Cloud size={16} />;
}

export default function WeatherSidebar({ isOpen, onClose }: WeatherSidebarProps) {
  const [weatherData, setWeatherData] = useState<any>(null);
  const [status, setStatus] = useState<string>("loading");
  const [message, setMessage] = useState<string>("");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchWeather = async () => {
    try {
      setIsRefreshing(true);
      const res = await getWeather();
      setStatus(res.status);
      if (res.status === "ok" && res.weather) {
        setWeatherData(res.weather);
      } else {
        setMessage(res.message || "Không có dữ liệu");
      }
    } catch (err) {
      setStatus("error");
      setMessage(err instanceof Error ? err.message : "Lỗi kết nối");
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    if (isOpen) {
      fetchWeather();
    }
  }, [isOpen]);

  const data = weatherData?.data;
  const current = data?.current;
  const forecast = data?.forecast?.forecastday?.[0];
  const location = data?.location;
  const hourly = forecast?.hour || [];

  // Get current hour to show relevant forecast
  const nowHour = new Date().getHours();
  const upcomingHours = hourly.filter((_: any, idx: number) => idx >= nowHour).slice(0, 8);
  // If less than 8, pad from beginning
  const displayHours =
    upcomingHours.length >= 8
      ? upcomingHours
      : [...upcomingHours, ...hourly.filter((_: any, idx: number) => idx < nowHour)].slice(0, 8);

  return (
    <div className={`weather-sidebar-overlay ${isOpen ? "weather-sidebar-overlay--open" : ""}`} onClick={onClose}>
      <div
        className={`weather-sidebar ${isOpen ? "weather-sidebar--open" : ""}`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="weather-sidebar__header">
          <div className="weather-sidebar__header-left">
            <CloudRain size={20} style={{ color: "var(--accent-secondary)" }} />
            <h3 className="weather-sidebar__title">Thời tiết</h3>
          </div>
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <button
              className="weather-sidebar__refresh"
              onClick={fetchWeather}
              disabled={isRefreshing}
              title="Tải lại"
            >
              <RefreshCw size={16} className={isRefreshing ? "weather-spin" : ""} />
            </button>
            <button className="weather-sidebar__close" onClick={onClose}>
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="weather-sidebar__content">
          {status === "loading" || (isRefreshing && !weatherData) ? (
            <div className="weather-sidebar__placeholder">
              <div className="typing-indicator">
                <span />
                <span />
                <span />
              </div>
              <p>Đang tải dữ liệu thời tiết...</p>
            </div>
          ) : status === "no_address" ? (
            <div className="weather-sidebar__placeholder">
              <MapPin size={40} style={{ opacity: 0.5, marginBottom: "12px" }} />
              <p>Chưa có địa chỉ</p>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                Vui lòng cập nhật địa chỉ trong phần Thiết lập thông tin cá nhân
              </span>
            </div>
          ) : status === "no_data" ? (
            <div className="weather-sidebar__placeholder">
              <Cloud size={40} style={{ opacity: 0.5, marginBottom: "12px" }} />
              <p>Chưa có dữ liệu thời tiết</p>
              <span style={{ fontSize: "12px", color: "var(--text-muted)" }}>
                {message || "Hệ thống sẽ tự động cập nhật mỗi giờ khi có lịch hẹn phụ thuộc thời tiết."}
              </span>
            </div>
          ) : status === "error" ? (
            <div className="weather-sidebar__placeholder">
              <p style={{ color: "var(--error)" }}>Lỗi: {message}</p>
            </div>
          ) : current ? (
            <>
              {/* Location */}
              <div className="weather-location">
                <MapPin size={14} />
                <span>{location?.name}{location?.country ? `, ${location?.country}` : ""}</span>
              </div>

              {/* Current Weather Card */}
              <div className="weather-current-card">
                <div className="weather-current-card__main">
                  <div className="weather-current-card__icon">
                    {getWeatherIcon(current.condition?.code || 1000, current.is_day)}
                  </div>
                  <div className="weather-current-card__temp">
                    {Math.round(current.temp_c)}°C
                  </div>
                </div>
                <div className="weather-current-card__condition">
                  {current.condition?.text}
                </div>
                <div className="weather-current-card__feels">
                  Cảm giác như {Math.round(current.feelslike_c)}°C
                </div>
              </div>

              {/* Stats Grid */}
              <div className="weather-stats-grid">
                <div className="weather-stat">
                  <Wind size={16} />
                  <div>
                    <span className="weather-stat__value">{current.wind_kph} km/h</span>
                    <span className="weather-stat__label">Gió {current.wind_dir}</span>
                  </div>
                </div>
                <div className="weather-stat">
                  <Droplets size={16} />
                  <div>
                    <span className="weather-stat__value">{current.humidity}%</span>
                    <span className="weather-stat__label">Độ ẩm</span>
                  </div>
                </div>
                <div className="weather-stat">
                  <Eye size={16} />
                  <div>
                    <span className="weather-stat__value">{current.vis_km} km</span>
                    <span className="weather-stat__label">Tầm nhìn</span>
                  </div>
                </div>
                <div className="weather-stat">
                  <Thermometer size={16} />
                  <div>
                    <span className="weather-stat__value">{current.pressure_mb} mb</span>
                    <span className="weather-stat__label">Áp suất</span>
                  </div>
                </div>
              </div>

              {/* Day Forecast */}
              {forecast?.day && (
                <div className="weather-forecast-day">
                  <h4 className="weather-section-title">Dự báo hôm nay</h4>
                  <div className="weather-forecast-day__row">
                    <div className="weather-forecast-day__minmax">
                      <span className="weather-temp-high">↑ {Math.round(forecast.day.maxtemp_c)}°</span>
                      <span className="weather-temp-low">↓ {Math.round(forecast.day.mintemp_c)}°</span>
                    </div>
                    <div className="weather-forecast-day__details">
                      <span>💧 Mưa: {forecast.day.daily_chance_of_rain}%</span>
                      <span>💨 Gió max: {Math.round(forecast.day.maxwind_kph)} km/h</span>
                      <span>☀️ UV: {forecast.day.uv}</span>
                    </div>
                  </div>
                </div>
              )}

              {/* Hourly Forecast */}
              {displayHours.length > 0 && (
                <div className="weather-hourly">
                  <h4 className="weather-section-title">Theo giờ</h4>
                  <div className="weather-hourly__scroll">
                    {displayHours.map((h: any, idx: number) => (
                      <div key={idx} className="weather-hourly__item">
                        <span className="weather-hourly__time">
                          {h.time?.split(" ")[1] || ""}
                        </span>
                        <span className="weather-hourly__icon">
                          {getWeatherIconSmall(h.condition?.code || 1000, h.is_day)}
                        </span>
                        <span className="weather-hourly__temp">
                          {Math.round(h.temp_c)}°
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Astro */}
              {forecast?.astro && (
                <div className="weather-astro">
                  <h4 className="weather-section-title">Mặt trời & Mặt trăng</h4>
                  <div className="weather-astro__grid">
                    <span>🌅 {forecast.astro.sunrise}</span>
                    <span>🌇 {forecast.astro.sunset}</span>
                    <span>🌙 {forecast.astro.moon_phase}</span>
                  </div>
                </div>
              )}

              {/* Last updated */}
              <div className="weather-sidebar__footer">
                Cập nhật: {current.last_updated || "N/A"}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
