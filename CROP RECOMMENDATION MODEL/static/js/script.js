const weatherData = {
  temp: null,
  humidity: null,
  rain: 0,
  location: "",
  updatedAt: "",
};

const dashboardCharts = {};

function formatUpdatedTime(isoText) {
  if (!isoText) {
    return "";
  }
  const date = new Date(isoText);
  if (Number.isNaN(date.getTime())) {
    return "";
  }
  return date.toLocaleString();
}

function renderWeatherPanel() {
  const panel = document.getElementById("weatherPanel");
  if (panel) {
    panel.classList.remove("hidden");
  }

  const tempText = document.getElementById("tempText");
  const humidityText = document.getElementById("humidityText");
  const rainText = document.getElementById("rainText");
  const locationText = document.getElementById("locationText");
  const updatedText = document.getElementById("updatedText");

  if (tempText) {
    tempText.textContent = `${weatherData.temp.toFixed(2)} °C`;
  }
  if (humidityText) {
    humidityText.textContent = `${weatherData.humidity.toFixed(2)} %`;
  }
  if (rainText) {
    rainText.textContent = `${weatherData.rain.toFixed(2)} mm`;
  }
  if (locationText) {
    locationText.textContent = weatherData.location;
  }
  if (updatedText) {
    updatedText.textContent = weatherData.updatedAt
      ? `Updated: ${weatherData.updatedAt}`
      : "";
  }
}

async function fetchOpenMeteoByCoordinates(latitude, longitude) {
  const weatherUrl =
    `https://api.open-meteo.com/v1/forecast?latitude=${latitude}&longitude=${longitude}` +
    "&current=temperature_2m,relative_humidity_2m,precipitation&timezone=auto" +
    `&t=${Date.now()}`;

  const response = await fetch(weatherUrl, { cache: "no-store" });
  const payload = await response.json();

  if (!response.ok || !payload.current) {
    throw new Error("Live weather API unavailable");
  }

  return {
    temp: Number(payload.current.temperature_2m ?? 0),
    humidity: Number(payload.current.relative_humidity_2m ?? 0),
    rain: Number(payload.current.precipitation ?? 0),
    observedAt: payload.current.time || "",
  };
}

async function fetchCoordinatesByCity(city) {
  const geoUrl =
    `https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}` +
    "&count=1&language=en&format=json" +
    `&t=${Date.now()}`;

  const response = await fetch(geoUrl, { cache: "no-store" });
  const payload = await response.json();

  if (!response.ok || !payload.results || !payload.results.length) {
    throw new Error("City not found");
  }

  const place = payload.results[0];
  const labelParts = [place.name, place.admin1, place.country].filter(Boolean);

  return {
    latitude: place.latitude,
    longitude: place.longitude,
    label: labelParts.join(", "),
  };
}

function getCurrentPosition() {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation not supported"));
      return;
    }

    navigator.geolocation.getCurrentPosition(resolve, reject, {
      enableHighAccuracy: true,
      timeout: 10000,
      maximumAge: 0,
    });
  });
}

async function fetchLocationLabelByCoordinates(latitude, longitude) {
  const reverseUrl =
    `https://geocoding-api.open-meteo.com/v1/reverse?latitude=${latitude}&longitude=${longitude}` +
    "&language=en&format=json" +
    `&t=${Date.now()}`;

  const response = await fetch(reverseUrl, { cache: "no-store" });
  const payload = await response.json();

  if (!response.ok || !payload.results || !payload.results.length) {
    return "Current Location";
  }

  const place = payload.results[0];
  const labelParts = [place.name, place.admin1, place.country].filter(Boolean);
  return labelParts.join(", ") || "Current Location";
}

function getHeaderOffset() {
  const header = document.querySelector(".site-header");
  return header ? header.offsetHeight + 10 : 84;
}

function scrollToSectionById(sectionId, smooth = true) {
  const target = document.getElementById(sectionId);
  if (!target) {
    return;
  }

  const top =
    target.getBoundingClientRect().top + window.scrollY - getHeaderOffset();
  window.scrollTo({
    top,
    behavior: smooth ? "smooth" : "auto",
  });
}

