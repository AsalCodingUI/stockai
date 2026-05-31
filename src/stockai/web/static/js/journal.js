// ── Signal Performance JS ──────────────────────────────────────────────────────
let winChart = null;
let pnlChart = null;
let currentTab = "open";

// ── Bootstrap ─────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  loadStats();
  loadOpenPlans();
});

// ── Stats ─────────────────────────────────────────────────────────────────────
async function loadStats() {
  try {
    const data = await window.appFetch("/api/journal/stats");
    document.getElementById("j-total").textContent = data.total ?? "—";
    document.getElementById("j-open").textContent = data.open ?? "—";

    const wr = data.win_rate ?? 0;
    const wrEl = document.getElementById("j-winrate");
    wrEl.textContent = `${wr.toFixed(1)}%`;
    wrEl.className = `stat-value ${wr >= 50 ? "text-success" : "text-error"}`;

    const pnl = data.avg_pnl_pct ?? 0;
    const pnlEl = document.getElementById("j-avgpnl");
    pnlEl.textContent = `${pnl >= 0 ? "+" : ""}${pnl.toFixed(1)}%`;
    pnlEl.className = `stat-value ${pnl >= 0 ? "text-success" : "text-error"}`;

    document.getElementById("j-wl").textContent = `${data.wins ?? 0} / ${data.losses ?? 0}`;

    renderWinRateChart(data.wins ?? 0, data.losses ?? 0);

    document.getElementById("wr-pct").textContent = `${wr.toFixed(1)}%`;
    document.getElementById("wr-pct").className = `text-2xl font-bold ${wr >= 50 ? "text-success" : "text-error"}`;
  } catch (err) {
    console.warn("loadStats error:", err);
  }
}

// ── Win Rate Doughnut ─────────────────────────────────────────────────────────
function renderWinRateChart(wins, losses) {
  const ctx = document.getElementById("win-rate-chart");
  if (!ctx) return;
  if (winChart) winChart.destroy();

  const total = wins + losses;
  winChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      datasets: [{
        data: total > 0 ? [wins, losses] : [1, 0],
        backgroundColor: total > 0 ? ["#10b981", "#ef4444"] : ["#27272a"],
        borderWidth: 0,
        hoverOffset: 4,
      }],
    },
    options: {
      cutout: "75%",
      plugins: { legend: { display: false }, tooltip: { enabled: total > 0 } },
      animation: { duration: 600 },
    },
  });
}

// ── P&L Bar Chart ─────────────────────────────────────────────────────────────
function renderPnLChart(closedPlans) {
  const ctx = document.getElementById("pnl-chart");
  if (!ctx) return;
  if (pnlChart) pnlChart.destroy();

  const relevant = closedPlans.filter(p => p.pnl_pct !== null).slice(-20);
  const labels = relevant.map(p => p.symbol);
  const values = relevant.map(p => parseFloat(p.pnl_pct ?? 0));
  const colors = values.map(v => v >= 0 ? "rgba(16,185,129,0.7)" : "rgba(239,68,68,0.7)");

  pnlChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: colors,
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false }, tooltip: {
        callbacks: { label: ctx => `${ctx.parsed.y >= 0 ? "+" : ""}${ctx.parsed.y.toFixed(1)}%` }
      }},
      scales: {
        x: { ticks: { color: "#71717a", font: { size: 10 } }, grid: { display: false } },
        y: {
          ticks: { color: "#71717a", font: { size: 10 }, callback: v => `${v >= 0 ? "+" : ""}${v}%` },
          grid: { color: "#27272a" },
          border: { dash: [4, 4] },
        },
      },
    },
  });
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function switchTab(tab) {
  currentTab = tab;
  const openBtn = document.getElementById("tab-open");
  const histBtn = document.getElementById("tab-history");
  const openPanel = document.getElementById("panel-open");
  const histPanel = document.getElementById("panel-history");
  const filterStatus = document.getElementById("filter-status");

  if (tab === "open") {
    openBtn.className = "tab-btn active px-4 py-1.5 text-xs rounded-md bg-zinc-50 text-zinc-950 font-semibold transition";
    histBtn.className = "tab-btn px-4 py-1.5 text-xs rounded-md bg-zinc-900 text-zinc-400 border border-zinc-800 hover:bg-zinc-800 hover:text-zinc-100 transition font-semibold";
    openPanel.style.display = "";
    histPanel.style.display = "none";
    filterStatus.classList.add("hidden");
    loadOpenPlans();
  } else {
    openBtn.className = "tab-btn px-4 py-1.5 text-xs rounded-md bg-zinc-900 text-zinc-400 border border-zinc-800 hover:bg-zinc-800 hover:text-zinc-100 transition font-semibold";
    histBtn.className = "tab-btn active px-4 py-1.5 text-xs rounded-md bg-zinc-50 text-zinc-950 font-semibold transition";
    openPanel.style.display = "none";
    histPanel.style.display = "";
    filterStatus.classList.remove("hidden");
    loadHistory();
  }
}

