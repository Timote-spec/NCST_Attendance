/* =========================================================================
   NCST - Application Core (state, api, router, UI primitives)
   Loaded first. Exposes window.App and shared helpers.
   ========================================================================= */
(function () {
  "use strict";

  const API = "/api/v1";

  /* ---------- Icons (inline SVG strings — Lucide style) ---------- */
  const ICON = {
    /* Navigation icons (modern, minimal, professional) */
    dashboard: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    layoutDashboard: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>',
    users: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    graduationCap: '<path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>',
    briefcase: '<rect x="2" y="7" width="20" height="14" rx="2" ry="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>',
    userCheck: '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><polyline points="16 11 18 13 22 9"/>',
    calendar: '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><path d="m9 16 2 2 4-4"/>',
    calendarCheck: '<rect x="3" y="4" width="18" height="18" rx="2" ry="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/><path d="m9 16 2 2 4-4"/>',
    clock: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16.5 12"/>',
    clock3: '<circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16.5 12"/>',
    face: '<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><circle cx="12" cy="12" r="1"/><path d="M12 17v.01"/><path d="M9 10a1 1 0 0 0-1 1v1a1 1 0 0 0 1 1"/><path d="M15 10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1"/>',
    scanFace: '<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><circle cx="12" cy="12" r="1"/><path d="M12 17v.01"/><path d="M9 10a1 1 0 0 0-1 1v1a1 1 0 0 0 1 1"/><path d="M15 10a1 1 0 0 1 1 1v1a1 1 0 0 1-1 1"/>',
    creditCard: '<rect x="1" y="4" width="22" height="16" rx="2" ry="2"/><line x1="1" y1="10" x2="23" y2="10"/>',
    qrCode: '<rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="4" height="4"/><rect x="8" y="18" width="3" height="3"/>',
    shieldCheck: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/><polyline points="9 12 11 14 15 10"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10"/>',
    barChart: '<line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/>',
    barChart3: '<line x1="12" y1="20" x2="12" y2="10"/><line x1="18" y1="20" x2="18" y2="4"/><line x1="6" y1="20" x2="6" y2="16"/>',
    lineChart: '<polyline points="22 12 18 8 14 12 10 8 6 12 2 8"/><path d="M2 20h20"/>',
    bell: '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>',
    megaphone: '<path d="m3 11 18-5v12l-18-5z"/><path d="M11.6 16.8a3 3 0 1 1-5.8-1.6"/>',
    settings: '<circle cx="12" cy="12" r="3"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>',
    user: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="10" r="3"/><path d="M7 20.662V19a3 3 0 0 1 3-3h4a3 3 0 0 1 3 3v1.662"/>',
    userCircle: '<circle cx="12" cy="12" r="10"/><circle cx="12" cy="10" r="3"/><path d="M7 20.662V19a3 3 0 0 1 3-3h4a3 3 0 0 1 3 3v1.662"/>',
    badgeCheck: '<path d="M12 2l3.09 3.09 4.45.65.82 4.39L22 12l-1.64 3.09-.82 4.39-4.45.65L12 22l-3.09-3.09-4.45-.65-.82-4.39L2 12l1.64-3.09.82-4.39 4.45-.65z"/><polyline points="9 12 11 14 15 10"/>',
    check: '<path d="M12 2l3.09 3.09 4.45.65.82 4.39L22 12l-1.64 3.09-.82 4.39-4.45.65L12 22l-3.09-3.09-4.45-.65-.82-4.39L2 12l1.64-3.09.82-4.39 4.45-.65z"/><polyline points="9 12 11 14 15 10"/>',
    archive: '<rect x="2" y="3" width="20" height="5" rx="1"/><path d="M4 8v11a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8"/><path d="M10 12h4"/>',
    audit: '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    fileText: '<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>',
    camera: '<path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"/><circle cx="12" cy="13" r="4"/>',
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    download: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>',
    upload: '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>',
    plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
    edit: '<path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/>',
    trash: '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>',
    refresh: '<path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>',
    close: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    logout: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
    logOut: '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/>',
    menu: '<line x1="4" y1="6" x2="20" y2="6"/><line x1="4" y1="12" x2="20" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/>',
    clipboard: '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="M12 11h4"/><path d="M12 16h4"/><path d="M8 11h.01"/><path d="M8 16h.01"/>',
    alert: '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    checkCircle: '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/>',
    xCircle: '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6"/><path d="m9 9 6 6"/>',
    eye: '<path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    eyeOff: '<path d="M9.88 9.88a3 3 0 1 0 4.24 4.24"/><path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 10 7 10 7a13.16 13.16 0 0 1-1.67 2.68"/><path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 7 10 7a9.74 9.74 0 0 0 5.39-1.61"/><line x1="2" y1="2" x2="22" y2="22"/>'
  };

  function svg(path, size) {
    const dim = size ? ` width="${size}" height="${size}"` : "";
    return `<svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"${dim} focusable="false">${path}</svg>`;
  }

  /* ---------- App state ---------- */
  const App = {
    API,
    ICON,
    svg,
    _token: localStorage.getItem("ncst_token"),
    _user: (function () { try { return JSON.parse(localStorage.getItem("ncst_user")); } catch (e) { return null; } })(),
    get token() { return this._token; },
    get user() { return this._user; },
    isAuthed() { return !!this._token; },
    payload() { try { return JSON.parse(atob(this._token.split(".")[1])); } catch (e) { return null; } },
    role() { return this.payload()?.role || "STUDENT"; },
    uid() { return this.payload()?.sub; },
    name() { return this._user?.name || "User"; },
    setAuth(token, user) { this._token = token; this._user = user; localStorage.setItem("ncst_token", token); localStorage.setItem("ncst_user", JSON.stringify(user)); },
    clear() { this._token = null; this._user = null; localStorage.removeItem("ncst_token"); localStorage.removeItem("ncst_user"); },
    content() { return document.getElementById("content"); },
    setPageTitle(t) { const el = document.getElementById("page-title"); if (el) el.textContent = t; },
  };

  /* ---------- API ---------- */
  App.api = async function (path, opts = {}) {
    const isForm = opts.body instanceof FormData;
    const headers = Object.assign({}, opts.headers || {});
    if (!isForm) headers["Content-Type"] = "application/json";
    if (App.token) headers["Authorization"] = "Bearer " + App.token;
    const res = await fetch(API + path, Object.assign({}, opts, { headers }));
    if (res.status === 401 && App.token) {
      App.clear();
      toast("Session expired. Please sign in again.", "error");
      setTimeout(() => (window.location.href = "/login"), 800);
      throw new Error("Session expired");
    }
    const ct = res.headers.get("content-type") || "";
    const data = ct.includes("application/json") ? await res.json() : null;
    if (!res.ok) {
      const detail = data?.detail || (data?.message) || ("Error " + res.status);
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  };

  /* ---------- Formatting ---------- */
  App.esc = function (s) {
    if (s === null || s === undefined) return "";
    return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  };
  App.fmtDateTime = function (ts) {
    if (!ts) return "\u2014";
    try { return new Date(ts).toLocaleString("en-US", { timeZone: "Asia/Manila", month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit" }); }
    catch (e) { return String(ts); }
  };
  App.fmtDate = function (d) {
    if (!d) return "\u2014";
    try { return new Date(d).toLocaleDateString("en-US", { timeZone: "Asia/Manila", month: "short", day: "numeric", year: "numeric" }); }
    catch (e) { return String(d); }
  };
  App.fmtTime = function (t) { return t || "\u2014"; };
  App.initials = function (name) {
    if (!name) return "?";
    return name.split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();
  };
  App.badge = function (type, text, dot) {
    const cls = { primary: "badge-primary", success: "badge-success", warning: "badge-warning", danger: "badge-danger", muted: "badge-muted" }[type] || "badge-muted";
    return `<span class="badge ${cls}">${dot ? '<span class="badge-dot"></span>' : ""}${App.esc(text)}</span>`;
  };
  App.statusBadge = function (status) {
    const s = (status || "").toUpperCase();
    if (s === "ACTIVE" || s === "APPROVED" || s === "PRESENT" || s === "REGISTERED" || s === "OK") return App.badge("success", status);
    if (s === "ARCHIVED" || s === "REJECTED" || s === "ABSENT") return App.badge("danger", status);
    if (s === "PENDING" || s === "LATE" || s === "RE_REGISTRATION_PENDING") return App.badge("warning", status);
    return App.badge("muted", status);
  };

  /* ---------- UI primitives ---------- */
  function toast(msg, type = "info") {
    const c = document.getElementById("toast-container");
    if (!c) return;
    const icons = { success: ICON.checkCircle, error: ICON.xCircle, warning: ICON.alert, info: ICON.info };
    const el = document.createElement("div");
    el.className = "toast " + type;
    el.innerHTML = `<span class="toast-icon">${svg(icons[type] || icons.info, 18)}</span><span>${App.esc(msg)}</span>`;
    c.appendChild(el);
    setTimeout(() => { el.style.opacity = "0"; el.style.transition = "opacity .3s"; setTimeout(() => el.remove(), 300); }, 4000);
  }
  App.toast = toast;

  App.spinner = function (lg) { return `<span class="spinner ${lg ? "spinner-lg" : ""}"></span>`; };

  App.skeleton = function (lines = 3) {
    let s = "";
    for (let i = 0; i < lines; i++) s += `<div class="skeleton skeleton-line" style="width:${90 - i * 10}%"></div>`;
    return s;
  };

  App.emptyState = function (title, msg, icon = ICON.info, actionHtml = "") {
    const iconHtml = typeof icon === "string" && icon.startsWith("<svg") ? icon : svg(icon);
    return `<div class="empty-state"><div class="icon">${iconHtml}</div><h3>${App.esc(title)}</h3><p>${App.esc(msg)}</p>${actionHtml}</div>`;
  };

  /* In-app "route not found" view. Distinct from the server 404 so a missing
     client route is never silently redirected to the dashboard. */
  App.notFound = function (path) {
    App.setPageTitle("Not Found");
    return `<div class="empty-state" style="padding:3rem">
        <div class="icon">${svg(ICON.search)}</div>
        <h3>Page not found</h3>
        <p>No client route is registered for <code>${App.esc(path || "")}</code>.</p>
        <a class="btn btn-primary mt-2" href="#/dashboard/overview">Return to Dashboard</a>
      </div>`;
  };

  App.loadingBlock = function (text = "Loading\u2026") {
    return `<div class="text-center text-muted" style="padding:3rem;">${App.spinner(true)}<div class="mt-2">${App.esc(text)}</div></div>`;
  };

  App.alert = function (type, msg) {
    const icons = { error: ICON.xCircle, success: ICON.checkCircle, warning: ICON.alert, info: ICON.info };
    return `<div class="alert alert-${type}"><span>${svg(icons[type] || icons.info, 18)}</span><div>${App.esc(msg)}</div></div>`;
  };

  /* ---------- Modal ---------- */
  App.modal = function ({ title, body, footer, size, onOpen }) {
    App.closeModal();
    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    backdrop.innerHTML = `
      <div class="modal-card ${size === "lg" ? "lg" : ""}" role="dialog" aria-modal="true">
        <div class="modal-header"><h3>${title}</h3><button class="modal-close" data-close>&times;</button></div>
        <div class="modal-body">${body}</div>
        ${footer ? `<div class="modal-footer">${footer}</div>` : ""}
      </div>`;
    document.body.appendChild(backdrop);
    backdrop.addEventListener("click", (e) => {
      if (e.target === backdrop || e.target.hasAttribute("data-close")) App.closeModal();
    });
    document.addEventListener("keydown", escClose);
    if (typeof onOpen === "function") onOpen(backdrop);
    return backdrop;
  };
  App.closeModal = function () {
    document.querySelectorAll(".modal-backdrop").forEach((m) => m.remove());
    document.removeEventListener("keydown", escClose);
  };
  function escClose(e) { if (e.key === "Escape") App.closeModal(); }

  App.confirm = function (title, message, onConfirm, danger = false) {
    App.modal({
      title,
      body: `<p class="text-muted">${App.esc(message)}</p>`,
      footer: `<button class="btn btn-secondary" data-close>Cancel</button>
               <button class="btn ${danger ? "btn-danger" : "btn-primary"}" id="confirm-ok">Confirm</button>`,
      onOpen: (m) => {
        m.querySelector("#confirm-ok").addEventListener("click", () => { App.closeModal(); onConfirm(); });
      },
    });
  };

  /* ---------- Pagination component ---------- */
  App.pagination = function (total, page, pageSize, cb) {
    const pages = Math.max(1, Math.ceil(total / pageSize));
    const info = `Showing ${total === 0 ? 0 : (page - 1) * pageSize + 1}\u2013${Math.min(page * pageSize, total)} of ${total}`;
    let btns = "";
    btns += `<button class="btn btn-secondary btn-sm" ${page <= 1 ? "disabled" : ""} data-page="${page - 1}">Prev</button>`;
    const start = Math.max(1, page - 2), end = Math.min(pages, page + 2);
    if (start > 1) btns += `<button class="btn btn-ghost btn-sm" data-page="1">1</button>${start > 2 ? "<span class='text-muted'>\u2026</span>" : ""}`;
    for (let i = start; i <= end; i++) {
      btns += `<button class="btn btn-sm ${i === page ? "btn-primary" : "btn-secondary"}" data-page="${i}">${i}</button>`;
    }
    if (end < pages) btns += `${end < pages - 1 ? "<span class='text-muted'>\u2026</span>" : ""}<button class="btn btn-ghost btn-sm" data-page="${pages}">${pages}</button>`;
    btns += `<button class="btn btn-secondary btn-sm" ${page >= pages ? "disabled" : ""} data-page="${page + 1}">Next</button>`;
    const el = document.createElement("div");
    el.className = "pagination";
    el.innerHTML = `<span class="page-info">${info}</span>${btns}`;
    el.addEventListener("click", (e) => {
      const p = e.target.closest("[data-page]");
      if (p && !p.disabled) cb(parseInt(p.dataset.page, 10));
    });
    return el;
  };

  /* ---------- Router ---------- */
  const Router = {
    routes: {},
    add(pattern, handler) { this.routes[pattern] = handler; },
    async resolve() {
      if (App._stream) { App._stream.getTracks().forEach((t) => t.stop()); App._stream = null; }
      if (window._liveTimer) { clearInterval(window._liveTimer); window._liveTimer = null; }
      const hash = (location.hash || "#/dashboard/overview").slice(1);
      let handler = null, params = {};
      for (const [pattern, fn] of Object.entries(this.routes)) {
        const keys = [];
        const re = new RegExp("^" + pattern.replace(/:(\w+)/g, (_, k) => { keys.push(k); return "([^/]+)"; }) + "$");
        const m = re.exec(hash);
        if (m) { handler = fn; keys.forEach((k, i) => (params[k] = decodeURIComponent(m[i + 1]))); break; }
      }
      const isUnknown = !handler && hash && hash !== "/dashboard/overview";
      if (isUnknown) {
        App.content().innerHTML = App.notFound(hash);
      } else {
        if (!handler) handler = this.routes["/dashboard/overview"];
        try {
          await handler(params);
        } catch (err) {
          App.content().innerHTML = App.alert("error", "Failed to load this page: " + err.message);
        }
      }
      App.buildSidebar();
      const sb = document.getElementById("sidebar");
      const ov = document.getElementById("sidebar-overlay");
      if (sb) sb.classList.remove("open");
      if (ov) ov.classList.remove("open");
    },
    async init() {
      this.validateNav();
      if (App.role() === "ADMIN" && App.isAuthed()) {
        try {
          const me = await App.api("/admin/me");
          window.__mainAdminEmail = me.main_admin_email || "";
        } catch (e) { /* ignore */ }
      }
      window.addEventListener("hashchange", () => this.resolve());
      this.resolve();
    },
    /* Single-source-of-truth guard: every sidebar NAV link MUST have a
       matching registered route, otherwise clicking it 404s. Fail loud. */
    validateNav() {
      const nav = App.NAV || {};
      for (const role of Object.keys(nav)) {
        for (const it of nav[role]) {
          if (it.section) continue;
          if (!it.href) continue;
          if (!this.routes[it.href]) {
            console.error(
              "[router] NAV item \"" + it.label + "\" (" + it.href + ") for role " +
              role + " has NO registered route. Navigation to it will fail."
            );
          }
        }
      }
    },
  };
  App.router = Router;

  /* ---------- Sidebar ---------- */
  const NAV = {
    ADMIN: [
      { section: "Management" },
      { href: "/dashboard/overview", label: "Overview", icon: "layoutDashboard" },
      { href: "/dashboard/students", label: "Users", icon: "users" },
      { href: "/dashboard/admin-management", label: "Admin Management", icon: "userCheck", mainAdminOnly: true },
      { href: "/dashboard/attendance", label: "Attendance", icon: "calendarCheck" },
      { href: "/dashboard/approvals", label: "Approval Center", icon: "badgeCheck" },
      { section: "Communication" },
      { href: "/dashboard/announcements", label: "Announcements", icon: "megaphone" },
      { href: "/dashboard/audit", label: "Audit Logs", icon: "fileText" },
      { section: "Account" },
      // Admin-only “My Profile” intentionally removed per audit requirement.
      { section: "Operations" },
      { href: "/dashboard/scanner", label: "Live Scanner", icon: "scanFace" },
      { href: "/dashboard/rfid", label: "RFID Management", icon: "creditCard" },
      { href: "/dashboard/settings", label: "Settings", icon: "settings" },
    ],
    STAFF: [
      { href: "/dashboard/overview", label: "Overview", icon: "layoutDashboard" },
      { href: "/dashboard/attendance", label: "Attendance", icon: "calendarCheck" },
      { href: "/dashboard/students", label: "Student Directory", icon: "graduationCap" },
      { href: "/dashboard/announcements", label: "Announcements", icon: "megaphone" },
      { href: "/dashboard/scanner", label: "Live Scanner", icon: "scanFace" },
      { href: "/dashboard/profile", label: "My Profile", icon: "userCircle" },
    ],
    FACULTY: [
      { href: "/dashboard/overview", label: "Overview", icon: "layoutDashboard" },
      { href: "/dashboard/attendance", label: "Attendance", icon: "calendarCheck" },
      { href: "/dashboard/students", label: "Student Directory", icon: "graduationCap" },
      { href: "/dashboard/announcements", label: "Announcements", icon: "megaphone" },
      { href: "/dashboard/scanner", label: "Live Scanner", icon: "scanFace" },
      { href: "/dashboard/profile", label: "My Profile", icon: "userCircle" },
    ],
    STUDENT: [
      { href: "/dashboard/overview", label: "Dashboard", icon: "layoutDashboard" },
      { href: "/dashboard/attendance", label: "My Attendance", icon: "clock3" },
      { href: "/dashboard/announcements", label: "Announcements", icon: "megaphone" },
      { href: "/dashboard/notifications", label: "Notifications", icon: "bell" },
      { href: "/dashboard/profile", label: "My Profile", icon: "userCircle" },
      { href: "/dashboard/face", label: "Face Profile", icon: "scanFace" },
    ],
  };
  App.NAV = NAV;

  App.buildSidebar = function () {
    const role = App.role();
    const items = NAV[role] || NAV.STUDENT;
    const nav = document.getElementById("sidebar-nav");
    if (!nav) return;
    const current = location.hash.slice(1) || "/dashboard/overview";
    const isAdminMain = (window.__mainAdminEmail || "").toLowerCase() ===
      (App.role() === "ADMIN" ? App.name().toLowerCase() : "");
    let html = "";
    for (const it of items) {
      if (it.section) { html += `<div class="nav-section">${App.esc(it.section)}</div>`; continue; }
      if (it.mainAdminOnly && !isAdminMain) continue;
      const active = current === it.href ? " active" : "";
      const link = it.href[0] === "#" ? it.href : "#" + it.href;
      html += `<a href="${link}" class="${active}">${svg(ICON[it.icon] || ICON.dashboard)}<span>${App.esc(it.label)}</span></a>`;
    }
    nav.innerHTML = html;
    const brand = document.getElementById("brand-name");
    if (brand) brand.textContent = role === "ADMIN" ? "NCST Admin" : role === "STAFF" ? "NCST Staff" : role === "FACULTY" ? "NCST Faculty" : "NCST Student";
    const un = document.getElementById("user-name"); if (un) un.textContent = App.name();
    const av = document.getElementById("user-avatar"); if (av) av.textContent = App.initials(App.name());
  };

  App.toggleSidebar = function () {
    const s = document.getElementById("sidebar"), o = document.getElementById("sidebar-overlay");
    if (s) s.classList.toggle("open");
    if (o) o.classList.toggle("open");
  };

  /* ---------- Camera helper (scanner embed) ---------- */
  App.startCamera = async function (videoEl, deviceId) {
    const stream = await navigator.mediaDevices.getUserMedia({
      video: deviceId ? { deviceId: { exact: deviceId } } : { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
    });
    videoEl.srcObject = stream;
    App._stream = stream;
    await new Promise((r) => (videoEl.onloadedmetadata = r));
    await videoEl.play();
    return stream;
  };
  App.stopCamera = function () {
    if (App._stream) { App._stream.getTracks().forEach((t) => t.stop()); App._stream = null; }
  };
  App.captureFrame = function (videoEl, quality = 0.9) {
    const canvas = document.createElement("canvas");
    canvas.width = videoEl.videoWidth || 640;
    canvas.height = videoEl.videoHeight || 480;
    canvas.getContext("2d").drawImage(videoEl, 0, 0);
    return new Promise((res) => canvas.toBlob((b) => res(b), "image/jpeg", quality));
  };

  window.App = App;
})();
