let portfolioChart = null;

function drawPortfolioChart(history) {
    const ctx = document.getElementById("portfolio-chart");
    if (!ctx) return;
    if (portfolioChart) {
        portfolioChart.destroy();
    }
    portfolioChart = new Chart(ctx, {
        type: "line",
        data: {
            labels: history.map((x) => x.date),
            datasets: [{
                data: history.map((x) => x.value),
                borderColor: "#00d4ff",
                backgroundColor: "rgba(0, 212, 255, 0.12)",
                tension: 0.3,
                fill: true,
            }],
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { color: "#94a3b8" }, grid: { color: "#1e1e2e" } },
                y: { ticks: { color: "#94a3b8" }, grid: { color: "#1e1e2e" } },
            },
        },
    });
}

async function loadPortfolio() {
    const summaryRes = await window.appFetch("/api/portfolio/summary");
    const historyRes = await window.appFetch("/api/portfolio/history?days=30");
    const summary = summaryRes.summary || {};
    const positions = summaryRes.positions || [];
    const risk = summaryRes.risk_metrics || {};

    document.getElementById("portfolio-modal").textContent = window.toRupiah(summary.total_cost_basis || 0);
    document.getElementById("portfolio-value").textContent = window.toRupiah(summary.total_market_value || 0);
    const retNode = document.getElementById("portfolio-return");
    const pnlPct = Number(summary.total_pnl_percent || 0);
    retNode.textContent = `${window.toPct(pnlPct)} (${window.toRupiah(summary.total_unrealized_pnl || 0)})`;
    retNode.style.color = pnlPct >= 0 ? "#00ff88" : "#ff3b5c";

    const posRoot = document.getElementById("positions-list");
    posRoot.innerHTML = "";
    if (!positions.length) {
        posRoot.innerHTML = '<div class="text-muted">No positions yet.</div>';
    } else {
        positions.forEach((p) => {
            const row = document.createElement("div");
            row.className = "signal-card";
            row.innerHTML = `
                <div class="flex items-center justify-between">
                    <strong>${p.symbol}</strong>
                    <span>${(p.shares || 0) / 100} lot</span>
                </div>
                <div class="text-sm text-muted">Avg: ${window.toRupiah(p.avg_cost || 0)} · Now: ${window.toRupiah(p.current_price || 0)}</div>
                <div class="text-sm">${window.toPct(p.pnl_percent || 0)} · ${window.toRupiah(p.unrealized_pnl || 0)}</div>
            `;
            posRoot.appendChild(row);
        });
    }

    const riskRoot = document.getElementById("risk-metrics");
    riskRoot.innerHTML = `
        <div>VaR (95%): ${window.toRupiah(risk.var_95 || 0)}</div>
        <div>Sharpe Ratio: ${risk.sharpe_ratio || 0}</div>
        <div>Max Drawdown: ${window.toPct(risk.max_drawdown_pct || 0)}</div>
        <div>Win Rate: ${window.toPct(risk.win_rate || 0)}</div>
    `;

    drawPortfolioChart(historyRes.history || []);
}

loadPortfolio().catch(console.error);
