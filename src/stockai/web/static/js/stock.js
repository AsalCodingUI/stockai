const symbol = window.STOCK_SYMBOL || "";
let currentPeriod = "3mo";
let currentTujan = "swing";
let mainChart = null;
let areaSeries = null;
let latestScores = {};
let chartDataCache = null;
let activePriceLines = [];

function drawChartLines(indicatorsData, tradePlanData) {
    if (!areaSeries) return;
    
    // Clear old lines
    activePriceLines.forEach(line => {
        try {
            areaSeries.removePriceLine(line);
        } catch (e) {
            console.error("Error removing price line:", e);
        }
    });
    activePriceLines = [];
    
    const lineStyle = window.LightweightCharts ? window.LightweightCharts.LineStyle.Dashed : 2;
    
    // 1. Draw Support and Resistance from indicatorsData
    if (indicatorsData?.levels) {
        const support = Number(indicatorsData.levels.support);
        const resistance = Number(indicatorsData.levels.resistance);
        
        if (support > 0) {
            const line = areaSeries.createPriceLine({
                price: support,
                color: "#27272a", // zinc-800 subtle gray
                lineWidth: 1,
                lineStyle: lineStyle,
                axisLabelVisible: true,
                title: "Support",
            });
            activePriceLines.push(line);
        }
        if (resistance > 0) {
            const line = areaSeries.createPriceLine({
                price: resistance,
                color: "#27272a", // zinc-800 subtle gray
                lineWidth: 1,
                lineStyle: lineStyle,
                axisLabelVisible: true,
                title: "Resistance",
            });
            activePriceLines.push(line);
        }
    }
    
    // 2. Draw Trade Plan levels
    if (tradePlanData) {
        const entryLow = Number(tradePlanData.entry_low);
        const entryHigh = Number(tradePlanData.entry_high);
        const stopLoss = Number(tradePlanData.stop_loss);
        const tp1 = Number(tradePlanData.tp1);
        const tp2 = Number(tradePlanData.tp2);
        
        if (entryLow > 0) {
            const line = areaSeries.createPriceLine({
                price: entryLow,
                color: "#3b82f6", // blue-500
                lineWidth: 1.5,
                lineStyle: lineStyle,
                axisLabelVisible: true,
                title: entryHigh > entryLow ? "Entry Low" : "Entry",
            });
            activePriceLines.push(line);
        }
        
        if (entryHigh > entryLow) {
            const line = areaSeries.createPriceLine({
                price: entryHigh,
                color: "#3b82f6", // blue-500
                lineWidth: 1.5,
                lineStyle: lineStyle,
                axisLabelVisible: true,
                title: "Entry High",
            });
            activePriceLines.push(line);
        }
        
        if (stopLoss > 0) {
            const line = areaSeries.createPriceLine({
                price: stopLoss,
                color: "#ef4444", // red-500
                lineWidth: 1.5,
                lineStyle: lineStyle,
                axisLabelVisible: true,
                title: "Stop Loss (SL)",
            });
            activePriceLines.push(line);
        }
        
        if (tp1 > 0) {
            const line = areaSeries.createPriceLine({
                price: tp1,
                color: "#22c55e", // green-500
                lineWidth: 1.5,
                lineStyle: lineStyle,
                axisLabelVisible: true,
                title: "TP1",
            });
            activePriceLines.push(line);
        }
        
        if (tp2 > 0) {
            const line = areaSeries.createPriceLine({
                price: tp2,
                color: "#10b981", // emerald-500
                lineWidth: 1.5,
                lineStyle: lineStyle,
                axisLabelVisible: true,
                title: "TP2",
            });
            activePriceLines.push(line);
        }
    }
}

window.setTujuan = function(tujuan) {
    currentTujan = tujuan;
    
    // Update button active state classes
    const swingBtn = document.getElementById("btn-tujuan-swing");
    const scalpBtn = document.getElementById("btn-tujuan-scalp");
    
    if (swingBtn && scalpBtn) {
        if (tujuan === "swing") {
            swingBtn.classList.add("active");
            scalpBtn.classList.remove("active");
        } else {
            scalpBtn.classList.add("active");
            swingBtn.classList.remove("active");
        }
    }
    
    loadStockDetail();
};

window.updateParameters = function() {
    loadStockDetail();
};


