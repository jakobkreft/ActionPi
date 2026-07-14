"use strict";

// ------------------------------------------------------------------ //
// App state                                                          //
// ------------------------------------------------------------------ //
const state = {
    camera: null,        // last known camera state from /api/status
    clockOffset: 0,      // serverTime - clientTime (seconds), for offline countdown
    connected: false,
    media: [],           // gallery items
    filter: "all",
    selecting: false,
    selected: new Set(), // set of paths
    viewerList: [],      // items currently viewable in lightbox
    viewerIndex: 0,
    tlName: null,        // open timelapse folder name
};

const $ = (id) => document.getElementById(id);
const now = () => Date.now() / 1000;
const serverNow = () => now() + state.clockOffset;

// ------------------------------------------------------------------ //
// Networking helpers                                                 //
// ------------------------------------------------------------------ //
async function api(path, opts = {}, timeout = 5000) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), timeout);
    try {
        const res = await fetch(path, { ...opts, signal: ctrl.signal });
        if (!res.ok) throw new Error("HTTP " + res.status);
        return res;
    } finally {
        clearTimeout(t);
    }
}

async function postJSON(path, body) {
    return api(path, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
    });
}

// ------------------------------------------------------------------ //
// Status polling + connection handling                               //
// ------------------------------------------------------------------ //
async function poll() {
    try {
        const res = await api("/api/status", {}, 4000);
        const data = await res.json();
        const prevState = state.camera && state.camera.state;
        state.camera = data.camera;
        state.clockOffset = data.camera.server_time - now();
        setConnected(true);
        updateSystem(data.system);
        // When a capture finishes, refresh the gallery to show the new file.
        if (prevState && prevState !== "idle" && data.camera.state === "idle") {
            loadMedia();
        }
        renderLive();
    } catch (e) {
        setConnected(false);
        renderLive(); // keep counting down from last known state
    }
}

function setConnected(ok) {
    state.connected = ok;
    const el = $("conn");
    const rec = state.camera && state.camera.state && state.camera.state !== "idle";
    if (!ok) {
        el.textContent = "disconnected";
        el.className = "badge badge-off";
    } else if (rec) {
        el.textContent = state.camera.mock ? "recording (mock)" : "recording";
        el.className = "badge badge-rec";
    } else {
        el.textContent = state.camera && state.camera.mock ? "ready (mock)" : "ready";
        el.className = "badge badge-ok";
    }
}

function updateSystem(sys) {
    if (!sys) return;
    $("stat-temp").textContent = sys.cpu_temp == null ? "n/a" : sys.cpu_temp + " °C";
    const d = sys.disk;
    $("stat-disk-text").textContent = `${d.free_gb} GB free`;
    const bar = $("stat-disk-bar");
    bar.style.width = d.percent + "%";
    bar.style.background = d.percent > 90 ? "var(--danger)" : d.percent > 75 ? "var(--warn)" : "var(--accent)";
    updateBattery(sys.battery);
    updateWifi(sys.wifi);
}

function updateBattery(b) {
    const wrap = $("stat-battery");
    if (!b || typeof b.percent !== "number") {
        wrap.classList.add("hidden");
        return;
    }
    wrap.classList.remove("hidden");
    $("batt-pct").textContent = b.percent + "%";
    const fill = $("batt-fill");
    fill.style.width = Math.max(4, Math.min(100, b.percent)) + "%";
    fill.style.background = b.percent <= 15 ? "var(--danger)" : b.percent <= 40 ? "var(--warn)" : "var(--ok)";
    const parts = [];
    if (b.voltage != null) parts.push(b.voltage.toFixed(2) + " V");
    if (b.status) parts.push(b.status);
    $("batt-volt").textContent = parts.join(" · ");
    const charging = b.status === "charging" || b.status === "full";
    $("batt-bolt").classList.toggle("hidden", !charging);
}

