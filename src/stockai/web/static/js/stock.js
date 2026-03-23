const symbol = window.STOCK_SYMBOL;
let mainChart = null;
let volumeChart = null;
let macdChart = null;
let currentPeriod = "3mo";
const MAIN_CHART_HEIGHT = 560;
const SUB_CHART_HEIGHT = 140;
window.tradePlan = null;
let chartDataCache = null;
let latestScores = null;
const seriesRefs = {};
const toggleState = {
    ema: true,
    ma: true,
    bb: true,
    levels: true,
    tradePlan: true,
    volumePane: true,
    volMa: true,
    volumeSpikes: true,
    macdPane: true,
};

function destroyCharts() {
    if (mainChart) {
        mainChart.remove();
        mainChart = null;
    }
    if (volumeChart) {
        volumeChart.remove();
        volumeChart = null;
    }
    if (macdChart) {
        macdChart.remove();
        macdChart = null;
    }
}

function addCandleSeriesCompat(chart, options) {
    if (!chart) return null;
    if (typeof chart.addCandlestickSeries === "function") {
        return chart.addCandlestickSeries(options);
    }
    if (typeof chart.addSeries === "function" && window.LightweightCharts?.CandlestickSeries) {
        return chart.addSeries(window.LightweightCharts.CandlestickSeries, options);
    }
    return null;
}

function addLineSeriesCompat(chart, options) {
    if (!chart) return null;
    if (typeof chart.addLineSeries === "function") {
        return chart.addLineSeries(options);
    }
    if (typeof chart.addSeries === "function" && window.LightweightCharts?.LineSeries) {
        return chart.addSeries(window.LightweightCharts.LineSeries, options);
    }
    return null;
}

function addHistogramSeriesCompat(chart, options = {}) {
    if (!chart) return null;
    if (typeof chart.addHistogramSeries === "function") {
        return chart.addHistogramSeries(options);
    }
    if (typeof chart.addSeries === "function" && window.LightweightCharts?.HistogramSeries) {
        return chart.addSeries(window.LightweightCharts.HistogramSeries, options);
    }
    return null;
}

function renderIndicatorSummary(summary, scores = null) {
    const container = document.getElementById("indicator-summary");
    if (!container || !summary) return;

    const rsiColor = summary.rsi > 70 ? "#ff3b5c" : summary.rsi < 30 ? "#00ff88" : "#ff9500";
    const macdColor = summary.macd_signal === "BULLISH" ? "#00ff88" : "#ff3b5c";
    const emaColor = summary.ema_signal === "BULLISH" ? "#00ff88" : "#ff3b5c";
    const trendColor = summary.trend === "BULLISH" ? "#00ff88" : "#ff3b5c";

    const scoreBar = (label, value, color) => {
        const safeValue = Number.isFinite(Number(value)) ? Number(value) : 0;
        const pct = Math.min(100, Math.max(0, safeValue));
        return `
            <div style="margin-bottom:8px;">
                <div style="display:flex;justify-content:space-between;margin-bottom:2px;">
                    <span style="font-size:11px;color:#94a3b8;">${label}</span>
                    <span style="font-size:11px;font-weight:600;color:${color};">${pct.toFixed(0)}</span>
                </div>
                <div style="background:#0f172a;border-radius:4px;height:4px;">
                    <div style="
                        width:${pct}%;height:100%;
                        background:${color};border-radius:4px;
                        transition:width 0.5s;
                    "></div>
                </div>
            </div>
        `;
    };

    const scoresHtml = scores ? `
        <div style="margin-top:12px;padding-top:12px;border-top:1px solid #1e293b;">
            <div style="font-size:11px;color:#64748b;margin-bottom:8px;">📊 COMPOSITE SCORES</div>
            ${scoreBar("Value", scores.value_score, "#3b82f6")}
            ${scoreBar("Quality", scores.quality_score, "#8b5cf6")}
            ${scoreBar("Momentum", scores.momentum_score, "#00ff88")}
            ${scoreBar("Stability", 100 - (Number(scores.volatility_score) || 0), "#fbbf24")}
            <div style="
                margin-top:8px;padding:8px;
                background:#0f172a;border-radius:6px;
                display:flex;justify-content:space-between;align-items:center;
            ">
                <span style="font-size:12px;color:#94a3b8;">Composite Score</span>
                <span style="
                    font-size:18px;font-weight:700;
                    color:${Number(scores.composite_score) >= 65 ? "#00ff88" : Number(scores.composite_score) >= 50 ? "#fbbf24" : "#ff3b5c"};
                ">${Number(scores.composite_score || 0).toFixed(1)}</span>
            </div>
        </div>
    ` : "";

    container.innerHTML = `
        <div class="indicator-item">
            <span class="label">RSI 14</span>
            <span style="color:${rsiColor}">${summary.rsi} ${summary.rsi_signal}</span>
        </div>
        <div class="indicator-item">
            <span class="label">MACD</span>
            <span style="color:${macdColor}">${summary.macd_signal} ${summary.macd_cross === "GOLDEN" ? "✓" : "✗"}</span>
        </div>
        <div class="indicator-item">
            <span class="label">EMA 8/21</span>
            <span style="color:${emaColor}">${summary.ema_signal}</span>
        </div>
        <div class="indicator-item">
            <span class="label">MA Signal</span>
            <span>${summary.ma_signal}</span>
        </div>
        <div class="indicator-item">
            <span class="label">MA200</span>
            <span>${summary.ma200_signal || "N/A"}</span>
        </div>
        <div class="indicator-item">
            <span class="label">Bollinger</span>
            <span>${summary.bb_position}</span>
        </div>
        <div class="indicator-item">
            <span class="label">Avg Vol</span>
            <span>${Math.round(summary.avg_volume || 0).toLocaleString("id-ID")}</span>
        </div>
        <div class="indicator-item" style="border-bottom:none;">
            <span class="label">Trend</span>
            <span style="color:${trendColor};font-weight:700;">${summary.trend}</span>
        </div>
        ${scoresHtml}
    `;
}

