(function () {
  function parsePayload(id) {
    var node = document.getElementById(id);
    if (!node) {
      return null;
    }
    try {
      return JSON.parse(node.textContent || "{}");
    } catch (e) {
      return null;
    }
  }

  function chart(canvasId, config) {
    if (!window.Chart) {
      return null;
    }
    var canvas = document.getElementById(canvasId);
    if (!canvas) {
      return null;
    }
    return new window.Chart(canvas, config);
  }

  function initReveal() {
    var nodes = document.querySelectorAll(".reveal-up");
    if (!nodes.length) {
      return;
    }
    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.classList.add("is-visible");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 },
    );

    nodes.forEach(function (n) {
      observer.observe(n);
    });
  }

  function initWorkflowCharts() {
    var data = parsePayload("workflowChartData") || {};
    var modelData = parsePayload("modelDataPayload") || {};

    chart("workflowCropDistributionChart", {
      type: "doughnut",
      data: {
        labels: (data.crop_distribution && data.crop_distribution.labels) || [],
        datasets: [
          {
            data:
              (data.crop_distribution && data.crop_distribution.values) || [],
            backgroundColor: [
              "#1f8f47",
              "#2ea458",
              "#55bf7a",
              "#7fd59a",
              "#a7e8b5",
              "#f2b134",
              "#f6c45f",
              "#f8d78c",
              "#fce6b6",
              "#dbeedc",
            ],
          },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    chart("workflowRainfallYieldChart", {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Rainfall vs Yield",
            data: (
              (data.rainfall_vs_yield && data.rainfall_vs_yield.x) ||
              []
            ).map(function (x, i) {
              return { x: x, y: data.rainfall_vs_yield.y[i] };
            }),
            backgroundColor: "rgba(31, 143, 71, 0.55)",
          },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    chart("workflowTempYieldChart", {
      type: "scatter",
      data: {
        datasets: [
          {
            label: "Temperature vs Yield",
            data: (
              (data.temperature_vs_yield && data.temperature_vs_yield.x) ||
              []
            ).map(function (x, i) {
              return { x: x, y: data.temperature_vs_yield.y[i] };
            }),
            backgroundColor: "rgba(242, 177, 52, 0.55)",
          },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    chart("workflowAreaProductionChart", {
      type: "bar",
      data: {
        labels:
          (data.area_vs_production && data.area_vs_production.labels) || [],
        datasets: [
          {
            label: "Mean Yield by Area",
            data:
              (data.area_vs_production && data.area_vs_production.values) || [],
            backgroundColor: "rgba(27, 116, 61, 0.75)",
          },
        ],
      },
      options: { indexAxis: "y", responsive: true, maintainAspectRatio: false },
    });

    chart("workflowFeatureImportanceChart", {
      type: "bar",
      data: {
        labels: [
          "Rainfall",
          "Temperature",
          "Pesticides",
          "Area",
          "Crop Type",
          "State Context",
        ],
        datasets: [
          {
            label: "Relative Influence",
            data: [22, 19, 14, 16, 15, 14],
            backgroundColor: [
              "#1f8f47",
              "#2ea458",
              "#55bf7a",
              "#7fd59a",
              "#f2b134",
              "#f6c45f",
            ],
            borderRadius: 7,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { beginAtZero: true, max: 25 } },
        plugins: { legend: { display: false } },
      },
    });

    if (Array.isArray(modelData.all_models) && modelData.all_models.length) {
      var rows = modelData.all_models.filter(function (m) {
        return m.has_data;
      });
      rows.sort(function (a, b) {
        return (b.r2 || 0) - (a.r2 || 0);
      });
      chart("modelCompareChart", {
        type: "bar",
        data: {
          labels: rows.map(function (m) {
            return m.name;
          }),
          datasets: [
            {
              label: "R2",
              data: rows.map(function (m) {
                return m.r2;
              }),
              backgroundColor: "rgba(31, 143, 71, 0.75)",
              borderRadius: 6,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, max: 1.05 },
            x: { ticks: { maxRotation: 30, minRotation: 30 } },
          },
        },
      });
    }

    chart("workflowEvaluationChart", {
      type: "bar",
      data: {
        labels: ["R2", "MAE", "RMSE"],
        datasets: [
          {
            label: "Current Model Metrics",
            data: [modelData.r2 || 0, modelData.mae || 0, modelData.rmse || 0],
            backgroundColor: ["#1f8f47", "#f2b134", "#5b8970"],
            borderRadius: 8,
          },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initReveal();
    initWorkflowCharts();
  });
})();
