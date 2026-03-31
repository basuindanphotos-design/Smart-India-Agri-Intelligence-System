(function () {
  "use strict";

  var chartInstances = {};
  var predictionHistory = [];
  var PREDICTION_HISTORY_KEY = "crop_prediction_history_v1";

  function loadPredictionHistory() {
    try {
      var raw = localStorage.getItem(PREDICTION_HISTORY_KEY);
      predictionHistory = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(predictionHistory)) {
        predictionHistory = [];
      }
    } catch (error) {
      predictionHistory = [];
    }
  }

  function savePredictionHistory() {
    try {
      localStorage.setItem(
        PREDICTION_HISTORY_KEY,
        JSON.stringify(predictionHistory),
      );
    } catch (error) {
      // Ignore localStorage failures silently.
    }
  }

  function csvEscape(value) {
    if (value === null || value === undefined) {
      return "";
    }
    var str = String(value);
    if (/[",\n]/.test(str)) {
      return '"' + str.replace(/"/g, '""') + '"';
    }
    return str;
  }

  function parseCsvLine(line) {
    var fields = [];
    var current = "";
    var inQuotes = false;
    var i;

    for (i = 0; i < line.length; i += 1) {
      var char = line[i];
      if (char === '"') {
        if (inQuotes && line[i + 1] === '"') {
          current += '"';
          i += 1;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (char === "," && !inQuotes) {
        fields.push(current);
        current = "";
      } else {
        current += char;
      }
    }
    fields.push(current);
    return fields;
  }

  function chartDefaults() {
    if (!window.Chart) {
      return;
    }
    window.Chart.defaults.color = "#365e48";
    window.Chart.defaults.font.family = "Segoe UI, Trebuchet MS, sans-serif";
  }

  function buildChart(canvasId, config) {
    var canvas = document.getElementById(canvasId);
    if (!canvas || !window.Chart) {
      return null;
    }
    var chart = new window.Chart(canvas, config);
    chartInstances[canvasId] = chart;
    return chart;
  }

  function readJsonPayload(scriptId) {
    var node = document.getElementById(scriptId);
    if (!node) {
      return null;
    }
    try {
      return JSON.parse(node.textContent);
    } catch (error) {
      return null;
    }
  }

  function initAnalyticsCharts() {
    var data = window.APP_DATA || readJsonPayload("chartDataPayload");
    if (!data) {
      return;
    }

    // Sort crop yield ascending left-to-right (shortest bar first)
    var cyLabels = data.crop_yield_comparison.labels.slice();
    var cyValues = data.crop_yield_comparison.values.slice();
    var cyPairs = cyLabels.map(function (l, i) {
      return [l, cyValues[i]];
    });
    cyPairs.sort(function (a, b) {
      return a[1] - b[1];
    });
    cyLabels = cyPairs.map(function (p) {
      return p[0];
    });
    cyValues = cyPairs.map(function (p) {
      return p[1];
    });

    buildChart("cropYieldChart", {
      type: "bar",
      data: {
        labels: cyLabels,
        datasets: [
          {
            label: "Mean Yield (hg/ha)",
            data: cyValues,
            borderRadius: 8,
            backgroundColor: "rgba(31, 143, 71, 0.75)",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: {
            beginAtZero: true,
            ticks: { maxTicksLimit: 6 },
            grid: { color: "rgba(0,0,0,0.06)" },
          },
        },
        plugins: { legend: { display: false } },
      },
    });

    buildChart("rainfallChart", {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Rainfall vs Yield",
            data: data.rainfall_vs_yield.x.map(function (x, i) {
              return { x: x, y: data.rainfall_vs_yield.y[i] };
            }),
            backgroundColor: "rgba(31, 143, 71, 0.5)",
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            title: { display: true, text: "Rainfall (mm/yr)" },
            beginAtZero: true,
          },
          y: {
            title: { display: true, text: "Yield (hg/ha)" },
            beginAtZero: true,
          },
        },
      },
    });

    buildChart("temperatureChart", {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Temperature vs Yield",
            data: data.temperature_vs_yield.x.map(function (x, i) {
              return { x: x, y: data.temperature_vs_yield.y[i] };
            }),
            backgroundColor: "rgba(242, 177, 52, 0.55)",
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { title: { display: true, text: "Temperature (°C)" } },
          y: {
            title: { display: true, text: "Yield (hg/ha)" },
            beginAtZero: true,
          },
        },
      },
    });

    buildChart("historicalChart", {
      type: "line",
      data: {
        labels: data.historical_yield_trends.labels,
        datasets: [
          {
            label: "Historical Mean Yield (hg/ha)",
            data: data.historical_yield_trends.values,
            fill: true,
            tension: 0.3,
            borderColor: "#1f8f47",
            backgroundColor: "rgba(31, 143, 71, 0.12)",
            pointRadius: 3,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { grid: { display: false } },
          y: {
            beginAtZero: false,
            ticks: { maxTicksLimit: 6 },
            grid: { color: "rgba(0,0,0,0.06)" },
          },
        },
      },
    });

    buildChart("cropDistChart", {
      type: "doughnut",
      data: {
        labels: data.crop_distribution.labels,
        datasets: [
          {
            data: data.crop_distribution.values,
            backgroundColor: [
              "#1f8f47",
              "#2eab5c",
              "#55bf7a",
              "#80d598",
              "#a7e8b5",
              "#f2b134",
              "#f6c45f",
              "#f8d78c",
              "#fce6b6",
              "#daeedd",
            ],
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
      },
    });

    // Sort area yield descending so the longest bar appears at top
    var apLabels = data.area_vs_production.labels.slice();
    var apValues = data.area_vs_production.values.slice();
    var apPairs = apLabels.map(function (l, i) {
      return [l, apValues[i]];
    });
    apPairs.sort(function (a, b) {
      return b[1] - a[1];
    });
    apLabels = apPairs.map(function (p) {
      return p[0];
    });
    apValues = apPairs.map(function (p) {
      return p[1];
    });

    buildChart("areaProdChart", {
      type: "bar",
      data: {
        labels: apLabels,
        datasets: [
          {
            label: "Mean Yield by Area (hg/ha)",
            data: apValues,
            backgroundColor: "rgba(27, 116, 61, 0.74)",
            borderRadius: 6,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: {
            beginAtZero: true,
            ticks: { maxTicksLimit: 6 },
            grid: { color: "rgba(0,0,0,0.06)" },
          },
          y: { grid: { display: false } },
        },
        plugins: { legend: { display: false } },
      },
    });
  }

  // Crop-specific yield thresholds (t/ha) [low, below_avg, good, high]
  // Covers all crops from both global dataset and India merged dataset
  var CROP_YIELD_THRESHOLDS = {
    // ---- Global dataset crops ----
    cassava: [5, 12, 18, 25],
    maize: [1.5, 3, 5, 7],
    "plantains and others": [5, 12, 20, 30],
    potatoes: [5, 12, 18, 25],
    "rice, paddy": [1.5, 3, 4.5, 6],
    sorghum: [0.8, 1.5, 2.5, 4],
    soybeans: [0.8, 1.5, 2.5, 3.5],
    "sweet potatoes": [4, 10, 15, 20],
    wheat: [1.5, 3, 4, 5],
    yams: [3, 8, 12, 18],
    // ---- India dataset crops (str.title() cased, lowercased for lookup) ----
    arecanut: [0.5, 1, 1.8, 2.5],
    "arhar/tur": [0.4, 0.8, 1.3, 2],
    bajra: [0.5, 1, 1.8, 3],
    banana: [10, 20, 30, 40],
    barley: [1, 2, 3, 4],
    "black pepper": [0.2, 0.5, 0.9, 1.5],
    cardamom: [0.1, 0.2, 0.4, 0.7],
    cashewnut: [0.3, 0.7, 1.2, 1.8],
    "castor seed": [0.5, 1, 1.8, 2.5],
    coconut: [3, 6, 10, 15],
    coriander: [0.5, 1, 1.5, 2],
    "cotton(lint)": [0.3, 0.5, 0.8, 1.2],
    "cowpea(lobia)": [0.5, 1, 1.8, 2.5],
    "dry chillies": [0.5, 1, 1.8, 2.5],
    garlic: [5, 10, 15, 20],
    ginger: [5, 12, 18, 25],
    gram: [0.5, 1, 1.8, 2.5],
    groundnut: [1, 2, 3, 4],
    "guar seed": [0.5, 1, 1.5, 2],
    "horse-gram": [0.2, 0.4, 0.7, 1],
    jowar: [0.5, 1, 1.8, 3],
    jute: [1.5, 2.5, 3.5, 5],
    khesari: [0.4, 0.8, 1.2, 1.8],
    linseed: [0.3, 0.6, 1, 1.5],
    masoor: [0.5, 1, 1.5, 2],
    mesta: [1, 2, 3, 4],
    "moong(green gram)": [0.4, 0.8, 1.3, 2],
    moth: [0.2, 0.4, 0.7, 1],
    "niger seed": [0.2, 0.4, 0.6, 1],
    "oilseeds total": [0.5, 1, 1.5, 2],
    onion: [0.8, 2, 3.5, 5],
    "other cereals": [0.5, 1, 2, 3],
    "other kharif pulses": [0.4, 0.8, 1.3, 2],
    "other oilseeds": [0.4, 0.8, 1.3, 2],
    "other rabi pulses": [0.4, 0.8, 1.3, 2],
    "other summer pulses": [0.4, 0.8, 1.3, 2],
    "peas & beans (pulses)": [0.5, 1, 1.5, 2],
    potato: [5, 12, 18, 25],
    ragi: [0.5, 1, 1.8, 2.5],
    "rapeseed &mustard": [0.5, 1, 1.5, 2.5],
    rice: [1.5, 3, 4.5, 6],
    safflower: [0.3, 0.7, 1, 1.5],
    sannhamp: [0.5, 1, 1.5, 2],
    sesamum: [0.2, 0.5, 0.8, 1.2],
    "small millets": [0.3, 0.7, 1.2, 1.8],
    soyabean: [0.8, 1.5, 2.5, 3.5],
    sugarcane: [20, 50, 70, 100],
    sunflower: [0.5, 1, 1.8, 2.5],
    "sweet potato": [4, 10, 15, 20],
    tapioca: [5, 12, 18, 25],
    tobacco: [0.8, 1.5, 2.5, 3.5],
    turmeric: [3, 7, 12, 18],
    urad: [0.4, 0.8, 1.3, 2],
    // ---- Aliases / alternate names ----
    "onions, dry": [0.8, 2, 3.5, 5],
    groundnuts: [1, 2, 3, 4],
    cotton: [0.3, 0.5, 0.8, 1.2],
    millet: [0.5, 1, 1.8, 3],
    bananas: [10, 20, 30, 40],
    tomatoes: [5, 15, 25, 40],
    grapes: [3, 7, 12, 18],
    oranges: [3, 8, 12, 18],
    mangoes: [2, 5, 8, 14],
    cashewnuts: [0.3, 0.7, 1.2, 1.8],
    coconuts: [3, 6, 10, 15],
    "sesame seed": [0.2, 0.5, 0.8, 1.2],
    coffee: [0.3, 0.7, 1.2, 1.8],
    tea: [1, 2, 3, 4],
    "pigeon pea": [0.4, 0.8, 1.3, 2],
    chickpea: [0.5, 1, 1.8, 2.5],
    mustard: [0.5, 1, 1.5, 2.5],
  };

  function getYieldRating(tonHa, cropName) {
    var key = (cropName || "").toLowerCase().trim();
    var t = CROP_YIELD_THRESHOLDS[key];
    // Fall back to global thresholds if crop not in map
    if (!t) {
      t = [1, 3, 6, 15];
    }
    if (tonHa < t[0]) {
      return { text: "Low Yield", cls: "rating-low" };
    }
    if (tonHa < t[1]) {
      return { text: "Below Average", cls: "rating-below" };
    }
    if (tonHa < t[2]) {
      return { text: "Good Yield", cls: "rating-good" };
    }
    if (tonHa < t[3]) {
      return { text: "High Yield", cls: "rating-high" };
    }
    return { text: "Exceptional", cls: "rating-exceptional" };
  }

  function getYieldScaleMax(cropName) {
    var key = (cropName || "").toLowerCase().trim();
    var t = CROP_YIELD_THRESHOLDS[key];
    // Use crop-specific high threshold as the progress scale upper bound.
    if (!t || !Array.isArray(t) || t.length < 4) {
      t = [1, 3, 6, 15];
    }
    return Math.max(2, t[3]);
  }

  var lastIntensityPercent = null;

  function getTrendText(currentPercent) {
    if (lastIntensityPercent === null || !isFinite(lastIntensityPercent)) {
      lastIntensityPercent = currentPercent;
      return "Same";
    }
    var delta = currentPercent - lastIntensityPercent;
    lastIntensityPercent = currentPercent;
    if (delta > 0.8) {
      return "Increasing";
    }
    if (delta < -0.8) {
      return "Decreasing";
    }
    return "Same";
  }

  function computeDynamicIntensityPercent(tonHa, totalTons, farmHa, cropName) {
    var scaleMax = getYieldScaleMax(cropName);
    var yieldComponent = Math.min((tonHa / scaleMax) * 100, 100);

    var safeArea = Math.max(0.01, Number(farmHa || 1));
    var safeTotal = Math.max(0.0, Number(totalTons || 0));

    // Production component introduces controlled responsiveness to farm-area change.
    var productionReference = Math.max(1.0, scaleMax * 25.0);
    var productionComponent =
      (Math.log1p(safeTotal) / Math.log1p(productionReference)) * 100;
    productionComponent = Math.max(0, Math.min(100, productionComponent));

    // Area factor is dampened to avoid unrealistic jumps for very large farms.
    var areaComponent = (Math.log1p(safeArea) / Math.log1p(100.0)) * 100;
    areaComponent = Math.max(0, Math.min(100, areaComponent));

    var dynamicPercent =
      yieldComponent * 0.68 + productionComponent * 0.22 + areaComponent * 0.1;

    if (tonHa > 0 && dynamicPercent < 4) {
      dynamicPercent = 4;
    }

    return {
      percent: Math.max(0, Math.min(100, dynamicPercent)),
      yieldComponent: yieldComponent,
    };
  }

  var barAnimationTimeoutId = null;

  function renderYieldIntensityBar(
    tonHa,
    totalTons,
    farmHa,
    cropName,
    options,
  ) {
    var opts = options || {};
    var isLive = !!opts.isLive;
    var computed = computeDynamicIntensityPercent(
      tonHa,
      totalTons,
      farmHa,
      cropName,
    );
    var barPct = computed.percent;
    var trendText = getTrendText(barPct);

    var barFill = document.getElementById("yieldBarFill");
    var barLabel = document.getElementById("yieldBarLabel");

    if (barFill) {
      if (barAnimationTimeoutId) {
        clearTimeout(barAnimationTimeoutId);
        barAnimationTimeoutId = null;
      }

      if (isLive) {
        barFill.style.transition = "width 0.28s ease";
        barFill.style.width = barPct.toFixed(1) + "%";
      } else {
        barFill.style.width = "0%";
        barAnimationTimeoutId = setTimeout(function () {
          barFill.style.width = barPct.toFixed(1) + "%";
          barAnimationTimeoutId = null;
        }, 80);
      }
    }

    if (barLabel) {
      barLabel.textContent =
        tonHa.toFixed(2) +
        " t/ha (" +
        barPct.toFixed(0) +
        "% \u2022 " +
        trendText +
        ")";
    }

    return barPct;
  }

  function updatePredictionUI(result, formPayload) {
    document.getElementById("predictionResult").classList.remove("d-none");
    var placeholder = document.getElementById("predictionPlaceholder");
    var skeleton = document.getElementById("predictionSkeleton");
    if (placeholder) {
      placeholder.classList.add("d-none");
    }
    if (skeleton) {
      skeleton.classList.add("d-none");
    }

    var tonHa = result.prediction_ton_per_ha;
    var hgHa = result.prediction_hg_per_ha;
    var totalTons = result.estimated_production_tons;
    var farmHa = result.farm_area_hectares;

    // Crop + state label
    var cropName = formPayload && formPayload.Item ? formPayload.Item : "Crop";
    var stateName = formPayload && formPayload.Area ? formPayload.Area : "";
    var cropLabelEl = document.getElementById("resultCropLabel");
    if (cropLabelEl) {
      cropLabelEl.textContent = cropName + (stateName ? " — " + stateName : "");
    }

    // Crop-aware yield rating
    var rating = getYieldRating(tonHa, cropName);
    var ratingBadge = document.getElementById("yieldRatingBadge");
    if (ratingBadge) {
      ratingBadge.textContent = rating.text;
      ratingBadge.className = "yield-rating-badge " + rating.cls;
    }

    // Dynamic bar responds to trained-model yield output and production scale.
    renderYieldIntensityBar(tonHa, totalTons, farmHa, cropName, {
      isLive: false,
    });

    // Metrics
    animateMetricValue("predictedYield", tonHa, " t/ha");
    animateMetricValue("yieldHgHa", hgHa, " hg/ha");
    animateMetricValue("estimatedProduction", totalTons, " tons");

    var farmLabel = document.getElementById("farmAreaLabel");
    if (farmLabel) {
      farmLabel.textContent =
        "for " + farmHa + " hectare" + (farmHa !== 1 ? "s" : "");
    }

    // Explanation
    document.getElementById("predictionExplanation").textContent =
      result.explanation;
    var factorList = document.getElementById("factorList");
    factorList.innerHTML = "";
    Object.keys(result.factors).forEach(function (key) {
      var item = document.createElement("li");
      item.textContent =
        key.charAt(0).toUpperCase() + key.slice(1) + ": " + result.factors[key];
      factorList.appendChild(item);
    });
  }

  function animateMetricValue(elementId, targetValue, suffix) {
    var element = document.getElementById(elementId);
    if (!element) {
      return;
    }
    var start = performance.now();
    var duration = 800;
    var initial = 0;

    function tick(now) {
      var progress = Math.min((now - start) / duration, 1);
      var current = initial + (targetValue - initial) * progress;
      element.textContent = current.toFixed(2) + suffix;
      if (progress < 1) {
        requestAnimationFrame(tick);
      }
    }

    requestAnimationFrame(tick);
  }

  function updateLiveInputHints(payload) {
    if (!payload) {
      return;
    }

    // Live-update crop+state badge even before prediction runs
    var cropLabelEl = document.getElementById("resultCropLabel");
    if (cropLabelEl) {
      var c = payload.Item && payload.Item.trim() ? payload.Item : "";
      var s = payload.Area && payload.Area.trim() ? payload.Area : "";
      if (c || s) {
        cropLabelEl.textContent = c + (c && s ? " — " : "") + s;
      }
    }

    var cropNode = document.getElementById("hintCrop");
    var regionNode = document.getElementById("hintRegion");
    var rainNode = document.getElementById("hintRainfall");
    var tempNode = document.getElementById("hintTemperature");

    if (cropNode) {
      cropNode.textContent =
        payload.Item && payload.Item.trim() ? payload.Item : "--";
    }
    if (regionNode) {
      regionNode.textContent =
        payload.Area && payload.Area.trim() ? payload.Area : "--";
    }
    if (rainNode) {
      rainNode.textContent =
        payload.average_rain_fall_mm_per_year &&
        payload.average_rain_fall_mm_per_year.trim()
          ? payload.average_rain_fall_mm_per_year + " mm"
          : "Model Default";
    }
    if (tempNode) {
      tempNode.textContent =
        payload.avg_temp && payload.avg_temp.trim()
          ? payload.avg_temp + " C"
          : "--";
    }
  }

  function renderPredictionHistory() {
    var table = document.getElementById("predictionHistoryTable");
    if (!table) {
      return;
    }
    var tbody = table.querySelector("tbody");
    if (!tbody) {
      return;
    }

    tbody.innerHTML = "";

    predictionHistory
      .slice()
      .sort(function (a, b) {
        return (
          new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
        );
      })
      .forEach(function (row) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" +
          (row.timestamp || "-") +
          "</td>" +
          "<td>" +
          (row.state || "-") +
          "</td>" +
          "<td>" +
          (row.crop || "-") +
          "</td>" +
          "<td>" +
          (row.year || "-") +
          "</td>" +
          "<td>" +
          (row.temperature || "-") +
          "</td>" +
          "<td>" +
          (row.rainfall || "-") +
          "</td>" +
          "<td>" +
          (row.pesticides || "-") +
          "</td>" +
          "<td>" +
          (row.farm_area || "-") +
          "</td>" +
          "<td>" +
          (row.yield_ton_ha || "-") +
          "</td>" +
          "<td>" +
          (row.total_production_tons || "-") +
          "</td>";
        tbody.appendChild(tr);
      });
  }

  function addPredictionHistoryRow(result, formPayload) {
    var record = {
      timestamp: new Date().toLocaleString(),
      state: formPayload && formPayload.Area ? formPayload.Area : "",
      crop: formPayload && formPayload.Item ? formPayload.Item : "",
      year: formPayload && formPayload.Year ? formPayload.Year : "",
      temperature:
        formPayload && formPayload.avg_temp ? formPayload.avg_temp : "",
      rainfall:
        formPayload && formPayload.average_rain_fall_mm_per_year
          ? formPayload.average_rain_fall_mm_per_year
          : "",
      pesticides:
        formPayload && formPayload.pesticides_tonnes
          ? formPayload.pesticides_tonnes
          : "",
      farm_area:
        formPayload && formPayload.farm_area_hectares
          ? formPayload.farm_area_hectares
          : "",
      yield_ton_ha:
        result && result.prediction_ton_per_ha !== undefined
          ? result.prediction_ton_per_ha
          : "",
      total_production_tons:
        result && result.estimated_production_tons !== undefined
          ? result.estimated_production_tons
          : "",
    };

    predictionHistory.push(record);
    if (predictionHistory.length > 500) {
      predictionHistory = predictionHistory.slice(
        predictionHistory.length - 500,
      );
    }
    savePredictionHistory();
    renderPredictionHistory();
  }

  function saveLatestPredictionContext(result, formPayload) {
    try {
      localStorage.setItem(
        "latest_farmer_prediction_context_v1",
        JSON.stringify({
          savedAt: new Date().toISOString(),
          formPayload: formPayload,
          result: result,
        }),
      );
    } catch (error) {
      // Ignore localStorage failures silently.
    }
  }

  function exportPredictionHistoryCsv() {
    if (!predictionHistory.length) {
      return;
    }
    var header = [
      "timestamp",
      "state",
      "crop",
      "year",
      "temperature",
      "rainfall",
      "pesticides",
      "farm_area",
      "yield_ton_ha",
      "total_production_tons",
    ];

    var lines = [header.join(",")];
    predictionHistory.forEach(function (row) {
      lines.push(
        [
          csvEscape(row.timestamp),
          csvEscape(row.state),
          csvEscape(row.crop),
          csvEscape(row.year),
          csvEscape(row.temperature),
          csvEscape(row.rainfall),
          csvEscape(row.pesticides),
          csvEscape(row.farm_area),
          csvEscape(row.yield_ton_ha),
          csvEscape(row.total_production_tons),
        ].join(","),
      );
    });

    var blob = new Blob([lines.join("\n")], {
      type: "text/csv;charset=utf-8;",
    });
    var link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = "result_prediction_data.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
  }

  function importPredictionHistoryCsv(file) {
    var reader = new FileReader();
    reader.onload = function (event) {
      var text = event.target.result || "";
      var lines = text.split(/\r?\n/).filter(function (line) {
        return line.trim().length > 0;
      });
      if (lines.length < 2) {
        return;
      }

      var headers = parseCsvLine(lines[0]).map(function (h) {
        return h.trim();
      });
      var importedRows = [];

      lines.slice(1).forEach(function (line) {
        var cols = parseCsvLine(line);
        var row = {};
        headers.forEach(function (h, idx) {
          row[h] = cols[idx] !== undefined ? cols[idx] : "";
        });

        if (row.state || row.crop || row.yield_ton_ha) {
          importedRows.push({
            timestamp: row.timestamp || new Date().toLocaleString(),
            state: row.state || "",
            crop: row.crop || "",
            year: row.year || "",
            temperature: row.temperature || "",
            rainfall: row.rainfall || "",
            pesticides: row.pesticides || "",
            farm_area: row.farm_area || "",
            yield_ton_ha: row.yield_ton_ha || "",
            total_production_tons: row.total_production_tons || "",
          });
        }
      });

      if (importedRows.length) {
        predictionHistory = predictionHistory.concat(importedRows);
        if (predictionHistory.length > 500) {
          predictionHistory = predictionHistory.slice(
            predictionHistory.length - 500,
          );
        }
        savePredictionHistory();
        renderPredictionHistory();
      }
    };

    reader.readAsText(file);
  }

  function initPredictionHistoryControls() {
    loadPredictionHistory();
    renderPredictionHistory();

    var importBtn = document.getElementById("predictionImportBtn");
    var importFile = document.getElementById("predictionImportFile");
    var exportBtn = document.getElementById("predictionExportBtn");
    var clearBtn = document.getElementById("predictionClearBtn");

    if (importBtn && importFile) {
      importBtn.addEventListener("click", function () {
        importFile.click();
      });

      importFile.addEventListener("change", function () {
        if (importFile.files && importFile.files[0]) {
          importPredictionHistoryCsv(importFile.files[0]);
        }
        importFile.value = "";
      });
    }

    if (exportBtn) {
      exportBtn.addEventListener("click", exportPredictionHistoryCsv);
    }

    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        predictionHistory = [];
        savePredictionHistory();
        renderPredictionHistory();
      });
    }
  }

  function initPredictionForm() {
    var form = document.getElementById("predictionForm");
    if (!form) {
      return;
    }

    var status = document.getElementById("predictStatus");
    var button = document.getElementById("predictButton");
    var placeholder = document.getElementById("predictionPlaceholder");
    var skeleton = document.getElementById("predictionSkeleton");
    var resultPanel = document.getElementById("predictionResult");
    var formPayload;
    var liveUpdateTimeout;
    var liveRequestCounter = 0;

    function normalizeYearPayload(payload) {
      if (!payload || !payload.Year) {
        return payload;
      }

      var rawYear = String(payload.Year).trim();
      if (rawYear.includes("-")) {
        var parsedYear = rawYear.split("-")[0];
        payload.Year = parsedYear;
      }

      return payload;
    }

    function getFormPayload() {
      return normalizeYearPayload(
        Object.fromEntries(new FormData(form).entries()),
      );
    }

    function syncHintsFromForm() {
      updateLiveInputHints(getFormPayload());
    }

    // Real-time yield bar update on input change
    function updateYieldBarLive() {
      if (liveUpdateTimeout) {
        clearTimeout(liveUpdateTimeout);
      }

      liveUpdateTimeout = setTimeout(function () {
        var payload = getFormPayload();
        var requestId = ++liveRequestCounter;

        // Only fetch if all required fields are filled
        if (
          !payload.Year ||
          !payload.Area ||
          !payload.Item ||
          !payload.pesticides_tonnes ||
          !payload.avg_temp ||
          !payload.farm_area_hectares
        ) {
          return;
        }

        fetch("/api/predict", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        })
          .then(function (response) {
            return response.json().then(function (data) {
              return { status: response.status, data: data };
            });
          })
          .then(function (result) {
            if (requestId !== liveRequestCounter) {
              return;
            }
            if (result.data.ok) {
              // Update only the yield bar without full UI update
              var tonHa = Number(result.data.result.prediction_ton_per_ha);
              var totalTons = result.data.result.estimated_production_tons;
              var farmHa = Number(payload.farm_area_hectares || 1);
              var cropName = payload.Item;
              renderYieldIntensityBar(tonHa, totalTons, farmHa, cropName, {
                isLive: true,
              });
            }
          })
          .catch(function (error) {
            // Silently fail for live updates
          });
      }, 500); // 500ms debounce
    }

    form.addEventListener("input", syncHintsFromForm);
    form.addEventListener("change", syncHintsFromForm);

    // Add live update listeners to key fields
    form.addEventListener("input", updateYieldBarLive);
    form.addEventListener("change", updateYieldBarLive);

    syncHintsFromForm();

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      if (!form.checkValidity()) {
        form.reportValidity();
        return;
      }

      button.disabled = true;
      if (status) {
        status.textContent = "";
      }
      formPayload = getFormPayload();
      updateLiveInputHints(formPayload);
      if (placeholder) {
        placeholder.classList.add("d-none");
      }
      if (resultPanel) {
        resultPanel.classList.add("d-none");
      }
      if (skeleton) {
        skeleton.classList.remove("d-none");
      }

      var payload = formPayload;

      fetch("/api/predict", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      })
        .then(function (response) {
          return response.json().then(function (data) {
            return { status: response.status, data: data };
          });
        })
        .then(function (result) {
          if (!result.data.ok) {
            throw new Error(result.data.error || "Prediction failed");
          }
          updatePredictionUI(result.data.result, formPayload);
          addPredictionHistoryRow(result.data.result, formPayload);
          saveLatestPredictionContext(result.data.result, formPayload);
        })
        .catch(function (error) {
          if (skeleton) {
            skeleton.classList.add("d-none");
          }
          if (placeholder) {
            placeholder.classList.remove("d-none");
          }
          if (status) {
            status.textContent = error.message;
          }
        })
        .finally(function () {
          button.disabled = false;
        });
    });
  }

  function animateCounters() {
    var nodes = document.querySelectorAll("[data-counter-target]");
    if (!nodes.length) {
      return;
    }

    nodes.forEach(function (node) {
      if (node.dataset.counterDone === "true") {
        return;
      }

      var target = parseFloat(node.dataset.counterTarget);
      if (!isFinite(target)) {
        return;
      }
      var decimals = parseInt(node.dataset.counterDecimals || "0", 10);
      var duration = 900;
      var start = performance.now();

      function step(now) {
        var progress = Math.min((now - start) / duration, 1);
        var value = target * progress;
        if (decimals > 0) {
          node.textContent = value.toFixed(decimals);
        } else {
          node.textContent = Math.round(value).toLocaleString();
        }
        if (progress < 1) {
          requestAnimationFrame(step);
        } else {
          node.dataset.counterDone = "true";
        }
      }

      requestAnimationFrame(step);
    });
  }

  function initChartControls() {
    document.querySelectorAll(".chart-action-download").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var chartId = btn.getAttribute("data-target-chart");
        var chart = chartInstances[chartId];
        if (!chart) {
          return;
        }
        var link = document.createElement("a");
        link.href = chart.toBase64Image("image/png", 1);
        link.download = chartId + ".png";
        link.click();
      });
    });

    document.querySelectorAll(".chart-action-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var chartId = btn.getAttribute("data-target-chart");
        var typeList = (btn.getAttribute("data-chart-types") || "bar,line")
          .split(",")
          .map(function (t) {
            return t.trim();
          });
        var chart = chartInstances[chartId];
        if (!chart || typeList.length < 2) {
          return;
        }

        var current = chart.config.type;
        var currentIdx = typeList.indexOf(current);
        var nextType = typeList[(currentIdx + 1) % typeList.length];
        chart.config.type = nextType;

        if (chartId === "areaProdChart") {
          chart.options.indexAxis = nextType === "bar" ? "y" : undefined;
        }

        if (nextType === "line") {
          chart.data.datasets.forEach(function (ds) {
            ds.fill = false;
            ds.tension = 0.3;
          });
        }

        chart.update();
      });
    });
  }

  function initModelPerformanceChart() {
    var modelData = window.MODEL_DATA || readJsonPayload("modelDataPayload");
    if (!modelData) {
      return;
    }

    var chartTitle = document.getElementById("modelCompareTitle");
    var chartNote = document.getElementById("modelCompareNote");

    var allModels = Array.isArray(modelData.all_models)
      ? modelData.all_models.filter(function (m) {
          return m && m.has_data && m.r2 !== null;
        })
      : [];

    // Preferred mode: compare all trained models with three metrics.
    if (allModels.length >= 2) {
      allModels.sort(function (a, b) {
        return (b.r2 || 0) - (a.r2 || 0);
      });

      var labels = allModels.map(function (m) {
        return m.name;
      });
      var labelMap = {
        HistGradientBoosting: "HistGB",
        GradientBoosting: "GradBoost",
        RandomForest: "RandForest",
      };
      var displayLabels = labels.map(function (name) {
        return labelMap[name] || name;
      });
      var r2Vals = allModels.map(function (m) {
        return m.r2;
      });
      var maeVals = allModels.map(function (m) {
        return m.mae;
      });
      var rmseVals = allModels.map(function (m) {
        return m.rmse;
      });

      if (chartTitle) {
        chartTitle.textContent = "All Trained Models Comparison";
      }
      if (chartNote) {
        chartNote.textContent =
          "Dynamic leaderboard from latest score files. Bars: R² (higher better), lines: MAE/RMSE (lower better).";
      }

      buildChart("modelCompareChart", {
        type: "bar",
        data: {
          labels: displayLabels,
          datasets: [
            {
              label: "R² (higher better)",
              data: r2Vals,
              yAxisID: "y",
              backgroundColor: "rgba(31, 143, 71, 0.75)",
              borderRadius: 6,
            },
            {
              label: "MAE (lower better)",
              type: "line",
              data: maeVals,
              yAxisID: "y1",
              borderColor: "rgba(242, 177, 52, 0.95)",
              backgroundColor: "rgba(242, 177, 52, 0.2)",
              tension: 0.25,
              pointRadius: 4,
            },
            {
              label: "RMSE (lower better)",
              type: "line",
              data: rmseVals,
              yAxisID: "y1",
              borderColor: "rgba(83, 128, 98, 0.95)",
              backgroundColor: "rgba(83, 128, 98, 0.2)",
              tension: 0.25,
              pointRadius: 4,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              labels: {
                color: "#173e2a",
                font: { size: 13, weight: "600" },
                boxWidth: 22,
                boxHeight: 10,
                padding: 14,
              },
            },
            tooltip: {
              callbacks: {
                title: function (items) {
                  var i = items[0].dataIndex;
                  return labels[i];
                },
              },
            },
          },
          scales: {
            y: {
              beginAtZero: true,
              max: 1.05,
              title: {
                display: true,
                text: "R²",
                color: "#173e2a",
                font: { size: 12, weight: "600" },
              },
              ticks: { color: "#254f38", font: { size: 12, weight: "600" } },
              grid: { color: "rgba(0,0,0,0.06)" },
            },
            y1: {
              beginAtZero: true,
              position: "right",
              title: {
                display: true,
                text: "Error (MAE / RMSE)",
                color: "#173e2a",
                font: { size: 12, weight: "600" },
              },
              ticks: { color: "#254f38", font: { size: 12, weight: "600" } },
              grid: { drawOnChartArea: false },
            },
            x: {
              ticks: {
                color: "#254f38",
                font: { size: 12, weight: "600" },
                maxRotation: 24,
                minRotation: 24,
                autoSkip: false,
              },
            },
          },
        },
      });
      return;
    }

    // Fallback mode: when only one model + baseline exists, show relative improvements.
    if (
      modelData.improvement_r2 !== null &&
      modelData.improvement_mae !== null &&
      modelData.improvement_rmse !== null
    ) {
      if (chartTitle) {
        chartTitle.textContent = "Improvement Over Baseline (%)";
      }
      if (chartNote) {
        chartNote.textContent =
          "Relative gains vs baseline predictor on the same validation split.";
      }

      buildChart("modelCompareChart", {
        type: "bar",
        data: {
          labels: ["R² Gain", "MAE Reduction", "RMSE Reduction"],
          datasets: [
            {
              label: "Improvement (%)",
              data: [
                modelData.improvement_r2,
                modelData.improvement_mae,
                modelData.improvement_rmse,
              ],
              backgroundColor: [
                "rgba(31, 143, 71, 0.75)",
                "rgba(55, 166, 92, 0.75)",
                "rgba(86, 186, 118, 0.75)",
              ],
              borderRadius: 8,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, title: { display: true, text: "%" } },
            x: { grid: { display: false } },
          },
          plugins: { legend: { display: false } },
        },
      });
      return;
    }

    buildChart("modelCompareChart", {
      type: "bar",
      data: {
        labels: ["R2", "MAE", "RMSE"],
        datasets: [
          {
            label: modelData.model_name,
            data: [modelData.r2, modelData.mae, modelData.rmse],
            backgroundColor: "rgba(31, 143, 71, 0.75)",
          },
          {
            label: "Baseline Mean Predictor",
            data: [
              modelData.baseline_r2,
              modelData.baseline_mae,
              modelData.baseline_rmse,
            ],
            backgroundColor: "rgba(242, 177, 52, 0.72)",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
      },
    });
  }

  function initWorkflowPanel() {
    var steps = document.querySelectorAll(".pipeline-step");
    if (!steps.length) {
      return;
    }

    steps.forEach(function (step) {
      step.addEventListener("click", function () {
        var targetId = step.getAttribute("data-step-target");
        steps.forEach(function (node) {
          node.classList.remove("active");
        });
        step.classList.add("active");

        document
          .querySelectorAll(".workflow-detail")
          .forEach(function (detail) {
            detail.classList.remove("active");
          });
        var target = document.getElementById(targetId);
        if (target) {
          target.classList.add("active");
        }
      });
    });
  }

  function initSmoothScroll() {
    document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
      anchor.addEventListener("click", function (event) {
        var href = anchor.getAttribute("href");
        if (!href || href.length < 2) {
          return;
        }
        var target = document.querySelector(href);
        if (!target) {
          return;
        }
        event.preventDefault();
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    });
  }

  chartDefaults();
  initPredictionHistoryControls();
  initPredictionForm();
  initAnalyticsCharts();
  initModelPerformanceChart();
  initChartControls();
  initWorkflowPanel();
  animateCounters();
  initSmoothScroll();
})();
