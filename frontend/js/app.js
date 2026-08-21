/* =========================================================================
   WeatherNow — frontend application logic
   Talks to the FastAPI backend under /api. No page reloads: every search,
   theme change, and geolocation lookup happens via fetch().
   ========================================================================= */
(() => {
  "use strict";

  const API_BASE = "/api";

  // ---- DOM references -----------------------------------------------
  const el = {
    searchForm: document.getElementById("searchForm"),
    cityInput: document.getElementById("cityInput"),
    locationBtn: document.getElementById("locationBtn"),
    themeToggle: document.getElementById("themeToggle"),
    themeIcon: document.getElementById("themeIcon"),

    errorBanner: document.getElementById("errorBanner"),
    errorText: document.getElementById("errorText"),
    errorDismiss: document.getElementById("errorDismiss"),

    heroSkeleton: document.getElementById("heroSkeleton"),
    heroContent: document.getElementById("heroContent"),
    heroCity: document.getElementById("heroCity"),
    heroUpdated: document.getElementById("heroUpdated"),
    heroIcon: document.getElementById("heroIcon"),
    heroTemp: document.getElementById("heroTemp"),
    heroDesc: document.getElementById("heroDesc"),
    heroFeels: document.getElementById("heroFeels"),
    heroRange: document.getElementById("heroRange"),

    statsGrid: document.getElementById("statsGrid"),
    dailyStrip: document.getElementById("dailyStrip"),
    hourlyScroll: document.getElementById("hourlyScroll"),

    historyList: document.getElementById("historyList"),
    historyEmpty: document.getElementById("historyEmpty"),
    clearHistoryBtn: document.getElementById("clearHistoryBtn"),

    statCardTemplate: document.getElementById("statCardTemplate"),
  };

  let tempChart = null;
  let humidChart = null;
  let lastCity = null;

  // ---- Theme -----------------------------------------------------------
  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    el.themeIcon.textContent = theme === "dark" ? "☀️" : "🌙";
    localStorage.setItem("weathernow-theme", theme);
    refreshChartTheme();
  }

  function initTheme() {
    const saved = localStorage.getItem("weathernow-theme");
    if (saved) {
      applyTheme(saved);
      return;
    }
    const prefersDark = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
    applyTheme(prefersDark ? "dark" : "light");
  }

  el.themeToggle.addEventListener("click", () => {
    const current = document.documentElement.getAttribute("data-theme");
    applyTheme(current === "dark" ? "light" : "dark");
  });

  // ---- Error banner ------------------------------------------------------
  function showError(message) {
    el.errorText.textContent = message;
    el.errorBanner.hidden = false;
  }
  function hideError() {
    el.errorBanner.hidden = true;
  }
  el.errorDismiss.addEventListener("click", hideError);

  // ---- Fetch helper --------------------------------------------------
  async function apiGet(path) {
    const res = await fetch(API_BASE + path);
    if (!res.ok) {
      let detail = `Request failed (${res.status}).`;
      try {
        const body = await res.json();
        if (body && body.detail) detail = body.detail;
      } catch (_) {
        /* ignore parse errors */
      }
      throw new Error(detail);
    }
    if (res.status === 204) return null;
    return res.json();
  }

  async function apiDelete(path) {
    const res = await fetch(API_BASE + path, { method: "DELETE" });
    if (!res.ok && res.status !== 204) {
      throw new Error(`Request failed (${res.status}).`);
    }
  }

  // ---- Loading state -----------------------------------------------------
  function setLoading(isLoading) {
    el.heroSkeleton.hidden = !isLoading;
    el.heroContent.hidden = isLoading;
  }

  // ---- Rendering: hero card ----------------------------------------------
  function renderHero(data) {
    el.heroCity.textContent = `${data.city}${data.country && data.country !== "N/A" ? ", " + data.country : ""}`;
    el.heroUpdated.textContent = `Updated ${data.last_updated}`;
    el.heroIcon.src = data.icon_url;
    el.heroIcon.alt = data.description;
    el.heroTemp.textContent = data.temperature != null ? `${Math.round(data.temperature)}${data.temp_symbol}` : "--";
    el.heroDesc.textContent = data.description || "—";
    el.heroFeels.textContent = data.feels_like != null ? `Feels like ${Math.round(data.feels_like)}${data.temp_symbol}` : "";
    const hi = data.temp_max != null ? Math.round(data.temp_max) : "--";
    const lo = data.temp_min != null ? Math.round(data.temp_min) : "--";
    el.heroRange.textContent = `H ${hi}${data.temp_symbol}   L ${lo}${data.temp_symbol}`;
  }

  // ---- Rendering: stats grid ----------------------------------------------
  function statCard(icon, label, value, sub) {
    const node = el.statCardTemplate.content.cloneNode(true);
    node.querySelector(".stat-card__icon").textContent = icon;
    node.querySelector(".stat-card__label").textContent = label;
    node.querySelector(".stat-card__value").textContent = value;
    node.querySelector(".stat-card__sub").textContent = sub || "";
    return node;
  }

  function renderStats(data) {
    el.statsGrid.innerHTML = "";
    const items = [
      ["💧", "Humidity", data.humidity != null ? `${data.humidity}%` : "N/A", "Relative humidity"],
      ["💨", "Wind", data.wind_speed != null ? `${data.wind_speed} ${data.speed_symbol}` : "N/A", windDirection(data.wind_deg)],
      ["🌡", "Pressure", data.pressure != null ? `${data.pressure} hPa` : "N/A", "Sea level"],
      ["👁", "Visibility", data.visibility != null ? `${(data.visibility / 1000).toFixed(1)} km` : "N/A", ""],
      ["☀", "UV Index", "N/A", "Needs paid tier"],
      ["🌧", "Precipitation", firstPop(), "Next few hours"],
      ["🌅", "Sunrise", data.sunrise || "N/A", ""],
      ["🌇", "Sunset", data.sunset || "N/A", ""],
    ];
    items.forEach(([icon, label, value, sub]) => el.statsGrid.appendChild(statCard(icon, label, value, sub)));
  }

  let lastHourly = [];
  function firstPop() {
    if (lastHourly.length && lastHourly[0].pop != null) return `${lastHourly[0].pop}%`;
    return "N/A";
  }

  function windDirection(deg) {
    if (deg == null) return "";
    const dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
    return dirs[Math.round(deg / 45) % 8];
  }

  // ---- Rendering: daily forecast strip ----------------------------------
  function renderDaily(daily, tempSymbol) {
    el.dailyStrip.innerHTML = "";
    daily.forEach((day) => {
      const div = document.createElement("div");
      div.className = "daily-item";
      div.innerHTML = `
        <p class="daily-item__label">${day.day_label}</p>
        <img class="daily-item__icon" src="${day.icon_url}" alt="${day.description}" loading="lazy" />
        <p class="daily-item__temps">${round(day.temp_max)}°<span>${round(day.temp_min)}°</span></p>
        <p class="daily-item__pop">${day.pop != null ? day.pop + "% rain" : ""}</p>
      `;
      el.dailyStrip.appendChild(div);
    });
  }

  // ---- Rendering: hourly forecast ----------------------------------------
  function renderHourly(hourly, tempSymbol) {
    lastHourly = hourly;
    el.hourlyScroll.innerHTML = "";
    hourly.forEach((h) => {
      const div = document.createElement("div");
      div.className = "hourly-item";
      div.innerHTML = `
        <p class="hourly-item__time">${h.time}</p>
        <img class="hourly-item__icon" src="${h.icon_url}" alt="" loading="lazy" />
        <p class="hourly-item__temp">${round(h.temperature)}${tempSymbol}</p>
        <p class="hourly-item__pop">${h.pop != null ? h.pop + "%" : ""}</p>
      `;
      el.hourlyScroll.appendChild(div);
    });
  }

  function round(n) {
    return n == null ? "--" : Math.round(n);
  }

  // ---- Rendering: charts ---------------------------------------------
  function chartColors() {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    return {
      grid: dark ? "rgba(255,255,255,0.08)" : "rgba(23,32,56,0.08)",
      text: dark ? "#a3aecb" : "#5b6b8c",
      accent: dark ? "#7dd3fc" : "#3d6bff",
      warm: dark ? "#fbbf24" : "#ff8a5c",
    };
  }

  function renderCharts(hourly) {
    const labels = hourly.map((h) => h.time);
    const temps = hourly.map((h) => h.temperature);
    const pops = hourly.map((h) => h.pop);
    const c = chartColors();

    const baseOptions = {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { labels: { color: c.text } } },
      scales: {
        x: { ticks: { color: c.text }, grid: { color: c.grid } },
        y: { ticks: { color: c.text }, grid: { color: c.grid } },
      },
    };

    if (tempChart) tempChart.destroy();
    tempChart = new Chart(document.getElementById("tempChart"), {
      type: "line",
      data: {
        labels,
        datasets: [
          {
            label: "Temperature",
            data: temps,
            borderColor: c.accent,
            backgroundColor: c.accent + "33",
            fill: true,
            tension: 0.35,
            pointRadius: 3,
          },
        ],
      },
      options: baseOptions,
    });

    if (humidChart) humidChart.destroy();
    humidChart = new Chart(document.getElementById("humidChart"), {
      type: "bar",
      data: {
        labels,
        datasets: [
          {
            label: "Chance of rain (%)",
            data: pops,
            backgroundColor: c.warm,
            borderRadius: 6,
          },
        ],
      },
      options: baseOptions,
    });
  }

  function refreshChartTheme() {
    if (!tempChart || !humidChart) return;
    renderCharts(lastHourly);
  }

  // ---- History sidebar -------------------------------------------------
  function timeAgo(searchedAt) {
    return searchedAt; // already a readable "YYYY-MM-DD HH:MM:SS" string
  }

  async function loadHistory() {
    try {
      const rows = await apiGet("/history?limit=20");
      el.historyList.querySelectorAll(".history-item").forEach((n) => n.remove());
      el.historyEmpty.hidden = rows.length > 0;
      rows.forEach((row) => {
        const li = document.createElement("li");
        li.className = "history-item";
        li.innerHTML = `
          <div class="history-item__main">
            <p class="history-item__city">${row.city}${row.country ? ", " + row.country : ""}</p>
            <p class="history-item__time">${timeAgo(row.searched_at)}</p>
          </div>
          <span class="history-item__temp">${row.temperature != null ? Math.round(row.temperature) + "°" : ""}</span>
          <button class="history-item__del" title="Remove" aria-label="Remove ${row.city} from history">✕</button>
        `;
        li.querySelector(".history-item__main").addEventListener("click", () => searchCity(row.city));
        li.querySelector(".history-item__temp").addEventListener("click", () => searchCity(row.city));
        li.querySelector(".history-item__del").addEventListener("click", async (evt) => {
          evt.stopPropagation();
          try {
            await apiDelete(`/history/${row.id}`);
            loadHistory();
          } catch (_) {
            /* best-effort */
          }
        });
        el.historyList.appendChild(li);
      });
    } catch (_) {
      /* history is a non-critical feature; fail silently */
    }
  }

  el.clearHistoryBtn.addEventListener("click", async () => {
    try {
      await apiDelete("/history");
      loadHistory();
    } catch (_) {
      /* ignore */
    }
  });

  // ---- Main search flow -----------------------------------------------
  async function searchCity(city) {
    if (!city || !city.trim()) {
      showError("Please enter a city name.");
      return;
    }
    hideError();
    setLoading(true);
    lastCity = city.trim();

    try {
      const [weather, forecast] = await Promise.all([
        apiGet(`/weather/${encodeURIComponent(lastCity)}`),
        apiGet(`/forecast/${encodeURIComponent(lastCity)}`),
      ]);
      renderHero(weather);
      renderDaily(forecast.daily, forecast.temp_symbol);
      renderHourly(forecast.hourly, forecast.temp_symbol);
      renderStats(weather);
      renderCharts(forecast.hourly);
      setLoading(false);
      el.cityInput.value = "";
      loadHistory();
    } catch (err) {
      setLoading(false);
      el.heroContent.hidden = false;
      showError(err.message || "Something went wrong. Please try again.");
    }
  }

  async function searchByCoords(lat, lon) {
    hideError();
    setLoading(true);
    try {
      const weather = await apiGet(`/weather?lat=${lat}&lon=${lon}`);
      lastCity = weather.city;
      const forecast = await apiGet(`/forecast?lat=${lat}&lon=${lon}`);
      renderHero(weather);
      renderDaily(forecast.daily, forecast.temp_symbol);
      renderHourly(forecast.hourly, forecast.temp_symbol);
      renderStats(weather);
      renderCharts(forecast.hourly);
      setLoading(false);
      loadHistory();
    } catch (err) {
      setLoading(false);
      el.heroContent.hidden = false;
      showError(err.message || "Could not fetch weather for your location.");
    }
  }

  el.searchForm.addEventListener("submit", (e) => {
    e.preventDefault();
    searchCity(el.cityInput.value);
  });

  el.locationBtn.addEventListener("click", () => {
    if (!navigator.geolocation) {
      showError("Geolocation is not supported by your browser.");
      return;
    }
    hideError();
    navigator.geolocation.getCurrentPosition(
      (pos) => searchByCoords(pos.coords.latitude, pos.coords.longitude),
      () => showError("Could not access your location. Please allow location access, or search by city name."),
      { timeout: 10000 }
    );
  });

  // ---- Boot --------------------------------------------------------------
  async function boot() {
    initTheme();
    await loadHistory();

    // Try to load the most recent search, otherwise a sensible default city.
    try {
      const rows = await apiGet("/history?limit=1");
      if (rows.length) {
        searchCity(rows[0].city);
        return;
      }
    } catch (_) {
      /* ignore */
    }
    searchCity("Nagpur");
  }

  boot();
})();
