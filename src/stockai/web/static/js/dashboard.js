let ihsgChart = null;

function addAreaSeriesCompat(chart, options) {
    if (!chart) return null;
    if (typeof chart.addAreaSeries === "function") return chart.addAreaSeries(options);
    if (typeof chart.addSeries === "function" && window.LightweightCharts?.AreaSeries) {
        return chart.addSeries(window.LightweightCharts.AreaSeries, options);
    }
    return null;
}

function renderCards(results) {
    const cards = document.getElementById("signal-cards");
    if (!cards) return;
    cards.innerHTML = "";
    const buySignals = (results || []).filter(row => ["READY", "A+", "A", "B"].includes(row.status));
    
    if (!buySignals.length) {
        cards.innerHTML = `
            <div class="col-span-full text-center py-8 text-muted text-xs font-mono">
                Belum ada sinyal beli (A+/A/B) saat ini. Sistem akan merekomendasikan ketika ada peluang bagus.
            </div>
        `;
        return;
    }

    buySignals.slice(0, 12).forEach((row) => {
        const wrapper = document.createElement("div");
        wrapper.innerHTML = window.renderSignalCard(row);
        const el = wrapper.firstElementChild;
        el.addEventListener("click", () => {
            window.location.href = `/stock/${row.symbol}`;
        });
        cards.appendChild(el);
    });
}

function renderIHSGQuote(quote) {
    const root = document.getElementById("ihsg-quote-display");
    if (!root || !quote || quote.price == null) return;
    
    const changeSign = quote.change_pct >= 0 ? "+" : "";
    const colorClass = quote.change_pct >= 0 ? "text-success" : "text-error";
    
    root.innerHTML = `
        <span class="font-mono text-zinc-100 text-sm font-semibold">${quote.price.toLocaleString("id-ID")}</span>
        <span class="font-mono ${colorClass} text-xs ml-1.5 font-semibold">(${changeSign}${Number(quote.change_pct).toFixed(2)}%)</span>
    `;
}

function renderPortfolioSummary(portfolio) {
    const root = document.getElementById("portfolio-summary-widget");
    if (!root) return;
    
    if (!portfolio || !portfolio.position_count) {
        root.innerHTML = `
            <div class="text-center py-6 text-muted text-xs font-mono">
                Tidak ada posisi portofolio aktif. Gunakan AI Entry Coach untuk membuat plan investasi pertama Anda.
            </div>
        `;
        return;
    }
    
    const fmt = (v) => `Rp ${Math.round(v).toLocaleString("id-ID")}`;
    const pnlColorClass = portfolio.total_unrealized_pnl >= 0 ? "text-success" : "text-error";
    const pnlSign = portfolio.total_unrealized_pnl >= 0 ? "+" : "";
    
    root.innerHTML = `
        <div class="space-y-3 font-mono text-xs">
            <div class="flex justify-between items-center py-1.5 border-b border-zinc-900/60">
                <span class="text-zinc-400">Posisi Aktif</span>
                <span class="text-zinc-100 font-bold">${portfolio.position_count} Saham</span>
            </div>
            <div class="flex justify-between items-center py-1.5 border-b border-zinc-900/60">
                <span class="text-zinc-400">Total Modal</span>
                <span class="text-zinc-200">${fmt(portfolio.total_cost_basis)}</span>
            </div>
            <div class="flex justify-between items-center py-1.5 border-b border-zinc-900/60">
                <span class="text-zinc-400">Nilai Pasar</span>
                <span class="text-zinc-200">${fmt(portfolio.total_market_value)}</span>
            </div>
            <div class="flex justify-between items-center py-1.5 border-b border-zinc-900/60">
                <span class="text-zinc-400">Unrealized P&L</span>
                <span class="${pnlColorClass} font-bold">
                    ${pnlSign}${fmt(portfolio.total_unrealized_pnl)} (${pnlSign}${Number(portfolio.total_pnl_percent).toFixed(2)}%)
                </span>
            </div>
            <div class="flex justify-between items-center py-1.5">
                <span class="text-zinc-400">Realized P&L</span>
                <span class="${portfolio.total_realized_pnl >= 0 ? 'text-success' : 'text-error'} font-bold">
                    ${portfolio.total_realized_pnl >= 0 ? "+" : ""}${fmt(portfolio.total_realized_pnl)}
                </span>
            </div>
        </div>
    `;
}