function updateWifi(w) {
    if (!w) return;
    const s = w.connected === false ? "reconnecting…" : "ok";
    $("conn").title = `Wi-Fi watchdog: ${s} · ${w.reconnects} reconnect(s)`;
}

// ------------------------------------------------------------------ //
// Live capture banner + countdown (runs every second, even offline)  //
// ------------------------------------------------------------------ //
function fmtDuration(sec) {
    sec = Math.max(0, Math.round(sec));
    const h = Math.floor(sec / 3600);
    const m = Math.floor((sec % 3600) / 60);
    const s = sec % 60;
    if (h > 0) return `${h}h ${String(m).padStart(2, "0")}m ${String(s).padStart(2, "0")}s`;
    if (m > 0) return `${m}m ${String(s).padStart(2, "0")}s`;
    return `${s}s`;
}

function renderLive() {
    const cam = state.camera;
    const live = $("live");
    const panel = $("capture-panel");
    if (!cam || cam.state === "idle") {
        live.classList.add("hidden");
        panel.classList.remove("hidden");
        return;
    }
    live.classList.remove("hidden");
    panel.classList.add("hidden");
    live.classList.toggle("processing", cam.state === "processing");

    $("live-mode").textContent = cam.state === "processing" ? "Processing " + cam.mode : cam.mode;

    const timeEl = $("live-time");
    const subEl = $("live-sub");
    if (cam.state === "processing") {
        timeEl.textContent = "finishing…";
        subEl.textContent = cam.name || "";
    } else if (cam.ends_at) {
        const remaining = cam.ends_at - serverNow();
        if (remaining > 0) {
            timeEl.textContent = fmtDuration(remaining) + " left";
        } else {
            timeEl.textContent = "finishing…";
        }
        let sub = cam.name || "";
        if (cam.mode === "timelapse" && cam.interval) sub += ` · every ${cam.interval}s`;
        if (!state.connected) sub += " · estimated (offline)";
        subEl.textContent = sub;
    } else {
        // photo — no fixed end time
        timeEl.textContent = "capturing…";
        subEl.textContent = state.connected ? "" : "estimated (offline)";
    }
}

// ------------------------------------------------------------------ //
// Capture controls                                                   //
// ------------------------------------------------------------------ //
let captureMode = "photo";

function setupCapture() {
    document.querySelectorAll(".seg").forEach((b) => {
        b.addEventListener("click", () => {
            captureMode = b.dataset.mode;
            document.querySelectorAll(".seg").forEach((x) => x.classList.toggle("active", x === b));
            ["photo", "video", "timelapse"].forEach((m) =>
                $("mode-" + m).classList.toggle("hidden", m !== captureMode));
            updateTlEstimate();
        });
    });

    ["tl-interval", "tl-duration", "tl-unit"].forEach((id) =>
        $(id).addEventListener("input", updateTlEstimate));

    $("btn-start").addEventListener("click", startCapture);
    $("btn-stop").addEventListener("click", stopCapture);
    updateTlEstimate();
}

function updateTlEstimate() {
    const interval = Math.max(1, parseInt($("tl-interval").value) || 1);
    const dur = Math.max(1, parseInt($("tl-duration").value) || 1) * parseInt($("tl-unit").value);
    const frames = Math.floor(dur / interval);
    $("tl-estimate").textContent = `≈ ${frames} frames over ${fmtDuration(dur)}`;
}

async function startCapture() {
    const btn = $("btn-start");
    btn.disabled = true;
    try {
        let res;
        if (captureMode === "photo") {
            res = await postJSON("/api/capture/photo", {});
        } else if (captureMode === "video") {
            const duration = (parseInt($("video-duration").value) || 1) * parseInt($("video-unit").value);
            res = await postJSON("/api/capture/video", { duration });
        } else {
            const interval = parseInt($("tl-interval").value) || 1;
            const duration = (parseInt($("tl-duration").value) || 1) * parseInt($("tl-unit").value);
            res = await postJSON("/api/capture/timelapse", { interval, duration });
        }
        const cam = await res.json();
        state.camera = cam;
        if (cam.server_time) state.clockOffset = cam.server_time - now();
        renderLive();
        setConnected(true);
    } catch (e) {
        toast("Could not start capture", true);
    } finally {
        btn.disabled = false;
    }
}

