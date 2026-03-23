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
            <div style="padding:12px 16px;color:#64748b;font-size:13px;">
                Tidak ada hasil untuk "<strong style="color:#94a3b8">${query || ""}</strong>"
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
                border-bottom:1px solid #0f172a;
                transition:background 0.1s;
            "
        >
            <div style="display:flex;align-items:center;gap:8px;">
                <span style="font-weight:700;font-size:14px;color:#f1f5f9;min-width:52px;">
                    ${highlightMatch(r.symbol, query)}
                </span>
                <span style="font-size:12px;color:#94a3b8;">
                    ${highlightMatch(r.name, query)}
                </span>
            </div>
            <span style="
                font-size:11px;color:#64748b;
                background:#0f172a;
                padding:2px 8px;border-radius:4px;
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
    background: #0f172a !important;
  }
  .search-item:hover {
    background: #0f172a !important;
  }
  #global-search:focus {
    border-color: #3b82f6 !important;
    box-shadow: 0 0 0 2px rgba(59,130,246,0.2);
  }
  .search-item mark {
    background: transparent;
    color: #3b82f6;
    font-weight: 700;
    text-decoration: underline;
    text-underline-offset: 2px;
  }
  .search-kbd {
    font-size: 11px;
    color: #475569;
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 4px;
    padding: 1px 6px;
    font-family: monospace;
    pointer-events: none;
  }
`;
document.head.appendChild(searchStyle);
