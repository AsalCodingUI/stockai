document.addEventListener("DOMContentLoaded", async () => {
  await loadWatchlist();
  await loadMonitorLogs();
  setInterval(loadMonitorLogs, 60000);
});

async function loadWatchlist() {
  const resp = await fetch("/api/coach/watchlist");
  const data = await resp.json();
  renderWatchlist(data.stocks || []);
}

function renderWatchlist(stocks) {
  const grid = document.getElementById("wl-grid");
  const count = document.getElementById("wl-count");
  if (!grid || !count) return;

  count.textContent = stocks.length;
  if (!stocks.length) {
    grid.innerHTML = `
      <div class="col-span-3 text-center py-8 text-muted text-sm">
        Belum ada saham di watchlist.<br>
        Tambah saham di atas untuk mulai monitoring.
      </div>`;
    return;
  }

  grid.innerHTML = stocks.map((s) => {
    const signalColor = {
      ENTRY_NOW: "#00ff88",
      WAIT: "#fbbf24",
      AVOID: "#ff3b5c",
    }[s.last_signal] || "#475569";

    const signalText = {
      ENTRY_NOW: "🟢 Sinyal Masuk",
      WAIT: "🟡 Tunggu",
      AVOID: "🔴 Hindari",
    }[s.last_signal] || "⚪ Belum discan";

    const modalFmt = new Intl.NumberFormat("id-ID", {
      style: "currency",
      currency: "IDR",
      maximumFractionDigits: 0,
    }).format(s.modal);

    const tujuanMap = { scalp: "Scalping", swing: "Swing", invest: "Investasi" };
    const lastAlert = s.last_alert
      ? new Date(s.last_alert).toLocaleString("id-ID", {
        hour: "2-digit", minute: "2-digit", day: "2-digit", month: "short",
      })
      : "-";

    return `
      <div style="
        background:#1e293b;border-radius:12px;padding:16px;
        border:1px solid ${s.last_signal === "ENTRY_NOW" ? "#00ff8840" : "#1e293b"};
        transition:all 0.2s;
      ">
        <div class="flex justify-between items-start mb-3">
          <div>
            <div class="text-lg font-bold text-white">${s.symbol}</div>
            <div class="text-xs text-muted">${tujuanMap[s.tujuan] || s.tujuan} · ${modalFmt}</div>
          </div>
          <button onclick="removeStock('${s.symbol}')" class="text-slate-600 hover:text-red-400 text-lg transition">✕</button>
        </div>
        <div style="color:${signalColor};font-size:13px;font-weight:600;margin-bottom:8px;">${signalText}</div>
        ${s.last_alert ? `<div class="text-xs text-muted mb-3">Update: ${lastAlert}</div>` : ""}
        <button onclick="analyzeStock('${s.symbol}', ${s.modal}, '${s.tujuan}')"
          class="w-full py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-sm font-semibold transition">
          🔍 Analisis Sekarang
        </button>
      </div>
    `;
  }).join("");
}

async function addToWatchlist() {
  const symbol = document.getElementById("wl-symbol")?.value.trim().toUpperCase();
  const modal = parseInt(document.getElementById("wl-modal")?.value || "5000000", 10);
  const tujuan = document.getElementById("wl-tujuan")?.value || "swing";
  if (!symbol) {
    alert("Masukkan kode saham dulu");
    return;
  }

  const resp = await fetch("/api/coach/watchlist", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol, modal, tujuan }),
  });

  if (!resp.ok) {
    const err = await resp.json();
    alert(`Gagal: ${err.detail || "Unknown error"}`);
    return;
  }

  const input = document.getElementById("wl-symbol");
  if (input) input.value = "";
  await loadWatchlist();
}

async function removeStock(symbol) {
  if (!confirm(`Hapus ${symbol} dari watchlist?`)) return;
  await fetch(`/api/coach/watchlist/${symbol}`, { method: "DELETE" });
  await loadWatchlist();
}

async function analyzeStock(symbol, modal, tujuan) {
  const modalEl = document.getElementById("analysis-modal");
  const body = document.getElementById("modal-body");
  const title = document.getElementById("modal-title");
  if (!modalEl || !body || !title) return;

  title.textContent = `🔍 Menganalisis ${symbol}...`;
  body.innerHTML = `<div class="text-center py-8 text-muted">
    ⏳ AI sedang membaca data dan berpikir...<br>
    <span class="text-xs">Biasanya 5-10 detik</span>
  </div>`;
  modalEl.style.display = "block";

  try {
    const resp = await fetch(`/api/coach/analyze/${symbol}?modal=${modal}&tujuan=${tujuan}`);
    if (!resp.ok) {
      const err = await resp.json();
      body.innerHTML = `<div class="text-red-400">Error: ${err.detail}</div>`;
      return;
    }
    const d = await resp.json();
    title.textContent = `${symbol} - Analisis AI`;
    renderAnalysis(d, body);
  } catch (e) {
    body.innerHTML = `<div class="text-red-400">Request gagal: ${e.message}</div>`;
  }
}