function renderIndicatorToggles() {
    const root = document.getElementById("indicator-toggles");
    if (!root) return;
    const items = [
        ["ema", "EMA 8/21"],
        ["ma", "MA 50/200"],
        ["bb", "Bollinger"],
        ["levels", "Support/Resistance"],
        ["tradePlan", "SL/TP"],
        ["volumePane", "Volume Pane"],
        ["volMa", "Vol MA20"],
        ["volumeSpikes", "Volume Spike Glow"],
        ["macdPane", "MACD Pane"],
    ];
    root.innerHTML = items.map(([key, label]) => `
        <label class="indicator-toggle">
            <input type="checkbox" data-toggle="${key}" ${toggleState[key] ? "checked" : ""} />
            <span>${label}</span>
        </label>
    `).join("");

    root.querySelectorAll("input[data-toggle]").forEach((input) => {
        input.addEventListener("change", () => {
            toggleState[input.dataset.toggle] = input.checked;
            applyIndicatorToggles();
        });
    });
}

function setSeriesVisible(series, visible, data) {
    if (!series) return;
    series.setData(visible ? (data || []) : []);
}

function volumeDataWithToggle() {
    const raw = chartDataCache?.indicators?.volume || [];
    return raw.map((v) => ({
        time: v.time,
        value: v.value,
        color: (toggleState.volumeSpikes && v.spike)
            ? (String(v.color).includes("00ff") ? "#00ff88" : "#ff3b5c")
            : v.color,
    }));
}

