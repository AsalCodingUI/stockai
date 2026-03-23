let btChart = null;

function addAreaSeriesCompat(chart, options) {
  if (!chart) return null;
  if (typeof chart.addAreaSeries === "function") return chart.addAreaSeries(options);
  if (typeof chart.addSeries === "function" && window.LightweightCharts?.AreaSeries) {
    return chart.addSeries(window.LightweightCharts.AreaSeries, options);
  }
  return null;
}

function addLineSeriesCompat(chart, options) {
  if (!chart) return null;
  if (typeof chart.addLineSeries === "function") return chart.addLineSeries(options);
  if (typeof chart.addSeries === "function" && window.LightweightCharts?.LineSeries) {
    return chart.addSeries(window.LightweightCharts.LineSeries, options);
  }
  return null;
}

async function runBacktest() {
  const symbol = document.getElementById("bt-symbol")?.value.trim().toUpperCase();
  const strategy = document.getElementById("bt-strategy")?.value;
  const period = document.getElementById("bt-period")?.value;
  const sl = parseFloat(document.getElementById("bt-sl")?.value || "7") / 100;
  const tp = parseFloat(document.getElementById("bt-tp")?.value || "15") / 100;
  const btn = document.getElementById("btn-run-bt");

  if (!symbol || !btn) return;

  btn.disabled = true;
  btn.textContent = "⏳ Running...";

  try {
    const url = `/api/backtest/${symbol}?strategy=${strategy}&period=${period}&sl_pct=${sl}&tp_pct=${tp}`;
    const resp = await fetch(url);
    if (!resp.ok) {
      const err = await resp.json();
      alert(`Error: ${err.detail || "Request failed"}`);
      return;
    }
    const data = await resp.json();
    renderBacktest(data);
  } catch (e) {
    alert(`Request failed: ${e.message}`);
  } finally {
    btn.disabled = false;
    btn.textContent = "▶ Run Backtest";
  }
}