function addAreaSeriesCompat(chart, options) {
    if (!chart) return null;
    if (typeof chart.addAreaSeries === "function") return chart.addAreaSeries(options);
    if (typeof chart.addSeries === "function" && window.LightweightCharts?.AreaSeries) {
        return chart.addSeries(window.LightweightCharts.AreaSeries, options);
    }
    return null;
}

function renderIndicatorSummary(summary, scores = null) {
    // Keep internal data for compatibility, but layout is simplified in template.
}

function renderGateRows(rows) {
    return (rows || [])
        .map((row) => `
            <div class="flex justify-between items-center text-[11px] text-zinc-400 font-mono py-1 border-b border-zinc-900/60">
                <span>${row.name}</span>
                <span class="${row.passed ? 'text-success' : 'text-zinc-500'} font-bold">${row.passed ? 'PASSED' : 'WATCH'}</span>
            </div>
        `)
        .join("");
}

function renderTradePlan(trade) {
    const plan = trade || {};
    const currentPrice = Number(window._currentPriceForTradePlan || 0);

    const fmt = (v) =>
        v != null && Number(v) !== 0
            ? `Rp ${Number(v).toLocaleString("id-ID")}`
            : '<span class="text-zinc-600">—</span>';

    const fmtRR = (v) =>
        v != null && Number(v) !== 0
            ? `<span class="${Number(v) >= 2 ? 'text-success' : Number(v) >= 1.5 ? 'text-warning' : 'text-error'} font-bold font-mono">${Number(v).toFixed(2)}x</span>`
            : '<span class="text-zinc-600">—</span>';

    const pctFromEntry = (target, entry) => {
        const t = Number(target);
        const e = Number(entry);
        if (!Number.isFinite(t) || !Number.isFinite(e) || e <= 0) return "";
        const pct = ((t - e) / e * 100).toFixed(1);
        const colorClass = Number(pct) >= 0 ? "text-success" : "text-error";
        return `<span class="${colorClass} text-[10px] ml-1.5 font-mono">(${Number(pct) > 0 ? "+" : ""}${pct}%)</span>`;
    };

    const entry = Number(plan.entry_low) > 0 ? Number(plan.entry_low) : currentPrice;
    const rows = [
        {
            label: '<i class="ph ph-sign-in mr-1.5 align-middle text-zinc-500"></i> Area Beli (Entry)',
            value: Number(plan.entry_low) > 0 && Number(plan.entry_high) > 0
                ? `${fmt(plan.entry_low)} – ${fmt(plan.entry_high)}`
                : fmt(entry),
            sub: "",
        },
        {
            label: '<i class="ph ph-x-circle mr-1.5 align-middle text-error"></i> Stop Loss',
            value: fmt(plan.stop_loss),
            sub: pctFromEntry(plan.stop_loss, entry),
        },
        {
            label: '<i class="ph ph-target mr-1.5 align-middle text-success"></i> Target 1 (TP1)',
            value: fmt(plan.tp1),
            sub: pctFromEntry(plan.tp1, entry),
        },
        {
            label: '<i class="ph ph-target mr-1.5 align-middle text-success"></i> Target 2 (TP2)',
            value: fmt(plan.tp2),
            sub: pctFromEntry(plan.tp2, entry),
        },
        {
            label: '<i class="ph ph-scales mr-1.5 align-middle text-zinc-500"></i> Risk/Reward',
            value: fmtRR(plan.rr),
            sub: "",
        },
    ];

    const rowsHtml = `
        <div class="grid md:grid-cols-2 gap-x-6 gap-y-1">
            ${rows.map((r) => `
                <div class="flex justify-between items-center py-2 border-b border-zinc-900/60">
                    <span class="text-zinc-400 text-xs">${r.label}</span>
                    <span class="text-zinc-100 text-xs font-semibold">
                        ${r.value}${r.sub || ""}
                    </span>
                </div>
            `).join("")}
        </div>
    `;

    const fallbackBadge = plan.is_fallback
        ? `<div class="mt-3 p-2 bg-warning/5 border border-warning/15 rounded-md text-[10px] text-warning flex items-center">
            <i class="ph ph-warning-octagon mr-1.5 text-xs"></i> 
            Plan dihitung otomatis berdasarkan Support & Resistance.
           </div>`
        : "";

    const riskCalc = `
        <div class="mt-4 pt-3 border-t border-zinc-900">
            <div class="text-[10px] text-muted mb-2 font-bold uppercase tracking-wider flex items-center">
                <i class="ph ph-calculator mr-1 text-xs"></i> Kalkulator Modal & Lot
            </div>
            <div class="flex gap-3">
                <input
                    id="modal-input"
                    type="number"
                    value="5000000"
                    placeholder="Masukkan modal (Rp)..."
                    class="px-3 py-1.5 bg-zinc-950 border border-zinc-800 rounded-md text-xs text-zinc-50 outline-none focus:border-zinc-500 transition-colors w-44"
                    oninput="calcRisk(this.value)"
                />
                <div id="risk-result" class="flex-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-400 items-center"></div>
            </div>
        </div>
    `;

    window._tradePlan = plan;
    window.calcRisk = function calcRisk(modalStr) {
        const modal = parseFloat(modalStr);
        if (!modal || modal <= 0) return;
        const p = window._tradePlan || {};
        const price = Number(window._currentPriceForTradePlan || 0);
        if (!price || price <= 0) return;

        const lots = Math.floor(modal / (price * 100));
        const shares = lots * 100;
        const totalCost = shares * price;
        const sl = Number(p.stop_loss) > 0 ? Number(p.stop_loss) : price * 0.97;
        const tp1 = Number(p.tp1) > 0 ? Number(p.tp1) : price;
        const riskPerShare = price - sl;
        const maxLoss = riskPerShare * shares;
        const potentialTP1 = shares * (tp1 - price);

        const riskRoot = document.getElementById("risk-result");
        if (!riskRoot) return;
        riskRoot.innerHTML = `
            <div>Lot: <span class="text-zinc-100 font-bold font-mono">${lots.toLocaleString("id-ID")} lot</span></div>
            <div>Modal Terpakai: <span class="text-zinc-200 font-bold font-mono">Rp ${totalCost.toLocaleString("id-ID")}</span></div>
            <div class="text-error">Risiko (SL): <span class="font-bold font-mono">-Rp ${maxLoss.toLocaleString("id-ID")}</span></div>
            <div class="text-success">Potensi Cuan (TP1): <span class="font-bold font-mono">+Rp ${potentialTP1.toLocaleString("id-ID")}</span></div>
        `;
    };

    setTimeout(() => calcRisk("5000000"), 50);

    window._tradePlan = plan;
    drawChartLines(chartDataCache, plan);
    return rowsHtml + fallbackBadge + riskCalc;
}

