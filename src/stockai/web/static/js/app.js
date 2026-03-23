window.toRupiah = function toRupiah(value) {
    const n = Number(value || 0);
    return new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(n);
};

window.toPct = function toPct(value, digits = 1) {
    const n = Number(value || 0);
    return `${n >= 0 ? "+" : ""}${n.toFixed(digits)}%`;
};

window.timeAgo = function timeAgo(iso) {
    if (!iso) return "-";
    const dt = new Date(iso);
    const diff = Math.max(0, Date.now() - dt.getTime());
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "baru saja";
    if (mins < 60) return `${mins} menit lalu`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs} jam lalu`;
    return `${Math.floor(hrs / 24)} hari lalu`;
};

window.appFetch = async function appFetch(url, options = {}) {
    const response = await fetch(url, options);
    if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `HTTP ${response.status}`);
    }
    return response.json();
};

window.fetchWithTimeout = async function fetchWithTimeout(url, timeout = 15000, options = {}) {
    const controller = new AbortController();
    const id = setTimeout(() => controller.abort(), timeout);
    try {
        const response = await fetch(url, { ...options, signal: controller.signal });
        clearTimeout(id);
        if (!response.ok) return null;
        return response.json();
    } catch (_err) {
        clearTimeout(id);
        return null;
    }
};

window.statusClass = function statusClass(status) {
    const s = String(status || "").toUpperCase();
    if (s === "READY") return "signal-ready";
    if (s === "WATCH") return "signal-watch";
    return "signal-rejected";
};

window.renderSignalCard = function renderSignalCard(item) {
    return `
        <div class="signal-card ${window.statusClass(item.status)} fade-in" data-symbol="${item.symbol}">
            <div class="flex items-center justify-between">
                <strong>${item.symbol}</strong>
                <span>${item.status} ${item.gate_passed || 0}/${item.gate_total || 6}</span>
            </div>
            <div class="mt-1 text-muted">${window.toRupiah(item.current_price || 0)}</div>
            <div class="mt-2 text-sm text-muted">
                SL: ${item.sl ? window.toRupiah(item.sl) : "-"} ·
                TP1: ${item.tp1 ? window.toRupiah(item.tp1) : "-"} ·
                R/R: ${item.rr ? `${item.rr}x` : "-"}
            </div>
            <div class="mt-2 text-sm text-muted">
                🔍 ${(item.smart_money || {}).signal || "NEUTRAL"} ·
                📊 ${(item.volume || {}).classification || "NORMAL"} ·
                💬 ${(item.sentiment || {}).label || "NEUTRAL"}
            </div>
            <div class="mt-2 text-sm text-muted">
                🎯 ${Math.round(((item.probability || {}).p5 || 0) * 100)}% prob naik 5% ·
                ${window.toPct(((item.probability || {}).expected || 0) * 100)}
            </div>
            <div class="mt-2 text-link">Lihat Detail →</div>
        </div>
    `;
};

async function loadSchedulerStatus() {
    const el = document.getElementById("next-scan-indicator");
    if (!el) return;
    const status = await window.fetchWithTimeout("/api/scheduler/status", 5000);
    if (!status || !status.jobs) return;
    const morning = status.jobs.find((j) => j.id === "morning_scan");
    if (morning?.next_run) {
        const parts = String(morning.next_run).split(" ");
        const hhmm = parts.length >= 3 ? parts[1].slice(0, 5) : String(morning.next_run);
        el.textContent = `⏱ Next scan: ${hhmm} WIB`;
    } else {
        el.textContent = "⏱ Next scan: -";
    }
}

document.addEventListener("DOMContentLoaded", () => {
    loadSchedulerStatus().catch(() => {});
});