// ── Open Plans ────────────────────────────────────────────────────────────────
async function loadOpenPlans() {
  const root = document.getElementById("open-plans-list");
  root.innerHTML = '<div class="text-muted text-sm">Memuat...</div>';
  try {
    const data = await window.appFetch("/api/journal/plans?status=OPEN&limit=50");
    const plans = data.plans || [];
    if (!plans.length) {
      root.innerHTML = '<div class="text-muted text-sm py-8 text-center font-mono">Belum ada sinyal aktif saat ini.</div>';
      return;
    }
    root.innerHTML = plans.map(p => renderPlanCard(p)).join("");
  } catch (err) {
    root.innerHTML = `<div class="text-error text-sm">${err.message}</div>`;
  }
}

function renderPlanCard(p) {
  const statusBadge = {
    OPEN: '<span class="badge badge-watch">⏳ OPEN</span>',
    TP1_HIT: '<span class="badge badge-ready">✅ TP1</span>',
    TP2_HIT: '<span class="badge badge-ready">✅ TP2</span>',
    TP3_HIT: '<span class="badge badge-ready">🏆 TP3</span>',
    SL_HIT: '<span class="badge badge-rejected">🛑 SL HIT</span>',
    MANUAL_CLOSE: '<span class="badge bg-zinc-900 border border-zinc-800 text-zinc-400">📤 CLOSED</span>',
  }[p.status] || `<span class="badge">${p.status}</span>`;

  const tujuanIcon = {
    scalp: '<i class="ph ph-lightning mr-1 text-zinc-400 align-middle"></i>',
    swing: '<i class="ph ph-arrows-clockwise mr-1 text-zinc-400 align-middle"></i>',
    invest: '<i class="ph ph-seedling mr-1 text-zinc-400 align-middle"></i>',
  }[p.tujuan] || '<i class="ph ph-clipboard-text mr-1 text-zinc-400 align-middle"></i>';

  return `
  <div class="card p-4 border border-zinc-800 bg-zinc-950/20" id="plan-${p.id}">
    <div class="flex items-start justify-between gap-2 mb-3">
      <div>
        <span class="font-bold text-base text-white font-mono">${p.symbol}</span>
        <span class="text-xs text-muted ml-2">${tujuanIcon} ${p.tujuan} · Modal ${window.toRupiah(p.modal)}</span>
      </div>
      <div class="flex items-center gap-2">${statusBadge}</div>
    </div>
    <div class="grid grid-cols-2 gap-x-4 gap-y-1 text-xs mb-3 text-zinc-300">
      <div><span class="text-muted">Area Beli:</span> <span class="font-mono">${window.toRupiah(p.entry_low)} – ${window.toRupiah(p.entry_high)}</span></div>
      <div><span class="text-muted">R/R Ratio:</span> <span class="font-mono text-zinc-100">${(p.risk_reward ?? 0).toFixed(2)}x</span></div>
      <div><span class="text-muted">Stop Loss:</span> <span class="font-mono text-error">${window.toRupiah(p.stop_loss)}</span></div>
      <div><span class="text-muted">Target 1:</span> <span class="font-mono text-success">${window.toRupiah(p.tp1)}</span></div>
      ${p.tp2 ? `<div><span class="text-muted">Target 2:</span> <span class="font-mono text-success">${window.toRupiah(p.tp2)}</span></div>` : ""}
      ${p.tp3 ? `<div><span class="text-muted">Target 3:</span> <span class="font-mono text-success">${window.toRupiah(p.tp3)}</span></div>` : ""}
    </div>
    ${p.notes ? `<div class="text-[11px] text-muted italic mb-3 border-l-2 border-zinc-800 pl-2">${p.notes}</div>` : ""}
    <div class="flex flex-wrap gap-2 items-center">
      <button onclick="checkLivePrice(${p.id})" id="btn-check-${p.id}"
        class="px-3 py-1.5 text-xs bg-zinc-900 hover:bg-zinc-800 border border-zinc-800 text-zinc-200 rounded-md transition flex items-center gap-1.5">
        <i class="ph ph-magnifying-glass"></i> Cek Harga Live
      </button>
      <div id="check-result-${p.id}" class="text-xs font-mono ml-auto"></div>
    </div>
    <div class="text-[10px] text-muted mt-2">Rekomendasi sejak ${window.timeAgo(p.created_at)}</div>
  </div>`;
}

