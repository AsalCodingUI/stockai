let ihsgChart = null;

function addCandleSeriesCompat(chart) {
    if (!chart) return null;
    if (typeof chart.addCandlestickSeries === "function") {
        return chart.addCandlestickSeries({
            upColor: "#00ff88",
            downColor: "#ff3b5c",
            borderUpColor: "#00ff88",
            borderDownColor: "#ff3b5c",
            wickUpColor: "#00ff88",
            wickDownColor: "#ff3b5c",
        });
    }
    if (typeof chart.addSeries === "function" && window.LightweightCharts?.CandlestickSeries) {
        return chart.addSeries(window.LightweightCharts.CandlestickSeries, {
            upColor: "#00ff88",
            downColor: "#ff3b5c",
            borderUpColor: "#00ff88",
            borderDownColor: "#ff3b5c",
            wickUpColor: "#00ff88",
            wickDownColor: "#ff3b5c",
        });
    }
    return null;
}

function renderCards(results) {
    const cards = document.getElementById("signal-cards");
    if (!cards) return;
    cards.innerHTML = "";
    (results || []).slice(0, 12).forEach((row) => {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = window.renderSignalCard(row);
        const el = wrapper.firstElementChild;
        el.addEventListener("click", () => {
            window.location.href = `/stock/${row.symbol}`;
        });
        cards.appendChild(el);
    });
}

async function initIHSGChart() {
    const container = document.getElementById("ihsg-chart");
    if (!container) return;
    if (typeof LightweightCharts === "undefined") {
        console.error("TradingView not loaded");
        container.innerHTML = '<div class="text-muted" style="padding:80px;text-align:center">Chart library unavailable</div>';
        return;
    }

    ihsgChart = LightweightCharts.createChart(container, {
        width: container.clientWidth,
        height: 220,
        layout: {
            background: { color: "#111118" },
            textColor: "#94a3b8",
        },
        grid: {
            vertLines: { color: "#1e1e2e" },
            horzLines: { color: "#1e1e2e" },
        },
        timeScale: {
            borderColor: "#1e1e2e",
            timeVisible: true,
        },
        crosshair: { mode: 1 },
    });

    const candleSeries = addCandleSeriesCompat(ihsgChart);
    if (!candleSeries) {
        container.innerHTML = '<div class="text-muted" style="padding:80px;text-align:center">Chart not supported by library version</div>';
        return;
    }

    const data = await window.fetchWithTimeout("/api/stock/%5EJKSE/chart?period=7d", 12000);
    if (data && data.candles && data.candles.length) {
        candleSeries.setData(data.candles);
        ihsgChart.timeScale().fitContent();
    } else {
        container.innerHTML = '<div class="text-muted" style="padding:80px;text-align:center">Chart data unavailable</div>';
    }

    window.addEventListener("resize", () => {
        if (ihsgChart && container.clientWidth > 0) {
            ihsgChart.applyOptions({ width: container.clientWidth });
        }
    });
}

async function loadDashboard() {
    const data = await window.fetchWithTimeout("/api/dashboard", 12000);
    if (!data) return;
    const last = data.last_scan || {};
    document.getElementById("kpi-ready").textContent = last.ready || 0;
    document.getElementById("kpi-watch").textContent = last.watch || 0;
    document.getElementById("kpi-scanned").textContent = last.scanned || 0;
    document.getElementById("kpi-last-scan").textContent = window.timeAgo(last.timestamp);
    renderCards(last.results || []);
}

document.addEventListener("DOMContentLoaded", async () => {
    await loadDashboard();
    await initIHSGChart();
});
