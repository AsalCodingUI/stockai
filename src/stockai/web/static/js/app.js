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
    if (s === "READY" || s === "A+" || s === "A") return "signal-ready";
    if (s === "WATCH" || s === "B") return "signal-watch";
    return "signal-rejected";
};

window.renderSignalCard = function renderSignalCard(item) {
    let statusText = item.status;
    let badgeClass = "badge-rejected";
    if (item.status === "A+" || item.status === "A") {
        statusText = `GRADE ${item.status}`;
        badgeClass = "badge-ready font-extrabold";
    } else if (item.status === "B") {
        statusText = "GRADE B";
        badgeClass = "badge-watch font-extrabold";
    } else if (item.status === "READY") {
        statusText = "BUY SIGNAL";
        badgeClass = "badge-ready font-extrabold";
    } else if (item.status === "WATCH") {
        statusText = "MONITORED";
        badgeClass = "badge-watch font-extrabold";
    }
    
    let layerBreakdown = "";
    if (item.layer_score && item.layer_score.layers) {
        const layers = item.layer_score.layers;
        layerBreakdown = `
            <div class="mt-3 pt-2.5 border-t border-zinc-800/80">
                <div class="text-[10px] uppercase tracking-wider text-zinc-500 font-semibold mb-1.5">Confluence Layers</div>
                <div class="grid grid-cols-5 gap-1 text-center">
                    <div class="px-0.5 py-0.5 rounded text-[8px] font-bold ${layers.trend.passed ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-zinc-800/50 text-zinc-600'}" title="${(layers.trend.reasons || []).join('\n')}">Trend</div>
                    <div class="px-0.5 py-0.5 rounded text-[8px] font-bold ${layers.setup.passed ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-zinc-800/50 text-zinc-600'}" title="${(layers.setup.reasons || []).join('\n')}">Setup</div>
                    <div class="px-0.5 py-0.5 rounded text-[8px] font-bold ${layers.momentum.passed ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-zinc-800/50 text-zinc-600'}" title="${(layers.momentum.reasons || []).join('\n')}">Mom</div>
                    <div class="px-0.5 py-0.5 rounded text-[8px] font-bold ${layers.volume.passed ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-zinc-800/50 text-zinc-600'}" title="${(layers.volume.reasons || []).join('\n')}">Vol</div>
                    <div class="px-0.5 py-0.5 rounded text-[8px] font-bold ${layers.fundamental.passed ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-zinc-800/50 text-zinc-600'}" title="${(layers.fundamental.reasons || []).join('\n')}">Fund</div>
                </div>
            </div>
        `;
    }
    
    return `
        <div class="signal-card ${window.statusClass(item.status)} fade-in" data-symbol="${item.symbol}">
            <div class="flex items-center justify-between mb-2">
                <strong class="font-mono text-zinc-100">${item.symbol}</strong>
                <span class="badge ${badgeClass}">${statusText}</span>
            </div>
            <div class="text-base font-bold text-zinc-200 font-mono">${window.toRupiah(item.current_price || 0)}</div>
            <div class="mt-2 text-xs text-muted leading-relaxed">
                Entry Mid: ~${window.toRupiah(item.current_price || 0)} ·
                Risk/Reward: <span class="font-bold text-zinc-300 font-mono">${item.rr ? `${item.rr}x` : "-"}</span>
            </div>
            <div class="mt-2 text-xs text-muted flex items-center gap-1.5 flex-wrap">
                <span class="inline-flex items-center"><i class="ph ph-magnifying-glass text-zinc-500 mr-1"></i> ${(item.smart_money || {}).signal || "NEUTRAL"}</span>
                <span class="text-zinc-700">|</span>
                <span class="inline-flex items-center"><i class="ph ph-chart-bar text-zinc-500 mr-1"></i> ${(item.volume || {}).classification || "NORMAL"}</span>
                <span class="text-zinc-700">|</span>
                <span class="inline-flex items-center"><i class="ph ph-chat-centered-text text-zinc-500 mr-1"></i> ${(item.sentiment || {}).label || "NEUTRAL"}</span>
            </div>
            <div class="mt-2 text-[10px] text-muted flex items-center font-mono">
                <i class="ph ph-target mr-1 text-xs text-zinc-500"></i> ${Math.round(((item.probability || {}).p5 || 0) * 100)}% prob naik 5% · Expected: ${window.toPct(((item.probability || {}).expected || 0) * 100)}
            </div>
            ${layerBreakdown}
            <div class="mt-3 text-xs text-link font-medium flex items-center justify-end">Lihat Detail <i class="ph ph-caret-right ml-1"></i></div>
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

// Global Stock Search
const searchInput = document.getElementById("global-search");
const searchDropdown = document.getElementById("search-dropdown");
let searchTimeout = null;

function showDropdown() {
    if (!searchDropdown) return;
    searchDropdown.style.display = "block";
}

function hideDropdown() {
    if (!searchDropdown) return;
    searchDropdown.style.display = "none";
    searchDropdown.innerHTML = "";
}

function setActiveItem(items, nextIndex) {
    items.forEach((item) => item.classList.remove("active"));
    if (nextIndex >= 0 && nextIndex < items.length) {
        items[nextIndex].classList.add("active");
        items[nextIndex].scrollIntoView({ block: "nearest" });
    }
}

function highlightMatch(text, query) {
    if (!query || !text) return text;
    const escaped = String(query).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const regex = new RegExp(`(${escaped})`, "gi");
    return String(text).replace(regex, "<mark>$1</mark>");
}

function renderDropdown(results, query) {
    if (!searchDropdown) return;
    if (!results.length) {
        searchDropdown.innerHTML = `
            <div style="padding:12px 16px;color:var(--color-text-muted);font-size:13px;">
                Tidak ada hasil untuk "<strong style="color:var(--color-text-secondary)">${query || ""}</strong>"
            </div>
        `;
        showDropdown();
        return;
    }

    searchDropdown.innerHTML = results.map((r, i) => `
        <div
            class="search-item ${i === 0 ? "active" : ""}"
            data-url="${r.url}"
            onclick="window.location.href='${r.url}'"
            style="
                display:flex;
                align-items:center;
                justify-content:space-between;
                padding:10px 16px;
                cursor:pointer;
                border-bottom:1px solid var(--color-border);
                transition:background 0.1s;
            "
        >
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-weight:700;font-size:14px;color:var(--color-text-primary);min-width:52px;font-family:var(--font-family-mono);">
                    ${highlightMatch(r.symbol, query)}
                </span>
                <span style="font-size:12px;color:var(--color-text-secondary);">
                    ${highlightMatch(r.name, query)}
                </span>
            </div>
            <span style="
                font-size:11px;color:var(--color-text-muted);
                background:var(--color-bg-tertiary);
                padding:2px 8px;border-radius:var(--radius-sm);
                white-space:nowrap;
            ">${r.sector}</span>
        </div>
    `).join("");

    const items = searchDropdown.querySelectorAll(".search-item");
    items.forEach((item) => {
        item.addEventListener("mouseenter", () => {
            items.forEach((el) => el.classList.remove("active"));
            item.classList.add("active");
        });
    });
    showDropdown();
}

async function fetchSearch(query) {
    if (!query || query.length < 2) {
        hideDropdown();
        return;
    }
    try {
        const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`);
        if (!response.ok) {
            hideDropdown();
            return;
        }
        const data = await response.json();
        renderDropdown(data.results || [], query);
    } catch (_err) {
        hideDropdown();
    }
}