function applyInitialSectionTarget() {
  const fromStorage = sessionStorage.getItem("scrollTarget");
  const fromHash = window.location.hash ? window.location.hash.slice(1) : "";
  const target = fromStorage || fromHash;

  if (!target) {
    return;
  }

  sessionStorage.removeItem("scrollTarget");
  setTimeout(() => scrollToSectionById(target, false), 40);
}

function setupDynamicNavbar() {
  const navLinks = Array.from(document.querySelectorAll(".menu a[href*='#']"));
  if (!navLinks.length) {
    return;
  }

  navLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      const href = link.getAttribute("href") || "";
      const hashIndex = href.indexOf("#");
      if (hashIndex === -1) {
        return;
      }

      const targetId = href.slice(hashIndex + 1);
      if (!targetId) {
        return;
      }

      const targetOnCurrentPage = document.getElementById(targetId);
      if (targetOnCurrentPage) {
        event.preventDefault();
        scrollToSectionById(targetId, true);
        history.replaceState(null, "", `#${targetId}`);
        return;
      }

      sessionStorage.setItem("scrollTarget", targetId);
    });
  });

  const sections = ["home", "predictor", "market", "weather", "about"]
    .map((id) => document.getElementById(id))
    .filter(Boolean);

  if (!sections.length) {
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }

        const id = entry.target.id;
        navLinks.forEach((link) => {
          const href = link.getAttribute("href") || "";
          const active = href.endsWith(`#${id}`) || href === `#${id}`;
          link.classList.toggle("active", active);
        });
      });
    },
    {
      threshold: 0.45,
    },
  );

  sections.forEach((section) => observer.observe(section));
}

async function fetchWeather() {
  const cityInput = document.getElementById("cityInput");
  if (!cityInput) {
    return;
  }

  const city = cityInput.value.trim();

  try {
    let latitude;
    let longitude;
    let locationLabel;

    if (city) {
      const locationData = await fetchCoordinatesByCity(city);
      latitude = locationData.latitude;
      longitude = locationData.longitude;
      locationLabel = locationData.label;
    } else {
      const position = await getCurrentPosition();
      latitude = position.coords.latitude;
      longitude = position.coords.longitude;
      locationLabel = await fetchLocationLabelByCoordinates(
        latitude,
        longitude,
      );
    }

    const weather = await fetchOpenMeteoByCoordinates(latitude, longitude);
    weatherData.temp = weather.temp;
    weatherData.humidity = weather.humidity;
    weatherData.rain = weather.rain;
    weatherData.location = locationLabel;
    weatherData.updatedAt = formatUpdatedTime(weather.observedAt);

    renderWeatherPanel();
  } catch (error) {
    alert(
      "Unable to fetch live weather data right now. Enter a valid city or allow location access and try again.",
    );
  }
}

function useWeatherForPrediction() {
  const tempInput = document.querySelector("input[name='temperature']");
  const humidityInput = document.querySelector("input[name='humidity']");
  const rainfallInput = document.getElementById("rainfallInput");
  const locationInput = document.getElementById("locationInput");

  if (tempInput && weatherData.temp !== null) {
    tempInput.value = weatherData.temp.toFixed(2);
  }
  if (humidityInput && weatherData.humidity !== null) {
    humidityInput.value = weatherData.humidity.toFixed(2);
  }
  if (rainfallInput) {
    rainfallInput.value = weatherData.rain.toFixed(2);
  }
  if (locationInput) {
    locationInput.value = weatherData.location;
  }
}

function validatePredictionForm() {
  const form = document.getElementById("predictionForm");
  if (!form) {
    return false;
  }

  // Check all input fields (temperature, humidity, area)
  const tempInput = form.querySelector("input[name='temperature']");
  const humidityInput = form.querySelector("input[name='humidity']");
  const areaInput = form.querySelector("input[name='area']");
  const locationInput = form.querySelector("input[name='location']");

  // Check all select fields
  const seasonSelect = form.querySelector("select[name='season']");
  const cropTypeSelect = form.querySelector("select[name='crop_type']");
  const waterSourceSelect = form.querySelector("select[name='water_source']");
  const climateTypeSelect = form.querySelector("select[name='climate_type']");
  const durationTypeSelect = form.querySelector("select[name='duration_type']");
  const farmingSystemSelect = form.querySelector(
    "select[name='farming_system']",
  );
  const economicUseSelect = form.querySelector("select[name='economic_use']");

  const inputs = [tempInput, humidityInput, areaInput];
  const selects = [
    seasonSelect,
    cropTypeSelect,
    waterSourceSelect,
    climateTypeSelect,
    durationTypeSelect,
    farmingSystemSelect,
    economicUseSelect,
  ];

  // Check if at least one input is filled
  const hasFilledInput = inputs.some(
    (input) => input && input.value && input.value.trim() !== "",
  );

  // Check if at least one select has a value
  const hasSelectedValue = selects.some(
    (select) => select && select.value && select.value !== "",
  );

  // Location can also count as a filled input
  const hasLocation =
    locationInput && locationInput.value && locationInput.value.trim() !== "";

  const isValid = hasFilledInput || hasSelectedValue || hasLocation;

  return isValid;
}