async function loadDashboardAlerts() {
    const root = document.getElementById("dashboard-alerts-widget");
    if (!root) return;
    
    try {
        const data = await window.fetchWithTimeout("/api/alerts", 10000);
        if (!data || !data.alerts || !data.alerts.length) {
            root.innerHTML = `
                <div class="text-center py-6 text-muted text-xs font-mono">
                    Tidak ada notifikasi sistem saat ini.
                </div>
            `;
            return;
        }
        
        const levelConfig = {
            'CRITICAL': { bg: 'rgba(239,68,68,0.12)', color: '#EF4444', border: 'rgba(239,68,68,0.2)' },
            'ERROR':    { bg: 'rgba(239,68,68,0.12)', color: '#EF4444', border: 'rgba(239,68,68,0.2)' },
            'WARNING':  { bg: 'rgba(245,158,11,0.12)', color: '#F59E0B', border: 'rgba(245,158,11,0.2)' },
            'SUCCESS':  { bg: 'var(--miro-success-bg)', color: 'var(--miro-success)', border: 'rgba(39,166,68,0.2)' },
        };
        
        const items = data.alerts.slice(0, 5);
        root.innerHTML = `
            <div class="space-y-2.5">
                ${items.map(alert => {
                    const cfg = levelConfig[alert.level] || { bg: 'var(--color-surface-soft)', color: 'var(--color-slate)', border: 'var(--color-hairline)' };
                    return `
                        <div class="flex flex-col p-2.5 bg-zinc-950 border border-zinc-900 rounded-md font-mono text-[11px]">
                            <div class="flex items-center justify-between gap-2 mb-1.5">
                                <span style="
                                    padding: 1px 6px;
                                    border-radius: 9999px;
                                    font-size: 8px; font-weight: 600;
                                    background: ${cfg.bg}; color: ${cfg.color};
                                    border: 1px solid ${cfg.border};
                                    text-transform: uppercase;
                                " class="font-sans">${alert.level}</span>
                                <span class="text-zinc-500 text-[10px]">${window.timeAgo(alert.timestamp)}</span>
                            </div>
                            <div class="text-zinc-200 leading-snug">${alert.title}</div>
                        </div>
                    `;
                }).join("")}
            </div>
        `;
    } catch (e) {
        console.error("Error loading dashboard alerts:", e);
    }
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
            background: { color: "#010102" },
            textColor: "#a1a1aa",
        },
        grid: {
            vertLines: { color: "#1C1D21" },
            horzLines: { color: "#1C1D21" },
        },
        timeScale: {
            borderColor: "#23252A",
            timeVisible: true,
        },
        crosshair: { mode: 1 },
    });

    const areaSeries = addAreaSeriesCompat(ihsgChart, {
        lineColor: "#fafafa",
        topColor: "rgba(250, 250, 250, 0.15)",
        bottomColor: "rgba(250, 250, 250, 0.0)",
        lineWidth: 2,
        title: "IHSG",
    });

    if (!areaSeries) {
        container.innerHTML = '<div class="text-muted" style="padding:80px;text-align:center">Chart not supported by library version</div>';
        return;
    }

    const data = await window.fetchWithTimeout("/api/stock/%5EJKSE/chart?period=7d", 12000);
    if (data && data.candles && data.candles.length) {
        const areaData = data.candles.map(c => ({
            time: c.time,
            value: c.close
        }));
        areaSeries.setData(areaData);
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
    
    // KPIs
    const last = data.last_scan || {};
    document.getElementById("kpi-ready").textContent = last.ready || 0;
    document.getElementById("kpi-watch").textContent = last.watch || 0;
    document.getElementById("kpi-scanned").textContent = last.scanned || 0;
    document.getElementById("kpi-last-scan").textContent = window.timeAgo(last.timestamp);
    
    // Render Market Regime
    const badge = document.getElementById("market-regime-badge");
    if (badge && data.regime) {
        const reg = data.regime.regime;
        const bias = data.regime.action_bias;
        const note = data.regime.regime_note || "";
        
        let colorClass = "bg-zinc-800 text-zinc-400 border-zinc-700";
        let icon = "ph ph-activity";
        if (reg === "BULL") {
            colorClass = "bg-emerald-500/10 text-emerald-400 border-emerald-500/20";
            icon = "ph ph-chart-line-up";
        } else if (reg === "BEAR") {
            colorClass = "bg-rose-500/10 text-rose-400 border-rose-500/20";
            icon = "ph ph-chart-line-down";
        } else if (reg === "VOLATILE") {
            colorClass = "bg-amber-500/10 text-amber-400 border-amber-500/20";
            icon = "ph ph-warning-circle";
        } else if (reg === "NEUTRAL") {
            colorClass = "bg-zinc-800 text-zinc-300 border-zinc-700";
            icon = "ph ph-equals";
        }
        
        badge.className = `badge ${colorClass} font-semibold uppercase tracking-wider text-[10px] py-1 px-2.5 rounded-full inline-flex items-center gap-1.5`;
        badge.innerHTML = `<i class="${icon}"></i> Regime: ${reg} (${bias})`;
        badge.title = note;
    } else if (badge) {
        badge.style.display = "none";
    }

    // Quotes & Widgets
    if (data.ihsg) {
        renderIHSGQuote(data.ihsg.quote);
    }
    renderPortfolioSummary(data.portfolio_summary);
    loadDashboardAlerts();
    
    // Active Signal Cards
    renderCards(last.results || []);
}

document.addEventListener("DOMContentLoaded", async () => {
    await loadDashboard();
    await initIHSGChart();
});