function applyIndicatorToggles() {
    if (!chartDataCache) return;

    setSeriesVisible(seriesRefs.ema8, toggleState.ema, chartDataCache.indicators?.ema8);
    setSeriesVisible(seriesRefs.ema21, toggleState.ema, chartDataCache.indicators?.ema21);
    setSeriesVisible(seriesRefs.ma50, toggleState.ma, chartDataCache.indicators?.ma50);
    setSeriesVisible(seriesRefs.ma200, toggleState.ma, chartDataCache.indicators?.ma200);
    setSeriesVisible(seriesRefs.bbUpper, toggleState.bb, chartDataCache.indicators?.bb_upper);
    setSeriesVisible(seriesRefs.bbMid, toggleState.bb, chartDataCache.indicators?.bb_mid);
    setSeriesVisible(seriesRefs.bbLower, toggleState.bb, chartDataCache.indicators?.bb_lower);

    setSeriesVisible(
        seriesRefs.supportLine,
        toggleState.levels,
        (chartDataCache.candles || []).map((c) => ({ time: c.time, value: chartDataCache.levels?.support })),
    );
    setSeriesVisible(
        seriesRefs.resistanceLine,
        toggleState.levels,
        (chartDataCache.candles || []).map((c) => ({ time: c.time, value: chartDataCache.levels?.resistance })),
    );

    if (toggleState.tradePlan) {
        setHorizontalLine(seriesRefs.slLine, chartDataCache.candles || [], window.tradePlan?.stop_loss);
        setHorizontalLine(seriesRefs.tp1Line, chartDataCache.candles || [], window.tradePlan?.tp1);
        setHorizontalLine(seriesRefs.tp2Line, chartDataCache.candles || [], window.tradePlan?.tp2);
        setHorizontalLine(seriesRefs.tp3Line, chartDataCache.candles || [], window.tradePlan?.tp3);
    } else {
        setSeriesVisible(seriesRefs.slLine, false, []);
        setSeriesVisible(seriesRefs.tp1Line, false, []);
        setSeriesVisible(seriesRefs.tp2Line, false, []);
        setSeriesVisible(seriesRefs.tp3Line, false, []);
    }

    setSeriesVisible(seriesRefs.volSeries, toggleState.volumePane, volumeDataWithToggle());
    setSeriesVisible(seriesRefs.volMaSeries, toggleState.volumePane && toggleState.volMa, chartDataCache.indicators?.vol_ma20);
    setSeriesVisible(seriesRefs.macdHist, toggleState.macdPane, chartDataCache.indicators?.macd_hist);
    setSeriesVisible(seriesRefs.macdLine, toggleState.macdPane, chartDataCache.indicators?.macd_line);
    setSeriesVisible(seriesRefs.signalLine, toggleState.macdPane, chartDataCache.indicators?.signal_line);
    setSeriesVisible(
        seriesRefs.zeroLine,
        toggleState.macdPane,
        (chartDataCache.indicators?.macd_line || []).map((d) => ({ time: d.time, value: 0 })),
    );

    const volContainer = document.getElementById("volume-chart");
    const macdContainer = document.getElementById("macd-chart");
    if (volContainer) volContainer.style.display = toggleState.volumePane ? "block" : "none";
    if (macdContainer) macdContainer.style.display = toggleState.macdPane ? "block" : "none";
}

function setHorizontalLine(series, candles, value) {
    if (!series) return;
    if (!candles?.length || !isValidPriceLevel(value, candles)) {
        series.setData([]);
        return;
    }
    const line = candles.map((c) => ({ time: c.time, value: Number(value) }));
    series.setData(line);
}

function isValidPriceLevel(value, candles) {
    if (value == null) return false;
    const n = Number(value);
    if (!Number.isFinite(n) || n <= 0) return false;
    if (!candles?.length) return true;
    const prices = candles.flatMap((c) => [Number(c.high), Number(c.low)]).filter((x) => Number.isFinite(x) && x > 0);
    if (!prices.length) return true;
    const minPrice = Math.min(...prices);
    const maxPrice = Math.max(...prices);
    // Ignore levels that are too far from visible price range (prevents flattening).
    return n >= minPrice * 0.6 && n <= maxPrice * 1.4;
}

