function showLoader(show) {
  const loader = document.getElementById("globalLoader");
  if (!loader) return;
  loader.classList.toggle("d-none", !show);
}

async function fetchJsonWithTimeout(url, timeoutMs = 20000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(url, { signal: controller.signal });
    if (!res.ok) {
      throw new Error(`Request failed: ${res.status}`);
    }
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

const LATEST_PREDICTION_STORAGE_KEY = "agriPrice.latestPredictionInsight";
const PREDICT_HISTORY_STORAGE_KEY = "agriPrice.predictHistoryRows";

function saveLatestPredictionBundle(payload, data) {
  try {
    sessionStorage.setItem(
      LATEST_PREDICTION_STORAGE_KEY,
      JSON.stringify({
        payload,
        data,
        savedAt: new Date().toISOString(),
      }),
    );
  } catch (_) {
    // Ignore storage failures and keep runtime flow functional.
  }
}

function readLatestPredictionBundle() {
  try {
    const raw = sessionStorage.getItem(LATEST_PREDICTION_STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

function exportPredictionBundle(bundle) {
  const payload = bundle?.payload || {};
  const result = bundle?.data || {};
  const details = result.details || {};

  const jsonExport = {
    input: payload,
    output: {
      predicted_price: result.predicted_price,
      current_market_price: result.current_market_price,
      profit_delta: result.profit_delta,
      recommendation: result.recommendation,
      recommendation_status: result.recommendation_status,
      confidence: result.confidence,
      best_market: result.best_market,
      trend: result.price_trend,
    },
    details,
    exported_at: new Date().toISOString(),
  };

  const csvRows = [
    ["Field", "Value"],
    ["State", payload.state],
    ["District", payload.district],
    ["Market", payload.market],
    ["Commodity", payload.commodity],
    ["Variety", payload.variety],
    ["Arrival Date", payload.arrival_date],
    ["Min Price", payload.min_price],
    ["Max Price", payload.max_price],
    ["Predicted Price", result.predicted_price],
    ["Current Market Price", result.current_market_price],
    ["Profit Delta", result.profit_delta],
    ["Recommendation", result.recommendation],
    ["Recommendation Status", result.recommendation_status],
    ["Confidence", result.confidence],
    ["Best Market", result.best_market],
    ["Price Trend", result.price_trend],
    ["Forecast Band Low", details.forecast_band?.low ?? ""],
    ["Forecast Band High", details.forecast_band?.high ?? ""],
    ["Market Data Points", details.market_data_points ?? ""],
    ["Variety Data Points", details.variety_data_points ?? ""],
    ["Summary 1", result.summary_lines?.[0] || ""],
    ["Summary 2", result.summary_lines?.[1] || ""],
    ["Summary 3", result.summary_lines?.[2] || ""],
    ["Education Tips", (details.education_tips || []).join(" | ")],
    ["Prediction Updated At", details.updated_at || ""],
  ];

  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const csvContent = csvRows.map((r) => r.map(esc).join(",")).join("\n");
  const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");

  const csvBlob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const csvUrl = URL.createObjectURL(csvBlob);
  const csvLink = document.createElement("a");
  csvLink.href = csvUrl;
  csvLink.download = `prediction_details_${stamp}.csv`;
  document.body.appendChild(csvLink);
  csvLink.click();
  csvLink.remove();
  URL.revokeObjectURL(csvUrl);

  const jsonBlob = new Blob([JSON.stringify(jsonExport, null, 2)], {
    type: "application/json;charset=utf-8;",
  });
  const jsonUrl = URL.createObjectURL(jsonBlob);
  const jsonLink = document.createElement("a");
  jsonLink.href = jsonUrl;
  jsonLink.download = `prediction_details_${stamp}.json`;
  document.body.appendChild(jsonLink);
  jsonLink.click();
  jsonLink.remove();
  URL.revokeObjectURL(jsonUrl);
}

function animateCounters() {
  document.querySelectorAll(".counter").forEach((el) => {
    const target = Number(el.dataset.target || 0);
    let current = 0;
    const step = Math.max(1, Math.floor(target / 45));
    const tick = () => {
      current += step;
      if (current >= target) {
        el.textContent = target;
      } else {
        el.textContent = current;
        requestAnimationFrame(tick);
      }
    };
    tick();
  });
}

function setupNavbarScroll() {
  const nav = document.getElementById("mainNavbar");
  if (!nav) return;
  const onScroll = () => nav.classList.toggle("scrolled", window.scrollY > 10);
  window.addEventListener("scroll", onScroll);
  onScroll();
}

async function setupPredictForm() {
  const form = document.getElementById("predictForm");
  if (!form) return;

  let farmerTrendChart = null;
  let lastPredictionPayload = null;
  let lastPredictionData = null;

  const stateEl = form.querySelector('select[name="state"]');
  const districtEl = form.querySelector('select[name="district"]');
  const marketEl = form.querySelector('select[name="market"]');
  const commodityEl = form.querySelector('select[name="commodity"]');
  const varietyEl = form.querySelector('select[name="variety"]');
  const arrivalDateEl = form.querySelector('input[name="arrival_date"]');
  const optionsUpdatedAtEl = document.getElementById("predictOptionsUpdatedAt");
  const autoSyncEl = document.getElementById("predictAutoSync");
  const autoSyncStatusEl = document.getElementById("predictAutoSyncStatus");
  const exportBtn = document.getElementById("exportPredictionDetailsBtn");
  const historyTableBody = document.getElementById("predictHistoryTableBody");
  const importHistoryBtn = document.getElementById("importPredictHistoryBtn");
  const exportHistoryBtn = document.getElementById("exportPredictHistoryBtn");
  const clearHistoryBtn = document.getElementById("clearPredictHistoryBtn");
  const historyImportInput = document.getElementById(
    "predictHistoryImportInput",
  );
  let stateOptionsInitialized = false;
  let latestCoverageText = "--";

  const csvEscape = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;

  const readHistoryRows = () => {
    try {
      const raw = localStorage.getItem(PREDICT_HISTORY_STORAGE_KEY);
      const parsed = raw ? JSON.parse(raw) : [];
      return Array.isArray(parsed) ? parsed : [];
    } catch (_) {
      return [];
    }
  };

  const writeHistoryRows = (rows) => {
    try {
      localStorage.setItem(
        PREDICT_HISTORY_STORAGE_KEY,
        JSON.stringify(Array.isArray(rows) ? rows.slice(0, 500) : []),
      );
    } catch (_) {
      // Ignore storage errors.
    }
  };

  const decisionFromStatus = (statusRaw) => {
    const status = String(statusRaw || "wait").toLowerCase();
    if (status === "sell" || status === "risk") return "Sell Today";
    if (status === "avoid" || status === "hold") return "Avoid Selling Now";
    return "Wait For Better Price";
  };

  const parseCsvLine = (line) => {
    const out = [];
    let cur = "";
    let inQuotes = false;
    for (let i = 0; i < line.length; i += 1) {
      const ch = line[i];
      if (ch === '"') {
        if (inQuotes && line[i + 1] === '"') {
          cur += '"';
          i += 1;
        } else {
          inQuotes = !inQuotes;
        }
      } else if (ch === "," && !inQuotes) {
        out.push(cur);
        cur = "";
      } else {
        cur += ch;
      }
    }
    out.push(cur);
    return out.map((x) => x.trim());
  };

  const renderPredictHistory = () => {
    if (!historyTableBody) return;
    const rows = readHistoryRows();
    if (!rows.length) {
      historyTableBody.innerHTML = `
        <tr>
          <td colspan="13" class="text-center text-muted py-3">No prediction records yet.</td>
        </tr>
      `;
      return;
    }

    historyTableBody.innerHTML = rows
      .map(
        (r) => `
          <tr>
            <td>${r.time || "--"}</td>
            <td>${r.state || "--"}</td>
            <td>${r.district || "--"}</td>
            <td>${r.market || "--"}</td>
            <td>${r.commodity || "--"}</td>
            <td>${r.variety || "--"}</td>
            <td>${r.arrival_date || "--"}</td>
            <td>${Number(r.min_price || 0).toFixed(2)}</td>
            <td>${Number(r.max_price || 0).toFixed(2)}</td>
            <td>${Number(r.expected_price || 0).toFixed(2)}</td>
            <td>${Number(r.current_price || 0).toFixed(2)}</td>
            <td>${r.decision || "--"}</td>
            <td>${r.confidence_pct || 0}%</td>
          </tr>
        `,
      )
      .join("");
  };

  const appendPredictHistoryRow = (payload, data) => {
    const existing = readHistoryRows();
    const newRow = {
      time: new Date().toLocaleString(),
      state: payload.state || "",
      district: payload.district || "",
      market: payload.market || "",
      commodity: payload.commodity || "",
      variety: payload.variety || "",
      arrival_date: payload.arrival_date || "",
      min_price: Number(payload.min_price || 0),
      max_price: Number(payload.max_price || 0),
      expected_price: Number(
        data.predicted_price ?? data.predicted_modal_price ?? 0,
      ),
      current_price: Number(data.current_market_price || 0),
      decision: decisionFromStatus(data.recommendation_status),
      confidence_pct: Math.max(
        0,
        Math.min(100, Math.round(Number(data.confidence || 0) * 100)),
      ),
    };
    writeHistoryRows([newRow, ...existing]);
    renderPredictHistory();
  };

  if (arrivalDateEl) {
    if (!arrivalDateEl.value) {
      arrivalDateEl.type = "text";
    }

    arrivalDateEl.addEventListener("focus", () => {
      arrivalDateEl.type = "date";
    });

    arrivalDateEl.addEventListener("blur", () => {
      if (!arrivalDateEl.value) {
        arrivalDateEl.type = "text";
      }
    });
  }

  const fillSelect = (
    selectEl,
    items,
    preferredValue,
    emptyLabel,
    allowUnselected = false,
  ) => {
    if (!selectEl) return;
    const options = Array.isArray(items) ? items : [];

    if (options.length === 0) {
      const label = emptyLabel || "";
      selectEl.innerHTML = `<option value="">${label}</option>`;
      selectEl.value = "";
      return;
    }

    selectEl.innerHTML = options
      .map((v) => `<option value="${v}">${v}</option>`)
      .join("");

    if (preferredValue && options.includes(preferredValue)) {
      selectEl.value = preferredValue;
    } else if (allowUnselected) {
      selectEl.selectedIndex = -1;
    }
  };

  const loadPredictOptions = async ({ preserve = true } = {}) => {
    const state = stateEl?.value || "";
    const district = districtEl?.value || "";
    const market = marketEl?.value || "";
    const commodity = commodityEl?.value || "";

    const query = new URLSearchParams({
      state,
      district,
      market,
      commodity,
    }).toString();
    const data = await fetchJsonWithTimeout(
      `/api/predict_options?${query}`,
      20000,
    );

    if (!stateOptionsInitialized) {
      fillSelect(stateEl, data.states, "", "No state data", true);
      stateOptionsInitialized = true;
    } else {
      // Keep the user's active state selection and only refresh dependent fields.
      const currentState = stateEl?.value || state;
      if (currentState && data.states?.includes(currentState)) {
        stateEl.value = currentState;
      }
    }
    fillSelect(
      districtEl,
      data.districts,
      preserve ? district : data.selected?.district,
      "No districts in selected state",
      true,
    );
    fillSelect(
      marketEl,
      data.markets,
      preserve ? marketEl?.value : data.selected?.market,
      "No markets in selected district",
      true,
    );
    fillSelect(
      commodityEl,
      data.commodities,
      preserve ? commodity : "",
      "No commodity data",
      true,
    );
    fillSelect(
      varietyEl,
      data.varieties,
      preserve ? varietyEl?.value : "",
      "No varieties for selected commodity",
      true,
    );

    if (optionsUpdatedAtEl) {
      const coverageText = data.coverage
        ? `Coverage: ${data.coverage.states_in_dataset}/${data.coverage.states_reference} states/UTs in current dataset.`
        : "";
      const noDataText = data.message ? ` ${data.message}` : "";
      optionsUpdatedAtEl.textContent = `Dataset-driven options updated: ${data.updated_at}. ${coverageText}${noDataText}`;
      latestCoverageText = data.coverage
        ? `${data.coverage.states_in_dataset}/${data.coverage.states_reference}`
        : "--";
    }
  };

  const formatMoney = (v) =>
    `₹ ${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

  const renderFarmerPanel = (data) => {
    const panel = document.getElementById("farmerPanel");
    if (!panel) return;

    const predicted = Number(
      data.predicted_price ?? data.predicted_modal_price ?? 0,
    );
    const current = Number(data.current_market_price ?? 0);
    const diff = Number(data.profit_delta ?? predicted - current);

    const cropEl = document.getElementById("fpCrop");
    const predEl = document.getElementById("fpPredPrice");
    const currentEl = document.getElementById("fpCurrentPrice");
    const deltaEl = document.getElementById("fpDelta");
    const trendEl = document.getElementById("fpTrend");
    const trendTextEl = document.getElementById("fpTrendText");
    const badgeEl = document.getElementById("fpActionBadge");
    const marketEl = document.getElementById("fpBestMarket");
    const reasonsEl = document.getElementById("fpMarketReasons");
    const confTextEl = document.getElementById("fpConfidenceText");
    const confBar = document.getElementById("fpConfidenceBar");
    const s1 = document.getElementById("fpSummary1");
    const s2 = document.getElementById("fpSummary2");
    const s3 = document.getElementById("fpSummary3");
    const tipsEl = document.getElementById("fpEducationTips");
    const metaLineEl = document.getElementById("fpMetaLine");

    if (cropEl) cropEl.textContent = data.crop || "Crop";
    if (predEl) predEl.textContent = formatMoney(predicted);
    if (currentEl) currentEl.textContent = formatMoney(current);

    if (deltaEl) {
      deltaEl.classList.remove("profit-up", "profit-down", "profit-flat");
      if (diff > 0.01) {
        deltaEl.classList.add("profit-up");
        deltaEl.textContent = `▲ +${formatMoney(diff)} Profit Opportunity`;
      } else if (diff < -0.01) {
        deltaEl.classList.add("profit-down");
        deltaEl.textContent = `▼ ${formatMoney(diff)} Lower than current market`;
      } else {
        deltaEl.classList.add("profit-flat");
        deltaEl.textContent = "→ Price is close to current market";
      }
    }

    const trend = (data.price_trend || "stable").toLowerCase();
    if (trendEl) {
      if (trend === "increasing") trendEl.textContent = "⬆ Price Rising";
      else if (trend === "decreasing") trendEl.textContent = "⬇ Price Falling";
      else trendEl.textContent = "→ Stable Price";
    }
    if (trendTextEl)
      trendTextEl.textContent = data.summary_lines?.[0] || "Prices are stable.";

    const status = (data.recommendation_status || "wait").toLowerCase();
    if (badgeEl) {
      badgeEl.className = "badge";
      if (status === "sell" || status === "risk") {
        badgeEl.classList.add("text-bg-danger");
        badgeEl.textContent = "Sell Today";
      } else if (status === "avoid" || status === "hold") {
        badgeEl.classList.add("text-bg-secondary");
        badgeEl.textContent = "Avoid Selling Now";
      } else if (status === "wait") {
        badgeEl.classList.add("text-bg-warning");
        badgeEl.textContent = "Wait For Better Price";
      } else {
        badgeEl.classList.add("text-bg-warning");
        badgeEl.textContent = "Wait For Better Price";
      }
    }

    if (marketEl) marketEl.textContent = data.best_market || "-";
    if (reasonsEl) {
      reasonsEl.innerHTML = (data.best_market_reasons || [])
        .map((r) => `<li>${r}</li>`)
        .join("");
    }

    const confidencePct = Math.max(
      0,
      Math.min(100, Math.round(Number(data.confidence || 0) * 100)),
    );
    if (confTextEl) confTextEl.textContent = `${confidencePct}%`;
    if (confBar) {
      confBar.style.width = `${confidencePct}%`;
      confBar.textContent = `${confidencePct}%`;
      confBar.className = "progress-bar";
      if (confidencePct >= 75) confBar.classList.add("bg-success");
      else if (confidencePct >= 50) confBar.classList.add("bg-warning");
      else confBar.classList.add("bg-danger");
    }

    if (s1)
      s1.textContent = data.summary_lines?.[0] || "Price movement is stable.";
    if (s2)
      s2.textContent =
        data.summary_lines?.[1] || "Check market daily for better timing.";
    if (s3)
      s3.textContent =
        data.summary_lines?.[2] || "Choose the best nearby market.";

    if (tipsEl) {
      tipsEl.innerHTML = (data.details?.education_tips || [])
        .map((t) => `<li>${t}</li>`)
        .join("");
    }

    if (metaLineEl) {
      const band = data.details?.forecast_band || {};
      const marketPts = Number(data.details?.market_data_points || 0);
      const varietyPts = Number(data.details?.variety_data_points || 0);
      metaLineEl.textContent = `Data points: market ${marketPts}, variety ${varietyPts} | Forecast band: ${formatMoney(band.low || 0)} to ${formatMoney(band.high || 0)} | Updated: ${data.details?.updated_at || "--"}`;
    }

    const forecastBandEl = document.getElementById("fpForecastBand");
    const dataStrengthEl = document.getElementById("fpDataStrength");
    const marketSignalEl = document.getElementById("fpMarketSignal");
    const latestArrivalEl = document.getElementById("fpLatestArrival");
    if (forecastBandEl || dataStrengthEl || marketSignalEl || latestArrivalEl) {
      const band = data.details?.forecast_band || {};
      const marketPts = Number(data.details?.market_data_points || 0);
      const varietyPts = Number(data.details?.variety_data_points || 0);
      const signal = (data.recommendation_status || "wait").toLowerCase();

      if (forecastBandEl) {
        forecastBandEl.textContent = `${formatMoney(band.low || 0)} to ${formatMoney(band.high || 0)} per ton`;
      }
      if (dataStrengthEl) {
        const grade =
          marketPts >= 20 && varietyPts >= 10
            ? "Strong"
            : marketPts >= 8
              ? "Moderate"
              : "Limited";
        dataStrengthEl.textContent = `Market points: ${marketPts}, Variety points: ${varietyPts} (${grade})`;
      }
      if (marketSignalEl) {
        marketSignalEl.textContent =
          signal === "sell" || signal === "risk"
            ? "Expected price above market. Selling window looks favorable."
            : signal === "avoid" || signal === "hold"
              ? "Current market stronger than expected. Delay may be safer."
              : "Near parity. Track mandi rates for 1-2 days.";
      }
      if (latestArrivalEl) {
        latestArrivalEl.textContent =
          data.details?.latest_market_arrival || "--";
      }
    }

    const qtyInput = document.getElementById("fpQty");
    const revenueEl = document.getElementById("fpRevenue");
    const updateRevenue = () => {
      const qty = Number(qtyInput?.value || 0);
      const revenue = predicted * qty;
      if (revenueEl) revenueEl.textContent = formatMoney(revenue);
    };
    if (qtyInput) qtyInput.oninput = updateRevenue;
    updateRevenue();

    const chartEl = document.getElementById("farmerTrendChart");
    if (chartEl) {
      if (farmerTrendChart) farmerTrendChart.destroy();
      const labels = data.chart?.labels || ["Now", "Forecast"];
      const values = data.chart?.values || [current, predicted];
      farmerTrendChart = new Chart(chartEl, {
        type: "line",
        data: {
          labels,
          datasets: [
            {
              label: "Price",
              data: values,
              borderColor: "#2e7d32",
              backgroundColor: "rgba(102, 187, 106, 0.25)",
              fill: true,
              tension: 0.2,
            },
          ],
        },
      });
    }

    panel.classList.remove("d-none");
  };

  const runPrediction = async (payload) => {
    showLoader(true);
    try {
      const res = await fetch("/predict_price", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!data.ok) throw new Error(data.message || "Prediction failed");

      lastPredictionPayload = { ...payload };
      lastPredictionData = data;
      // Render farmer-focused panel on pages where it exists (e.g., Test Application).
      renderFarmerPanel(data);

      // Render prediction-right-panel only on pages that include it.
      if (document.getElementById("predictResultContent")) {
        updatePredictionResultsPanel(payload, data);
      }

      // Render metric cards only on pages that include those cards.
      if (document.getElementById("metricCrop")) {
        updateMetricCards(payload, data);
      }
      return data;
    } finally {
      showLoader(false);
    }
  };

  const updatePredictionResultsPanel = (payload, data) => {
    const empty = document.getElementById("predictResultEmpty");
    const content = document.getElementById("predictResultContent");
    if (!empty || !content) return;

    empty.classList.add("d-none");
    content.classList.remove("d-none");

    const predicted = Number(
      data.predicted_price ?? data.predicted_modal_price ?? 0,
    );
    const current = Number(data.current_market_price ?? 0);
    const confidence = Math.max(
      0,
      Math.min(100, Math.round(Number(data.confidence || 0) * 100)),
    );
    const status = (data.recommendation_status || "wait").toLowerCase();

    const priceEl = document.getElementById("resultPrice");
    const currentEl = document.getElementById("resultCurrentPrice");
    const diffEl = document.getElementById("resultPriceDiff");
    const recEl = document.getElementById("resultRecommendation");
    const confEl = document.getElementById("resultConfidence");
    const bandEl = document.getElementById("resultBand");
    const trendEl = document.getElementById("resultTrendAnalysis");
    const signalEl = document.getElementById("resultMarketSignal");
    const bestMarketEl = document.getElementById("resultBestMarket");
    const dataPtsEl = document.getElementById("resultDataPoints");

    if (priceEl) priceEl.textContent = formatMoney(predicted) + " / ton";
    if (currentEl) currentEl.textContent = formatMoney(current) + " / ton";

    if (diffEl) {
      const priceDiff = predicted - current;
      const diffClass =
        priceDiff > 0.5
          ? "text-success"
          : priceDiff < -0.5
            ? "text-danger"
            : "text-warning";
      diffEl.className = `small ${diffClass}`;
      diffEl.textContent = `${priceDiff >= 0 ? "+" : ""}${formatMoney(priceDiff)} (${((priceDiff / current) * 100).toFixed(1)}%)`;
    }

    if (recEl) {
      let recText = "Wait For Better Price";
      let recClass = "badge text-bg-warning";
      if (status === "sell" || status === "risk") {
        recText = "Sell Today";
        recClass = "badge text-bg-danger";
      } else if (status === "avoid" || status === "hold") {
        recText = "Avoid Selling Now";
        recClass = "badge text-bg-secondary";
      }
      recEl.innerHTML = `<span class="${recClass}">${recText}</span>`;
    }

    if (confEl) {
      confEl.style.width = `${confidence}%`;
      confEl.textContent = `${confidence}%`;
      if (confidence >= 75) confEl.className = "progress-bar bg-success";
      else if (confidence >= 50) confEl.className = "progress-bar bg-warning";
      else confEl.className = "progress-bar bg-danger";
    }

    const band = data.details?.forecast_band || {};
    if (bandEl) {
      bandEl.textContent = `${formatMoney(band.low || 0)} to ${formatMoney(band.high || 0)} / ton`;
    }

    if (trendEl) {
      const trend = (data.price_trend || "stable").toLowerCase();
      trendEl.textContent =
        trend === "increasing"
          ? "📈 Prices are rising - Good selling window ahead"
          : trend === "decreasing"
            ? "📉 Prices are falling - Consider selling sooner"
            : "➡️ Stable trend - Monitor daily rates";
    }

    if (signalEl) {
      signalEl.textContent =
        status === "sell" || status === "risk"
          ? "Market advantage detected. Expected price is above current market rate."
          : status === "avoid" || status === "hold"
            ? "Market is stronger. Expected price is below current rate."
            : "Prices balanced. Monitor for better opportunities.";
    }

    if (bestMarketEl) {
      bestMarketEl.innerHTML = `<strong>${data.best_market || payload.market}</strong><br><small>${(data.best_market_reasons || []).map((r) => "• " + r).join("<br>")}</small>`;
    }

    if (dataPtsEl) {
      const marketPts = Number(data.details?.market_data_points || 0);
      const varietyPts = Number(data.details?.variety_data_points || 0);
      dataPtsEl.textContent = `Market data: ${marketPts} records | Variety data: ${varietyPts} records`;
    }

    // Update analysis sections
    updateAnalysisSections(payload, data);
  };

  const updateAnalysisSections = (payload, data) => {
    const analysisSection = document.getElementById("analysisSection");
    if (analysisSection) {
      analysisSection.classList.remove("d-none");
      // Scroll into view after a brief delay to ensure DOM is updated
      setTimeout(() => {
        analysisSection.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 100);
    }

    const predicted = Number(
      data.predicted_price ?? data.predicted_modal_price ?? 0,
    );
    const current = Number(data.current_market_price ?? 0);
    const realRange = data.details?.real_market_range || {
      min: current,
      max: current,
      avg: current,
    };

    // Price Analysis
    document.getElementById("analysisRange").textContent =
      `${formatMoney(realRange.min)} - ${formatMoney(realRange.max)}`;
    document.getElementById("analysisAvg").textContent = formatMoney(
      realRange.avg,
    );
    document.getElementById("analysisDiff").textContent =
      `${((predicted / current - 1) * 100).toFixed(1)}%`;
    document.getElementById("analysisVolatility").textContent =
      `${(((realRange.max - realRange.min) / realRange.avg) * 100).toFixed(1)}%`;

    const analysisInsight = document.getElementById("analysisInsight");
    if (predicted > realRange.max) {
      analysisInsight.textContent =
        "✓ Expected price is above historical maximum - exceptional selling opportunity.";
      analysisInsight.style.color = "#4caf50";
    } else if (predicted < realRange.min) {
      analysisInsight.textContent =
        "⚠ Expected price is below historical minimum - market caution advised.";
      analysisInsight.style.color = "#ff9800";
    } else if (predicted > realRange.avg) {
      analysisInsight.textContent =
        "↑ Expected price is above average - favorable conditions.";
      analysisInsight.style.color = "#2196f3";
    } else {
      analysisInsight.textContent =
        "↓ Expected price is below average - consider waiting.";
      analysisInsight.style.color = "#f44336";
    }

    // Risk Assessment
    const marketPts = Number(data.details?.market_data_points || 0);
    const varietyPts = Number(data.details?.variety_data_points || 0);

    document.getElementById("riskConcentration").textContent =
      marketPts > 20 ? "Low" : marketPts > 5 ? "Medium" : "High";
    document.getElementById("riskData").textContent =
      varietyPts > 10 ? "Rich" : varietyPts > 5 ? "Moderate" : "Limited";
    document.getElementById("riskSeasonal").textContent =
      data.price_trend === "stable" ? "Low" : "Medium";

    const overallRisk =
      marketPts < 5 || varietyPts < 5
        ? "HIGH"
        : marketPts < 20 || varietyPts < 10
          ? "MEDIUM"
          : "LOW";
    const riskBadge = document.getElementById("riskOverall");
    riskBadge.textContent = overallRisk;
    riskBadge.className =
      overallRisk === "HIGH"
        ? "badge bg-danger"
        : overallRisk === "MEDIUM"
          ? "badge bg-warning"
          : "badge bg-success";

    const riskAdvice = document.getElementById("riskAdvice");
    riskAdvice.textContent =
      overallRisk === "HIGH"
        ? "⚠️ Limited data available. Verify prediction with local mandi before final decision."
        : "✓ Sufficient data confidence. Prediction is based on solid market data.";

    // Profit Calculator Setup
    const profitQty = document.getElementById("profitQty");
    const profitCost = document.getElementById("profitCost");
    const profitTransport = document.getElementById("profitTransport");
    const profitRevenue = document.getElementById("profitRevenue");
    const profitTotalCost = document.getElementById("profitTotalCost");
    const profitNet = document.getElementById("profitNet");

    const updateProfit = () => {
      const qty = Number(profitQty?.value || 0);
      const cost = Number(profitCost?.value || 0);
      const transport = Number(profitTransport?.value || 0);
      const revenue = qty * predicted;
      const totalCost = qty * (cost + transport);
      const netProfit = revenue - totalCost;

      if (profitRevenue) profitRevenue.textContent = formatMoney(revenue);
      if (profitTotalCost) profitTotalCost.textContent = formatMoney(totalCost);
      if (profitNet) {
        profitNet.textContent = formatMoney(netProfit);
        profitNet.style.color = netProfit > 0 ? "#2e7d32" : "#c62828";
      }
    };

    [profitQty, profitCost, profitTransport].forEach((el) => {
      if (el) el.addEventListener("input", updateProfit);
    });
    updateProfit();

    // Seasonal Analysis
    const chartValues = data.chart?.values || [];
    if (chartValues.length > 0) {
      const maxPrice = Math.max(...chartValues);
      const minPrice = Math.min(...chartValues);
      document.getElementById("seasonalPeak").textContent =
        formatMoney(maxPrice);
      document.getElementById("seasonalLow").textContent =
        formatMoney(minPrice);
      document.getElementById("seasonalVariation").textContent =
        `${((minPrice > 0 ? maxPrice / minPrice - 1 : 0) * 100).toFixed(1)}%`;
      document.getElementById("seasonalPosition").textContent =
        predicted > maxPrice * 0.9
          ? "📈 Near Peak Season"
          : "📉 Off-Peak Season";
    }

    // Market Comparison
    const selectedPrice = current;
    const bestPrice = data.best_market ? current * 1.05 : current; // Estimated best market
    const maxPrice = Math.max(selectedPrice, bestPrice);

    document.getElementById("compSelected").textContent =
      `${payload.market}: ${formatMoney(selectedPrice)}`;
    document.getElementById("compBest").textContent =
      `${data.best_market}: ${formatMoney(bestPrice)}`;
    document.getElementById("compSelectedBar").style.width =
      `${(selectedPrice / maxPrice) * 100}%`;
    document.getElementById("compBestBar").style.width =
      `${(bestPrice / maxPrice) * 100}%`;
    document.getElementById("compAdvice").textContent =
      bestPrice > selectedPrice
        ? `💡 Better price expected at ${data.best_market}`
        : "✓ Current market is competitive";

    // Historical Chart
    renderHistoricalChart(data);

    // Education Tips
    const tipsContainer = document.getElementById("educationTipsContainer");
    if (tipsContainer) {
      tipsContainer.innerHTML = (data.details?.education_tips || [])
        .map(
          (tip) =>
            `<div class="col-md-6"><div class="p-3" style="background: rgba(255,255,255,0.05); border-radius: 8px; border-left: 3px solid var(--primary);">
          <small><i class="fas fa-lightbulb me-2" style="color: var(--primary);"></i>${tip}</small>
        </div></div>`,
        )
        .join("");
    }
  };

  let historicalChart = null;
  const renderHistoricalChart = (data) => {
    const chartEl = document.getElementById("historicalChart");
    if (!chartEl) return;

    const labels = data.chart?.labels || ["Now"];
    const values = data.chart?.values || [0];

    if (historicalChart) historicalChart.destroy();

    historicalChart = new Chart(chartEl, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Price Trend",
            data: values,
            borderColor: "var(--primary)",
            backgroundColor: "rgba(46, 125, 50, 0.1)",
            fill: true,
            tension: 0.3,
            pointBackgroundColor: "var(--primary)",
            pointBorderColor: "#fff",
            pointRadius: 5,
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: true, labels: { color: "#999" } },
        },
        scales: {
          y: { beginAtZero: false, ticks: { color: "#999" } },
          x: { ticks: { color: "#999" } },
        },
      },
    });

    const stats = document.getElementById("historicalStats");
    if (stats) {
      const avg = (values.reduce((a, b) => a + b, 0) / values.length).toFixed(
        2,
      );
      const trend = data.price_trend || "stable";
      stats.textContent = `Avg: ${formatMoney(avg)} | Trend: ${trend.toUpperCase()}`;
    }
  };

  const updateMetricCards = (payload, data) => {
    const commodity = payload.commodity || "--";
    const market = payload.market || "--";
    const state = payload.state || "--";
    const variety = payload.variety || "--";
    const minPrice = Number(payload.min_price || 0);
    const maxPrice = Number(payload.max_price || 0);
    const realRange = data.details?.real_market_range || {};
    const latestArrival = data.details?.latest_market_arrival || "--";
    const currentPrice = Number(data.current_market_price || 0);
    const expectedPrice = Number(
      data.predicted_price ?? data.predicted_modal_price ?? 0,
    );
    const gap = expectedPrice - currentPrice;

    document.getElementById("metricCrop").textContent =
      `Commodity: ${commodity}`;
    document.getElementById("metricMarket").textContent = `Market: ${market}`;
    document.getElementById("metricRegion").textContent = `Region: ${state}`;

    document.getElementById("metricRangeLabel").textContent =
      `Real Price Range: ${formatMoney(realRange.min || minPrice)} - ${formatMoney(realRange.max || maxPrice)}`;
    document.getElementById("metricDateLabel").textContent =
      `Latest Arrival: ${latestArrival}`;
    document.getElementById("metricVarietyLabel").textContent =
      `Variety: ${variety} | Input: ${formatMoney(minPrice)}-${formatMoney(maxPrice)}`;

    document.getElementById("metricDataPoints").textContent =
      `Current Price: ${formatMoney(currentPrice)}`;
    document.getElementById("metricMarkets").textContent =
      `Expected Price: ${formatMoney(expectedPrice)}`;
    document.getElementById("metricCommodities").textContent =
      `Gap: ${gap >= 0 ? "+" : ""}${formatMoney(gap)}`;

    const confidencePct = Math.max(
      0,
      Math.min(100, Math.round(Number(data.confidence || 0) * 100)),
    );
    document.getElementById("metricAccuracy").textContent =
      `Confidence: ${confidencePct}%`;
    document.getElementById("metricCoverage").textContent =
      `Coverage: ${latestCoverageText}`;
    document.getElementById("metricModelSignal").textContent =
      `Signal: ${decisionFromStatus(data.recommendation_status)}`;
  };

  const exportPredictionDetails = () => {
    if (!lastPredictionPayload || !lastPredictionData) {
      alert("No prediction available to export yet.");
      return;
    }
    exportPredictionBundle({
      payload: lastPredictionPayload,
      data: lastPredictionData,
    });
  };

  exportBtn?.addEventListener("click", exportPredictionDetails);

  importHistoryBtn?.addEventListener("click", () => {
    historyImportInput?.click();
  });

  historyImportInput?.addEventListener("change", async (e) => {
    const file = e.target?.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const lines = text
        .split(/\r?\n/)
        .map((l) => l.trim())
        .filter(Boolean);
      if (lines.length < 2) {
        alert("CSV has no data rows to import.");
        return;
      }

      const headers = parseCsvLine(lines[0]).map((h) => h.toLowerCase());
      const idx = (name) => headers.indexOf(name);
      const importedRows = [];
      for (let i = 1; i < lines.length; i += 1) {
        const cols = parseCsvLine(lines[i]);
        importedRows.push({
          time: cols[idx("time")] || "",
          state: cols[idx("state")] || "",
          district: cols[idx("district")] || "",
          market: cols[idx("market")] || "",
          commodity: cols[idx("commodity")] || "",
          variety: cols[idx("variety")] || "",
          arrival_date: cols[idx("arrival_date")] || "",
          min_price: Number(cols[idx("min_price")] || 0),
          max_price: Number(cols[idx("max_price")] || 0),
          expected_price: Number(cols[idx("expected_price")] || 0),
          current_price: Number(cols[idx("current_price")] || 0),
          decision: cols[idx("decision")] || "",
          confidence_pct: Number(cols[idx("confidence_pct")] || 0),
        });
      }

      writeHistoryRows([...importedRows, ...readHistoryRows()]);
      renderPredictHistory();
      alert(`Imported ${importedRows.length} record(s).`);
    } catch (_) {
      alert("Failed to import CSV.");
    } finally {
      if (historyImportInput) historyImportInput.value = "";
    }
  });

  exportHistoryBtn?.addEventListener("click", () => {
    const rows = readHistoryRows();
    if (!rows.length) {
      alert("No history records to export.");
      return;
    }

    const header = [
      "time",
      "state",
      "district",
      "market",
      "commodity",
      "variety",
      "arrival_date",
      "min_price",
      "max_price",
      "expected_price",
      "current_price",
      "decision",
      "confidence_pct",
    ];

    const csv = [header.map(csvEscape).join(",")]
      .concat(
        rows.map((r) =>
          [
            r.time,
            r.state,
            r.district,
            r.market,
            r.commodity,
            r.variety,
            r.arrival_date,
            r.min_price,
            r.max_price,
            r.expected_price,
            r.current_price,
            r.decision,
            r.confidence_pct,
          ]
            .map(csvEscape)
            .join(","),
        ),
      )
      .join("\n");

    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `predict_history_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  });

  clearHistoryBtn?.addEventListener("click", () => {
    if (!confirm("Clear all saved prediction history records?")) return;
    writeHistoryRows([]);
    renderPredictHistory();
  });

  autoSyncEl?.addEventListener("change", () => {
    if (autoSyncStatusEl) {
      autoSyncStatusEl.textContent = autoSyncEl.checked
        ? "Auto-sync active (options only)"
        : "Auto-sync paused";
    }
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const payload = Object.fromEntries(new FormData(form).entries());
    try {
      const result = await runPrediction(payload);
      saveLatestPredictionBundle(payload, result);
      appendPredictHistoryRow(payload, result);
      if (autoSyncStatusEl)
        autoSyncStatusEl.textContent = `Last prediction: ${new Date().toLocaleTimeString()} (manual submit)`;
    } catch (err) {
      alert(err.message || "Prediction request failed.");
    }
  });

  const uploadForm = document.getElementById("uploadForm");
  if (uploadForm) {
    uploadForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const msg = document.getElementById("uploadMessage");
      showLoader(true);
      try {
        const res = await fetch("/upload_dataset", {
          method: "POST",
          body: new FormData(uploadForm),
        });
        const data = await res.json();
        msg.textContent = data.message || "Upload completed.";
        msg.className = data.ok
          ? "text-success d-block mt-2"
          : "text-danger d-block mt-2";
        if (data.ok) {
          await loadPredictOptions({ preserve: false });
        }
      } catch (_) {
        msg.textContent = "Upload failed.";
        msg.className = "text-danger d-block mt-2";
      } finally {
        showLoader(false);
      }
    });
  }

  stateEl?.addEventListener("change", async () => {
    await loadPredictOptions({ preserve: true });
  });

  districtEl?.addEventListener("change", async () => {
    await loadPredictOptions({ preserve: true });
  });

  marketEl?.addEventListener("change", async () => {
    await loadPredictOptions({ preserve: true });
  });

  commodityEl?.addEventListener("change", async () => {
    await loadPredictOptions({ preserve: true });
  });

  renderPredictHistory();
  await loadPredictOptions({ preserve: false });

  window.setInterval(async () => {
    try {
      await loadPredictOptions({ preserve: true });
    } catch (_) {
      // Keep silent for background sync and let manual refresh continue.
    }
  }, 30000);
}