function setupPredictionLoading() {
  const form = document.getElementById("predictionForm");
  const loadingOverlay = document.getElementById("loadingOverlay");

  if (!form || !loadingOverlay) {
    return;
  }

  loadingOverlay.classList.add("hidden");

  form.addEventListener("submit", (event) => {
    if (!validatePredictionForm()) {
      event.preventDefault();
      alert(
        "Please provide at least one factor (temperature, humidity, land area, location, or any selection) to get a prediction.",
      );
      return false;
    }
    if (!form.checkValidity()) {
      return;
    }
    loadingOverlay.classList.remove("hidden");
  });

  window.addEventListener("pageshow", () => {
    loadingOverlay.classList.add("hidden");
  });
}

function setupRevealStagger() {
  const items = document.querySelectorAll(".reveal");
  items.forEach((item, idx) => {
    item.style.animationDelay = `${idx * 0.08}s`;
  });
}

function createCharts() {
  if (typeof Chart === "undefined" || !window.dashboardData) {
    return;
  }

  const suitabilityCanvas = document.getElementById("suitabilityChart");
  const environmentCanvas = document.getElementById("environmentChart");
  const productionCanvas = document.getElementById("productionChart");

  if (!suitabilityCanvas || !environmentCanvas || !productionCanvas) {
    return;
  }

  const chartDefaults = {
    plugins: {
      legend: {
        labels: {
          color: "#1f3d2d",
          font: {
            family: "Manrope",
          },
        },
      },
    },
    scales: {
      x: {
        ticks: { color: "#1f3d2d" },
        grid: { color: "rgba(31, 138, 68, 0.1)" },
      },
      y: {
        ticks: { color: "#1f3d2d" },
        grid: { color: "rgba(31, 138, 68, 0.1)" },
      },
    },
  };

  const data = window.dashboardData;

  ["suitabilityChart", "environmentChart", "productionChart"].forEach((key) => {
    if (dashboardCharts[key]) {
      dashboardCharts[key].destroy();
      dashboardCharts[key] = null;
    }
  });

  dashboardCharts.suitabilityChart = new Chart(suitabilityCanvas, {
    type: "bar",
    data: {
      labels: data.suitability.labels,
      datasets: [
        {
          label: "Suitability Score",
          data: data.suitability.values,
          backgroundColor: ["#2a9d56", "#74c69d", "#ffd166"],
          borderRadius: 10,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      ...chartDefaults,
    },
  });

  dashboardCharts.environmentChart = new Chart(environmentCanvas, {
    type: "radar",
    data: {
      labels: data.environment.labels,
      datasets: [
        {
          label: "Environmental Factors",
          data: data.environment.values,
          backgroundColor: "rgba(42, 157, 86, 0.2)",
          borderColor: "#2a9d56",
          borderWidth: 2,
          pointBackgroundColor: "#f4b942",
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: chartDefaults.plugins,
      scales: {
        r: {
          angleLines: { color: "rgba(31, 138, 68, 0.25)" },
          grid: { color: "rgba(31, 138, 68, 0.15)" },
          pointLabels: { color: "#1f3d2d" },
          ticks: { color: "#1f3d2d", backdropColor: "rgba(0,0,0,0)" },
        },
      },
    },
  });

  dashboardCharts.productionChart = new Chart(productionCanvas, {
    type: "line",
    data: {
      labels: data.production.labels,
      datasets: [
        {
          label: "Prediction",
          data: data.production.values,
          borderColor: "#f4b942",
          backgroundColor: "rgba(244, 185, 66, 0.25)",
          borderWidth: 3,
          tension: 0.35,
          fill: true,
          pointRadius: 5,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      ...chartDefaults,
    },
  });
}

function createExtendedCharts() {
  if (typeof Chart === "undefined" || !window.dashboardData) {
    return;
  }

  const data = window.dashboardData;
  const radarCanvas = document.getElementById("radarChart");
  const riskCanvas = document.getElementById("riskChart");
  const projectionCanvas = document.getElementById("projectionChart");

  if (radarCanvas && data.radar) {
    if (dashboardCharts.radarChart) {
      dashboardCharts.radarChart.destroy();
      dashboardCharts.radarChart = null;
    }
    dashboardCharts.radarChart = new Chart(radarCanvas, {
      type: "radar",
      data: {
        labels: data.radar.labels,
        datasets: [
          {
            label: "Input Factor Score",
            data: data.radar.values,
            backgroundColor: "rgba(42, 157, 86, 0.18)",
            borderColor: "#2a9d56",
            borderWidth: 2,
            pointBackgroundColor: "#f4b942",
            pointRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#1f3d2d", font: { family: "Manrope" } } },
        },
        scales: {
          r: {
            min: 0,
            max: 100,
            angleLines: { color: "rgba(31, 138, 68, 0.2)" },
            grid: { color: "rgba(31, 138, 68, 0.12)" },
            pointLabels: {
              color: "#1f3d2d",
              font: { family: "Manrope", size: 12 },
            },
            ticks: {
              color: "#1f3d2d",
              backdropColor: "rgba(0,0,0,0)",
              stepSize: 20,
            },
          },
        },
      },
    });
  }

  if (riskCanvas && data.risk) {
    if (dashboardCharts.riskChart) {
      dashboardCharts.riskChart.destroy();
      dashboardCharts.riskChart = null;
    }
    dashboardCharts.riskChart = new Chart(riskCanvas, {
      type: "bar",
      data: {
        labels: data.risk.labels,
        datasets: [
          {
            label: "Risk Score (0-100)",
            data: data.risk.values,
            backgroundColor: data.risk.colors,
            borderRadius: 8,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#1f3d2d", font: { family: "Manrope" } } },
        },
        scales: {
          x: {
            ticks: { color: "#1f3d2d" },
            grid: { color: "rgba(31, 138, 68, 0.1)" },
          },
          y: {
            min: 0,
            max: 100,
            ticks: { color: "#1f3d2d" },
            grid: { color: "rgba(31, 138, 68, 0.1)" },
          },
        },
      },
    });
  }

  if (projectionCanvas && data.yield_projection) {
    if (dashboardCharts.projectionChart) {
      dashboardCharts.projectionChart.destroy();
      dashboardCharts.projectionChart = null;
    }
    dashboardCharts.projectionChart = new Chart(projectionCanvas, {
      type: "line",
      data: {
        labels: data.yield_projection.labels,
        datasets: [
          {
            label: "Projected Total Yield (tons)",
            data: data.yield_projection.values,
            borderColor: "#2563eb",
            backgroundColor: "rgba(37, 99, 235, 0.12)",
            borderWidth: 3,
            tension: 0.35,
            fill: true,
            pointRadius: 6,
            pointBackgroundColor: "#f4b942",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: "#1f3d2d", font: { family: "Manrope" } } },
        },
        scales: {
          x: {
            ticks: { color: "#1f3d2d" },
            grid: { color: "rgba(31, 138, 68, 0.1)" },
          },
          y: {
            ticks: { color: "#1f3d2d" },
            grid: { color: "rgba(31, 138, 68, 0.1)" },
          },
        },
      },
    });
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const weatherBtn = document.getElementById("weatherBtn");
  const useWeatherBtn = document.getElementById("useWeatherBtn");

  applyInitialSectionTarget();
  setupDynamicNavbar();

  if (weatherBtn) {
    weatherBtn.addEventListener("click", fetchWeather);
  }
  if (useWeatherBtn) {
    useWeatherBtn.addEventListener("click", useWeatherForPrediction);
  }

  setupPredictionLoading();
  setupRevealStagger();
  createCharts();
  createExtendedCharts();
});