async function initAdvancedChart(period = "3mo") {
    const mainContainer = document.getElementById("main-chart");
    const volContainer = document.getElementById("volume-chart");
    const macdContainer = document.getElementById("macd-chart");
    if (!mainContainer || !volContainer || !macdContainer) return;
    if (typeof LightweightCharts === "undefined") {
        mainContainer.innerHTML = '<div class="text-muted" style="padding:120px;text-align:center">Chart library unavailable</div>';
        return;
    }

    currentPeriod = period;
    const data = await window.fetchWithTimeout(`/api/stock/${symbol}/indicators?period=${encodeURIComponent(period)}`, 35000);
    if (!data || data.error) {
        await renderBasicFallbackChart(period);
        return;
    }

    destroyCharts();
    mainContainer.innerHTML = "";
    volContainer.innerHTML = "";
    macdContainer.innerHTML = "";

    mainChart = LightweightCharts.createChart(mainContainer, {
        width: mainContainer.clientWidth,
        height: MAIN_CHART_HEIGHT,
        layout: { background: { color: "#111118" }, textColor: "#94a3b8" },
        grid: { vertLines: { color: "#1e1e2e" }, horzLines: { color: "#1e1e2e" } },
        timeScale: { borderColor: "#1e1e2e", timeVisible: true },
        rightPriceScale: {
            borderColor: "#1e1e2e",
            scaleMargins: { top: 0.08, bottom: 0.08 },
        },
    });

    const candleSeries = addCandleSeriesCompat(mainChart, {
        upColor: "#00ff88",
        downColor: "#ff3b5c",
        borderUpColor: "#00ff88",
        borderDownColor: "#ff3b5c",
        wickUpColor: "#00ff88",
        wickDownColor: "#ff3b5c",
    });
    if (!candleSeries) {
        mainContainer.innerHTML = '<div class="text-muted" style="padding:120px;text-align:center">Chart API unsupported</div>';
        return;
    }
    candleSeries.setData(data.candles || []);
    chartDataCache = data;
    seriesRefs.candleSeries = candleSeries;

    seriesRefs.ema8 = addLineSeriesCompat(mainChart, { color: "#00d4ff", lineWidth: 1, title: "EMA8" });
    seriesRefs.ema21 = addLineSeriesCompat(mainChart, { color: "#ff9500", lineWidth: 1, title: "EMA21" });
    seriesRefs.ma50 = addLineSeriesCompat(mainChart, { color: "#ffd60a", lineWidth: 1, lineStyle: 2, title: "MA50" });
    seriesRefs.ma200 = addLineSeriesCompat(mainChart, { color: "#bf5af2", lineWidth: 1, lineStyle: 2, title: "MA200" });
    seriesRefs.bbUpper = addLineSeriesCompat(mainChart, { color: "#64748b", lineWidth: 1, lineStyle: 3, title: "BB Upper" });
    seriesRefs.bbMid = addLineSeriesCompat(mainChart, { color: "#64748b", lineWidth: 1, lineStyle: 3, title: "BB Mid" });
    seriesRefs.bbLower = addLineSeriesCompat(mainChart, { color: "#64748b", lineWidth: 1, lineStyle: 3, title: "BB Lower" });

    if (seriesRefs.ema8) seriesRefs.ema8.setData(data.indicators?.ema8 || []);
    if (seriesRefs.ema21) seriesRefs.ema21.setData(data.indicators?.ema21 || []);
    if (seriesRefs.ma50) seriesRefs.ma50.setData(data.indicators?.ma50 || []);
    if (seriesRefs.ma200) seriesRefs.ma200.setData(data.indicators?.ma200 || []);
    if (seriesRefs.bbUpper) seriesRefs.bbUpper.setData(data.indicators?.bb_upper || []);
    if (seriesRefs.bbMid) seriesRefs.bbMid.setData(data.indicators?.bb_mid || []);
    if (seriesRefs.bbLower) seriesRefs.bbLower.setData(data.indicators?.bb_lower || []);

    seriesRefs.supportLine = addLineSeriesCompat(mainChart, { color: "#00ff8866", lineWidth: 1, lineStyle: 1, title: "Support" });
    seriesRefs.resistanceLine = addLineSeriesCompat(mainChart, { color: "#ff3b5c66", lineWidth: 1, lineStyle: 1, title: "Resistance" });
    setHorizontalLine(seriesRefs.supportLine, data.candles, data.levels?.support);
    setHorizontalLine(seriesRefs.resistanceLine, data.candles, data.levels?.resistance);

    seriesRefs.slLine = null;
    seriesRefs.tp1Line = null;
    seriesRefs.tp2Line = null;
    seriesRefs.tp3Line = null;
    if (window.tradePlan && data.candles?.length) {
        seriesRefs.slLine = addLineSeriesCompat(mainChart, { color: "#ff3b5c", lineWidth: 2, lineStyle: 0, title: "SL" });
        seriesRefs.tp1Line = addLineSeriesCompat(mainChart, { color: "#00ff8899", lineWidth: 1, lineStyle: 2, title: "TP1" });
        seriesRefs.tp2Line = addLineSeriesCompat(mainChart, { color: "#00ff88cc", lineWidth: 1, lineStyle: 2, title: "TP2" });
        seriesRefs.tp3Line = addLineSeriesCompat(mainChart, { color: "#00d4ff99", lineWidth: 1, lineStyle: 2, title: "TP3" });
        setHorizontalLine(seriesRefs.slLine, data.candles, window.tradePlan.stop_loss);
        setHorizontalLine(seriesRefs.tp1Line, data.candles, window.tradePlan.tp1);
        setHorizontalLine(seriesRefs.tp2Line, data.candles, window.tradePlan.tp2);
        setHorizontalLine(seriesRefs.tp3Line, data.candles, window.tradePlan.tp3);
    }
    mainChart.timeScale().fitContent();

    volumeChart = LightweightCharts.createChart(volContainer, {
        width: volContainer.clientWidth,
        height: SUB_CHART_HEIGHT,
        layout: { background: { color: "#111118" }, textColor: "#94a3b8" },
        grid: { vertLines: { color: "#1e1e2e" }, horzLines: { color: "#1e1e2e" } },
        timeScale: { borderColor: "#1e1e2e", timeVisible: false },
        rightPriceScale: { borderColor: "#1e1e2e" },
    });
    seriesRefs.volSeries = addHistogramSeriesCompat(volumeChart, { priceFormat: { type: "volume" } });
    seriesRefs.volMaSeries = addLineSeriesCompat(volumeChart, { color: "#ffffff66", lineWidth: 1, title: "Vol MA20" });
    if (seriesRefs.volSeries) {
        seriesRefs.volSeries.setData((data.indicators?.volume || []).map((v) => ({
            time: v.time,
            value: v.value,
            color: v.spike ? (String(v.color).includes("00ff") ? "#00ff88" : "#ff3b5c") : v.color,
        })));
    }
    if (seriesRefs.volMaSeries) seriesRefs.volMaSeries.setData(data.indicators?.vol_ma20 || []);
    volumeChart.timeScale().fitContent();

    macdChart = LightweightCharts.createChart(macdContainer, {
        width: macdContainer.clientWidth,
        height: SUB_CHART_HEIGHT,
        layout: { background: { color: "#111118" }, textColor: "#94a3b8" },
        grid: { vertLines: { color: "#1e1e2e" }, horzLines: { color: "#1e1e2e" } },
        timeScale: { borderColor: "#1e1e2e", timeVisible: true },
        rightPriceScale: { borderColor: "#1e1e2e" },
    });
    seriesRefs.macdHist = addHistogramSeriesCompat(macdChart);
    seriesRefs.macdLine = addLineSeriesCompat(macdChart, { color: "#00d4ff", lineWidth: 1, title: "MACD" });
    seriesRefs.signalLine = addLineSeriesCompat(macdChart, { color: "#ff9500", lineWidth: 1, title: "Signal" });
    seriesRefs.zeroLine = addLineSeriesCompat(macdChart, { color: "#64748b66", lineWidth: 1, lineStyle: 1, title: "Zero" });

    if (seriesRefs.macdHist) seriesRefs.macdHist.setData(data.indicators?.macd_hist || []);
    if (seriesRefs.macdLine) seriesRefs.macdLine.setData(data.indicators?.macd_line || []);
    if (seriesRefs.signalLine) seriesRefs.signalLine.setData(data.indicators?.signal_line || []);
    if (seriesRefs.zeroLine && data.indicators?.macd_line) {
        seriesRefs.zeroLine.setData(data.indicators.macd_line.map((d) => ({ time: d.time, value: 0 })));
    }
    macdChart.timeScale().fitContent();

    if (mainChart?.timeScale && volumeChart?.timeScale && macdChart?.timeScale) {
        mainChart.timeScale().subscribeVisibleLogicalRangeChange((range) => {
            if (!range) return;
            volumeChart.timeScale().setVisibleLogicalRange(range);
            macdChart.timeScale().setVisibleLogicalRange(range);
        });
    }

    window.requestAnimationFrame(() => {
        if (mainChart) mainChart.applyOptions({ width: mainContainer.clientWidth });
        if (volumeChart) volumeChart.applyOptions({ width: volContainer.clientWidth });
        if (macdChart) macdChart.applyOptions({ width: macdContainer.clientWidth });
    });

    renderIndicatorSummary(data.summary || {}, latestScores);
    applyIndicatorToggles();
}