async function stopCapture() {
    const btn = $("btn-stop");
    btn.disabled = true;
    try {
        const res = await postJSON("/api/capture/stop", {});
        state.camera = await res.json();
        renderLive();
    } catch (e) {
        toast("Could not stop", true);
    } finally {
        btn.disabled = false;
    }
}

// ------------------------------------------------------------------ //
// Gallery                                                            //
// ------------------------------------------------------------------ //
function fmtSize(bytes) {
    if (!bytes) return "";
    const u = ["B", "KB", "MB", "GB"];
    let i = 0, n = bytes;
    while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
    return `${n.toFixed(n < 10 && i > 0 ? 1 : 0)} ${u[i]}`;
}

function fmtDate(epoch) {
    if (!epoch) return "";
    const d = new Date(epoch * 1000);
    return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

async function loadMedia() {
    try {
        const res = await api("/api/media", {}, 8000);
        state.media = await res.json();
        renderGallery();
    } catch (e) {
        /* keep whatever we had */
    }
}

function renderGallery() {
    const grid = $("gallery");
    grid.innerHTML = "";
    const items = state.media.filter((m) => state.filter === "all" || m.kind === state.filter);
    $("gallery-empty").classList.toggle("hidden", items.length > 0);

    for (const item of items) {
        const card = document.createElement("div");
        card.className = "card" + (state.selected.has(item.path) ? " selected" : "");
        card.dataset.path = item.path;

        const label = item.kind === "video" ? "▶ video"
            : item.kind === "timelapse" ? `⧉ ${item.count} frames` : "photo";

        card.innerHTML = `
            <div class="pill">${label}</div>
            <div class="check">✓</div>
            <img class="thumb" src="${item.thumb}" loading="lazy"
                 onerror="this.outerHTML='<div class=&quot;thumb-fallback&quot;>${item.kind === "video" ? "▶" : "▦"}</div>'">
            <div class="meta">
                <div class="name">${item.name}</div>
                <div class="sub">${fmtDate(item.mtime)}${item.size ? " · " + fmtSize(item.size) : ""}</div>
            </div>`;

        card.addEventListener("click", () => onCardClick(item));
        grid.appendChild(card);
    }
    updateSelectionUI();
}

function onCardClick(item) {
    if (state.selecting) {
        toggleSelect(item.path);
        return;
    }
    if (item.kind === "timelapse") {
        openTimelapse(item.name);
    } else {
        const viewable = state.media.filter(
            (m) => (m.kind === "photo" || m.kind === "video") &&
                   (state.filter === "all" || m.kind === state.filter));
        openViewer(viewable, viewable.findIndex((m) => m.path === item.path));
    }
}

function setupTabs() {
    document.querySelectorAll(".tab").forEach((t) => {
        t.addEventListener("click", () => {
            state.filter = t.dataset.filter;
            document.querySelectorAll(".tab").forEach((x) => x.classList.toggle("active", x === t));
            renderGallery();
        });
    });
}

// ------------------------------------------------------------------ //
// Selection mode                                                     //
// ------------------------------------------------------------------ //
function setupSelection() {
    $("btn-select").addEventListener("click", () => setSelecting(!state.selecting));
    $("btn-cancel-select").addEventListener("click", () => setSelecting(false));
    $("btn-del-selected").addEventListener("click", deleteSelected);
    $("btn-dl-selected").addEventListener("click", downloadSelected);
}

function setSelecting(on) {
    state.selecting = on;
    document.body.classList.toggle("selecting", on);
    $("select-toolbar").classList.toggle("hidden", !on);
    $("btn-select").textContent = on ? "Done" : "Select";
    if (!on) {
        state.selected.clear();
        renderGallery();
    }
}

function toggleSelect(path) {
    if (state.selected.has(path)) state.selected.delete(path);
    else state.selected.add(path);
    const card = document.querySelector(`.card[data-path="${cssEscape(path)}"]`);
    if (card) card.classList.toggle("selected", state.selected.has(path));
    updateSelectionUI();
}

function updateSelectionUI() {
    const n = state.selected.size;
    $("select-count").textContent = `${n} selected`;
    $("btn-del-selected").disabled = n === 0;
    $("btn-dl-selected").disabled = n === 0;
}

function downloadSelected() {
    if (state.selected.size === 0) return;
    const qs = [...state.selected].map((p) => "path=" + encodeURIComponent(p)).join("&");
    triggerDownload("/api/download?" + qs);
}

async function deleteSelected() {
    if (state.selected.size === 0) return;
    if (!confirm(`Delete ${state.selected.size} item(s)? This cannot be undone.`)) return;
    await doDelete([...state.selected]);
    setSelecting(false);
}

// ------------------------------------------------------------------ //
// Viewer (lightbox)                                                  //
// ------------------------------------------------------------------ //
function openViewer(list, index) {
    if (index < 0 || !list.length) return;
    state.viewerList = list;
    state.viewerIndex = index;
    $("viewer").classList.remove("hidden");
    renderViewer();
}

function renderViewer() {
    const item = state.viewerList[state.viewerIndex];
    if (!item) return;
    $("viewer-title").textContent = item.name;
    const content = $("viewer-content");
    content.innerHTML = item.kind === "video"
        ? `<video src="${item.url}" controls autoplay playsinline></video>`
        : `<img src="${item.url}" alt="${item.name}">`;
    $("viewer-download").href = item.url + "?download=1";
    const multi = state.viewerList.length > 1;
    $("viewer-prev").classList.toggle("hidden", !multi);
    $("viewer-next").classList.toggle("hidden", !multi);
}

function setupViewer() {
    $("viewer-close").addEventListener("click", closeViewer);
    $("viewer-prev").addEventListener("click", () => stepViewer(-1));
    $("viewer-next").addEventListener("click", () => stepViewer(1));
    $("viewer-delete").addEventListener("click", async () => {
        const item = state.viewerList[state.viewerIndex];
        if (!item) return;
        if (!confirm(`Delete ${item.name}?`)) return;
        await doDelete([item.path]);
        state.viewerList.splice(state.viewerIndex, 1);
        if (!state.viewerList.length) closeViewer();
        else { state.viewerIndex = Math.min(state.viewerIndex, state.viewerList.length - 1); renderViewer(); }
    });
    document.addEventListener("keydown", (e) => {
        if ($("viewer").classList.contains("hidden")) return;
        if (e.key === "Escape") closeViewer();
        if (e.key === "ArrowLeft") stepViewer(-1);
        if (e.key === "ArrowRight") stepViewer(1);
    });
}

function stepViewer(d) {
    const n = state.viewerList.length;
    state.viewerIndex = (state.viewerIndex + d + n) % n;
    renderViewer();
}

function closeViewer() {
    $("viewer").classList.add("hidden");
    $("viewer-content").innerHTML = "";
}

// ------------------------------------------------------------------ //
// Timelapse frame browser                                            //
// ------------------------------------------------------------------ //
async function openTimelapse(name) {
    state.tlName = name;
    $("tlview").classList.remove("hidden");
    $("tlview-title").textContent = name;
    $("tlview-download").href = "/api/download?path=" + encodeURIComponent("timelapses/" + name);
    const grid = $("tlview-grid");
    grid.innerHTML = "<p class='empty'>Loading…</p>";
    try {
        const res = await api("/api/media/timelapse/" + encodeURIComponent(name));
        const data = await res.json();
        grid.innerHTML = "";
        const viewList = data.frames.map((f) => ({ ...f, kind: "photo" }));
        data.frames.forEach((f, i) => {
            const card = document.createElement("div");
            card.className = "card";
            card.innerHTML = `<img class="thumb" src="${f.url}" loading="lazy">
                <div class="meta"><div class="name">${f.name}</div></div>`;
            card.addEventListener("click", () => openViewer(viewList, i));
            grid.appendChild(card);
        });
        if (!data.frames.length) grid.innerHTML = "<p class='empty'>No frames.</p>";
    } catch (e) {
        grid.innerHTML = "<p class='empty'>Could not load frames.</p>";
    }
}

function setupTimelapseView() {
    $("tlview-close").addEventListener("click", () => {
        $("tlview").classList.add("hidden");
        state.tlName = null;
    });
}

// ------------------------------------------------------------------ //
// Delete / download helpers                                          //
// ------------------------------------------------------------------ //
async function doDelete(paths) {
    try {
        await postJSON("/api/delete", { paths });
        toast(`Deleted ${paths.length} item(s)`);
        state.selected.clear();
        await loadMedia();
    } catch (e) {
        toast("Delete failed", true);
    }
}

function triggerDownload(url) {
    const a = document.createElement("a");
    a.href = url;
    a.download = "";
    document.body.appendChild(a);
    a.click();
    a.remove();
}

// ------------------------------------------------------------------ //
// Power                                                              //
// ------------------------------------------------------------------ //
function setupPower() {
    $("btn-shutdown").addEventListener("click", async () => {
        if (!confirm("Shut down the ActionPi? You will lose connection.")) return;
        try { await postJSON("/api/shutdown", {}); toast("Shutting down…"); } catch (e) {}
    });
    $("btn-reboot").addEventListener("click", async () => {
        if (!confirm("Reboot the ActionPi?")) return;
        try { await postJSON("/api/reboot", {}); toast("Rebooting…"); } catch (e) {}
    });
}

// ------------------------------------------------------------------ //
// Debug screen (diagnostics + live logs)                             //
// ------------------------------------------------------------------ //
let debugTimer = null;
let logRecords = [];
let logSeq = 0;

function setupDebug() {
    $("btn-debug").addEventListener("click", openDebug);
    $("debug-close").addEventListener("click", closeDebug);
    $("log-level").addEventListener("change", renderLogs);
}

async function openDebug() {
    $("debug").classList.remove("hidden");
    logRecords = [];
    logSeq = 0;
    $("log-console").innerHTML = "";
    await refreshDiag();
    await pollLogs();
    clearInterval(debugTimer);
    let ticks = 0;
    debugTimer = setInterval(async () => {
        await pollLogs();
        if (++ticks % 3 === 0) refreshDiag();
    }, 2000);
}

function closeDebug() {
    $("debug").classList.add("hidden");
    clearInterval(debugTimer);
    debugTimer = null;
}

async function refreshDiag() {
    try {
        const res = await api("/api/debug", {}, 6000);
        renderDiag(await res.json());
    } catch (e) { /* stay on last snapshot */ }
}

async function pollLogs() {
    try {
        const res = await api("/api/logs?after=" + logSeq, {}, 6000);
        const recs = (await res.json()).records || [];
        if (recs.length) {
            for (const r of recs) {
                logRecords.push(r);
                if (r.seq > logSeq) logSeq = r.seq;
            }
            if (logRecords.length > 1200) logRecords = logRecords.slice(-1200);
            renderLogs();
        }
    } catch (e) { /* ignore while disconnected */ }
}

function renderLogs() {
    const min = { DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40 }[$("log-level").value] || 0;
    const con = $("log-console");
    const atBottom = con.scrollHeight - con.scrollTop - con.clientHeight < 40;
    con.innerHTML = logRecords.filter((r) => r.levelno >= min).map(logLineHTML).join("");
    if (atBottom) con.scrollTop = con.scrollHeight;
}

function logLineHTML(r) {
    const t = new Date(r.ts * 1000).toLocaleTimeString();
    let s = `<div class="log-line"><span class="lt">${t}</span> ` +
        `<span class="lvl-${r.level}">${r.level}</span> ` +
        `<span class="ln">${esc(r.name)}</span> ${esc(r.msg)}</div>`;
    if (r.exc) s += `<div class="log-exc">${esc(r.exc)}</div>`;
    return s;
}

function renderDiag(d) {
    const b = d.battery || {};
    let bBadge;
    if (b.mock) bBadge = ["mock", "b-warn"];
    else if (b.available && b.bus_open) bBadge = b.reads_ok ? ["ok", "b-ok"] : ["opened", "b-warn"];
    else bBadge = ["unavailable", "b-err"];

    const c = d.camera || {};
    const w = d.wifi || {};
    let wBadge;
    if (!w.enabled) wBadge = ["disabled", "b-mute"];
    else if (w.connected === false) wBadge = ["reconnecting", "b-err"];
    else if (w.connected) wBadge = ["connected", "b-ok"];
    else wBadge = ["starting", "b-warn"];

    const cards = [
        diagCard("Battery", bBadge, b),
        diagCard("Camera", c.mock ? ["mock", "b-warn"] : ["ready", "b-ok"],
            { mock: c.mock, state: c.state, ...(c.tools || {}) }),
        diagCard("Wi-Fi", wBadge, w),
        diagCard("System", ["", "b-mute"], flattenSystem(d.system)),
        diagCard("Host", ["", "b-mute"],
            { python: d.python, platform: d.platform, base_dir: d.base_dir, log_file: d.log_file }),
    ];
    $("diag-cards").innerHTML = cards.join("");
}

function flattenSystem(s) {
    if (!s) return {};
    const out = { cpu_temp: s.cpu_temp };
    if (s.disk) { out.disk_free_gb = s.disk.free_gb; out.disk_used_pct = s.disk.percent; }
    if (s.battery) { out.battery_pct = s.battery.percent; out.battery_v = s.battery.voltage; }
    return out;
}

function diagCard(title, badge, obj) {
    const rows = Object.entries(obj)
        .map(([k, v]) => `<span class="k">${esc(k)}</span><span class="v">${esc(formatValue(v))}</span>`)
        .join("");
    const badgeHTML = badge[0] ? `<span class="diag-badge ${badge[1]}">${esc(badge[0])}</span>` : "";
    return `<div class="diag-card"><h4>${esc(title)}${badgeHTML}</h4><div class="diag-kv">${rows}</div></div>`;
}

function formatValue(v) {
    if (v === null || v === undefined) return "—";
    if (typeof v === "boolean") return v ? "yes" : "no";
    if (typeof v === "object") return JSON.stringify(v);
    return String(v);
}

// ------------------------------------------------------------------ //
// Utilities                                                          //
// ------------------------------------------------------------------ //
let toastTimer = null;
function toast(msg, isErr) {
    const el = $("toast");
    el.textContent = msg;
    el.className = "toast" + (isErr ? " err" : "");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add("hidden"), 3000);
}

function cssEscape(s) {
    return (window.CSS && CSS.escape) ? CSS.escape(s) : s.replace(/["\\]/g, "\\$&");
}

function esc(s) {
    return String(s).replace(/[&<>"]/g, (c) =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

// ------------------------------------------------------------------ //
// Boot                                                               //
// ------------------------------------------------------------------ //
function init() {
    setupCapture();
    setupTabs();
    setupSelection();
    setupViewer();
    setupTimelapseView();
    setupPower();
    setupDebug();

    poll();
    loadMedia();
    setInterval(poll, 2500);   // sync with server
    setInterval(renderLive, 1000); // local countdown, keeps ticking offline
}

document.addEventListener("DOMContentLoaded", init);