function renderBacktest(d) {
  const alphaColor = d.alpha >= 0 ? "#00ff88" : "#ff3b5c";
  const returnColor = d.total_return_pct >= 0 ? "#00ff88" : "#ff3b5c";

  const cards = [
    { label: "Total Return", value: `${d.total_return_pct > 0 ? "+" : ""}${d.total_return_pct}%`, color: returnColor },
    { label: "Alpha vs IHSG", value: `${d.alpha > 0 ? "+" : ""}${d.alpha}%`, color: alphaColor },
    { label: "Win Rate", value: `${d.win_rate}%`, color: d.win_rate >= 50 ? "#00ff88" : "#fbbf24" },
    { label: "Max Drawdown", value: `${d.max_drawdown_pct}%`, color: "#ff3b5c" },
    { label: "Sharpe Ratio", value: d.sharpe_ratio, color: d.sharpe_ratio >= 1 ? "#00ff88" : "#fbbf24" },
  ];

  const summaryEl = document.getElementById("bt-summary");
  const secondaryEl = document.getElementById("bt-secondary");
  if (!summaryEl || !secondaryEl) return;

  summaryEl.style.display = "grid";
  summaryEl.innerHTML = cards.map((c) => `
    <div style="background:#1e293b;border-radius:10px;padding:14px;text-align:center;">
      <div style="font-size:11px;color:#64748b;margin-bottom:4px;">${c.label}</div>
      <div style="font-size:22px;font-weight:700;color:${c.color};">${c.value}</div>
    </div>
  `).join("");

  secondaryEl.style.display = "block";
  secondaryEl.innerHTML = `
    <div style="display:flex;gap:16px;flex-wrap:wrap;padding:12px 0;font-size:12px;color:#94a3b8;">
      <span>Trades: <strong style="color:#f1f5f9">${d.total_trades}</strong></span>
      <span>Wins: <strong style="color:#00ff88">${d.win_trades}</strong></span>
      <span>Losses: <strong style="color:#ff3b5c">${d.loss_trades}</strong></span>
      <span>Profit Factor: <strong style="color:#f1f5f9">${d.profit_factor}</strong></span>
      <span>Avg Win: <strong style="color:#00ff88">+${d.avg_win_pct}%</strong></span>
      <span>Avg Loss: <strong style="color:#ff3b5c">${d.avg_loss_pct}%</strong></span>
      <span>Avg Hold: <strong style="color:#f1f5f9">${d.avg_hold_days} days</strong></span>
      <span>Best Trade: <strong style="color:#00ff88">+${d.best_trade_pct}%</strong></span>
      <span>Worst Trade: <strong style="color:#ff3b5c">${d.worst_trade_pct}%</strong></span>
      <span>Period: <strong style="color:#f1f5f9">${d.period}</strong></span>
    </div>
  `;

  const chartSection = document.getElementById("bt-chart-section");
  const chartEl = document.getElementById("bt-equity-chart");
  if (chartSection && chartEl) {
    chartSection.style.display = "block";
    chartEl.innerHTML = "";

    if (typeof LightweightCharts !== "undefined") {
      const chart = LightweightCharts.createChart(chartEl, {
        layout: { background: { color: "#0f172a" }, textColor: "#94a3b8" },
        grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
        width: chartEl.clientWidth,
        height: 300,
      });
      btChart = chart;

      const equitySeries = addAreaSeriesCompat(chart, {
        lineColor: "#3b82f6",
        topColor: "rgba(59,130,246,0.3)",
        bottomColor: "rgba(59,130,246,0.0)",
        lineWidth: 2,
        title: d.symbol,
      });
      if (!equitySeries) {
        chartEl.innerHTML = '<div class="text-muted" style="padding:120px;text-align:center">Chart API unsupported</div>';
        return;
      }
      equitySeries.setData((d.equity_curve || []).map((e) => ({ time: e.time, value: e.value })));

      if (d.benchmark_curve && d.benchmark_curve.length > 0) {
        const bmSeries = addLineSeriesCompat(chart, {
          color: "#475569",
          lineWidth: 1,
          lineStyle: 2,
          title: "IHSG",
        });
        if (bmSeries) bmSeries.setData(d.benchmark_curve);
      }

      const markers = [];
      for (const trade of d.trades || []) {
        if (trade.entry_date) {
          markers.push({ time: trade.entry_date, position: "belowBar", color: "#3b82f6", shape: "arrowUp", text: "B" });
        }
        if (trade.exit_date) {
          markers.push({
            time: trade.exit_date,
            position: "aboveBar",
            color: trade.pnl_pct >= 0 ? "#00ff88" : "#ff3b5c",
            shape: "arrowDown",
            text: trade.exit_reason === "stop_loss" ? "SL" : trade.exit_reason === "take_profit" ? "TP" : "S",
          });
        }
      }
      markers.sort((a, b) => (a.time > b.time ? 1 : -1));
      if (typeof equitySeries.setMarkers === "function") {
        equitySeries.setMarkers(markers);
      }
    }
  }

  const tradesSection = document.getElementById("bt-trades-section");
  const tradeCount = document.getElementById("bt-trade-count");
  const tbody = document.getElementById("bt-trade-tbody");
  if (!tradesSection || !tradeCount || !tbody) return;
  tradesSection.style.display = "block";
  tradeCount.textContent = `${(d.trades || []).length} trades`;

  tbody.innerHTML = (d.trades || []).map((t) => {
    const pnlColor = t.pnl_pct >= 0 ? "#00ff88" : "#ff3b5c";
    const reasonBadge = {
      stop_loss: '<span style="color:#ff3b5c;font-size:10px">SL</span>',
      take_profit: '<span style="color:#00ff88;font-size:10px">TP</span>',
      signal: '<span style="color:#94a3b8;font-size:10px">Signal</span>',
      end_of_data: '<span style="color:#64748b;font-size:10px">EOD</span>',
    }[t.exit_reason] || t.exit_reason;

    return `
      <tr class="border-b border-slate-800 hover:bg-slate-800/30">
        <td class="py-2 pr-4 text-slate-300">${t.entry_date}</td>
        <td class="py-2 pr-4 text-slate-300">${t.exit_date || "-"}</td>
        <td class="py-2 pr-4 text-right">Rp ${Number(t.entry_price).toLocaleString("id-ID")}</td>
        <td class="py-2 pr-4 text-right">Rp ${Number(t.exit_price || 0).toLocaleString("id-ID")}</td>
        <td class="py-2 pr-4 text-right">${Number(t.shares).toLocaleString("id-ID")}</td>
        <td class="py-2 pr-4 text-right" style="color:${pnlColor}">
          ${t.pnl >= 0 ? "+" : ""}Rp ${Number(t.pnl).toLocaleString("id-ID")}
        </td>
        <td class="py-2 pr-4 text-right font-semibold" style="color:${pnlColor}">
          ${t.pnl_pct >= 0 ? "+" : ""}${t.pnl_pct}%
        </td>
        <td class="py-2 pr-4 text-right text-slate-400">${t.hold_days}d</td>
        <td class="py-2">${reasonBadge}</td>
      </tr>
    `;
  }).join("");
}

