const symbol = window.STOCK_SYMBOL;
let mainChart = null;
let volumeChart = null;
let macdChart = null;
let currentPeriod = "3mo";
window.tradePlan = null;
let chartDataCache = null;
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

function renderIndicatorSummary(summary) {
    const container = document.getElementById("indicator-summary");
    if (!container || !summary) return;

    const rsiColor = summary.rsi > 70 ? "#ff3b5c" : summary.rsi < 30 ? "#00ff88" : "#ff9500";
    const macdColor = summary.macd_signal === "BULLISH" ? "#00ff88" : "#ff3b5c";
    const emaColor = summary.ema_signal === "BULLISH" ? "#00ff88" : "#ff3b5c";
    const trendColor = summary.trend === "BULLISH" ? "#00ff88" : "#ff3b5c";

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

    setSeriesVisible(
        seriesRefs.slLine,
        toggleState.tradePlan,
        (chartDataCache.candles || []).map((c) => ({ time: c.time, value: window.tradePlan?.stop_loss })),
    );
    setSeriesVisible(
        seriesRefs.tp1Line,
        toggleState.tradePlan,
        (chartDataCache.candles || []).map((c) => ({ time: c.time, value: window.tradePlan?.tp1 })),
    );
    setSeriesVisible(
        seriesRefs.tp2Line,
        toggleState.tradePlan,
        (chartDataCache.candles || []).map((c) => ({ time: c.time, value: window.tradePlan?.tp2 })),
    );
    setSeriesVisible(
        seriesRefs.tp3Line,
        toggleState.tradePlan,
        (chartDataCache.candles || []).map((c) => ({ time: c.time, value: window.tradePlan?.tp3 })),
    );

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
    if (!series || !candles?.length || !isValidPriceLevel(value, candles)) return;
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
        height: 360,
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
        height: 120,
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
        height: 120,
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

    renderIndicatorSummary(data.summary || {});
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
        height: 360,
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
    const fmt = (v) => (Number(v) > 0 ? window.toRupiah(v) : "-");
    return `
        Entry: ${fmt(plan.entry_low)} - ${fmt(plan.entry_high)}<br>
        SL: ${fmt(plan.stop_loss)}<br>
        TP1: ${fmt(plan.tp1)} · TP2: ${fmt(plan.tp2)} · TP3: ${fmt(plan.tp3)}<br>
        R/R: ${plan.rr ? Number(plan.rr).toFixed(2) : "-"}
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
    document.getElementById("trade-plan").innerHTML = renderTradePlan(data.trade_plan);
    window.tradePlan = {
        stop_loss: Number(data.trade_plan?.stop_loss) > 0 ? Number(data.trade_plan?.stop_loss) : null,
        tp1: Number(data.trade_plan?.tp1) > 0 ? Number(data.trade_plan?.tp1) : null,
        tp2: Number(data.trade_plan?.tp2) > 0 ? Number(data.trade_plan?.tp2) : null,
        tp3: Number(data.trade_plan?.tp3) > 0 ? Number(data.trade_plan?.tp3) : null,
    };
}

function renderFull(data) {
    const latest = data.latest || {};
    const sentiment = data.sentiment || {};
    const forecast = data.forecast || {};
    document.getElementById("stock-headline").textContent =
        `${window.toRupiah(latest.price || 0)} | Vol ${Math.round((latest.volume || 0) / 1000000)}M`;

    const gateRows = (data.analysis || {}).gate_status || [];
    if (gateRows.length) {
        document.getElementById("gate-status").innerHTML = renderGateRows(gateRows);
    }

    const tradePlan = (data.analysis || {}).trade_plan || {};
    document.getElementById("trade-plan").innerHTML = renderTradePlan(tradePlan);
    window.tradePlan = {
        stop_loss: Number(tradePlan.stop_loss) > 0 ? Number(tradePlan.stop_loss) : null,
        tp1: Number(tradePlan.tp1) > 0 ? Number(tradePlan.tp1) : null,
        tp2: Number(tradePlan.tp2) > 0 ? Number(tradePlan.tp2) : null,
        tp3: Number(tradePlan.tp3) > 0 ? Number(tradePlan.tp3) : null,
    };

    document.getElementById("ml-forecast").innerHTML = `
        Prob +5%: ${Math.round((forecast.probability_5pct || 0) * 100)}%<br>
        Expected: ${window.toPct((forecast.expected_return || 0) * 100)}<br>
        Confidence: ${forecast.confidence || "-"}<br>
        Cases: ${forecast.similar_cases || 0}
    `;

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