function renderAnalysis(d, container) {
  const actionConfig = {
    ENTRY_NOW: { color: "#00ff88", bg: "rgba(0,255,136,0.1)", emoji: "🟢", text: "MASUK SEKARANG" },
    WAIT: { color: "#fbbf24", bg: "rgba(251,191,36,0.1)", emoji: "🟡", text: "TUNGGU DULU" },
    AVOID: { color: "#ff3b5c", bg: "rgba(255,59,92,0.1)", emoji: "🔴", text: "HINDARI" },
  }[d.action] || { color: "#94a3b8", bg: "transparent", emoji: "⚪", text: d.action };

  const fmtRp = (v) => `Rp ${Number(v).toLocaleString("id-ID")}`;
  const reasonList = d.action === "ENTRY_NOW" ? (d.reason_entry || []) : (d.reason_wait || []);

  const gateTotal = d.snapshot?.gate_total || 8;

  container.innerHTML = `
    <div style="background:${actionConfig.bg};border:1px solid ${actionConfig.color}40;border-radius:10px;padding:16px;margin-bottom:16px;text-align:center;">
      <div style="font-size:28px;margin-bottom:4px;">${actionConfig.emoji}</div>
      <div style="font-size:20px;font-weight:800;color:${actionConfig.color};">${actionConfig.text}</div>
      <div style="font-size:12px;color:#94a3b8;margin-top:4px;">Confidence: ${d.confidence}%</div>
    </div>

    <div style="font-size:14px;color:#e2e8f0;margin-bottom:16px;padding:12px;background:#0f172a;border-radius:8px;line-height:1.6;">
      ${d.summary || "-"}
    </div>

    ${d.action === "ENTRY_NOW" ? `
      <div style="background:#1e293b;border-radius:10px;padding:14px;margin-bottom:12px;">
        <div style="font-size:11px;color:#64748b;margin-bottom:10px;font-weight:600;">💰 SETUP ENTRY</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:13px;">
          <div><div style="color:#64748b;font-size:10px;">Entry Range</div><div style="color:#f1f5f9;font-weight:600;">${fmtRp(d.entry_low)} - ${fmtRp(d.entry_high)}</div></div>
          <div><div style="color:#64748b;font-size:10px;">Stop Loss</div><div style="color:#ff3b5c;font-weight:600;">${fmtRp(d.stop_loss)}</div></div>
          <div><div style="color:#64748b;font-size:10px;">Target 1</div><div style="color:#00ff88;font-weight:600;">${fmtRp(d.target1)}</div></div>
          <div><div style="color:#64748b;font-size:10px;">Target 2</div><div style="color:#00ff88;font-weight:600;">${fmtRp(d.target2)}</div></div>
          <div><div style="color:#64748b;font-size:10px;">Risk/Reward</div><div style="color:#f1f5f9;font-weight:600;">1:${d.risk_reward}</div></div>
          ${d.suggested_lot > 0 ? `<div><div style="color:#64748b;font-size:10px;">Saran Lot</div><div style="color:#f1f5f9;font-weight:600;">${d.suggested_lot} lot</div></div>` : ""}
        </div>
      </div>
    ` : ""}

    ${reasonList.length ? `
      <div style="margin-bottom:12px;">
        <div style="font-size:11px;color:#64748b;margin-bottom:6px;font-weight:600;">✅ KENAPA ${d.action === "ENTRY_NOW" ? "BAGUS" : "BELUM BAGUS"}</div>
        ${reasonList.slice(0, 4).map((r) => `<div style="font-size:13px;color:#e2e8f0;padding:4px 0;border-bottom:1px solid #1e293b;">• ${r}</div>`).join("")}
      </div>
    ` : ""}

    ${d.what_to_wait ? `
      <div style="background:#1e293b;border-radius:8px;padding:12px;margin-bottom:12px;">
        <div style="font-size:11px;color:#64748b;margin-bottom:6px;font-weight:600;">⏳ YANG HARUS TERJADI DULU</div>
        <div style="font-size:13px;color:#fbbf24;line-height:1.6;">${d.what_to_wait}</div>
      </div>
    ` : ""}

    ${d.warning?.length ? `
      <div style="margin-bottom:12px;">
        <div style="font-size:11px;color:#64748b;margin-bottom:6px;font-weight:600;">🚨 RISIKO</div>
        ${d.warning.slice(0, 3).map((w) => `<div style="font-size:13px;color:#ff3b5c;padding:4px 0;">⚠️ ${w}</div>`).join("")}
      </div>
    ` : ""}

    ${d.snapshot ? `
      <div style="background:#0f172a;border-radius:8px;padding:12px;margin-top:8px;">
        <div style="font-size:11px;color:#475569;margin-bottom:8px;font-weight:600;">📊 DATA TEKNIKAL</div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;font-size:12px;color:#64748b;">
          <div>Harga: <span style="color:#f1f5f9">${fmtRp(d.snapshot.price)} (${d.snapshot.change_pct > 0 ? "+" : ""}${d.snapshot.change_pct}%)</span></div>
          <div>Trend: <span style="color:#f1f5f9">${d.snapshot.trend}</span></div>
          <div>RSI: <span style="color:#f1f5f9">${d.snapshot.rsi}</span></div>
          <div>Gate: <span style="color:#f1f5f9">${d.snapshot.gate_score}/${gateTotal}</span></div>
          <div>Volume: <span style="color:#f1f5f9">${d.snapshot.vol_ratio}x avg</span></div>
          <div>IHSG: <span style="color:#f1f5f9">${d.snapshot.ihsg_trend}</span></div>
          <div>Stoch RSI: <span style="color:#f1f5f9">K ${d.snapshot.stoch_rsi_k} / D ${d.snapshot.stoch_rsi_d}</span></div>
          <div>Bollinger: <span style="color:#f1f5f9">${d.snapshot.bb_position}</span></div>
          <div>Pattern: <span style="color:#f1f5f9">${d.snapshot.candle_pattern}</span></div>
          <div>Sentiment: <span style="color:#f1f5f9">${d.snapshot.sentiment_label} (${Number(d.snapshot.sentiment_score || 0).toFixed(1)})</span></div>
          <div>Breadth: <span style="color:#f1f5f9">${d.snapshot.market_breadth} (${Number(d.snapshot.advance_ratio || 0).toFixed(2)})</span></div>
          <div>Sector Rot.: <span style="color:#f1f5f9">${d.snapshot.leading_sector} / ${d.snapshot.lagging_sector}</span></div>
        </div>
      </div>
    ` : ""}

    <div style="font-size:10px;color:#334155;margin-top:12px;text-align:center;">
      ⚠️ Bukan saran investasi. Keputusan akhir tetap di tangan Anda.
      Selalu gunakan risk management yang tepat.
    </div>
  `;
}