// ── Check Live Price ──────────────────────────────────────────────────────────
async function checkLivePrice(planId) {
  const btn = document.getElementById(`btn-check-${planId}`);
  const resultEl = document.getElementById(`check-result-${planId}`);
  btn.disabled = true;
  btn.innerHTML = '<i class="ph ph-arrows-clockwise animate-spin mr-1.5"></i> Mengecek...';
  resultEl.textContent = "";

  try {
    const res = await window.appFetch(`/api/journal/plans/${planId}/check`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) });
    const outcome = res.outcome;
    const pnl = res.pnl_pct;
    const priceStr = window.toRupiah(res.price);
    const outcomeColor = {
      TP1_HIT: "text-success", TP2_HIT: "text-success", TP3_HIT: "text-success",
      SL_HIT: "text-error", ENTRY_ZONE: "text-warning", OPEN: "text-zinc-500",
    }[outcome] || "text-zinc-500";

    resultEl.innerHTML = `<span class="${outcomeColor} font-bold">${outcome}</span> @ ${priceStr}${pnl !== null ? ` (${pnl >= 0 ? "+" : ""}${pnl.toFixed(1)}%)` : ""}`;

    // Reload if terminal outcome
    if (["SL_HIT", "TP1_HIT", "TP2_HIT", "TP3_HIT"].includes(outcome)) {
      setTimeout(() => { loadOpenPlans(); loadStats(); }, 1500);
    }
  } catch (err) {
    resultEl.textContent = `❌ ${err.message}`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="ph ph-magnifying-glass mr-1.5"></i> Cek Harga Live';
  }
}

// ── History Tab ───────────────────────────────────────────────────────────────
async function loadHistory() {
  const root = document.getElementById("history-list");
  root.innerHTML = '<div class="text-muted text-sm">Memuat...</div>';
  const status = document.getElementById("filter-status")?.value || "";
  try {
    const url = `/api/journal/plans?limit=100${status ? "&status=" + status : ""}`;
    const data = await window.appFetch(url);
    const plans = (data.plans || []).filter(p => p.status !== "OPEN");
    if (!plans.length) {
      root.innerHTML = '<div class="text-muted text-sm py-8 text-center font-mono">Belum ada sinyal ditutup.</div>';
      return;
    }
    renderPnLChart(plans);
    root.innerHTML = `
    <table style="width:100%;border-collapse:collapse;font-size:13px;" class="min-w-[600px]">
      <thead>
        <tr style="color:var(--color-text-muted);border-bottom:1px solid var(--border);">
          <th class="py-2 text-left">Saham</th>
          <th class="py-2 text-left">Tujuan</th>
          <th class="py-2 text-left">Hasil Akhir</th>
          <th class="py-2 text-right">P&L</th>
          <th class="py-2 text-right">Durasi</th>
          <th class="py-2 text-right">R/R</th>
          <th class="py-2 text-left pr-2">Tanggal Selesai</th>
        </tr>
      </thead>
      <tbody>
        ${plans.map(p => `
          <tr style="border-bottom:1px solid var(--color-bg-secondary);" class="hover:bg-zinc-900/40 transition">
            <td class="py-2 font-bold text-white font-mono">${p.symbol}</td>
            <td class="py-2 text-muted">${p.tujuan}</td>
            <td class="py-2">${statusLabel(p.status)}</td>
            <td class="py-2 text-right font-mono ${(p.pnl_pct ?? 0) >= 0 ? "text-success" : "text-error"}">
              ${p.pnl_pct !== null ? `${p.pnl_pct >= 0 ? "+" : ""}${p.pnl_pct.toFixed(1)}%` : "—"}
            </td>
            <td class="py-2 text-right text-muted">${p.days_held ?? "—"} hari</td>
            <td class="py-2 text-right font-mono text-zinc-300">${(p.risk_reward ?? 0).toFixed(2)}x</td>
            <td class="py-2 text-muted text-xs">${p.exit_date ? window.timeAgo(p.exit_date) : "—"}</td>
          </tr>
        `).join("")}
      </tbody>
    </table>`;
  } catch (err) {
    root.innerHTML = `<div class="text-error text-sm">${err.message}</div>`;
  }
}

