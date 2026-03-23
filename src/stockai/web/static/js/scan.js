let allResults = [];
let currentFilter = "ALL";
let source = null;

function redrawResults() {
    const root = document.getElementById("scan-results");
    root.innerHTML = "";
    const shown = allResults.filter((row) => currentFilter === "ALL" || row.status === currentFilter);
    shown.forEach((row) => {
        const wrap = document.createElement("div");
        wrap.innerHTML = window.renderSignalCard(row);
        const el = wrap.firstElementChild;
        el.addEventListener("click", () => {
            window.location.href = `/stock/${row.symbol}`;
        });
        root.appendChild(el);
    });
}

function startScan() {
    if (source) source.close();
    allResults = [];
    redrawResults();
    source = new EventSource("/api/scan/stream?index=ALL");
    source.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.event === "completed") {
            source.close();
            return;
        }
        const progress = data.progress || {};
        const bar = document.getElementById("scan-progress-bar");
        const text = document.getElementById("scan-progress-text");
        bar.style.width = `${progress.percent || 0}%`;
        text.textContent = `${progress.scanned || 0}/${progress.total || 0} ${progress.current_symbol || ""}`;
        if (data.result) {
            allResults.push(data.result);
            redrawResults();
        }
    };
}

document.getElementById("btn-run-scan").addEventListener("click", startScan);
document.querySelectorAll(".btn-filter").forEach((btn) => {
    btn.addEventListener("click", () => {
        document.querySelectorAll(".btn-filter").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        currentFilter = btn.dataset.filter;
        redrawResults();
    });
});

window.appFetch("/api/scan/last")
    .then((data) => {
        if (data.available) {
            allResults = data.results || [];
            redrawResults();
        }
    })
    .catch(() => {});
