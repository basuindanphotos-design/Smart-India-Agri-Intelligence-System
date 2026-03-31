(function () {
  "use strict";

  var chartRegistry = {};
  var STORAGE_KEY = "latest_farmer_prediction_context_v1";
  var lastContextStamp = null;

  function createChart(id, config) {
    if (!window.Chart) {
      return null;
    }
    var canvas = document.getElementById(id);
    if (!canvas) {
      return null;
    }
    if (chartRegistry[id]) {
      chartRegistry[id].destroy();
    }
    chartRegistry[id] = new window.Chart(canvas, config);
    return chartRegistry[id];
  }

  function latestContext() {
    try {
      var raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch (error) {
      return null;
    }
  }

  function progressHtml(title, payload) {
    return (
      '<div class="climate-progress">' +
      '<div class="head"><span>' +
      title +
      "</span><strong>" +
      payload.label +
      "</strong></div>" +
      '<div class="mini-progress"><span style="width:' +
      payload.score +
      '%"></span></div>' +
      "</div>"
    );
  }

  function stackCard(title, detail, cls) {
    return (
      '<div class="stack-card ' +
      (cls || "") +
      '"><h4>' +
      title +
      "</h4><p>" +
      detail +
      "</p></div>"
    );
  }

  function fillSnapshot(cards) {
    var root = document.getElementById("snapshotCards");
    if (!root) {
      return;
    }
    root.innerHTML = "";
    (cards || []).forEach(function (card) {
      var div = document.createElement("div");
      div.className = "snapshot-card";
      div.innerHTML =
        "<h4>" +
        card.title +
        "</h4><p>" +
        card.value +
        '</p><div class="mini-progress"><span style="width:' +
        card.score +
        '%"></span></div>';
      root.appendChild(div);
    });
  }

  function fillList(rootId, rows, builder) {
    var root = document.getElementById(rootId);
    if (!root) {
      return;
    }
    root.innerHTML = "";
    (rows || []).forEach(function (row) {
      var wrapper = document.createElement("div");
      wrapper.innerHTML = builder(row);
      root.appendChild(wrapper.firstChild);
    });
  }

  function renderCharts(hist) {
    createChart("fiYearlyTrendChart", {
      type: "line",
      data: {
        labels: hist.yearly_trend.labels || [],
        datasets: [
          {
            label: "Yield Trend",
            data: hist.yearly_trend.values || [],
            borderColor: "#1f8f47",
            backgroundColor: "rgba(31,143,71,0.12)",
            fill: true,
            tension: 0.28,
          },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false },
    });

    createChart("fiYieldDistChart", {
      type: "bar",
      data: {
        labels: hist.yield_distribution.labels || [],
        datasets: [
          {
            label: "Yield Distribution",
            data: hist.yield_distribution.values || [],
            backgroundColor: "rgba(242,177,52,0.78)",
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

    createChart("fiTopRegionsChart", {
      type: "bar",
      data: {
        labels: (hist.top_regions || []).map(function (r) {
          return r.State;
        }),
        datasets: [
          {
            label: "Top Regions",
            data: (hist.top_regions || []).map(function (r) {
              return r.Yield;
            }),
            backgroundColor: "rgba(31,143,71,0.78)",
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
  }

  function updateProfit(insights) {
    var marketPriceInput = document.getElementById("marketPriceInput");
    var productionQtyInput = document.getElementById("productionQtyInput");
    var price =
      marketPriceInput && marketPriceInput.value
        ? parseFloat(marketPriceInput.value)
        : null;
    var qty =
      productionQtyInput && productionQtyInput.value
        ? parseFloat(productionQtyInput.value)
        : insights.profit.production_quantity;
    var value = price !== null && !Number.isNaN(price) ? qty * price : null;
    var range = value !== null ? [value * 0.9, value * 1.1] : null;
    document.getElementById("profitValue").textContent =
      value !== null ? value.toFixed(2) : "Enter market price";
    document.getElementById("profitRange").textContent = range
      ? range[0].toFixed(2) + " - " + range[1].toFixed(2)
      : "Enter market price";
  }

  function setText(id, value) {
    var node = document.getElementById(id);
    if (node) {
      node.textContent = value;
    }
  }

  function renderInputContext(payload) {
    setText("fiInputYear", payload.Year || "-");
    setText(
      "fiInputRainfall",
      payload.average_rain_fall_mm_per_year
        ? payload.average_rain_fall_mm_per_year + " mm"
        : "Model Default",
    );
    setText(
      "fiInputPesticides",
      payload.pesticides_tonnes ? payload.pesticides_tonnes + " t" : "-",
    );
    setText("fiInputTemp", payload.avg_temp ? payload.avg_temp + " C" : "-");
    setText("fiInputState", payload.Area || "-");
    setText("fiInputCrop", payload.Item || "-");
    setText(
      "fiInputArea",
      payload.farm_area_hectares ? payload.farm_area_hectares + " ha" : "-",
    );
  }

  function renderInsights(response, payload) {
    var prediction = response.prediction;
    var insights = response.insights;
    var locked = document.getElementById("farmerInsightLocked");
    var root = document.getElementById("farmerInsightRoot");
    var empty = document.getElementById("farmerInsightEmpty");
    var dashboard = document.getElementById("farmerInsightDashboard");

    if (locked) {
      locked.classList.add("d-none");
    }
    if (root) {
      root.classList.remove("d-none");
    }
    if (empty) {
      empty.classList.add("d-none");
    }
    if (dashboard) {
      dashboard.classList.remove("d-none");
    }

    renderInputContext(payload || {});

    document.getElementById("fiPredYield").textContent =
      prediction.prediction_ton_per_ha.toFixed(2) + " t/ha";
    document.getElementById("fiEstProd").textContent =
      prediction.estimated_production_tons.toFixed(2) + " tons";
    document.getElementById("fiLandArea").textContent =
      prediction.farm_area_hectares + " ha";
    document.getElementById("fiYieldPotential").textContent =
      insights.summary.yield_potential.label;

    fillSnapshot(insights.snapshot);

    var climateGroup = document.getElementById("climateProgressGroup");
    climateGroup.innerHTML =
      progressHtml("Climate Match", insights.climate.climate_match) +
      progressHtml("Rainfall Suitability", insights.climate.rainfall) +
      progressHtml("Temperature Suitability", insights.climate.temperature) +
      progressHtml("Humidity Conditions", insights.climate.humidity);

    document.getElementById("timelineDuration").textContent =
      insights.timeline.duration;
    fillList("timelineStages", insights.timeline.stages, function (stage) {
      return (
        '<div class="timeline-stage"><strong>' +
        stage.name +
        "</strong><span>" +
        stage.days +
        "</span></div>"
      );
    });

    fillList(
      "resourceGrid",
      [
        {
          title: "Water Requirement",
          detail: insights.resources.water_requirement,
        },
        {
          title: "Fertilizer Demand",
          detail: insights.resources.fertilizer_demand,
        },
        { title: "Pest Risk", detail: insights.resources.pest_risk },
        {
          title: "Labor Intensity",
          detail: insights.resources.labor_intensity,
        },
      ],
      function (row) {
        return (
          '<div class="resource-card"><h4>' +
          row.title +
          "</h4><p>" +
          row.detail +
          "</p></div>"
        );
      },
    );

    document.getElementById("benchmarkPred").textContent =
      insights.benchmark.predicted_yield.toFixed(2) + " t/ha";
    document.getElementById("benchmarkAvg").textContent =
      insights.benchmark.regional_average !== null
        ? insights.benchmark.regional_average.toFixed(2) + " t/ha"
        : "Not available";
    document.getElementById("benchmarkDiff").textContent =
      insights.benchmark.difference_pct !== null
        ? insights.benchmark.difference_pct.toFixed(2) + "%"
        : "Not available";

    fillList("educationList", insights.education, function (text) {
      return stackCard("Educational Tip", text, "");
    });

    fillList("riskList", insights.risks, function (risk) {
      return stackCard(risk.title, risk.detail, "risk-" + risk.level);
    });

    document.getElementById("intelRisk").textContent =
      insights.intelligence.risk_assessment;
    document.getElementById("intelClimate").textContent =
      insights.intelligence.climate_suitability;
    document.getElementById("intelMarket").textContent =
      insights.intelligence.market_context;
    document.getElementById("intelConfidence").textContent =
      insights.intelligence.prediction_confidence + "%";

    fillList("recommendationCards", insights.recommendations, function (row) {
      return stackCard(row.title, row.detail, "");
    });

    fillList(
      "decisionSupportCards",
      insights.decision_support || [],
      function (row) {
        return '<div class="decision-card">' + row + "</div>";
      },
    );

    var productionQtyInput = document.getElementById("productionQtyInput");
    if (productionQtyInput && !productionQtyInput.value) {
      productionQtyInput.value = insights.profit.production_quantity;
    }
    updateProfit(insights);
    renderCharts(insights.historical);

    if (productionQtyInput) {
      productionQtyInput.oninput = function () {
        updateProfit(insights);
      };
    }
    var marketPriceInput = document.getElementById("marketPriceInput");
    if (marketPriceInput) {
      marketPriceInput.oninput = function () {
        updateProfit(insights);
      };
    }
  }

  function fetchInsights(force) {
    var context = latestContext();
    var locked = document.getElementById("farmerInsightLocked");
    var root = document.getElementById("farmerInsightRoot");
    if (!context || !context.formPayload) {
      if (locked) {
        locked.classList.remove("d-none");
      }
      if (root) {
        root.classList.add("d-none");
      }
      return;
    }

    if (!force && context.savedAt && lastContextStamp === context.savedAt) {
      return;
    }

    lastContextStamp = context.savedAt || String(Date.now());

    if (locked) {
      locked.classList.add("d-none");
    }
    if (root) {
      root.classList.remove("d-none");
    }

    var payload = Object.assign({}, context.formPayload);
    var marketPriceInput = document.getElementById("marketPriceInput");
    var productionQtyInput = document.getElementById("productionQtyInput");
    if (marketPriceInput && marketPriceInput.value) {
      payload.market_price_per_ton = marketPriceInput.value;
    }
    if (productionQtyInput && productionQtyInput.value) {
      payload.production_quantity = productionQtyInput.value;
    }

    fetch("/api/farmer-insights", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (res) {
        return res.json();
      })
      .then(function (res) {
        if (res && res.ok) {
          renderInsights(res, payload);
        } else {
          if (locked) {
            locked.classList.remove("d-none");
          }
          if (root) {
            root.classList.add("d-none");
          }
        }
      })
      .catch(function () {
        if (locked) {
          locked.classList.remove("d-none");
        }
        if (root) {
          root.classList.add("d-none");
        }
      });
  }

  document.addEventListener("DOMContentLoaded", function () {
    var btn = document.getElementById("refreshFarmerInsightBtn");
    if (btn) {
      btn.addEventListener("click", function () {
        fetchInsights(true);
      });
    }
    window.addEventListener("focus", function () {
      fetchInsights();
    });
    window.addEventListener("storage", function (event) {
      if (event.key === STORAGE_KEY) {
        fetchInsights(true);
      }
    });
    setInterval(function () {
      fetchInsights();
    }, 1500);

    fetchInsights(true);
  });
})();