function statusLabel(s) {
  const map = {
    TP1_HIT: '<span class="text-success"><i class="ph ph-check-circle mr-1 align-middle"></i> TP1</span>',
    TP2_HIT: '<span class="text-success"><i class="ph ph-check-circle mr-1 align-middle"></i> TP2</span>',
    TP3_HIT: '<span class="text-success"><i class="ph ph-crown mr-1 align-middle"></i> TP3</span>',
    SL_HIT: '<span class="text-error"><i class="ph ph-x-circle mr-1 align-middle"></i> SL</span>',
    MANUAL_CLOSE: '<span class="text-zinc-400"><i class="ph ph-sign-out mr-1 align-middle"></i> Closed</span>',
    CANCELLED: '<span class="text-zinc-500"><i class="ph ph-trash mr-1 align-middle"></i> Cancelled</span>',
  };
  return map[s] || `<span class="text-muted">${s}</span>`;
}

// ── AI Feedback ───────────────────────────────────────────────────────────────
async function loadAIFeedback() {
  const panel = document.getElementById("ai-feedback-panel");
  const btn = document.getElementById("btn-ai-feedback");
  btn.disabled = true;
  btn.innerHTML = '<i class="ph ph-arrows-clockwise animate-spin mr-1 align-middle"></i> Menganalisa...';
  panel.innerHTML = '<div class="text-muted text-sm animate-pulse"><i class="ph ph-robot mr-1.5 align-middle"></i> AI sedang menganalisa data performa rotasi modal...</div>';

  try {
    const data = await window.appFetch("/api/journal/ai-feedback");
    const fb = data.feedback || {};
    const stats = data.stats || {};

    const gradeColor = { A: "text-success", B: "text-zinc-200", C: "text-warning", D: "text-error" };
    const wr = fb.win_rate_analysis || {};
    const grade = wr.grade || "—";

    panel.innerHTML = `
      <div class="mb-3 p-3 rounded-lg border border-zinc-800 bg-zinc-950">
        <div class="flex items-center gap-3 mb-2">
          <div class="text-3xl font-extrabold ${gradeColor[grade] || "text-white"} font-mono">${grade}</div>
          <div>
            <div class="text-sm font-semibold">${fb.source === "gemini" ? "🤖 Gemini Analysis" : "📊 Statistical Analysis"}</div>
            <div class="text-xs text-muted">${stats.closed ?? 0} closed trades · ${(stats.win_rate ?? 0).toFixed(1)}% win rate · ${(stats.avg_pnl_pct ?? 0) >= 0 ? "+" : ""}${(stats.avg_pnl_pct ?? 0).toFixed(1)}% avg P&L</div>
          </div>
        </div>
        <p class="text-xs text-zinc-300 leading-relaxed">${fb.summary || "—"}</p>
      </div>
      ${fb.strengths?.length ? `
        <div class="mb-3">
          <div class="text-xs font-semibold text-success mb-1">💪 KEKUATAN SIGNAL</div>
          ${fb.strengths.map(s => `<div class="text-xs text-zinc-300 mb-1 flex items-start"><i class="ph ph-caret-right text-success mr-1 mt-0.5"></i> ${s}</div>`).join("")}
        </div>` : ""}
      ${fb.weaknesses?.length ? `
        <div class="mb-3">
          <div class="text-xs font-semibold text-error mb-1">⚠️ KELEMAHAN / DITINGKATKAN</div>
          ${fb.weaknesses.map(w => `<div class="text-xs text-zinc-300 mb-1 flex items-start"><i class="ph ph-caret-right text-error mr-1 mt-0.5"></i> ${w}</div>`).join("")}
        </div>` : ""}
      ${fb.suggestions?.length ? `
        <div>
          <div class="text-xs font-semibold text-zinc-200 mb-1">💡 REKOMENDASI ROTASI MODAL</div>
          ${fb.suggestions.map((s, i) => `<div class="text-xs text-zinc-300 mb-1 flex items-start"><span class="text-zinc-500 font-bold mr-1.5">${i + 1}.</span> ${s}</div>`).join("")}
        </div>` : ""}
    `;
  } catch (err) {
    panel.innerHTML = `<div class="text-error text-sm"><i class="ph ph-x-circle mr-1 align-middle"></i> ${err.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.innerHTML = '<i class="ph ph-lightning mr-1 align-middle"></i> Analisa';
  }
}