async function initAdvancedChart(period = "3mo") {
    const mainContainer = document.getElementById("main-chart");
    if (!mainContainer) return;
    if (typeof LightweightCharts === "undefined") {
        mainContainer.innerHTML = '<div class="text-muted" style="padding:120px;text-align:center">Chart library unavailable</div>';
        return;
    }

    currentPeriod = period;
    const data = await window.fetchWithTimeout(`/api/stock/${symbol}/indicators?period=${encodeURIComponent(period)}`, 35000);
    if (!data || data.error || !data.candles?.length) {
        mainContainer.innerHTML = '<div class="text-muted" style="padding:120px;text-align:center">Chart data unavailable</div>';
        return;
    }

    mainContainer.innerHTML = "";

    mainChart = LightweightCharts.createChart(mainContainer, {
        width: mainContainer.clientWidth,
        height: 280,
        layout: { background: { color: "#09090b" }, textColor: "#a1a1aa" },
        grid: { vertLines: { color: "#27272a" }, horzLines: { color: "#27272a" } },
        timeScale: { borderColor: "#27272a", timeVisible: true },
        rightPriceScale: {
            borderColor: "#27272a",
            scaleMargins: { top: 0.08, bottom: 0.08 },
        },
    });

    areaSeries = addAreaSeriesCompat(mainChart, {
        lineColor: "#fafafa",
        topColor: "rgba(250, 250, 250, 0.15)",
        bottomColor: "rgba(250, 250, 250, 0.0)",
        lineWidth: 2,
        title: symbol,
    });

    if (!areaSeries) {
        mainContainer.innerHTML = '<div class="text-muted" style="padding:120px;text-align:center">Chart API unsupported</div>';
        return;
    }

    const areaData = (data.candles || []).map(c => ({
        time: c.time,
        value: c.close
    }));
    areaSeries.setData(areaData);
    mainChart.timeScale().fitContent();

    chartDataCache = data;
    drawChartLines(chartDataCache, window._tradePlan);

    window.addEventListener("resize", () => {
        if (mainChart && mainContainer.clientWidth > 0) {
            mainChart.applyOptions({ width: mainContainer.clientWidth });
        }
    });
}