if (searchInput && searchDropdown) {
    const searchBadge = document.getElementById("search-shortcut-badge");
    searchInput.addEventListener("focus", () => {
        if (searchBadge) searchBadge.style.display = "none";
    });
    searchInput.addEventListener("blur", () => {
        setTimeout(() => {
            if (searchBadge) searchBadge.style.display = "inline";
        }, 200);
    });

    searchInput.addEventListener("input", (event) => {
        clearTimeout(searchTimeout);
        const query = String(event.target.value || "").trim();
        if (query.length < 2) {
            hideDropdown();
            return;
        }
        searchTimeout = setTimeout(() => fetchSearch(query), 250);
    });

    searchInput.addEventListener("keydown", (event) => {
        const items = Array.from(searchDropdown.querySelectorAll(".search-item"));
        const active = searchDropdown.querySelector(".search-item.active");
        const idx = items.indexOf(active);

        if (event.key === "ArrowDown") {
            event.preventDefault();
            const next = Math.min(items.length - 1, idx + 1);
            setActiveItem(items, next < 0 ? 0 : next);
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            const prev = Math.max(0, idx - 1);
            setActiveItem(items, prev);
        } else if (event.key === "Enter") {
            event.preventDefault();
            if (!items.length) return;
            const target = searchDropdown.querySelector(".search-item.active") || items[0];
            const url = target?.dataset?.url;
            if (url) window.location.href = url;
        } else if (event.key === "Escape") {
            hideDropdown();
            searchInput.blur();
        }
    });

    document.addEventListener("click", (event) => {
        if (!event.target.closest(".search-container")) {
            hideDropdown();
        }
    });

    document.addEventListener("keydown", (event) => {
        const tag = (document.activeElement?.tagName || "").toUpperCase();
        const isTyping = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";

        if (event.key === "/" && !isTyping) {
            event.preventDefault();
            searchInput.focus();
            searchInput.select();
            return;
        }

        if (event.key.toLowerCase() === "k" && (event.metaKey || event.ctrlKey)) {
            event.preventDefault();
            searchInput.focus();
            searchInput.select();
        }
    });
}

const searchStyle = document.createElement("style");
searchStyle.textContent = `
  .search-item.active {
    background: var(--color-bg-hover) !important;
  }
  .search-item:hover {
    background: var(--color-bg-hover) !important;
  }
  #global-search:focus {
    border-color: var(--color-border-hover) !important;
  }
  .search-item mark {
    background: transparent;
    color: var(--color-primary) !important;
    font-weight: 700;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .search-kbd {
    font-size: 11px;
    color: var(--color-text-muted) !important;
    background: var(--color-bg-tertiary) !important;
    border: 1px solid var(--color-border) !important;
    border-radius: var(--radius-sm) !important;
    padding: 1px 6px;
    font-family: monospace;
    pointer-events: none;
  }
`;
document.head.appendChild(searchStyle);