async function renderBasicFallbackChart(period = "3mo") {
    const mainContainer = document.getElementById("main-chart");
    const volContainer = document.getElementById("volume-chart");
    const macdContainer = document.getElementById("macd-chart");
    if (!mainContainer || typeof LightweightCharts === "undefined") {
        if (mainContainer) mainContainer.innerHTML = '<div class="text-muted" style="padding:120px;text-align:center">Chart unavailable</div>';
        return;
    }

    const basic = await window.fetchWithTimeout(`/api/stock/${symbol}/chart?period=${encodeURIComponent(period)}`, 20000);
    const summaryRoot = document.getElementById("indicator-summary");
    if (!basic || !basic.candles?.length) {
        mainContainer.innerHTML = '<div class="text-muted" style="padding:120px;text-align:center">Chart unavailable</div>';
        if (volContainer) volContainer.innerHTML = "";
        if (macdContainer) macdContainer.innerHTML = "";
        if (summaryRoot) summaryRoot.innerHTML = '<div class="text-muted">Indicator data unavailable</div>';
        return;
    }

    destroyCharts();
    mainContainer.innerHTML = "";
    if (volContainer) volContainer.style.display = "none";
    if (macdContainer) macdContainer.style.display = "none";

    mainChart = LightweightCharts.createChart(mainContainer, {
        width: mainContainer.clientWidth,
        height: MAIN_CHART_HEIGHT,
        layout: { background: { color: "#111118" }, textColor: "#94a3b8" },
        grid: { vertLines: { color: "#1e1e2e" }, horzLines: { color: "#1e1e2e" } },
        timeScale: { borderColor: "#1e1e2e", timeVisible: true },
        rightPriceScale: { borderColor: "#1e1e2e" },
    });

    const candleSeries = addCandleSeriesCompat(mainChart, {
        upColor: "#00ff88",
        downColor: "#ff3b5c",
        borderUpColor: "#00ff88",
        borderDownColor: "#ff3b5c",
        wickUpColor: "#00ff88",
        wickDownColor: "#ff3b5c",
    });
    if (candleSeries) candleSeries.setData(basic.candles);

    const ma50 = addLineSeriesCompat(mainChart, { color: "#ffd60a", lineWidth: 1, lineStyle: 2, title: "MA50" });
    const ma200 = addLineSeriesCompat(mainChart, { color: "#bf5af2", lineWidth: 1, lineStyle: 2, title: "MA200" });
    if (ma50) ma50.setData(basic.ma50 || []);
    if (ma200) ma200.setData(basic.ma200 || []);
    mainChart.timeScale().fitContent();
    if (summaryRoot) summaryRoot.innerHTML = '<div class="text-muted">Advanced indicators unavailable, showing basic chart.</div>';
}