function renderMLForecast(forecast, patterns) {
    const root = document.getElementById("ml-forecast");
    if (!root) return;
    if (!forecast) {
        root.innerHTML = '<span class="text-zinc-500">Data tidak tersedia</span>';
        return;
    }

    const confColor = { HIGH: "text-success", MEDIUM: "text-warning", LOW: "text-error" };
    const p5 = ((Number(forecast.probability_5pct) || 0) * 100).toFixed(0);
    const expected = ((Number(forecast.expected_return) || 0) * 100).toFixed(1);
    const conf = forecast.confidence || "LOW";

    root.innerHTML = `
        <div class="grid grid-cols-2 gap-3 mb-3">
            <div class="bg-zinc-950 border border-zinc-800 rounded-md p-3 text-center">
                <div class="text-[10px] text-muted mb-1 font-mono">Prob. Naik 5%</div>
                <div class="text-xl font-bold font-mono ${Number(p5) >= 60 ? 'text-success' : Number(p5) >= 40 ? 'text-warning' : 'text-error'}">${p5}%</div>
            </div>
            <div class="bg-zinc-950 border border-zinc-800 rounded-md p-3 text-center">
                <div class="text-[10px] text-muted mb-1 font-mono">Expected Return</div>
                <div class="text-xl font-bold font-mono ${Number(expected) >= 0 ? 'text-success' : 'text-error'}">${Number(expected) > 0 ? "+" : ""}${expected}%</div>
            </div>
        </div>
        <div class="flex justify-between items-center bg-zinc-950 border border-zinc-800 p-2.5 rounded-md text-xs font-mono">
            <span class="text-muted">Akurasi Prediksi</span>
            <span class="font-extrabold ${confColor[conf] || "text-muted"}">${conf}</span>
        </div>
    `;
}

async function loadScoring() {
    const minTp = document.getElementById("input-min-tp")?.value || "";
    const minCl = document.getElementById("input-min-cl")?.value || "";
    
    let url = `/api/stock/${symbol}/scoring?tujuan=${encodeURIComponent(currentTujan)}`;
    if (minTp) url += `&min_tp=${encodeURIComponent(minTp)}`;
    if (minCl) url += `&min_cl=${encodeURIComponent(minCl)}`;

    const data = await window.fetchWithTimeout(url, 15000);
    if (!data) {
        document.getElementById("gate-status").innerHTML = '<div class="text-muted">Scoring unavailable</div>';
        return;
    }
    const confidence = String(data.gates?.confidence || "REJECTED").toUpperCase();
    let gateBadgeClass = "gate-badge gate-badge-reject";

    if (confidence === "HIGH") gateBadgeClass = "gate-badge gate-badge-pass";
    else if (confidence === "WATCH") gateBadgeClass = "gate-badge gate-badge-watch";

    const gateTotal = data.gates?.total || 6;
    const gatePassed = data.gates?.passed || 0;

    document.getElementById("gate-status").innerHTML = `
        <div class="${gateBadgeClass}">${confidence}</div>
        <div class="text-xs font-mono text-zinc-400 mt-2">Passed: ${gatePassed}/${gateTotal} Gates</div>
        <div class="text-xs font-mono text-muted mt-0.5">Composite Score: ${Number(data.scores?.composite_score || 0).toFixed(1)}</div>
    `;
    latestScores = data.scores || latestScores;
    document.getElementById("trade-plan").innerHTML = renderTradePlan(data.trade_plan || {});
}

