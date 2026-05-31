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
      <div class="col-span-full text-center py-12 text-muted text-xs font-mono">
        Belum ada saham di monitor list.<br>
        Tambah saham di atas untuk mulai monitoring otomatis.
      </div>`;
    return;
  }

  grid.innerHTML = stocks.map((s) => {
    let signalColorClass = "text-zinc-500";
    let signalText = '<i class="ph ph-circle mr-1.5 align-middle"></i> Belum discan';
    let cardBorderClass = "border-zinc-800";

    if (s.last_signal === "ENTRY_NOW") {
      signalColorClass = "text-success";
      signalText = '<i class="ph ph-check-circle mr-1.5 align-middle"></i> Sinyal Masuk';
      cardBorderClass = "border-success/30 bg-success/5";
    } else if (s.last_signal === "WAIT") {
      signalColorClass = "text-warning";
      signalText = '<i class="ph ph-clock mr-1.5 align-middle"></i> Tunggu';
    } else if (s.last_signal === "AVOID") {
      signalColorClass = "text-error";
      signalText = '<i class="ph ph-warning mr-1.5 align-middle"></i> Hindari';
    }

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
      <div class="card p-4 border ${cardBorderClass} transition duration-200">
        <div class="flex justify-between items-start mb-3">
          <div>
            <div class="text-base font-bold text-zinc-100 font-mono">${s.symbol}</div>
            <div class="text-xs text-muted mt-0.5">${tujuanMap[s.tujuan] || s.tujuan} · ${modalFmt}</div>
          </div>
          <button onclick="removeStock('${s.symbol}')" class="text-zinc-500 hover:text-error text-lg transition">
            <i class="ph ph-trash"></i>
          </button>
        </div>
        <div class="text-xs font-semibold ${signalColorClass} mb-4">${signalText}</div>
        ${s.last_alert ? `<div class="text-[10px] text-muted mb-4 font-mono">Terakhir Alert: ${lastAlert}</div>` : ""}
        <button onclick="analyzeStock('${s.symbol}', ${s.modal}, '${s.tujuan}')"
          class="w-full py-1.5 bg-zinc-50 hover:bg-zinc-200 text-zinc-950 rounded-md text-xs font-semibold transition flex items-center justify-center">
          <i class="ph ph-magnifying-glass mr-1.5"></i> Analisis AI
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
  if (!confirm(`Hapus ${symbol} dari monitor list?`)) return;
  await fetch(`/api/coach/watchlist/${symbol}`, { method: "DELETE" });
  await loadWatchlist();
}

async function analyzeStock(symbol, modal, tujuan) {
  const modalEl = document.getElementById("analysis-modal");
  const body = document.getElementById("modal-body");
  const title = document.getElementById("modal-title");
  if (!modalEl || !body || !title) return;

  title.textContent = `Analisis ${symbol}...`;
  body.innerHTML = `
    <div class="text-center py-8 text-muted">
      <i class="ph ph-arrows-clockwise animate-spin text-2xl mb-2 block mx-auto text-zinc-400"></i>
      <span class="text-xs">AI sedang membaca data dan menyusun alokasi lot...</span>
    </div>`;
  modalEl.style.display = "block";

  try {
    const resp = await fetch(`/api/coach/analyze/${symbol}?modal=${modal}&tujuan=${tujuan}`);
    if (!resp.ok) {
      const err = await resp.json();
      body.innerHTML = `<div class="text-error font-mono">Error: ${err.detail}</div>`;
      return;
    }
    const d = await resp.json();
    title.textContent = `${symbol} — Rekomendasi AI`;
    renderAnalysis(d, body);
  } catch (e) {
    body.innerHTML = `<div class="text-error font-mono">Request gagal: ${e.message}</div>`;
  }
}

function renderAnalysis(d, container) {
  let actionColorClass = "text-zinc-400";
  let actionBgClass = "bg-zinc-950 border-zinc-800";
  let actionIcon = '<i class="ph ph-circle text-3xl mb-1 block"></i>';
  let actionText = d.action;

  if (d.action === "ENTRY_NOW") {
    actionColorClass = "text-success";
    actionBgClass = "bg-success/5 border-success/20";
    actionIcon = '<i class="ph ph-check-circle text-success text-3xl mb-1 block"></i>';
    actionText = "MASUK SEKARANG";
  } else if (d.action === "WAIT") {
    actionColorClass = "text-warning";
    actionBgClass = "bg-warning/5 border-warning/20";
    actionIcon = '<i class="ph ph-clock text-warning text-3xl mb-1 block"></i>';
    actionText = "TUNGGU DULU";
  } else if (d.action === "AVOID") {
    actionColorClass = "text-error";
    actionBgClass = "bg-error/5 border-error/20";
    actionIcon = '<i class="ph ph-warning text-error text-3xl mb-1 block"></i>';
    actionText = "HINDARI";
  }

  const fmtRp = (v) => `Rp ${Number(v).toLocaleString("id-ID")}`;
  const reasonList = d.action === "ENTRY_NOW" ? (d.reason_entry || []) : (d.reason_wait || []);
  const gateTotal = d.snapshot?.gate_total || 8;

  container.innerHTML = `
    <div class="border rounded-lg p-4 mb-4 text-center ${actionBgClass}">
      <div>${actionIcon}</div>
      <div class="text-base font-extrabold ${actionColorClass}">${actionText}</div>
      <div class="text-[10px] text-muted mt-1 font-mono">AI Confidence: ${d.confidence}%</div>
    </div>

    <div class="text-xs text-zinc-300 mb-4 p-3 bg-zinc-900 border border-zinc-800 rounded-md leading-relaxed">
      ${d.summary || "-"}
    </div>

    ${d.action === "ENTRY_NOW" ? `
      <div class="bg-zinc-900 border border-zinc-800 rounded-md p-4 mb-4">
        <div class="text-[10px] text-muted mb-3 font-semibold uppercase tracking-wider">💰 SETUP ALOKASI MODAL</div>
        <div class="grid grid-cols-2 gap-4 text-xs">
          <div><div class="text-muted text-[10px]">Area Beli (Entry)</div><div class="text-zinc-100 font-bold font-mono">${fmtRp(d.entry_low)} - ${fmtRp(d.entry_high)}</div></div>
          <div><div class="text-muted text-[10px]">Stop Loss (Batas Risiko)</div><div class="text-error font-bold font-mono">${fmtRp(d.stop_loss)}</div></div>
          <div><div class="text-muted text-[10px]">Target Jual 1</div><div class="text-success font-bold font-mono">${fmtRp(d.target1)}</div></div>
          <div><div class="text-muted text-[10px]">Target Jual 2</div><div class="text-success font-bold font-mono">${fmtRp(d.target2)}</div></div>
          <div><div class="text-muted text-[10px]">Risk/Reward Ratio</div><div class="text-zinc-100 font-bold font-mono">1:${d.risk_reward}</div></div>
          ${d.suggested_lot > 0 ? `<div><div class="text-muted text-[10px]">Saran Jumlah Beli</div><div class="text-success font-extrabold font-mono">${d.suggested_lot} lot</div></div>` : ""}
        </div>
      </div>
    ` : ""}

    ${reasonList.length ? `
      <div class="mb-4">
        <div class="text-[10px] text-muted mb-2 font-semibold uppercase tracking-wider">💡 ALASAN UTAMA (${d.action === "ENTRY_NOW" ? "BULLISH" : "BEARISH"})</div>
        <div class="space-y-1">
          ${reasonList.slice(0, 4).map((r) => `<div class="text-xs text-zinc-300 py-1 border-b border-zinc-800/60 font-medium flex items-start"><i class="ph ph-caret-right text-muted mr-1.5 mt-0.5"></i> ${r}</div>`).join("")}
        </div>
      </div>
    ` : ""}

    ${d.what_to_wait ? `
      <div class="bg-zinc-900 border border-zinc-800 rounded-md p-3 mb-4">
        <div class="text-[10px] text-muted mb-1.5 font-semibold uppercase tracking-wider">⏳ KONDISI YANG DITUNGGU</div>
        <div class="text-xs text-warning leading-relaxed font-medium">${d.what_to_wait}</div>
      </div>
    ` : ""}

    ${d.warning?.length ? `
      <div class="mb-4">
        <div class="text-[10px] text-muted mb-2 font-semibold uppercase tracking-wider">🚨 RISIKO UTAMA</div>
        <div class="space-y-1">
          ${d.warning.slice(0, 3).map((w) => `<div class="text-xs text-error font-medium flex items-start"><i class="ph ph-warning mr-1.5 mt-0.5"></i> ${w}</div>`).join("")}
        </div>
      </div>
    ` : ""}

    ${d.snapshot ? `
      <div class="bg-zinc-950 border border-zinc-800 rounded-md p-3">
        <div class="text-[10px] text-muted mb-2.5 font-semibold uppercase tracking-wider">📊 DATA KONDISI MARKET</div>
        <div class="grid grid-cols-2 gap-x-4 gap-y-2 text-xs text-zinc-400 font-mono">
          <div>Harga: <span class="text-zinc-200">${fmtRp(d.snapshot.price)} (${d.snapshot.change_pct > 0 ? "+" : ""}${d.snapshot.change_pct}%)</span></div>
          <div>Tren: <span class="text-zinc-200">${d.snapshot.trend}</span></div>
          <div>RSI 14: <span class="text-zinc-200">${d.snapshot.rsi}</span></div>
          <div>Gate Score: <span class="text-zinc-200">${d.snapshot.gate_score}/${gateTotal}</span></div>
          <div>Volume: <span class="text-zinc-200">${d.snapshot.vol_ratio}x avg</span></div>
          <div>Tren IHSG: <span class="text-zinc-200">${d.snapshot.ihsg_trend}</span></div>
          <div>Stoch RSI: <span class="text-zinc-200">K ${d.snapshot.stoch_rsi_k} / D ${d.snapshot.stoch_rsi_d}</span></div>
          <div>Bollinger: <span class="text-zinc-200">${d.snapshot.bb_position}</span></div>
          <div>Pola Lilin: <span class="text-zinc-200">${d.snapshot.candle_pattern}</span></div>
          <div>Sentimen: <span class="text-zinc-200">${d.snapshot.sentiment_label} (${Number(d.snapshot.sentiment_score || 0).toFixed(1)})</span></div>
        </div>
      </div>
    ` : ""}

    <div class="text-[10px] text-muted mt-5 text-center leading-relaxed font-medium">
      <i class="ph ph-info mr-1 align-middle"></i> Bukan saran finansial. Keputusan akhir dan manajemen risiko sepenuhnya di tangan Anda.
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
    btn.innerHTML = '<i class="ph ph-arrows-clockwise animate-spin mr-1.5"></i> Scanning...';
  }

  await fetch("/api/coach/scan", { method: "POST" });
  setTimeout(async () => {
    await loadWatchlist();
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = '<i class="ph ph-arrows-clockwise mr-1.5"></i> Scan Sekarang';
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

    const runColorClass = status.running ? "text-success" : "text-error";
    statusEl.innerHTML = `
      Status Aktif: <span class="font-bold ${runColorClass}">${status.running ? "YA" : "TIDAK"}</span> ·
      Interval Cek: ${status.interval_sec || 0}s ·
      Sektor IHSG: ${(status.last_market_context && status.last_market_context.market_breadth) || "MIXED"} ·
      Alert Terkirim: ${status.alerts_logged || 0}
    `;

    const decisions = logs.decisions || [];
    if (!decisions.length) {
      logsEl.innerHTML = "Belum ada log keputusan.";
      return;
    }

    logsEl.innerHTML = decisions.map((row) => {
      let actionClass = "text-warning";
      if (row.action === "ENTRY_NOW") actionClass = "text-success";
      else if (row.action === "AVOID") actionClass = "text-error";

      return `
        <div class="p-3 border border-zinc-800 rounded-md mb-2 bg-zinc-950 font-mono">
          <div class="flex justify-between items-center text-xs">
            <span class="font-bold text-zinc-100">${row.symbol}</span>
            <span class="${actionClass} font-bold">${row.action} (${row.confidence}%)</span>
          </div>
          <div class="text-[10px] text-muted mt-1 leading-relaxed">
            MTF: ${row.trend_2m || "-"} / ${row.trend_15m || "-"} / ${row.trend_1d || "-"} ·
            Sentimen: ${row.sentiment_label || "NEUTRAL"} ·
            IHSG: ${row.market_breadth || "MIXED"}
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    // silent fail for logs polling
  }
}