function renderGateRows(rows) {
    return (rows || [])
        .map((row) => `<div class="text-sm">${row.passed ? "OK" : "X"} ${row.name} ${row.value}/${row.threshold}</div>`)
        .join("");
}

function renderTradePlan(trade) {
    const plan = trade || {};
    const currentPrice = Number(window._currentPriceForTradePlan || 0);

    const fmt = (v) =>
        v != null && Number(v) !== 0
            ? `Rp ${Number(v).toLocaleString("id-ID")}`
            : '<span style="color:#475569">—</span>';

    const fmtRR = (v) =>
        v != null && Number(v) !== 0
            ? `<span style="color:${Number(v) >= 2 ? "#00ff88" : Number(v) >= 1.5 ? "#fbbf24" : "#ff3b5c"}">${Number(v).toFixed(2)}x</span>`
            : '<span style="color:#475569">—</span>';

    const pctFromEntry = (target, entry) => {
        const t = Number(target);
        const e = Number(entry);
        if (!Number.isFinite(t) || !Number.isFinite(e) || e <= 0) return "";
        const pct = ((t - e) / e * 100).toFixed(1);
        const color = Number(pct) >= 0 ? "#00ff88" : "#ff3b5c";
        return `<span style="color:${color};font-size:11px;margin-left:4px">${Number(pct) > 0 ? "+" : ""}${pct}%</span>`;
    };

    const entry = Number(plan.entry_low) > 0 ? Number(plan.entry_low) : currentPrice;
    const rows = [
        {
            label: "📥 Entry Zone",
            value: Number(plan.entry_low) > 0 && Number(plan.entry_high) > 0
                ? `${fmt(plan.entry_low)} – ${fmt(plan.entry_high)}`
                : fmt(entry),
            sub: "",
        },
        {
            label: "🛑 Stop Loss",
            value: fmt(plan.stop_loss),
            sub: pctFromEntry(plan.stop_loss, entry),
        },
        {
            label: "🎯 TP1",
            value: fmt(plan.tp1),
            sub: pctFromEntry(plan.tp1, entry),
        },
        {
            label: "🎯 TP2",
            value: fmt(plan.tp2),
            sub: pctFromEntry(plan.tp2, entry),
        },
        {
            label: "🎯 TP3",
            value: fmt(plan.tp3),
            sub: pctFromEntry(plan.tp3, entry),
        },
        {
            label: "⚖️ Risk/Reward",
            value: fmtRR(plan.rr),
            sub: "",
        },
    ];

    const rowsHtml = rows.map((r) => `
        <div style="
            display:flex;justify-content:space-between;align-items:center;
            padding:8px 0;border-bottom:1px solid #1e293b;
        ">
            <span style="color:#94a3b8;font-size:12px;">${r.label}</span>
            <span style="font-size:13px;font-weight:600;color:#f1f5f9;">
                ${r.value}${r.sub || ""}
            </span>
        </div>
    `).join("");

    const fallbackBadge = plan.is_fallback
        ? `<div style="
            margin-top:8px;padding:6px 10px;
            background:#1e293b;border-radius:6px;
            font-size:11px;color:#64748b;
        ">
            ⚠️ Plan dihitung dari Support/Resistance (analyzer tidak generate plan untuk saham ini)
        </div>`
        : "";

    const riskCalc = `
        <div style="margin-top:12px;">
            <div style="font-size:11px;color:#64748b;margin-bottom:6px;">💰 RISK CALCULATOR</div>
            <div style="display:flex;gap:8px;align-items:center;">
                <input
                    id="modal-input"
                    type="number"
                    placeholder="Modal (Rp)"
                    style="
                        flex:1;padding:6px 8px;
                        background:#0f172a;border:1px solid #334155;
                        border-radius:6px;color:#f1f5f9;font-size:12px;
                    "
                    oninput="calcRisk(this.value)"
                />
            </div>
            <div id="risk-result" style="margin-top:6px;font-size:12px;color:#94a3b8;"></div>
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
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:4px;margin-top:4px;">
                <span style="color:#64748b">Lot:</span>
                <span style="color:#f1f5f9;font-weight:600">${lots.toLocaleString("id-ID")} lot</span>
                <span style="color:#64748b">Lembar:</span>
                <span style="color:#f1f5f9">${shares.toLocaleString("id-ID")} lembar</span>
                <span style="color:#64748b">Total modal:</span>
                <span style="color:#f1f5f9">Rp ${totalCost.toLocaleString("id-ID")}</span>
                <span style="color:#ff3b5c">Max loss (SL):</span>
                <span style="color:#ff3b5c;font-weight:600">-Rp ${maxLoss.toLocaleString("id-ID")}</span>
                <span style="color:#00ff88">Profit TP1:</span>
                <span style="color:#00ff88;font-weight:600">+Rp ${potentialTP1.toLocaleString("id-ID")}</span>
            </div>
        `;
    };

    return rowsHtml + fallbackBadge + riskCalc;
}