function renderFull(data) {
    const latest = data.latest || {};
    const sentiment = data.sentiment || {};
    const forecast = data.forecast || {};
    window._currentPriceForTradePlan = Number(latest.price) || 0;
    latestScores = data.analysis || latestScores;

    const priceText = window.toRupiah(latest.price || 0);
    const volText = `${Math.round((latest.volume || 0) / 1000000)}M`;
    document.getElementById("last-price-display").textContent = priceText;

    const gateRows = (data.analysis || {}).gate_status || [];
    const gateSummary = (data.analysis || {}).gates || {};
    if (gateRows.length) {
        const confidence = String(gateSummary.confidence || "REJECTED").toUpperCase();
        let gateBadgeClass = "gate-badge gate-badge-reject";
        if (confidence === "HIGH") gateBadgeClass = "gate-badge gate-badge-pass";
        else if (confidence === "WATCH") gateBadgeClass = "gate-badge gate-badge-watch";

        const summaryHtml = `
            <div class="${gateBadgeClass}">${confidence}</div>
            <div class="flex justify-between items-center text-xs font-mono py-1.5 border-b border-zinc-900 mt-2 text-zinc-400">
                <span>Gate Score</span>
                <span class="font-bold text-zinc-200">${gateSummary.passed || 0}/${gateSummary.total || 6}</span>
            </div>
            <div class="flex justify-between items-center text-xs font-mono py-1.5 border-b border-zinc-900 text-zinc-400">
                <span>Composite Score</span>
                <span class="font-bold text-zinc-200">${Number((data.analysis || {}).composite_score || 0).toFixed(1)}</span>
            </div>
        `;
        document.getElementById("gate-status").innerHTML = summaryHtml + `<div class="mt-3">${renderGateRows(gateRows)}</div>`;
    }

    const tradePlan = (data.analysis || {}).trade_plan || {};
    document.getElementById("trade-plan").innerHTML = renderTradePlan(tradePlan);
    renderMLForecast(forecast, data.patterns || []);

    const patterns = data.patterns || [];
    document.getElementById("pattern-panel").innerHTML = patterns.length
        ? `<div class="space-y-1">
            ${patterns.slice(0, 3).map((p) => `<div class="text-xs text-zinc-300 flex justify-between"><span>${String(p.name || "").replaceAll("_", " ")}</span><span class="text-muted">${p.strength || "MEDIUM"}</span></div>`).join("")}
           </div>`
        : '<span class="text-zinc-500 text-xs">Tidak ada pola candlestick terdeteksi</span>';

    const news = data.news || [];
    let sentimentColorClass = "text-zinc-400";
    if (sentiment.sentiment === "BULLISH") sentimentColorClass = "text-success font-bold";
    else if (sentiment.sentiment === "BEARISH") sentimentColorClass = "text-error font-bold";

    document.getElementById("sentiment-news").innerHTML = `
        <div class="text-xs text-zinc-300 font-mono mb-4 border-b border-zinc-900 pb-3 flex justify-between">
            <span>Sentimen Konsensus: <span class="${sentimentColorClass}">${sentiment.sentiment || "NEUTRAL"}</span></span>
            <span class="text-muted">Skor: ${sentiment.score || 0}</span>
        </div>
        <div class="space-y-2.5">
            ${news.slice(0, 6).map((n) => `
                <div class="text-xs">
                    <a class="text-zinc-200 hover:text-white hover:underline font-semibold leading-relaxed flex items-start" href="${n.url || "#"}" target="_blank">
                        <i class="ph ph-newspaper text-sm mr-2 mt-0.5 text-muted"></i> ${n.title}
                    </a>
                </div>
            `).join("")}
        </div>
    `;
}

async function loadStockDetail() {
    const mainContainer = document.getElementById("main-chart");
    if (mainContainer) mainContainer.innerHTML = '<div class="skeleton"></div>';
    
    // Parallelize loading to prevent sequential blocking
    loadScoring().catch(console.error);
    initAdvancedChart(currentPeriod).catch(console.error);

    const minTp = document.getElementById("input-min-tp")?.value || "";
    const minCl = document.getElementById("input-min-cl")?.value || "";
    
    let url = `/api/stock/${symbol}/full?tujuan=${encodeURIComponent(currentTujan)}`;
    if (minTp) url += `&min_tp=${encodeURIComponent(minTp)}`;
    if (minCl) url += `&min_cl=${encodeURIComponent(minCl)}`;

    window.fetchWithTimeout(url, 25000).then((data) => {
        if (!data) {
            document.getElementById("ml-forecast").innerHTML = '<div class="text-muted">Analysis unavailable</div>';
            return;
        }
        renderFull(data);
        initAdvancedChart(currentPeriod).catch(() => {});
    });
}

function activateTfButton(period) {
    document.querySelectorAll(".tf-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.period === period);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    activateTfButton(currentPeriod);
    loadStockDetail().catch(console.error);

    document.querySelectorAll(".tf-btn").forEach((btn) => {
        btn.addEventListener("click", async () => {
            const period = btn.dataset.period || "3mo";
            currentPeriod = period;
            activateTfButton(period);
            await initAdvancedChart(period);
        });
    });
});