function createChart(canvasId, config) {
  const el = document.getElementById(canvasId);
  if (!el) return null;
  return new Chart(el, config);
}

const pageCharts = {};
function upsertChart(key, canvasId, config) {
  if (pageCharts[key]) {
    pageCharts[key].destroy();
  }
  pageCharts[key] = createChart(canvasId, config);
}

async function setupFarmerKnowledgeInsightPage() {
  const content = document.getElementById("farmerInsightContent");
  if (!content) return;

  const emptyState = document.getElementById("farmerInsightEmpty");
  const exportBtn = document.getElementById("exportFarmerInsightBtn");
  const bundle = readLatestPredictionBundle();

  if (!bundle?.data) {
    emptyState?.classList.remove("d-none");
    content.classList.add("d-none");
    exportBtn?.setAttribute("disabled", "disabled");
    return;
  }

  const payload = bundle.payload || {};
  const data = bundle.data || {};

  const write = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };

  const formatMoney = (v) =>
    `₹ ${Number(v || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;

  write("insightState", payload.state || "--");
  write("insightDistrict", payload.district || "--");
  write("insightMarket", payload.market || "--");
  write("insightCommodity", payload.commodity || "--");
  write("insightVariety", payload.variety || "--");

  const predicted = Number(
    data.predicted_price ?? data.predicted_modal_price ?? 0,
  );
  const current = Number(data.current_market_price ?? 0);
  const diff = Number(data.profit_delta ?? predicted - current);

  write("fpCrop", data.crop || payload.commodity || "Crop");
  write("fpPredPrice", formatMoney(predicted));
  write("fpCurrentPrice", formatMoney(current));

  const deltaEl = document.getElementById("fpDelta");
  if (deltaEl) {
    deltaEl.classList.remove("profit-up", "profit-down", "profit-flat");
    if (diff > 0.01) {
      deltaEl.classList.add("profit-up");
      deltaEl.textContent = `▲ +${formatMoney(diff)} Profit Opportunity`;
    } else if (diff < -0.01) {
      deltaEl.classList.add("profit-down");
      deltaEl.textContent = `▼ ${formatMoney(diff)} Lower than current market`;
    } else {
      deltaEl.classList.add("profit-flat");
      deltaEl.textContent = "→ Price is close to current market";
    }
  }

  const trend = (data.price_trend || "stable").toLowerCase();
  write(
    "fpTrend",
    trend === "increasing"
      ? "⬆ Price Rising"
      : trend === "decreasing"
        ? "⬇ Price Falling"
        : "→ Stable Price",
  );
  write("fpTrendText", data.summary_lines?.[0] || "Prices are stable.");

  const badgeEl = document.getElementById("fpActionBadge");
  if (badgeEl) {
    badgeEl.className = "badge";
    const status = (data.recommendation_status || "wait").toLowerCase();
    if (status === "sell" || status === "risk") {
      badgeEl.classList.add("text-bg-danger");
      badgeEl.textContent = "Sell Today";
    } else if (status === "avoid" || status === "hold") {
      badgeEl.classList.add("text-bg-secondary");
      badgeEl.textContent = "Avoid Selling Now";
    } else if (status === "wait") {
      badgeEl.classList.add("text-bg-warning");
      badgeEl.textContent = "Wait For Better Price";
    } else {
      badgeEl.classList.add("text-bg-warning");
      badgeEl.textContent = "Wait For Better Price";
    }
  }

  write("fpBestMarket", data.best_market || "-");
  const reasonsEl = document.getElementById("fpMarketReasons");
  if (reasonsEl) {
    reasonsEl.innerHTML = (data.best_market_reasons || [])
      .map((reason) => `<li>${reason}</li>`)
      .join("");
  }

  const confidencePct = Math.max(
    0,
    Math.min(100, Math.round(Number(data.confidence || 0) * 100)),
  );
  write("fpConfidenceText", `${confidencePct}%`);
  const confBar = document.getElementById("fpConfidenceBar");
  if (confBar) {
    confBar.style.width = `${confidencePct}%`;
    confBar.textContent = `${confidencePct}%`;
    confBar.className = "progress-bar";
    if (confidencePct >= 75) confBar.classList.add("bg-success");
    else if (confidencePct >= 50) confBar.classList.add("bg-warning");
    else confBar.classList.add("bg-danger");
  }

  write("fpSummary1", data.summary_lines?.[0] || "Price movement is stable.");
  write(
    "fpSummary2",
    data.summary_lines?.[1] || "Check market daily for better timing.",
  );
  write(
    "fpSummary3",
    data.summary_lines?.[2] || "Choose the best nearby market.",
  );

  const tipsEl = document.getElementById("fpEducationTips");
  if (tipsEl) {
    tipsEl.innerHTML = (data.details?.education_tips || [])
      .map((tip) => `<li>${tip}</li>`)
      .join("");
  }

  const band = data.details?.forecast_band || {};
  write(
    "fpMetaLine",
    `Data points: market ${Number(data.details?.market_data_points || 0)}, variety ${Number(data.details?.variety_data_points || 0)} | Forecast band: ${formatMoney(band.low || 0)} to ${formatMoney(band.high || 0)} | Updated: ${data.details?.updated_at || "--"}`,
  );

  const qtyInput = document.getElementById("fpQty");
  const revenueEl = document.getElementById("fpRevenue");
  const updateRevenue = () => {
    const qty = Number(qtyInput?.value || 0);
    if (revenueEl) revenueEl.textContent = formatMoney(predicted * qty);
  };
  qtyInput?.addEventListener("input", updateRevenue);
  updateRevenue();

  upsertChart("farmerInsightChart", "farmerInsightChart", {
    type: "line",
    data: {
      labels: data.chart?.labels || ["Now", "Forecast"],
      datasets: [
        {
          label: "Price",
          data: data.chart?.values || [current, predicted],
          borderColor: "#2e7d32",
          backgroundColor: "rgba(102, 187, 106, 0.25)",
          fill: true,
          tension: 0.2,
        },
      ],
    },
  });

  exportBtn?.addEventListener("click", () => exportPredictionBundle(bundle));
  emptyState?.classList.add("d-none");
  content.classList.remove("d-none");
}

async function setupDashboard() {
  const trendCanvas = document.getElementById("trendChart");
  if (!trendCanvas) return;
  const exportBtn = document.getElementById("exportCoverageCsv");
  let latestCoverageRows = [];

  const csvCell = (value) => {
    const text = String(value ?? "");
    const escaped = text.replace(/"/g, '""');
    return `"${escaped}"`;
  };

  const exportCoverageCsv = () => {
    if (!latestCoverageRows.length) {
      alert("Coverage data is not loaded yet. Please wait a moment.");
      return;
    }

    const header = ["State/UT", "Districts", "Markets", "Records"];
    const lines = [header.map(csvCell).join(",")];
    latestCoverageRows.forEach((row) => {
      lines.push(
        [row.State, row.districts, row.markets, row.records]
          .map(csvCell)
          .join(","),
      );
    });

    const csvText = lines.join("\n");
    const blob = new Blob([csvText], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);

    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    const a = document.createElement("a");
    a.href = url;
    a.download = `data_coverage_report_${stamp}.csv`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  exportBtn?.addEventListener("click", exportCoverageCsv);

  const setText = (id, value, raw = false) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = raw ? value : Number(value || 0).toLocaleString();
  };

  const loadDashboard = async () => {
    const data = await fetchJsonWithTimeout("/api/dashboard_data", 25000);

    upsertChart("trendChart", "trendChart", {
      type: "line",
      data: {
        labels: data.trend.labels,
        datasets: [
          {
            label: "Modal Price",
            data: data.trend.values,
            borderColor: "#2e7d32",
            backgroundColor: "rgba(102, 187, 106, 0.35)",
            fill: true,
            tension: 0.25,
          },
        ],
      },
    });

    upsertChart("monthlyChart", "monthlyChart", {
      type: "bar",
      data: {
        labels: data.monthly.labels,
        datasets: [
          {
            label: "Monthly Avg",
            data: data.monthly.values,
            backgroundColor: "#ffa000",
          },
        ],
      },
    });

    upsertChart("commodityChart", "commodityChart", {
      type: "bar",
      data: {
        labels: data.commodity.labels,
        datasets: [
          {
            label: "Commodity Avg",
            data: data.commodity.values,
            backgroundColor: "#66bb6a",
          },
        ],
      },
      options: { indexAxis: "y" },
    });

    upsertChart("stateChart", "stateChart", {
      type: "doughnut",
      data: {
        labels: data.state.labels,
        datasets: [
          {
            data: data.state.values,
            backgroundColor: [
              "#2e7d32",
              "#66bb6a",
              "#ffa000",
              "#8bc34a",
              "#43a047",
              "#7cb342",
              "#26a69a",
              "#c0ca33",
              "#f9a825",
              "#ff7043",
            ],
          },
        ],
      },
    });

    upsertChart("districtChart", "districtChart", {
      type: "bar",
      data: {
        labels: data.district.labels,
        datasets: [
          {
            label: "District Avg",
            data: data.district.values,
            backgroundColor: "#1e88e5",
          },
        ],
      },
      options: { indexAxis: "y" },
    });

    upsertChart("spreadChart", "spreadChart", {
      type: "bar",
      data: {
        labels: data.spread.labels,
        datasets: [
          {
            label: "Avg Spread",
            data: data.spread.values,
            backgroundColor: "#00897b",
          },
        ],
      },
    });

    setText("statRecords", data.stats.records);
    setText("statStates", data.stats.states);
    setText("statMarkets", data.stats.markets);
    setText("statCommodities", data.stats.commodities);
    setText("dashModelName", data.meta.model_name, true);
    setText("dashModelTrainedAt", data.meta.trained_at, true);
    setText("dashDatasetModifiedAt", data.meta.dataset_last_modified, true);
    setText("dashRealRows", data.stats.real_rows);
    setText("dashSyntheticRows", data.stats.synthetic_rows);

    const coverageBody = document.getElementById("coverageTableBody");
    latestCoverageRows = data.coverage?.rows || [];
    if (coverageBody) {
      coverageBody.innerHTML = latestCoverageRows
        .map(
          (row) => `
            <tr>
              <td>${row.State}</td>
              <td>${Number(row.districts).toLocaleString()}</td>
              <td>${Number(row.markets).toLocaleString()}</td>
              <td>${Number(row.records).toLocaleString()}</td>
            </tr>
          `,
        )
        .join("");
    }

    setText(
      "dashboardUpdatedAt",
      `Last refreshed: ${data.meta.updated_at}`,
      true,
    );
  };

  await loadDashboard();
  window.setInterval(loadDashboard, 30000);
}

async function setupLiveOverview() {
  let hasAnimated = false;

  const writeValue = (id, value) => {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
  };

  const setCounterTarget = (id, value) => {
    const el = document.getElementById(id);
    if (!el) return;
    const numeric = Number(value || 0);
    if (!hasAnimated) {
      el.dataset.target = String(numeric);
      el.textContent = "0";
    } else {
      el.textContent = numeric.toLocaleString();
    }
  };

  const load = async () => {
    const data = await fetchJsonWithTimeout("/api/live_overview", 20000);

    setCounterTarget("homeRecords", data.stats.records);
    setCounterTarget("homeStates", data.stats.states);
    setCounterTarget("homeMarkets", data.stats.markets);
    setCounterTarget("homeAiReady", data.stats.ai_ready);

    writeValue("homeDatasetLastModified", data.dataset_last_modified || "--");
    writeValue("homeModelName", data.model?.name || "--");
    writeValue("homeModelTrainedAt", data.model?.trained_at || "--");
    writeValue("homeLiveUpdatedAt", data.updated_at || "--");

    writeValue(
      "footerDatasetStamp",
      `Dataset sync: ${data.dataset_last_modified || "--"}`,
    );
    writeValue("footerModelStamp", `Model: ${data.model?.name || "--"}`);
    writeValue("footerUpdatedAt", `Updated at: ${data.updated_at || "--"}`);

    if (!hasAnimated && document.querySelector("#homeRecords.counter")) {
      animateCounters();
      hasAnimated = true;
    }
  };

  await load();
  window.setInterval(load, 30000);
}

async function setupDatasetTable() {
  const tableBody = document.getElementById("datasetTableBody");
  if (!tableBody) return;

  let page = 1;
  let totalPages = 1;

  const searchEl = document.getElementById("datasetSearch");
  const sortByEl = document.getElementById("datasetSortBy");
  const orderEl = document.getElementById("datasetOrder");
  const metaEl = document.getElementById("datasetMeta");

  async function loadTable() {
    const q = encodeURIComponent(searchEl.value || "");
    const sortBy = encodeURIComponent(sortByEl.value || "Arrival_Year");
    const order = encodeURIComponent(orderEl.value || "desc");

    const res = await fetch(
      `/api/dataset?page=${page}&per_page=20&q=${q}&sort_by=${sortBy}&order=${order}`,
    );
    const data = await res.json();

    totalPages = data.total_pages || 1;
    tableBody.innerHTML = data.rows
      .map(
        (row) => `
                <tr>
                    <td>${row.State}</td>
                    <td>${row.District}</td>
                    <td>${row.Market}</td>
                    <td>${row.Commodity}</td>
                      <td>${String(row.Data_Source || "real").toLowerCase() === "synthetic" ? '<span class="badge text-bg-warning">synthetic</span>' : '<span class="badge text-bg-success">real</span>'}</td>
                    <td>${Number(row.Min_Price).toFixed(2)}</td>
                    <td>${Number(row.Max_Price).toFixed(2)}</td>
                    <td>${Number(row.Modal_Price).toFixed(2)}</td>
                </tr>
            `,
      )
      .join("");

    metaEl.textContent = `Page ${data.page} of ${data.total_pages} | Total records: ${data.total}`;
  }

  document.getElementById("datasetReload")?.addEventListener("click", () => {
    page = 1;
    loadTable();
  });

  document.getElementById("prevPage")?.addEventListener("click", () => {
    if (page > 1) {
      page -= 1;
      loadTable();
    }
  });

  document.getElementById("nextPage")?.addEventListener("click", () => {
    if (page < totalPages) {
      page += 1;
      loadTable();
    }
  });

  await loadTable();
}

async function setupEdaData() {
  const histMin = document.getElementById("histMin");
  if (!histMin) return;

  const refreshBtn = document.getElementById("refreshEdaData");
  const updatedAtEl = document.getElementById("edaDataUpdatedAt");

  const load = async () => {
    showLoader(true);
    try {
      const data = await fetchJsonWithTimeout("/api/eda_data", 25000);

      const histCfg = (id, key, titleColor, chartKey) =>
        upsertChart(chartKey, id, {
          type: "line",
          data: {
            labels: data.hist[key].labels,
            datasets: [
              {
                label: key,
                data: data.hist[key].values,
                borderColor: titleColor,
                backgroundColor: "rgba(102, 187, 106, 0.25)",
                fill: true,
                tension: 0.2,
              },
            ],
          },
        });

      histCfg("histMin", "Min_Price", "#2e7d32", "histMin");
      histCfg("histMax", "Max_Price", "#ffa000", "histMax");
      histCfg("histModal", "Modal_Price", "#1e88e5", "histModal");

      upsertChart("catState", "catState", {
        type: "bar",
        data: {
          labels: data.categorical.State.labels,
          datasets: [
            {
              data: data.categorical.State.values,
              backgroundColor: "#66bb6a",
            },
          ],
        },
      });

      upsertChart("catCommodity", "catCommodity", {
        type: "bar",
        data: {
          labels: data.categorical.Commodity.labels,
          datasets: [
            {
              data: data.categorical.Commodity.values,
              backgroundColor: "#ffa000",
            },
          ],
        },
      });

      const corrTable = document.getElementById("corrTable");
      if (corrTable) {
        const labels = data.corr.labels;
        const head = `<thead><tr><th></th>${labels.map((l) => `<th>${l}</th>`).join("")}</tr></thead>`;
        const bodyRows = data.corr.matrix
          .map(
            (row, i) =>
              `<tr><th>${labels[i]}</th>${row.map((v) => `<td>${Number(v).toFixed(3)}</td>`).join("")}</tr>`,
          )
          .join("");
        corrTable.innerHTML = `${head}<tbody>${bodyRows}</tbody>`;
      }

      if (updatedAtEl)
        updatedAtEl.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
    } catch (err) {
      if (updatedAtEl) {
        updatedAtEl.textContent = `Error: ${err.message || "Failed to load EDA data"}`;
      }
    } finally {
      showLoader(false);
    }
  };

  refreshBtn?.addEventListener("click", load);
  await load();
}

async function setupEdaData2() {
  const scatterSupply = document.getElementById("scatterSupply");
  if (!scatterSupply) return;

  const refreshBtn = document.getElementById("refreshEdaData2");
  const updatedAtEl = document.getElementById("edaData2UpdatedAt");

  const load = async () => {
    showLoader(true);
    try {
      const data = await fetchJsonWithTimeout("/api/eda_data2", 25000);

      upsertChart("scatterSupply", "scatterSupply", {
        type: "scatter",
        data: {
          datasets: [
            {
              label: "Min Price vs Modal",
              data: data.scatter_supply.x.map((x, i) => ({
                x,
                y: data.scatter_supply.y[i],
              })),
              backgroundColor: "rgba(46,125,50,0.45)",
            },
          ],
        },
      });

      upsertChart("scatterDemand", "scatterDemand", {
        type: "scatter",
        data: {
          datasets: [
            {
              label: "Max Price vs Modal",
              data: data.scatter_demand.x.map((x, i) => ({
                x,
                y: data.scatter_demand.y[i],
              })),
              backgroundColor: "rgba(255,160,0,0.45)",
            },
          ],
        },
      });

      upsertChart("monthlyLineEda2", "monthlyLineEda2", {
        type: "line",
        data: {
          labels: data.line_monthly.labels,
          datasets: [
            {
              label: "Monthly Modal Price",
              data: data.line_monthly.values,
              borderColor: "#1e88e5",
              backgroundColor: "rgba(30,136,229,0.22)",
              fill: true,
              tension: 0.2,
            },
          ],
        },
      });

      if (updatedAtEl)
        updatedAtEl.textContent = `Updated: ${new Date().toLocaleTimeString()}`;
    } catch (err) {
      if (updatedAtEl) {
        updatedAtEl.textContent = `Error: ${err.message || "Failed to load EDA 2 data"}`;
      }
    } finally {
      showLoader(false);
    }
  };

  refreshBtn?.addEventListener("click", load);
  await load();
}

async function setupModelsData() {
  const table = document.querySelector("#modelsTable tbody");
  if (!table) return;

  const refreshBtn = document.getElementById("refreshModelsData");
  const updatedAtEl = document.getElementById("modelsDataUpdatedAt");

  const load = async () => {
    showLoader(true);
    try {
      const data = await fetchJsonWithTimeout("/api/models_data", 30000);
      table.innerHTML = (data.rows || [])
        .map(
          (row) => `
            <tr>
              <td>${row.model}</td>
              <td>${Number(row.train_r2).toFixed(4)}</td>
              <td>${Number(row.test_r2).toFixed(4)}</td>
              <td>${Number(row.train_rmse).toFixed(2)}</td>
              <td>${Number(row.test_rmse).toFixed(2)}</td>
            </tr>
          `,
        )
        .join("");
      if (updatedAtEl)
        updatedAtEl.textContent = `Updated: ${new Date().toLocaleTimeString()}${data.cached ? " (cached)" : ""}`;
    } catch (err) {
      table.innerHTML = `<tr><td colspan="5" class="text-danger">${err.message || "Failed to load model evaluation"}</td></tr>`;
      if (updatedAtEl) {
        updatedAtEl.textContent = `Error: ${err.message || "Failed to load models data"}`;
      }
    } finally {
      showLoader(false);
    }
  };

  refreshBtn?.addEventListener("click", load);
  await load();
}

async function setupBasicInfo() {
  const head = document.getElementById("basicHead");
  if (!head) return;

  const refreshBtn = document.getElementById("refreshBasicInfo");
  const updatedAt = document.getElementById("basicInfoUpdatedAt");

  const load = async () => {
    showLoader(true);
    try {
      const data = await fetchJsonWithTimeout("/api/basic_info", 20000);
      document.getElementById("basicHead").innerHTML = data.head_html;
      document.getElementById("basicShape").textContent =
        `(${data.shape[0]}, ${data.shape[1]})`;
      document.getElementById("basicDescribe").innerHTML = data.desc_html;
      document.getElementById("basicInfoTable").innerHTML = data.info_html;
      if (updatedAt) updatedAt.textContent = `Updated: ${data.updated_at}`;
    } finally {
      showLoader(false);
    }
  };

  refreshBtn?.addEventListener("click", load);
  await load();
}

async function setupPreprocessingData() {
  const pre = document.getElementById("preNumBefore");
  if (!pre) return;

  const refreshBtn = document.getElementById("refreshPreprocessing");
  const updatedAt = document.getElementById("preprocessingUpdatedAt");
  const sourceFilter = document.getElementById("preDataSourceFilter");
  const summary = document.getElementById("preprocessingSummary");

  const load = async () => {
    showLoader(true);
    try {
      const source = sourceFilter?.value || "real";
      const data = await fetchJsonWithTimeout(
        `/api/preprocessing_data?source=${encodeURIComponent(source)}`,
        20000,
      );
      document.getElementById("preNumBefore").innerHTML = data.num_before_html;
      document.getElementById("preCatBefore").innerHTML = data.cat_before_html;
      document.getElementById("preNumAfter").innerHTML = data.num_after_html;
      document.getElementById("preCatAfter").innerHTML = data.cat_after_html;
      document.getElementById("preHead").innerHTML = data.head_html;
      if (updatedAt) updatedAt.textContent = `Updated: ${data.updated_at}`;
      if (summary) {
        summary.textContent = `Source: ${String(data.source_applied || source).toUpperCase()} | Filtered rows: ${Number(data.rows_filtered || 0).toLocaleString()} / Total rows: ${Number(data.rows_total || 0).toLocaleString()} | Real: ${Number(data.real_rows || 0).toLocaleString()} | Synthetic: ${Number(data.synthetic_rows || 0).toLocaleString()}`;
      }
    } finally {
      showLoader(false);
    }
  };

  refreshBtn?.addEventListener("click", load);
  sourceFilter?.addEventListener("change", load);
  await load();
}

document.addEventListener("DOMContentLoaded", async () => {
  setupNavbarScroll();
  await setupLiveOverview();
  if (
    document.querySelector(".counter") &&
    !document.getElementById("homeRecords")
  )
    animateCounters();
  await setupPredictForm();
  await setupDashboard();
  await setupFarmerKnowledgeInsightPage();
  await setupDatasetTable();
  await setupEdaData();
  await setupEdaData2();
  await setupModelsData();
  await setupBasicInfo();
  await setupPreprocessingData();
});