function setTradePlanForChart(plan) {
    const data = plan || {};
    window.tradePlan = {
        stop_loss: Number(data.stop_loss) > 0 ? Number(data.stop_loss) : null,
        tp1: Number(data.tp1) > 0 ? Number(data.tp1) : null,
        tp2: Number(data.tp2) > 0 ? Number(data.tp2) : null,
        tp3: Number(data.tp3) > 0 ? Number(data.tp3) : null,
    };
}

function renderMLForecast(forecast, patterns) {
    const root = document.getElementById("ml-forecast");
    if (!root) return;
    if (!forecast) {
        root.innerHTML = '<span style="color:#475569">Data tidak tersedia</span>';
        return;
    }

    const confColor = { HIGH: "#00ff88", MEDIUM: "#fbbf24", LOW: "#ff3b5c" };
    const p5 = ((Number(forecast.probability_5pct) || 0) * 100).toFixed(0);
    const expected = ((Number(forecast.expected_return) || 0) * 100).toFixed(1);
    const conf = forecast.confidence || "LOW";

    const patternList = (patterns || []).slice(0, 4).map((p) => {
        if (typeof p === "string") return p;
        return p?.name || "";
    }).filter(Boolean);
    const patternsHtml = patternList.length
        ? patternList.map((p) => `
            <span style="
                display:inline-block;
                padding:2px 8px;margin:2px;
                background:#1e293b;border-radius:4px;
                font-size:11px;color:#94a3b8;
            ">${String(p).replaceAll("_", " ")}</span>
        `).join("")
        : '<span style="color:#475569;font-size:12px;">Tidak ada pola terdeteksi</span>';

    root.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px;">
            <div style="background:#0f172a;border-radius:8px;padding:10px;text-align:center;">
                <div style="font-size:11px;color:#64748b;margin-bottom:4px;">Prob. Naik 5%</div>
                <div style="font-size:22px;font-weight:700;color:${Number(p5) >= 60 ? "#00ff88" : Number(p5) >= 40 ? "#fbbf24" : "#ff3b5c"};">
                    ${p5}%
                </div>
            </div>
            <div style="background:#0f172a;border-radius:8px;padding:10px;text-align:center;">
                <div style="font-size:11px;color:#64748b;margin-bottom:4px;">Expected Return</div>
                <div style="font-size:22px;font-weight:700;color:${Number(expected) >= 0 ? "#00ff88" : "#ff3b5c"};">
                    ${Number(expected) > 0 ? "+" : ""}${expected}%
                </div>
            </div>
        </div>
        <div style="
            display:flex;justify-content:space-between;align-items:center;
            padding:8px;background:#0f172a;border-radius:6px;margin-bottom:10px;
        ">
            <span style="font-size:12px;color:#94a3b8;">Confidence</span>
            <span style="
                font-size:12px;font-weight:700;
                color:${confColor[conf] || "#64748b"};
                background:${(confColor[conf] || "#64748b")}22;
                padding:2px 10px;border-radius:4px;
            ">${conf}</span>
        </div>
        <div style="font-size:11px;color:#64748b;margin-bottom:6px;">🕯️ POLA TERDETEKSI</div>
        <div>${patternsHtml}</div>
    `;
}

async function loadScoring() {
    const data = await window.fetchWithTimeout(`/api/stock/${symbol}/scoring`, 15000);
    if (!data) {
        document.getElementById("gate-status").innerHTML = '<div class="text-muted">Scoring unavailable</div>';
        return;
    }
    document.getElementById("gate-status").innerHTML = `
        <div class="text-sm">Gate: ${data.gates?.passed || 0}/${data.gates?.total || 6} (${data.gates?.confidence || "-"})</div>
        <div class="text-sm text-muted">Composite: ${data.scores?.composite_score || 0}</div>
    `;
    latestScores = data.scores || latestScores;
    document.getElementById("trade-plan").innerHTML = renderTradePlan(data.trade_plan || {});
    setTradePlanForChart(data.trade_plan || {});
}

function renderFull(data) {
    const latest = data.latest || {};
    const sentiment = data.sentiment || {};
    const forecast = data.forecast || {};
    window._currentPriceForTradePlan = Number(latest.price) || 0;
    latestScores = data.analysis || latestScores;
    document.getElementById("stock-headline").textContent =
        `${window.toRupiah(latest.price || 0)} | Vol ${Math.round((latest.volume || 0) / 1000000)}M`;

    const gateRows = (data.analysis || {}).gate_status || [];
    if (gateRows.length) {
        document.getElementById("gate-status").innerHTML = renderGateRows(gateRows);
    }

    const tradePlan = (data.analysis || {}).trade_plan || {};
    document.getElementById("trade-plan").innerHTML = renderTradePlan(tradePlan);
    setTradePlanForChart(tradePlan);
    renderMLForecast(forecast, data.patterns || []);
    renderIndicatorSummary(chartDataCache?.summary || {}, data.analysis || {});

    const patterns = data.patterns || [];
    document.getElementById("pattern-panel").innerHTML = patterns.length
        ? patterns.slice(0, 3).map((p) => `${String(p.name || "").replaceAll("_", " ")} (${p.strength || "MEDIUM"})`).join("<br>")
        : '<span class="text-muted">No pattern detected</span>';

    const news = data.news || [];
    document.getElementById("sentiment-news").innerHTML = `
        <div class="text-sm mb-2">Sentiment: ${sentiment.sentiment || "NEUTRAL"} (score: ${sentiment.score || 0})</div>
        ${news.slice(0, 6).map((n) => `<div class="text-sm text-muted"><a class="text-link" href="${n.url || "#"}" target="_blank">${n.title}</a></div>`).join("")}
    `;
}

async function loadStockDetail() {
    const mainContainer = document.getElementById("main-chart");
    if (mainContainer) mainContainer.innerHTML = '<div class="skeleton"></div>';
    await loadScoring();
    await initAdvancedChart(currentPeriod);

    window.fetchWithTimeout(`/api/stock/${symbol}/full`, 20000).then((data) => {
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

window.addEventListener("resize", () => {
    const mainContainer = document.getElementById("main-chart");
    const volContainer = document.getElementById("volume-chart");
    const macdContainer = document.getElementById("macd-chart");
    if (mainChart && mainContainer) mainChart.applyOptions({ width: mainContainer.clientWidth });
    if (volumeChart && volContainer) volumeChart.applyOptions({ width: volContainer.clientWidth });
    if (macdChart && macdContainer) macdChart.applyOptions({ width: macdContainer.clientWidth });
});

document.addEventListener("DOMContentLoaded", () => {
    renderIndicatorToggles();
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
