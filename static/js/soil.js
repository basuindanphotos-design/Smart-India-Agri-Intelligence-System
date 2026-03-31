(function () {
  const form = document.getElementById("soil-form");
  if (!form) {
    return;
  }

  let npkChart;
  let radarChart;
  let gaugeChart;

  const DRIVER_RULES = {
    nitrogen: {
      label: "Nitrogen (N)",
      low: 80,
      high: 140,
      lowText:
        "Low nitrogen can reduce leaf growth and tillering; crop vigor and yield potential may decline.",
      highText:
        "High nitrogen can increase lodging and imbalance nutrient uptake; optimize split dosing.",
      optimalText:
        "Nitrogen is in a productive range for vegetative growth and canopy development.",
    },
    phosphorus: {
      label: "Phosphorus (P)",
      low: 20,
      high: 60,
      lowText:
        "Low phosphorus can weaken root establishment and early crop growth.",
      highText:
        "High phosphorus may suppress micronutrient availability; avoid excess P-heavy fertilizers.",
      optimalText:
        "Phosphorus is in a healthy range for root strength and crop establishment.",
    },
    potassium: {
      label: "Potassium (K)",
      low: 120,
      high: 280,
      lowText:
        "Low potassium may reduce stress tolerance and grain/fruit quality.",
      highText:
        "High potassium can create nutrient imbalance with magnesium/calcium in some soils.",
      optimalText:
        "Potassium is in a balanced range supporting stress resistance and quality.",
    },
    ph: {
      label: "pH Level",
      low: 6.5,
      high: 7.5,
      lowText:
        "Acidic pH may reduce nutrient availability and increase aluminum toxicity risk.",
      highText:
        "Alkaline pH can lock micronutrients like zinc and iron; crops may show deficiency symptoms.",
      optimalText:
        "pH is near neutral, favorable for broad nutrient availability.",
    },
    moisture: {
      label: "Soil Moisture (%)",
      low: 35,
      high: 60,
      lowText:
        "Low moisture can reduce nutrient mobility and increase drought stress on crops.",
      highText:
        "Excess moisture may reduce root oxygen and increase disease pressure.",
      optimalText:
        "Moisture is in an efficient zone for uptake and root activity.",
    },
    organic_carbon: {
      label: "Organic Carbon (%)",
      low: 0.5,
      high: 0.9,
      lowText:
        "Low organic carbon weakens soil structure, microbial activity, and moisture retention.",
      highText:
        "High organic carbon generally supports soil resilience; maintain with balanced residue management.",
      optimalText:
        "Organic carbon is in a good range for structure and biological soil health.",
    },
    electrical_conductivity: {
      label: "Electrical Conductivity (dS/m)",
      low: 0.2,
      high: 1.2,
      lowText:
        "Very low EC indicates low soluble salts; monitor nutrient supply consistency.",
      highText:
        "High EC indicates salinity risk that may reduce water uptake and crop performance.",
      optimalText: "EC is in a suitable range with low salinity stress risk.",
    },
  };

  function createChart(ctx, config, existingChart) {
    if (!ctx || !window.Chart) {
      return existingChart;
    }
    if (existingChart) {
      existingChart.destroy();
    }
    return new window.Chart(ctx, config);
  }

  function formatNumber(value, digits = 2) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed.toFixed(digits) : "--";
  }

  function levelColor(level) {
    if (level === "Optimal") return "#1f8f48";
    if (level === "Low") return "#d3911e";
    return "#d15245";
  }

  function renderNpkPanel(npk) {
    const root = document.getElementById("npk-bars");
    if (!root) return;

    const nutrients = [
      { key: "nitrogen", label: "Nitrogen (N)", max: 200 },
      { key: "phosphorus", label: "Phosphorus (P)", max: 120 },
      { key: "potassium", label: "Potassium (K)", max: 320 },
    ];

    root.innerHTML = nutrients
      .map((item) => {
        const node = npk[item.key] || { value: 0, level: "Low" };
        const width = Math.min((Number(node.value) / item.max) * 100, 100);
        const color = levelColor(node.level);
        return `
          <div class="npk-item">
            <div class="npk-item-head">
              <span>${item.label}</span>
              <strong style="color:${color}">${node.level}</strong>
            </div>
            <div class="npk-track"><div class="npk-fill" style="width:${width}%; background:${color}"></div></div>
          </div>
        `;
      })
      .join("");
  }

  function renderCharts(result) {
    const npk = result.npk || {};
    const score = Number(result.score?.score || 0);

    const npkCtx = document.getElementById("npkChart");
    npkChart = createChart(
      npkCtx,
      {
        type: "bar",
        data: {
          labels: ["Nitrogen", "Phosphorus", "Potassium"],
          datasets: [
            {
              data: [
                npk.nitrogen?.value || 0,
                npk.phosphorus?.value || 0,
                npk.potassium?.value || 0,
              ],
              backgroundColor: ["#2d8a4b", "#68b14e", "#1c6f3b"],
              borderRadius: 8,
            },
          ],
        },
        options: { responsive: true, plugins: { legend: { display: false } } },
      },
      npkChart,
    );

    const radarCtx = document.getElementById("radarChart");
    radarChart = createChart(
      radarCtx,
      {
        type: "radar",
        data: {
          labels: ["N", "P", "K", "pH", "Moisture", "Org. Carbon", "EC"],
          datasets: [
            {
              label: "Soil Parameters",
              data: [
                npk.nitrogen?.value || 0,
                npk.phosphorus?.value || 0,
                npk.potassium?.value || 0,
                result.ph?.value || 0,
                result.moisture?.value || 0,
                Number(form.organic_carbon.value || 0),
                Number(form.electrical_conductivity.value || 0),
              ],
              fill: true,
              borderColor: "#2d8a4b",
              backgroundColor: "rgba(45, 138, 75, 0.18)",
            },
          ],
        },
        options: { responsive: true, scales: { r: { beginAtZero: true } } },
      },
      radarChart,
    );

    const gaugeCtx = document.getElementById("gaugeChart");
    gaugeChart = createChart(
      gaugeCtx,
      {
        type: "doughnut",
        data: {
          labels: ["Score", "Remaining"],
          datasets: [
            {
              data: [score, Math.max(0, 100 - score)],
              backgroundColor: [result.score?.color || "#2d8a4b", "#e7efe2"],
              borderWidth: 0,
            },
          ],
        },
        options: {
          cutout: "75%",
          responsive: true,
          plugins: { legend: { display: false } },
        },
      },
      gaugeChart,
    );
  }

  function renderList(listId, values) {
    const root = document.getElementById(listId);
    if (!root) return;
    root.innerHTML = (values || []).map((x) => `<li>${x}</li>`).join("");
  }

  function renderAlerts(alerts) {
    const root = document.getElementById("alert-cards");
    if (!root) return;

    const safeAlerts =
      alerts && alerts.length
        ? alerts
        : [
            {
              title: "No Critical Alerts",
              message: "No major soil warnings detected.",
              severity: "info",
            },
          ];

    root.innerHTML = safeAlerts
      .map(
        (a) =>
          `<article class="alert-card alert-${a.severity || "info"}"><strong>${a.title}</strong><p>${a.message}</p></article>`,
      )
      .join("");
  }

  function renderCrops(crops) {
    const root = document.getElementById("crop-tags");
    if (!root) return;
    root.innerHTML = (crops || [])
      .map((c) => `<span class="crop-tag">${c}</span>`)
      .join("");
  }

  function renderResult(result) {
    const scoreValue = Number(result.score?.score || 0);
    const scoreFill = document.getElementById("score-fill");
    const scoreNumber = document.getElementById("score-number");
    const soilGrade = document.getElementById("soil-grade");

    if (scoreFill)
      scoreFill.style.width = `${Math.max(0, Math.min(100, scoreValue))}%`;
    if (scoreNumber) scoreNumber.textContent = formatNumber(scoreValue, 1);
    if (soilGrade) {
      soilGrade.textContent = `${result.score?.grade || "Unknown"} Soil (${formatNumber(scoreValue, 1)})`;
      soilGrade.style.color = result.score?.color || "#2d8a4b";
    }

    const phMeta = document.getElementById("ph-meta");
    const moistureMeta = document.getElementById("moisture-meta");
    if (phMeta)
      phMeta.textContent = `pH ${formatNumber(result.ph?.value, 2)} -> ${result.ph?.category || "Unknown"}. ${result.ph?.suggestion || ""}`;
    if (moistureMeta)
      moistureMeta.textContent = `Moisture ${formatNumber(result.moisture?.value, 1)}% -> ${result.moisture?.status || "Unknown"}. ${result.moisture?.advice || ""}`;

    const mlCropText = document.getElementById("ml-crop-link");
    if (mlCropText) {
      mlCropText.textContent = result.crop_recommendation_from_ml
        ? `Linked Crop Recommendation Model suggests: ${result.crop_recommendation_from_ml}`
        : "Linked crop recommendation is unavailable for current inputs.";
    }

    const summary = document.getElementById("farmer-summary");
    if (summary)
      summary.textContent = result.summary || "No summary available.";

    renderNpkPanel(result.npk || {});
    renderList("advice-list", result.advice || []);
    renderList("plan-list", result.improvement_plan || []);
    renderCrops(result.suitable_crops || []);
    renderAlerts(result.alerts || []);
    renderCharts(result);
  }

  function classifyDriver(value, low, high) {
    if (!Number.isFinite(value)) return "Unknown";
    if (value < low) return "Low";
    if (value > high) return "High";
    return "Optimal";
  }

  function getDriverNote(rule, status) {
    if (status === "Low") return rule.lowText;
    if (status === "High") return rule.highText;
    if (status === "Optimal") return rule.optimalText;
    return "Enter a valid number to evaluate this factor.";
  }

  function renderDriverIntelligence() {
    const list = document.getElementById("driver-list");
    const overview = document.getElementById("driver-overview");
    if (!list || !overview) return;

    const entries = Object.entries(DRIVER_RULES).map(([key, rule]) => {
      const raw = Number(form[key]?.value);
      const status = classifyDriver(raw, rule.low, rule.high);
      return {
        label: rule.label,
        value: Number.isFinite(raw) ? raw : null,
        status,
        note: getDriverNote(rule, status),
      };
    });

    const evaluated = entries.filter((x) => x.status !== "Unknown");
    const riskCount = evaluated.filter((x) => x.status !== "Optimal").length;

    if (!evaluated.length) {
      overview.textContent =
        "Enter values to see live agronomic interpretation for N, P, K, pH, moisture, organic carbon, and conductivity.";
    } else if (riskCount === 0) {
      overview.textContent =
        "Current inputs indicate mostly balanced soil conditions. Continue monitoring and validate with periodic soil tests.";
    } else {
      overview.textContent = `${riskCount} factor(s) are outside optimal range. Corrective action on these can improve crop response and reduce risk.`;
    }

    list.innerHTML = entries
      .map(
        (entry) => `
          <article class="driver-item">
            <div class="driver-item-head">
              <span>${entry.label}</span>
              <span>${entry.value !== null ? formatNumber(entry.value, 2) : "--"} • ${entry.status}</span>
            </div>
            <p class="driver-item-note">${entry.note}</p>
          </article>
        `,
      )
      .join("");
  }

  async function analyzeSoil(event) {
    event.preventDefault();

    const payload = Object.fromEntries(new FormData(form).entries());
    Object.keys(payload).forEach((k) => {
      payload[k] = Number(payload[k]);
    });

    const submitBtn = form.querySelector("button[type='submit']");
    const oldText = submitBtn?.textContent || "Analyze Soil Health";
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.textContent = "Analyzing...";
    }

    try {
      const response = await fetch("/api/soil-health/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const data = await response.json();
      if (!response.ok || !data.ok) {
        throw new Error(data.error || "Soil analysis failed.");
      }

      renderResult(data.result);
    } catch (error) {
      const summary = document.getElementById("farmer-summary");
      if (summary) summary.textContent = `Analysis failed: ${error.message}`;
    } finally {
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.textContent = oldText;
      }
    }
  }

  form.addEventListener("submit", analyzeSoil);
  form.addEventListener("input", renderDriverIntelligence);
  form.addEventListener("change", renderDriverIntelligence);
  renderDriverIntelligence();
})();
