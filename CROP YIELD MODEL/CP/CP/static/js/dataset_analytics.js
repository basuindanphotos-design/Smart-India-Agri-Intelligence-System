(function () {
  "use strict";

  var analytics = null;
  var analyticsCharts = {};
  var initialized = false;

  function buildChart(canvasId, config) {
    if (!window.Chart) {
      return null;
    }
    var canvas = document.getElementById(canvasId);
    if (!canvas) {
      return null;
    }
    var chart = new window.Chart(canvas, config);
    analyticsCharts[canvasId] = chart;
    return chart;
  }

  function formatNum(value, digits) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
      return "-";
    }
    return Number(value).toFixed(digits || 2);
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) {
      el.textContent = value;
    }
  }

  function fillStats() {
    var stats = analytics.stats || {};
    setText("avgYield", formatNum(stats.average_yield, 2));
    setText("medianYield", formatNum(stats.median_yield, 2));
    setText("stdYield", formatNum(stats.yield_std, 2));
    setText("avgRain", formatNum(stats.average_rainfall, 2));
    setText("avgTemp", formatNum(stats.average_temperature, 2));
    setText("avgPest", formatNum(stats.average_pesticides, 2));

    var dq = analytics.data_quality || {};
    setText(
      "dqMissing",
      dq.missing_values !== undefined ? dq.missing_values : "-",
    );
    setText(
      "dqDuplicate",
      dq.duplicate_rows !== undefined ? dq.duplicate_rows : "-",
    );
    setText(
      "dqCompleteness",
      dq.completeness_pct !== undefined ? dq.completeness_pct + "%" : "-",
    );
  }

  function fillCoverageTable() {
    var rows = analytics.coverage_report || [];
    var tbody = document.querySelector("#coverageTable tbody");
    if (!tbody) {
      return;
    }
    tbody.innerHTML = "";
    rows.slice(0, 30).forEach(function (row) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" +
        (row.Crop || "-") +
        "</td>" +
        "<td>" +
        (row.records || 0) +
        "</td>" +
        "<td>" +
        formatNum(row.avg_yield, 2) +
        "</td>" +
        "<td>" +
        formatNum(row.avg_area, 2) +
        "</td>" +
        "<td>" +
        formatNum(row.avg_rainfall, 2) +
        "</td>";
      tbody.appendChild(tr);
    });
  }

  function renderCharts() {
    var hist = analytics.yield_histogram || { labels: [], values: [] };
    buildChart("yieldHistogramChart", {
      type: "bar",
      data: {
        labels: hist.labels,
        datasets: [
          {
            label: "Yield Frequency",
            data: hist.values,
            backgroundColor: "rgba(31, 143, 71, 0.75)",
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });

    var topCrops = analytics.top_crops || { labels: [], values: [] };
    buildChart("topCropsChart", {
      type: "bar",
      data: {
        labels: topCrops.labels,
        datasets: [
          {
            label: "Avg Yield",
            data: topCrops.values,
            backgroundColor: "rgba(27, 116, 61, 0.74)",
            borderRadius: 6,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });

    var scatter = analytics.area_yield_scatter || { x: [], y: [] };
    buildChart("areaYieldScatterChart", {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Area vs Yield",
            data: scatter.x.map(function (x, i) {
              return { x: x, y: scatter.y[i] };
            }),
            backgroundColor: "rgba(31, 143, 71, 0.45)",
            pointRadius: 3,
          },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    var climate = analytics.climate_impact || {
      labels: [],
      yield: [],
      rainfall: [],
      temperature: [],
    };
    buildChart("climateImpactChart", {
      type: "line",
      data: {
        labels: climate.labels,
        datasets: [
          {
            label: "Yield",
            data: climate.yield,
            yAxisID: "y",
            borderColor: "#1f8f47",
            backgroundColor: "rgba(31,143,71,0.2)",
            tension: 0.25,
          },
          {
            label: "Rainfall",
            data: climate.rainfall,
            yAxisID: "y1",
            borderColor: "#2e7ec9",
            backgroundColor: "rgba(46,126,201,0.2)",
            tension: 0.25,
          },
          {
            label: "Temperature",
            data: climate.temperature,
            yAxisID: "y2",
            borderColor: "#f2b134",
            backgroundColor: "rgba(242,177,52,0.2)",
            tension: 0.25,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { position: "left", title: { display: true, text: "Yield" } },
          y1: {
            position: "right",
            grid: { drawOnChartArea: false },
            title: { display: true, text: "Rainfall" },
          },
          y2: { display: false },
        },
      },
    });

    var yearly = analytics.yearly_yield_trend || { labels: [], values: [] };
    buildChart("yearlyYieldTrendChart", {
      type: "line",
      data: {
        labels: yearly.labels,
        datasets: [
          {
            label: "Avg Yield / Year",
            data: yearly.values,
            borderColor: "#1f8f47",
            backgroundColor: "rgba(31,143,71,0.15)",
            fill: true,
            tension: 0.28,
          },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    var region = analytics.region_yield_rank || { labels: [], values: [] };
    buildChart("regionYieldRankChart", {
      type: "bar",
      data: {
        labels: region.labels,
        datasets: [
          {
            label: "Yield Rank",
            data: region.values,
            backgroundColor: "rgba(27,116,61,0.74)",
            borderRadius: 6,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });

    var season = analytics.season_distribution || { labels: [], values: [] };
    buildChart("seasonDistributionChart", {
      type: "pie",
      data: {
        labels: season.labels,
        datasets: [
          {
            data: season.values,
            backgroundColor: [
              "#1f8f47",
              "#2eab5c",
              "#80d598",
              "#f2b134",
              "#f6c45f",
              "#5c8f73",
              "#9acbb0",
              "#cde9d8",
            ],
          },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    var cat = analytics.category_yield || { labels: [], values: [] };
    buildChart("categoryYieldChart", {
      type: "bar",
      data: {
        labels: cat.labels,
        datasets: [
          {
            label: "Avg Yield by Category",
            data: cat.values,
            backgroundColor: "rgba(31,143,71,0.72)",
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });

    var fi = analytics.feature_importance || { labels: [], values: [] };
    buildChart("featureImportanceChart", {
      type: "bar",
      data: {
        labels: fi.labels,
        datasets: [
          {
            label: "Feature Importance (%)",
            data: fi.values,
            backgroundColor: [
              "#1f8f47",
              "#2eab5c",
              "#55bf7a",
              "#f2b134",
              "#5c8f73",
            ],
            borderRadius: 6,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
      },
    });

    if (window.Plotly && analytics.correlation) {
      var corr = analytics.correlation;
      window.Plotly.newPlot(
        "correlationHeatmap",
        [
          {
            z: corr.values,
            x: corr.labels,
            y: corr.labels,
            type: "heatmap",
            colorscale: "YlGn",
            zmin: -1,
            zmax: 1,
          },
        ],
        {
          margin: { t: 20, r: 20, b: 40, l: 60 },
          paper_bgcolor: "rgba(0,0,0,0)",
          plot_bgcolor: "rgba(0,0,0,0)",
        },
        { responsive: true },
      );
    }
  }

  function initChartActions() {
    document
      .querySelectorAll("button[data-target-chart]")
      .forEach(function (btn) {
        var target = btn.getAttribute("data-target-chart");
        if (!target || !analyticsCharts[target]) {
          return;
        }

        if (btn.classList.contains("chart-action-download")) {
          btn.addEventListener("click", function () {
            var chart = analyticsCharts[target];
            var a = document.createElement("a");
            a.href = chart.toBase64Image("image/png", 1);
            a.download = target + ".png";
            a.click();
          });
        }

        if (btn.classList.contains("chart-action-toggle")) {
          var types = (btn.getAttribute("data-chart-types") || "bar,line")
            .split(",")
            .map(function (t) {
              return t.trim();
            });
          btn.setAttribute("data-chart-index", "0");
          btn.addEventListener("click", function () {
            var chart = analyticsCharts[target];
            if (!chart || types.length < 2) {
              return;
            }
            var index = parseInt(btn.getAttribute("data-chart-index"), 10) || 0;
            index = (index + 1) % types.length;
            btn.setAttribute("data-chart-index", String(index));
            chart.config.type = types[index];
            chart.update();
          });
        }
      });

    var exportBtn = document.getElementById("coverageExportBtn");
    if (exportBtn) {
      exportBtn.addEventListener("click", function () {
        window.location.href = "/api/dataset-coverage.csv";
      });
    }
  }

  function initAdvancedDatasetAnalytics() {
    if (initialized) {
      return;
    }
    initialized = true;

    fetch("/api/dataset-analytics")
      .then(function (res) {
        return res.json();
      })
      .then(function (res) {
        if (!res || !res.ok || !res.data) {
          return;
        }
        analytics = res.data;
        fillStats();
        fillCoverageTable();
        renderCharts();
        initChartActions();
      })
      .catch(function () {
        // Keep page usable even when analytics endpoint fails.
      });
  }

  function setupLazyLoad() {
    var root = document.getElementById("advancedAnalyticsRoot");
    if (!root) {
      return;
    }
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            initAdvancedDatasetAnalytics();
            observer.disconnect();
          }
        });
      },
      { threshold: 0.1 },
    );
    observer.observe(root);
  }

  document.addEventListener("DOMContentLoaded", setupLazyLoad);
})();