function openScanModal() {
  const m = document.getElementById("scan-modal");
  if (m) m.style.display = "flex";
}

function closeScanModal() {
  const m = document.getElementById("scan-modal");
  if (m) m.style.display = "none";
}

function runScan() {
  const index = document.getElementById("scan-index")?.value || "IDX30";
  const strategy = document.getElementById("scan-strategy")?.value || "ema_cross";
  const period = document.getElementById("bt-period")?.value || "1y";

  const progressEl = document.getElementById("scan-progress");
  const barEl = document.getElementById("scan-bar");
  const currentEl = document.getElementById("scan-current");
  const resultsEl = document.getElementById("scan-results");
  if (!progressEl || !barEl || !currentEl || !resultsEl) return;

  progressEl.style.display = "block";
  resultsEl.innerHTML = "";

  const url = `/api/backtest/scan/stream?index=${index}&strategy=${strategy}&period=${period}`;
  const es = new EventSource(url);

  es.onmessage = (e) => {
    const data = JSON.parse(e.data);

    if (data.event === "completed") {
      es.close();
      progressEl.style.display = "none";
      renderScanResults(data.results || []);
      return;
    }

    if (data.progress) {
      const pct = data.progress.percent;
      barEl.style.width = `${pct}%`;
      currentEl.textContent = `${data.progress.current_symbol} (${data.progress.scanned}/${data.progress.total})`;
    }
  };

  es.onerror = () => {
    es.close();
    progressEl.style.display = "none";
  };
}

function renderScanResults(results) {
  const el = document.getElementById("scan-results");
  if (!el) return;

  if (!results.length) {
    el.innerHTML = '<p class="text-muted text-sm">Tidak ada hasil yang memenuhi filter.</p>';
    return;
  }

  el.innerHTML = `
    <div style="font-size:11px;color:#64748b;margin-bottom:8px;">
      Top ${results.length} saham by return - klik untuk backtest detail
    </div>
    ${results.slice(0, 20).map((r, i) => `
      <div onclick="loadFromScan('${r.symbol}')"
        style="
          display:flex;justify-content:space-between;align-items:center;
          padding:8px 10px;margin-bottom:4px;
          background:#0f172a;border-radius:8px;cursor:pointer;
          border:1px solid #1e293b;
          transition:border-color 0.1s;
        "
        onmouseover="this.style.borderColor='#3b82f6'"
        onmouseout="this.style.borderColor='#1e293b'"
      >
        <div style="display:flex;align-items:center;gap:10px;">
          <span style="color:#64748b;font-size:11px;width:20px;">${i + 1}</span>
          <span style="font-weight:700;color:#f1f5f9;">${r.symbol}</span>
          <span style="font-size:11px;color:#475569;">WR: ${r.win_rate}%</span>
          <span style="font-size:11px;color:#475569;">${r.total_trades} trades</span>
        </div>
        <div style="display:flex;gap:12px;align-items:center;">
          <span style="font-size:12px;color:${r.alpha >= 0 ? "#00ff88" : "#ff3b5c"}">
            alpha ${r.alpha >= 0 ? "+" : ""}${r.alpha}%
          </span>
          <span style="
            font-size:14px;font-weight:700;
            color:${r.total_return_pct >= 0 ? "#00ff88" : "#ff3b5c"};
          ">
            ${r.total_return_pct >= 0 ? "+" : ""}${r.total_return_pct}%
          </span>
        </div>
      </div>
    `).join("")}
  `;
}

function loadFromScan(symbol) {
  closeScanModal();
  const input = document.getElementById("bt-symbol");
  if (input) input.value = symbol;
  runBacktest();
}

window.addEventListener("resize", () => {
  const chartEl = document.getElementById("bt-equity-chart");
  if (btChart && chartEl) {
    btChart.applyOptions({ width: chartEl.clientWidth });
  }
});