function closeAnalysis() {
  const modal = document.getElementById("analysis-modal");
  if (modal) modal.style.display = "none";
}

async function triggerScan() {
  const btn = document.getElementById("btn-trigger-scan");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "⏳ Scanning...";
  }

  await fetch("/api/coach/scan", { method: "POST" });
  setTimeout(async () => {
    await loadWatchlist();
    if (btn) {
      btn.disabled = false;
      btn.textContent = "🔄 Scan Semua Sekarang";
    }
  }, 5000);
}

async function testTelegram() {
  const resp = await fetch("/api/coach/test-telegram", { method: "POST" });
  if (resp.ok) {
    alert("✅ Berhasil! Cek Telegram kamu.");
  } else {
    const err = await resp.json();
    alert(`❌ Gagal: ${err.detail}`);
  }
}

async function loadMonitorLogs() {
  const statusEl = document.getElementById("monitor-status");
  const logsEl = document.getElementById("monitor-logs");
  if (!statusEl || !logsEl) return;

  try {
    const [statusResp, logsResp] = await Promise.all([
      fetch("/api/coach/monitor/status"),
      fetch("/api/coach/monitor/logs?limit=8"),
    ]);
    if (!statusResp.ok || !logsResp.ok) {
      return;
    }

    const status = await statusResp.json();
    const logs = await logsResp.json();

    statusEl.innerHTML = `
      Running: <span style="color:${status.running ? "#00ff88" : "#ff3b5c"}">${status.running ? "YES" : "NO"}</span> ·
      Interval: ${status.interval_sec || 0}s ·
      Breadth: ${(status.last_market_context && status.last_market_context.market_breadth) || "MIXED"} ·
      Alerts: ${status.alerts_logged || 0}
    `;

    const decisions = logs.decisions || [];
    if (!decisions.length) {
      logsEl.innerHTML = "Belum ada log keputusan.";
      return;
    }

    logsEl.innerHTML = decisions.map((row) => {
      const color = row.action === "ENTRY_NOW" ? "#00ff88" : row.action === "AVOID" ? "#ff3b5c" : "#fbbf24";
      return `
        <div style="padding:8px 10px;border:1px solid #1e293b;border-radius:8px;margin-bottom:6px;background:#0f172a;">
          <div style="display:flex;justify-content:space-between;gap:8px;">
            <span style="font-weight:700;color:#f1f5f9;">${row.symbol}</span>
            <span style="color:${color};font-weight:700;">${row.action} (${row.confidence}%)</span>
          </div>
          <div style="color:#64748b;margin-top:4px;">
            MTF ${row.trend_2m || "-"} / ${row.trend_15m || "-"} / ${row.trend_1d || "-"} ·
            Sent ${row.sentiment_label || "NEUTRAL"} ·
            Breadth ${row.market_breadth || "MIXED"}
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    // silent fail for dashboard polling
  }
}
