/* =========================================================================
   NCST — Admin portal pages (student management, approvals, audit, settings)
   Also serves the staff "Student Directory" via /dashboard/students.
   ========================================================================= */
(function () {
  "use strict";
  const App = window.App;
  const I = App.ICON;
  const svg = App.svg;

  const Admin = {
    /* ---------------- Students / Directory ---------------- */
    studentsPage() {
      const role = App.role();
      if (role === "STAFF" || role === "FACULTY") return Admin.directoryPage();
      App.setPageTitle("Student Management");
      App.content().innerHTML = `
        <div class="page-header">
          <div><h1>Student & User Management</h1><p>Register, edit, archive, and manage institutional accounts.</p></div>
          <div class="page-actions">
            <button class="btn btn-secondary" onclick="Admin.openBulkImport()">${svg(I.upload)} Bulk Import</button>
            <button class="btn btn-primary" onclick="Admin.openAddStudent()">${svg(I.plus)} Add User</button>
          </div>
        </div>
        <div class="card">
          <div class="toolbar">
            <div class="search">${svg(I.search)}<input class="form-control" id="usr-search" placeholder="Search name or ID…"></div>
            <select class="form-control" id="usr-role" style="max-width:150px"><option value="">All roles</option><option value="STUDENT">Student</option><option value="STAFF">Staff</option><option value="FACULTY">Faculty</option></select>
            <select class="form-control" id="usr-status" style="max-width:150px"><option value="">All status</option><option value="ACTIVE">Active</option><option value="ARCHIVED">Archived</option></select>
            <button class="btn btn-primary" onclick="Admin.loadStudents(1)">${svg(I.search)} Filter</button>
          </div>
          <div id="usr-table">${App.loadingBlock("Loading users…")}</div>
          <div id="usr-pager"></div>
        </div>`;
      App.content().querySelector("#usr-search").addEventListener("keydown", (e) => { if (e.key === "Enter") Admin.loadStudents(1); });
      Admin.loadStudents(1);
    },

    directoryPage() {
      App.setPageTitle("Student Directory");
      App.content().innerHTML = `
        <div class="page-header"><div><h1>Student Directory</h1><p>Search and view enrolled students (read-only).</p></div></div>
        <div class="card">
          <div class="toolbar">
            <div class="search">${svg(I.search)}<input class="form-control" id="usr-search" placeholder="Search name or ID…"></div>
            <select class="form-control" id="usr-role" style="max-width:150px"><option value="">All roles</option><option value="STUDENT">Student</option><option value="STAFF">Staff</option><option value="FACULTY">Faculty</option></select>
            <select class="form-control" id="usr-status" style="max-width:150px"><option value="">All status</option><option value="ACTIVE">Active</option><option value="ARCHIVED">Archived</option></select>
            <button class="btn btn-primary" onclick="Admin.loadStudents(1)">${svg(I.search)} Filter</button>
          </div>
          <div id="usr-table">${App.loadingBlock("Loading…")}</div>
          <div id="usr-pager"></div>
        </div>`;
      App.content().querySelector("#usr-search").addEventListener("keydown", (e) => { if (e.key === "Enter") Admin.loadStudents(1); });
      Admin.loadStudents(1);
    },

    async loadStudents(page) {
      Admin._usrPage = page || 1;
      const search = document.getElementById("usr-search")?.value || "";
      const roleFilter = document.getElementById("usr-role")?.value || "";
      const status = document.getElementById("usr-status")?.value || "";
      const wrap = document.getElementById("usr-table");
      const pager = document.getElementById("usr-pager");
      const isStaff = App.role() === "STAFF" || App.role() === "FACULTY";
      wrap.innerHTML = App.loadingBlock("Loading…");
      try {
        let rows, total;
        if (isStaff) {
          const params = new URLSearchParams();
          if (search) params.set("search", search);
          if (roleFilter) params.set("role", roleFilter);
          if (status) params.set("status", status);
          const qs = params.toString();
          rows = await App.api(`/staff/students${qs ? `?${qs}` : ""}`);
          total = rows.length;
        } else {
          const q = `?page=${page}&page_size=25` + (search ? `&search=${encodeURIComponent(search)}` : "") + (roleFilter ? `&role=${roleFilter}` : "") + (status ? `&status=${status}` : "");
          const data = await App.api(`/admin/users${q}`);
          rows = data.items || [];
          total = data.total || rows.length;
        }
        if (!rows.length) { wrap.innerHTML = App.emptyState("No users found", "Try adjusting your filters or add a new user.", I.users); pager.innerHTML = ""; return; }
        const isAdmin = App.role() === "ADMIN";
        const photo = (uid) => `<img src="${App.API}/images/${App.esc(uid)}" alt="" style="width:30px;height:30px;border-radius:50%;object-fit:cover;background:var(--surface-2);vertical-align:middle;margin-right:6px;" onerror="this.style.display='none'">`;
        const hasQr = (u) => u.qr_token ? App.badge("success", "✓", true) : App.badge("muted", "—");
        const hasRfid = (u) => u.rfid_uid ? `<code style="font-size:.8rem;background:var(--surface-2);padding:2px 7px;border-radius:5px">${App.esc(u.rfid_uid)}</code>` : `<span class="text-muted">—</span>`;
        const body = rows.map((u) => `<tr>
          <td>${photo(u.user_id)}</td>
          <td class="cell-strong">${App.esc(u.first_name + " " + u.last_name)}</td>
          <td>${App.badge("muted", u.role)}</td>
          <td>${App.esc(u.section || u.department_section || "—")}</td>
          <td style="text-align:center">${hasQr(u)}</td>
          <td style="text-align:center">${hasRfid(u)}</td>
          <td>${App.statusBadge(u.status)}</td>
          <td class="text-right" style="white-space:nowrap">
            ${isAdmin ? `<div style="display:inline-flex;gap:2px;flex-wrap:nowrap;align-items:center">
            ${u.rfid_uid
              ? `<button class="btn btn-ghost btn-sm" title="Replace RFID" onclick="Admin.openAssignRfid('${u.user_id}')">${svg(I.edit)}</button>
                 <button class="btn btn-ghost btn-sm btn-danger" title="Remove RFID" onclick="Admin.openRemoveRfid('${u.user_id}')">${svg(I.trash)}</button>`
              : `<button class="btn btn-ghost btn-sm" title="Assign RFID" onclick="Admin.openAssignRfid('${u.user_id}')">${svg(I.plus)}</button>`
            }
            <span class="text-muted" style="opacity:.3">|</span>
            <button class="btn btn-ghost btn-sm" title="Edit" onclick="Admin.openEditStudent('${u.user_id}')">${svg(I.edit)}</button>
            <button class="btn btn-ghost btn-sm" title="Re-enroll face" onclick="Admin.openReenroll('${u.user_id}')">${svg(I.camera)}</button>
            <button class="btn btn-ghost btn-sm" title="Reset password" onclick="Admin.openResetPassword('${u.user_id}')">${svg(I.settings)}</button>
            <button class="btn btn-ghost btn-sm ${u.status === "ACTIVE" ? "btn-danger" : "btn-success"}" title="Archive/Restore" onclick="Admin.toggleUser('${u.user_id}')">${u.status === "ACTIVE" ? svg(I.archive) : svg(I.refresh)}</button>
            </div>` : ""}
          </td></tr>`).join("");
        wrap.innerHTML = `<div class="table-wrap"><table class="data"><thead><tr><th></th><th>Name</th><th>Role</th><th>Section</th><th style="text-align:center">QR</th><th style="text-align:center">RFID UID</th><th>Status</th><th></th></tr></thead><tbody>${body}</tbody></table></div>`;
        if (isStaff) {
          pager.innerHTML = `<div class="pagination"><span class="page-info">Showing ${rows.length} result${rows.length === 1 ? "" : "s"}</span></div>`;
        } else {
          pager.replaceChildren(App.pagination(total, page, 25, (p) => Admin.loadStudents(p)));
        }
      } catch (e) { wrap.innerHTML = App.alert("error", e.message); }
    },

    openAddStudent() {
      openUserForm("Add User", null);
    },
    openEditStudent(id) {
      App.api(`/admin/users/${id}`).then((u) => openUserForm("Edit User", u)).catch((e) => App.toast(e.message, "error"));
    },

    async toggleUser(id) {
      try { await App.api(`/admin/users/${id}/status`, { method: "PUT" }); App.toast("Status updated.", "success"); Admin.loadStudents(Admin._usrPage || 1); }
      catch (e) { App.toast(e.message, "error"); }
    },

    openReenroll(id) {
      faceCaptureModal(`Re-enroll Face — ${id}`, async (blob) => {
        const fd = new FormData(); fd.append("image", blob, "face.jpg");
        await App.api(`/admin/users/${id}/re-enroll`, { method: "POST", body: fd });
        App.toast("Face re-enrolled.", "success");
      });
    },

    openResetPassword(id) {
      App.modal({
        title: "Reset User Password",
        body: `<div class="form-group"><label>New Password (min 6 chars)</label><input class="form-control" id="rp-pw" type="text" placeholder="Temporary password"></div>
          <p class="form-hint">The user will be notified. They can change it later.</p>`,
        footer: `<button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="rp-save">Reset</button>`,
        onOpen: (m) => m.querySelector("#rp-save").addEventListener("click", async () => {
          const pw = m.querySelector("#rp-pw").value.trim();
          try { await App.api(`/admin/users/${id}/reset-password`, { method: "POST", body: JSON.stringify({ new_password: pw }) }); App.toast("Password reset.", "success"); App.closeModal(); }
          catch (e) { App.toast(e.message, "error"); }
        }),
      });
    },

    openBulkImport() {
      App.api("/admin/students/bulk-template").then((tpl) => {
        const csv = [tpl.headers.join(","), tpl.sample.join(",")].join("\n");
        App.modal({
          title: "Bulk Import Students",
          size: "lg",
          body: `<p class="form-hint">Paste CSV rows (header required). Columns: ${tpl.headers.join(", ")}.</p>
            <textarea class="form-control" id="bulk-csv" rows="10" style="font-family:monospace">${csv}</textarea>
            <div class="mt-2"><button class="btn btn-ghost btn-sm" onclick="Admin.downloadTemplate()">${svg(I.download)} Download template</button></div>
            <div id="bulk-msg" class="mt-2"></div>`,
          footer: `<button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="bulk-import">Import</button>`,
          onOpen: (m) => {
            window.__bulkCsv = csv;
            m.querySelector("#bulk-import").addEventListener("click", async () => {
              const text = m.querySelector("#bulk-csv").value.trim();
              const lines = text.split(/\r?\n/).filter(Boolean);
              const headers = lines[0].split(",").map((h) => h.trim());
              const rows = lines.slice(1).map((l) => {
                const cells = l.split(",");
                const o = {}; headers.forEach((h, i) => (o[h] = (cells[i] || "").trim())); return o;
              });
              try {
                const r = await App.api("/admin/students/bulk-import", { method: "POST", body: JSON.stringify({ rows }) });
                App.toast(r.message, "success"); App.closeModal(); Admin.loadStudents(1);
              } catch (e) { m.querySelector("#bulk-msg").innerHTML = App.alert("error", e.message); }
            });
          },
        });
      }).catch((e) => App.toast(e.message, "error"));
    },

    downloadTemplate() {
      const csv = window.__bulkCsv || "user_id,first_name,last_name,role,department_section\n";
      const blob = new Blob([csv], { type: "text/csv" });
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "students-template.csv"; a.click();
    },

    /* ---------------- Approvals ---------------- */
    approvalsPage() {
      App.setPageTitle("Approval Center");
      App.content().innerHTML = `
        <div class="page-header"><div><h1>Approval Center</h1><p>Review profile changes, re-registration, and account requests.</p></div>
          <button class="btn btn-secondary" onclick="Admin.loadApprovals()">${svg(I.refresh)} Refresh</button></div>
        <div class="grid grid-2">
          <div class="card"><div class="card-header"><div class="card-title">Approval Requests</div></div><div id="appr-list">${App.loadingBlock()}</div></div>
          <div class="card"><div class="card-header"><div class="card-title">Profile Change Requests</div></div><div id="prof-list">${App.loadingBlock()}</div></div>
        </div>`;
      Admin.loadApprovals();
    },

    async loadApprovals() {
      try {
        const approvals = await App.api("/approvals");
        const prof = App.role() === "ADMIN"
          ? await App.api("/admin/profile-update-requests").catch(() => [])
          : (await App.api("/students/me/requests").catch(() => ({ profile_updates: [] }))).profile_updates || [];
        const aWrap = document.getElementById("appr-list");
        const pWrap = document.getElementById("prof-list");
        if (!approvals.length) aWrap.innerHTML = App.emptyState("Nothing pending", "No approval requests.", I.check);
        else aWrap.innerHTML = `<div class="timeline">` + approvals.map((a) => `
          <div class="timeline-item ${a.status === "APPROVED" ? "success" : a.status === "REJECTED" ? "warning" : ""}">
            <span class="tl-dot"></span>
            <div class="d-flex justify-between align-center"><div><div class="tl-title">${App.esc(a.request_type)}</div><div class="tl-sub">${App.esc(a.user_id)} · ${App.fmtDateTime(a.requested_at)}</div></div>${App.statusBadge(a.status)}</div>
            ${a.details ? `<div class="text-xs text-muted mt-1">${App.esc(a.details)}</div>` : ""}
            ${a.status === "PENDING" ? `<div class="mt-1"><button class="btn btn-success btn-sm" onclick="Admin.decide(${a.id},'APPROVED')">Approve</button> <button class="btn btn-danger btn-sm" onclick="Admin.decide(${a.id},'REJECTED')">Reject</button></div>` : ""}
          </div>`).join("") + `</div>`;
        const pu = prof.profile_updates || [];
        if (!pu.length) pWrap.innerHTML = App.emptyState("Nothing pending", "No profile change requests.", I.user);
        else pWrap.innerHTML = `<div class="timeline">` + pu.map((p) => `
          <div class="timeline-item ${p.status === "APPROVED" ? "success" : p.status === "REJECTED" ? "warning" : ""}">
            <span class="tl-dot"></span>
            <div class="tl-title">${App.esc(p.field_name)}</div>
            <div class="tl-sub">${App.esc(p.user_id)}: ${App.esc(p.old_value || "—")} → <b>${App.esc(p.new_value)}</b></div>
            <div class="text-xs text-muted">${App.fmtDateTime(p.requested_at)} · ${App.statusBadge(p.status)}</div>
          </div>`).join("") + `</div>`;
      } catch (e) { App.toast(e.message, "error"); }
    },

    async decide(id, decision) {
      try { await App.api(`/approvals/${id}/decide`, { method: "POST", body: JSON.stringify({ decision, notes: "" }) }); App.toast(`Request ${decision.toLowerCase()}.`, "success"); Admin.loadApprovals(); }
      catch (e) { App.toast(e.message, "error"); }
    },

    /* ---------------- Audit ---------------- */
    auditPage() {
      App.setPageTitle("Audit Logs");
      App.content().innerHTML = `
        <div class="page-header"><div><h1>Audit Logs</h1><p>Record of administrative actions across the system.</p></div></div>
        <div class="card">
          <div class="toolbar">
            <div class="search">${svg(I.search)}<input class="form-control" id="aud-search" placeholder="Search action or email…"></div>
            <button class="btn btn-primary" onclick="Admin.loadAudit(1)">${svg(I.search)} Filter</button>
          </div>
          <div id="aud-table">${App.loadingBlock("Loading logs…")}</div>
          <div id="aud-pager"></div>
        </div>`;
      Admin.loadAudit(1);
    },

    async loadAudit(page) {
      Admin._audPage = page || 1;
      const search = document.getElementById("aud-search")?.value || "";
      const wrap = document.getElementById("aud-table");
      wrap.innerHTML = App.loadingBlock("Loading…");
      try {
        const q = `?page=${page}&page_size=20` + (search ? `&search=${encodeURIComponent(search)}` : "");
        const d = await App.api(`/admin/audit-logs${q}`);
        if (!d.items.length) { wrap.innerHTML = App.emptyState("No logs", "No audit entries match.", I.audit); document.getElementById("aud-pager").innerHTML = ""; return; }
        const body = d.items.map((r) => `<tr><td class="cell-sub">${App.esc(r.logged_at)}</td><td class="cell-strong">${App.esc(r.action)}</td><td>${App.esc(r.admin_email || "system")}</td><td class="text-muted text-sm">${App.esc(r.details || "")}</td></tr>`).join("");
        wrap.innerHTML = `<div class="table-wrap"><table class="data"><thead><tr><th>Time</th><th>Action</th><th>User</th><th>Details</th></tr></thead><tbody>${body}</tbody></table></div>`;
        document.getElementById("aud-pager").replaceChildren(App.pagination(d.total, page, 20, (p) => Admin.loadAudit(p)));
      } catch (e) { wrap.innerHTML = App.alert("error", e.message); }
    },

    /* ---------------- Settings ---------------- */
    settingsPage() {
      App.setPageTitle("System Settings");
      App.content().innerHTML = `<div id="set-wrap">${App.loadingBlock("Loading settings…")}</div>`;
      Admin.loadSettings();
    },

    async loadSettings() {
      const wrap = document.getElementById("set-wrap");
      try {
        const [face, me] = await Promise.all([App.api("/health/face"), App.api("/admin/me")]);
        window.__mainAdminEmail = me.main_admin_email || "";
        wrap.innerHTML = `
          <div class="grid grid-2">
            <div class="card"><div class="card-header"><div class="card-title">Face Recognition Engine</div></div>
              <div class="mb-2">${face.status === "ok" ? App.badge("success", "Operational") : App.badge("danger", "Error")}</div>
              <div class="text-sm text-muted">Model: <b>${App.esc(face.model)}</b></div>
              <div class="text-sm text-muted">Engine: ${App.esc(face.engine)}</div>
              ${face.error ? `<div class="alert alert-warning mt-2">${App.esc(face.error)}</div>` : ""}
            </div>
            <div class="card"><div class="card-header"><div class="card-title">Change My Password</div></div>
              <div class="pf-pw" style="max-width:none">
                <div class="form-group"><label>Current Password</label><input class="form-control" id="cp-old" type="password" placeholder="Enter current password"></div>
                <div class="form-group"><label>New Password</label><input class="form-control" id="cp-new" type="password" placeholder="Enter new password (min 6 chars)"></div>
                <div class="form-group"><label>Confirm New Password</label><input class="form-control" id="cp-confirm" type="password" placeholder="Confirm new password"></div>
                <button class="btn btn-primary" id="cp-save">${svg(I.check)} Update Password</button>
              </div>
            </div>
          </div>
          <div class="card mt-3"><div class="card-header"><div class="card-title">System Information</div></div>
            <div class="text-sm text-muted">NCST Face Recognition Attendance System · v1.0.0</div>
            <div class="text-sm text-muted">Security: password hashing (bcrypt), JWT sessions, rate limiting, parameterized queries.</div>
          </div>`;
        wrap.querySelectorAll("#cp-old, #cp-new, #cp-confirm").forEach(el => {
          el.addEventListener("keydown", (e) => { if (e.key === "Enter") wrap.querySelector("#cp-save").click(); });
        });
        wrap.querySelector("#cp-save").addEventListener("click", async () => {
          const oldp = wrap.querySelector("#cp-old").value;
          const newp = wrap.querySelector("#cp-new").value;
          const confirm = wrap.querySelector("#cp-confirm")?.value;
          if (!oldp || !newp) { App.toast("Please fill in all password fields.", "warning"); return; }
          if (newp.length < 6) { App.toast("New password must be at least 6 characters.", "warning"); return; }
          if (newp !== confirm) { App.toast("Passwords do not match.", "warning"); return; }
          const btn = wrap.querySelector("#cp-save");
          btn.disabled = true; btn.innerHTML = App.spinner() + " Updating…";
          try {
            await App.api("/auth/change-password", { method: "POST", body: JSON.stringify({ old_password: oldp, new_password: newp }) });
            App.toast("Password updated.", "success");
            wrap.querySelector("#cp-old").value = "";
            wrap.querySelector("#cp-new").value = "";
            if (wrap.querySelector("#cp-confirm")) wrap.querySelector("#cp-confirm").value = "";
          } catch (e) { App.toast(e.message, "error"); }
          finally { btn.disabled = false; btn.innerHTML = `${svg(I.check)} Update Password`; }
        });
      } catch (e) { wrap.innerHTML = App.alert("error", e.message); }
    },

    /* ---------------- Admin Management ---------------- */
    async adminManagementPage() {
      App.setPageTitle("Admin Management");
      try {
        const me = await App.api("/admin/me");
        if ((me.email || "").toLowerCase() !== (me.main_admin_email || "").toLowerCase()) {
          location.hash = "#/dashboard/overview";
          return;
        }
        window.__mainAdminEmail = me.main_admin_email;
        window.__currentAdminId = me.admin_id;
      } catch (e) { location.hash = "#/dashboard/overview"; return; }

      App.content().innerHTML = `
        <div class="page-header">
          <div><h1>Admin Management</h1><p>Create, edit, and manage administrator accounts.</p></div>
          <button class="btn btn-secondary" onclick="Admin.loadAdmins()">${svg(I.refresh)} Refresh</button>
        </div>
        <div class="card" id="am-create-card">
          <div class="card-header"><div class="card-title">Create New Admin</div></div>
          <div id="ca-msg"></div>
          <div class="form-row cols-3">
            <div class="form-group"><label>Email *</label><input class="form-control" id="ca-email" type="email" placeholder="admin@ncst.edu.ph"><div class="field-error" id="err-ca-email"></div></div>
            <div class="form-group"><label>First Name *</label><input class="form-control" id="ca-fn" placeholder="Juan"><div class="field-error" id="err-ca-fn"></div></div>
            <div class="form-group"><label>Last Name *</label><input class="form-control" id="ca-ln" placeholder="Dela Cruz"><div class="field-error" id="err-ca-ln"></div></div>
          </div>
          <button class="btn btn-primary" id="ca-save">${svg(I.plus)} Create Admin Account</button>
        </div>
        <div class="card mt-3">
          <div class="card-header"><div class="card-title">All Admin Accounts</div></div>
          <div id="am-table">${App.loadingBlock("Loading admins…")}</div>
        </div>`;
      Admin._wireCreateAdmin();
      Admin.loadAdmins();
    },

    _wireCreateAdmin() {
      const wrap = document.getElementById("am-create-card");
      if (!wrap) return;
      const caEmail = wrap.querySelector("#ca-email");
      const caFn = wrap.querySelector("#ca-fn");
      const caLn = wrap.querySelector("#ca-ln");
      const nameRe = /^[a-zA-Z\s'-]+$/;
      const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

      function caClearErrors() {
        wrap.querySelectorAll("#err-ca-email, #err-ca-fn, #err-ca-ln").forEach(el => el.textContent = "");
        [caEmail, caFn, caLn].forEach(el => el?.classList.remove("is-invalid"));
      }
      function caShowErr(el, errEl, msg) {
        if (el) el.classList.add("is-invalid");
        if (errEl) errEl.textContent = msg;
      }

      wrap.querySelector("#ca-save").addEventListener("click", async () => {
        caClearErrors();
        const email = (caEmail?.value || "").trim();
        const fn = (caFn?.value || "").trim();
        const ln = (caLn?.value || "").trim();
        let valid = true;

        if (!email) { caShowErr(caEmail, wrap.querySelector("#err-ca-email"), "Email is required"); valid = false; }
        else if (!emailRe.test(email)) { caShowErr(caEmail, wrap.querySelector("#err-ca-email"), "Enter a valid email"); valid = false; }
        if (!fn) { caShowErr(caFn, wrap.querySelector("#err-ca-fn"), "First Name is required"); valid = false; }
        else if (!nameRe.test(fn)) { caShowErr(caFn, wrap.querySelector("#err-ca-fn"), "Letters only"); valid = false; }
        if (!ln) { caShowErr(caLn, wrap.querySelector("#err-ca-ln"), "Last Name is required"); valid = false; }
        else if (!nameRe.test(ln)) { caShowErr(caLn, wrap.querySelector("#err-ca-ln"), "Letters only"); valid = false; }
        if (!valid) return;

        const btn = wrap.querySelector("#ca-save");
        btn.disabled = true;
        btn.innerHTML = App.spinner() + " Creating…";
        try {
          const res = await App.api("/admin/create-admin", {
            method: "POST",
            body: JSON.stringify({ email, first_name: fn, last_name: ln }),
          });
          App.toast(res.message, "success");
          wrap.querySelector("#ca-msg").innerHTML = App.alert("success", res.message);
          caEmail.value = ""; caFn.value = ""; caLn.value = "";
          Admin.loadAdmins();
        } catch (e) { wrap.querySelector("#ca-msg").innerHTML = App.alert("error", e.message); }
        finally { btn.disabled = false; btn.innerHTML = `${svg(I.plus)} Create Admin Account`; }
      });
    },

    async loadAdmins() {
      const wrap = document.getElementById("am-table");
      if (!wrap) return;
      wrap.innerHTML = App.loadingBlock("Loading admins…");
      try {
        const admins = await App.api("/admin/list-admins");
        if (!admins.length) { wrap.innerHTML = App.emptyState("No admin accounts", "No admins found.", I.users); return; }
        const body = admins.map(a => {
          const statusBadge = a.status === "ARCHIVED"
            ? `<span class="badge badge-danger">Archived</span>`
            : `<span class="badge badge-success">Active</span>`;
          const canManage = a.admin_id !== window.__currentAdminId;
          const actions = canManage
            ? `<button class="btn btn-ghost btn-sm" title="Edit" onclick="Admin.openEditAdmin('${a.admin_id}')">${svg(I.edit)}</button>
               <button class="btn btn-ghost btn-sm ${a.status === 'ACTIVE' ? 'btn-danger' : 'btn-success'}" title="${a.status === 'ACTIVE' ? 'Archive' : 'Restore'}" onclick="Admin.toggleAdmin('${a.admin_id}')">${a.status === 'ACTIVE' ? svg(I.archive) : svg(I.refresh)}</button>`
            : "";
          return `<tr>
            <td class="cell-strong">${App.esc(a.email)}</td>
            <td>${App.esc(a.first_name)}</td>
            <td>${App.esc(a.last_name)}</td>
            <td>${statusBadge}</td>
            <td class="cell-sub">${App.fmtDateTime(a.created_at)}</td>
            <td class="text-right" style="text-align:right;white-space:nowrap">${actions}</td>
          </tr>`;
        }).join("");
        wrap.innerHTML = `<div class="table-wrap"><table class="data">
          <thead><tr><th>Email</th><th>First Name</th><th>Last Name</th><th>Status</th><th>Created</th><th></th></tr></thead>
          <tbody>${body}</tbody></table></div>`;
      } catch (e) { wrap.innerHTML = App.alert("error", e.message); }
    },

    async openEditAdmin(adminId) {
      try {
        const admins = await App.api("/admin/list-admins");
        const a = admins.find(x => x.admin_id === adminId);
        if (!a) { App.toast("Admin not found.", "error"); return; }
        App.modal({
          title: "Edit Admin Account",
          body: `
            <div class="form-group"><label>Email</label><input class="form-control" value="${App.esc(a.email)}" disabled style="background:#f1f5f9"></div>
            <div class="form-row cols-2">
              <div class="form-group"><label>First Name *</label><input class="form-control" id="ea-fn" value="${App.esc(a.first_name)}"><div class="field-error" id="err-ea-fn"></div></div>
              <div class="form-group"><label>Last Name *</label><input class="form-control" id="ea-ln" value="${App.esc(a.last_name)}"><div class="field-error" id="err-ea-ln"></div></div>
            </div>`,
          footer: `<button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="ea-save">Save Changes</button>`,
          onOpen: (m) => {
            m.querySelector("#ea-save").addEventListener("click", async () => {
              const fn = m.querySelector("#ea-fn").value.trim();
              const ln = m.querySelector("#ea-ln").value.trim();
              const nameRe = /^[a-zA-Z\s'-]+$/;
              let valid = true;
              m.querySelectorAll(".field-error").forEach(el => el.textContent = "");
              m.querySelectorAll(".is-invalid").forEach(el => el.classList.remove("is-invalid"));

              if (!fn) { m.querySelector("#err-ea-fn").textContent = "Required"; m.querySelector("#ea-fn").classList.add("is-invalid"); valid = false; }
              else if (!nameRe.test(fn)) { m.querySelector("#err-ea-fn").textContent = "Letters only"; m.querySelector("#ea-fn").classList.add("is-invalid"); valid = false; }
              if (!ln) { m.querySelector("#err-ea-ln").textContent = "Required"; m.querySelector("#ea-ln").classList.add("is-invalid"); valid = false; }
              else if (!nameRe.test(ln)) { m.querySelector("#err-ea-ln").textContent = "Letters only"; m.querySelector("#ea-ln").classList.add("is-invalid"); valid = false; }
              if (!valid) return;

              const btn = m.querySelector("#ea-save");
              btn.disabled = true; btn.innerHTML = App.spinner() + " Saving…";
              try {
                await App.api(`/admin/${adminId}`, { method: "PUT", body: JSON.stringify({ first_name: fn, last_name: ln }) });
                App.toast("Admin updated.", "success");
                App.closeModal();
                Admin.loadAdmins();
              } catch (e) { App.toast(e.message, "error"); }
              finally { btn.disabled = false; btn.textContent = "Save Changes"; }
            });
          },
        });
      } catch (e) { App.toast(e.message, "error"); }
    },

    async toggleAdmin(adminId) {
      try {
        const res = await App.api(`/admin/${adminId}/status`, { method: "PUT" });
        App.toast(res.message, "success");
        Admin.loadAdmins();
      } catch (e) { App.toast(e.message, "error"); }
    },

    /* ---------------- RFID Management ---------------- */
    rfidPage() {
      App.setPageTitle("RFID Management");
      App.content().innerHTML = `
        <div class="page-header"><div><h1>RFID Card Management</h1><p>Assign, edit, or remove RFID cards for students and staff.</p></div></div>
        <div class="card">
          <div class="toolbar">
            <div class="search">${svg(I.search)}<input class="form-control" id="rfid-search" placeholder="Search name or ID…"></div>
            <select class="form-control" id="rfid-role" style="max-width:150px"><option value="">All roles</option><option value="STUDENT">Student</option><option value="STAFF">Staff</option><option value="FACULTY">Faculty</option></select>
            <select class="form-control" id="rfid-filter" style="max-width:180px"><option value="">All cards</option><option value="assigned">With RFID</option><option value="unassigned">Without RFID</option></select>
            <button class="btn btn-primary" onclick="Admin.loadRfidStudents(1)">${svg(I.search)} Filter</button>
          </div>
          <div id="rfid-table">${App.loadingBlock("Loading…")}</div>
          <div id="rfid-pager"></div>
        </div>`;
      Admin.loadRfidStudents(1);
    },

    async loadRfidStudents(page) {
      const search = document.getElementById("rfid-search")?.value || "";
      const roleFilter = document.getElementById("rfid-role")?.value || "";
      const rfidFilter = document.getElementById("rfid-filter")?.value || "";
      const wrap = document.getElementById("rfid-table");
      const pager = document.getElementById("rfid-pager");
      wrap.innerHTML = App.loadingBlock("Loading…");
      try {
        const q = `?page=${page}&page_size=25` + (search ? `&search=${encodeURIComponent(search)}` : "") + (roleFilter ? `&role=${roleFilter}` : "");
        const data = await App.api(`/admin/users${q}`);
        let rows = data.items || [];
        const total = data.total || rows.length;

        if (rfidFilter === "assigned") rows = rows.filter((u) => u.rfid_uid);
        else if (rfidFilter === "unassigned") rows = rows.filter((u) => !u.rfid_uid);

        if (!rows.length) { wrap.innerHTML = App.emptyState("No users found", "Try adjusting your filters.", I.users); pager.innerHTML = ""; return; }

        const body = rows.map((u) => `<tr>
          <td class="cell-strong">${App.esc(u.first_name + " " + u.last_name)}</td>
          <td class="cell-sub">${App.esc(u.user_id)}</td>
          <td>${App.badge("muted", u.role)}</td>
          <td>${u.rfid_uid ? `<code style="font-size:.85rem;background:var(--surface-2);padding:2px 8px;border-radius:6px">${App.esc(u.rfid_uid)}</code>` : `<span class="text-muted">—</span>`}</td>
          <td>${u.rfid_uid ? App.badge("success", "Assigned", true) : App.badge("muted", "Unassigned")}</td>
          <td class="text-right" style="white-space:nowrap">
            <button class="btn btn-ghost btn-sm" title="${u.rfid_uid ? "Edit RFID" : "Assign RFID"}" onclick="Admin.openAssignRfid('${u.user_id}')">${svg(u.rfid_uid ? I.edit : I.plus)} ${u.rfid_uid ? "Edit" : "Assign"}</button>
          </td></tr>`).join("");
        wrap.innerHTML = `<div class="table-wrap"><table class="data"><thead><tr><th>Name</th><th>ID</th><th>Role</th><th>RFID UID</th><th>Status</th><th></th></tr></thead><tbody>${body}</tbody></table></div>`;
        pager.replaceChildren(App.pagination(total, page, 25, (p) => Admin.loadRfidStudents(p)));
      } catch (e) { wrap.innerHTML = App.alert("error", e.message); }
    },

    openAssignRfid(userId) {
      App.api(`/admin/users/${userId}`).then((u) => {
        const hasRfid = !!u.rfid_uid;
        App.modal({
          title: hasRfid ? "Edit RFID Card" : "Assign RFID Card",
          body: `<div class="form-group"><label>Student Name</label><input class="form-control" value="${App.esc(u.first_name + " " + u.last_name)}" disabled></div>
            <div class="form-group"><label>Student ID</label><input class="form-control" value="${App.esc(u.user_id)}" disabled></div>
            <div class="form-group"><label>RFID UID</label>
              <input class="form-control" id="rfid-uid-input" value="${App.esc(u.rfid_uid || "")}" placeholder="Scan or type RFID card UID" autocomplete="off" ${hasRfid ? "" : "autofocus"}>
              <p class="form-hint">Scan the RFID card or type the UID manually.</p>
            </div>
            <div id="rfid-msg"></div>`,
          footer: `<button class="btn btn-secondary" data-close>Cancel</button>
            ${hasRfid ? `<button class="btn btn-danger" id="rfid-remove" style="margin-right:auto">${svg(I.trash)} Remove Card</button>` : ""}
            <button class="btn btn-primary" id="rfid-save">${hasRfid ? "Update" : "Assign Card"}</button>`,
          onOpen: (m) => {
            const input = m.querySelector("#rfid-uid-input");
            const msg = m.querySelector("#rfid-msg");
            const saveBtn = m.querySelector("#rfid-save");

            const doSave = async (clear) => {
              const rfidVal = clear ? "" : input.value.trim();
              if (!clear && !rfidVal) { msg.innerHTML = App.alert("error", "Please scan or enter an RFID UID."); return; }
              saveBtn.disabled = true; saveBtn.innerHTML = App.spinner() + " Saving…";
              try {
                await App.api(`/admin/users/${userId}`, {
                  method: "PUT",
                  body: JSON.stringify({
                    first_name: u.first_name, last_name: u.last_name, role: u.role,
                    department_section: u.department_section, email: u.email,
                    course: u.course, year_level: u.year_level, section: u.section,
                    contact_number: u.contact_number, address: u.address,
                    emergency_contact: u.emergency_contact, rfid_uid: rfidVal,
                  }),
                });
                App.toast(clear ? "RFID card removed." : "RFID card assigned.", "success");
                App.closeModal();
                Admin.loadRfidStudents(1);
              } catch (e) { msg.innerHTML = App.alert("error", e.message); }
              finally { saveBtn.disabled = false; saveBtn.innerHTML = hasRfid ? "Update" : "Assign Card"; }
            };

            saveBtn.addEventListener("click", () => doSave(false));

            const removeBtn = m.querySelector("#rfid-remove");
            if (removeBtn) {
              removeBtn.addEventListener("click", () => {
                App.confirm("Remove RFID Card", "Are you sure you want to remove this RFID card from " + App.esc(u.first_name + " " + u.last_name) + "?", () => doSave(true), true);
              });
            }

            input.addEventListener("keydown", (e) => { if (e.key === "Enter") doSave(false); });
          },
        });
      }).catch((e) => App.toast(e.message, "error"));
    },

    openRemoveRfid(userId) {
      App.api(`/admin/users/${userId}`).then((u) => {
        App.confirm("Remove RFID Card",
          "Are you sure you want to remove the RFID card from <strong>" + App.esc(u.first_name + " " + u.last_name) + "</strong>?",
          async () => {
            try {
              await App.api(`/admin/users/${userId}`, {
                method: "PUT",
                body: JSON.stringify({
                  first_name: u.first_name, last_name: u.last_name, role: u.role,
                  department_section: u.department_section, email: u.email,
                  course: u.course, year_level: u.year_level, section: u.section,
                  contact_number: u.contact_number, address: u.address,
                  emergency_contact: u.emergency_contact, rfid_uid: "",
                }),
              });
              App.toast("RFID card removed.", "success");
              Admin.loadStudents(Admin._usrPage || 1);
            } catch (e) { App.toast(e.message, "error"); }
          }, true);
      }).catch((e) => App.toast(e.message, "error"));
    },
  };

  /* ---------------- Shared form helpers ---------------- */
  function openUserForm(title, user) {
    const u = user || {};
    App.modal({
      title,
      size: "lg",
      body: `
        <div class="form-row cols-2">
          <div class="form-group"><label>User ID *</label><input class="form-control" id="uf-id" value="${App.esc(u.user_id || "")}" ${u.user_id ? "disabled" : ""}></div>
          <div class="form-group"><label>Role *</label><select class="form-control" id="uf-role"><option value="STUDENT" ${u.role === "STUDENT" ? "selected" : ""}>Student</option><option value="STAFF" ${u.role === "STAFF" ? "selected" : ""}>Staff</option><option value="FACULTY" ${u.role === "FACULTY" ? "selected" : ""}>Faculty</option></select></div>
        </div>
        <div class="form-row cols-2">
          <div class="form-group"><label>First Name *</label><input class="form-control" id="uf-fn" value="${App.esc(u.first_name || "")}"><div class="field-error" id="err-fn"></div></div>
          <div class="form-group"><label>Last Name *</label><input class="form-control" id="uf-ln" value="${App.esc(u.last_name || "")}"><div class="field-error" id="err-ln"></div></div>
        </div>
        <div class="form-group"><label>Department / Section *</label><input class="form-control" id="uf-dep" value="${App.esc(u.department_section || "")}" placeholder="e.g. BSCS-3A"></div>
        ${u.user_id ? "" : `<div class="form-row cols-2"><div class="form-group"><label>Email *</label><input class="form-control" id="uf-email" type="email" placeholder="user@ncst.edu"><div class="field-error" id="err-email"></div></div><div class="form-group"><label>Default Password</label><input class="form-control" id="uf-pw" value="Default123!" disabled style="background:#f1f5f9;color:#94a3b8"></div></div>`}
        ${u.user_id ? `<div class="form-group"><label>Email</label><input class="form-control" value="${App.esc(u.email || "")}" disabled style="background:#f1f5f9"></div>` : ""}
        <div class="form-row cols-2"><div class="form-group"><label>Contact Number</label><input class="form-control" id="uf-contact" value="${App.esc(u.contact_number || "")}"></div><div class="form-group"><label>Emergency Contact</label><input class="form-control" id="uf-emerg" value="${App.esc(u.emergency_contact || "")}"></div></div>
        ${u.user_id ? `<div class="form-group"><label>RFID UID</label><input class="form-control" id="uf-rfid" value="${App.esc(u.rfid_uid || "")}" placeholder="Scan or type RFID card UID"></div>` : ""}
        ${u.user_id ? "" : `<div class="form-group"><label>Face Image *</label><div id="uf-cam-wrap"></div></div>`}
        <div id="uf-msg" class="mt-1"></div>`,
      footer: `<button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="uf-save">${u.user_id ? "Save Changes" : "Register User"}</button>`,
      onOpen: (m) => {
        if (!u.user_id) setupFaceCapture(m.querySelector("#uf-cam-wrap"));

        function clearErrors() {
          m.querySelectorAll(".field-error").forEach(el => el.textContent = "");
          m.querySelectorAll(".is-invalid").forEach(el => el.classList.remove("is-invalid"));
        }
        function showFieldError(fieldId, msg) {
          const errEl = m.querySelector("#err-" + fieldId);
          const input = m.querySelector("#uf-" + fieldId);
          if (errEl) errEl.textContent = msg;
          if (input) input.classList.add("is-invalid");
        }

        m.querySelector("#uf-save").addEventListener("click", async () => {
          clearErrors();
          const payload = {
            first_name: m.querySelector("#uf-fn").value.trim(),
            last_name: m.querySelector("#uf-ln").value.trim(),
            role: m.querySelector("#uf-role").value,
            department_section: m.querySelector("#uf-dep").value.trim(),
            contact_number: m.querySelector("#uf-contact").value.trim(),
            emergency_contact: m.querySelector("#uf-emerg").value.trim(),
            rfid_uid: u.user_id ? (m.querySelector("#uf-rfid")?.value.trim() || "") : undefined,
          };

          if (!u.user_id) {
            const email = m.querySelector("#uf-email").value.trim();
            const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            const nameRe = /^[a-zA-Z\s'-]+$/;
            let valid = true;

            if (!email) { showFieldError("email", "Email is required"); valid = false; }
            else if (!emailRe.test(email)) { showFieldError("email", "Email must be a valid email address"); valid = false; }

            if (!payload.first_name) { showFieldError("fn", "First Name is required"); valid = false; }
            else if (!nameRe.test(payload.first_name)) { showFieldError("fn", "First Name must contain only letters"); valid = false; }

            if (!payload.last_name) { showFieldError("ln", "Last Name is required"); valid = false; }
            else if (!nameRe.test(payload.last_name)) { showFieldError("ln", "Last Name must contain only letters"); valid = false; }

            if (!valid) return;

            const saveBtn = m.querySelector("#uf-save"); saveBtn.disabled = true; saveBtn.innerHTML = App.spinner() + " Saving…";
            try {
              const fd = new FormData();
              fd.append("user_id", m.querySelector("#uf-id").value.trim());
              fd.append("first_name", payload.first_name);
              fd.append("last_name", payload.last_name);
              fd.append("role", payload.role);
              fd.append("department_section", payload.department_section);
              fd.append("contact_number", payload.contact_number); fd.append("emergency_contact", payload.emergency_contact);
              fd.append("email", email);
              const pw = m.querySelector("#uf-pw").value; if (pw) fd.append("password", pw);
              if (!window.__captureBlob) { m.querySelector("#uf-msg").innerHTML = App.alert("warning", "Please capture a face image."); saveBtn.disabled = false; saveBtn.textContent = "Register User"; return; }
              fd.append("image", window.__captureBlob, "face.jpg");
              await App.api("/register", { method: "POST", body: fd });
              App.toast("User registered.", "success");
              App.closeModal(); Admin.loadStudents(Admin._usrPage || 1);
            } catch (e) {
              const parsed = parseApiError(e.message);
              if (parsed) {
                parsed.forEach(p => showFieldError(p.field, p.message));
              } else {
                m.querySelector("#uf-msg").innerHTML = App.alert("error", e.message);
              }
              saveBtn.disabled = false; saveBtn.textContent = "Register User";
            }
          } else {
            if (!payload.first_name || !payload.last_name || !payload.department_section) { m.querySelector("#uf-msg").innerHTML = App.alert("warning", "Name, role, and department are required."); return; }
            const saveBtn = m.querySelector("#uf-save"); saveBtn.disabled = true; saveBtn.innerHTML = App.spinner() + " Saving…";
            try {
              await App.api(`/admin/users/${u.user_id}`, { method: "PUT", body: JSON.stringify(payload) });
              App.toast("User updated.", "success");
              App.closeModal(); Admin.loadStudents(Admin._usrPage || 1);
            } catch (e) {
              const parsed = parseApiError(e.message);
              if (parsed) {
                parsed.forEach(p => {
                  const fieldMap = { first_name: "fn", last_name: "ln", email: "email" };
                  showFieldError(fieldMap[p.field] || p.field, p.message);
                });
              } else {
                m.querySelector("#uf-msg").innerHTML = App.alert("error", e.message);
              }
              saveBtn.disabled = false; saveBtn.textContent = "Save Changes";
            }
          }
        });
      },
    });
  }

  function parseApiError(msg) {
    try {
      const arr = JSON.parse(msg);
      if (!Array.isArray(arr)) return null;
      return arr.map(item => {
        const loc = item.loc || [];
        const field = loc[loc.length - 1] || "";
        let message = item.msg || "Invalid value";
        if (item.type === "missing") {
          const labelMap = { email: "Email", first_name: "First Name", last_name: "Last Name", user_id: "User ID", department_section: "Department / Section" };
          message = (labelMap[field] || field) + " is required";
        }
        return { field, message };
      });
    } catch { return null; }
  }

  function setupFaceCapture(wrap) {
    wrap.innerHTML = `<video id="uf-video" autoplay playsinline muted style="width:100%;border-radius:12px;background:#000;display:none"></video>
      <div class="empty-state" id="uf-prev">Camera off</div>
      <div class="toolbar mt-2"><button class="btn btn-secondary" id="uf-start">Start Camera</button><button class="btn btn-primary" id="uf-cap" disabled>Capture</button></div>`;
    const video = wrap.querySelector("#uf-video");
    const prev = wrap.querySelector("#uf-prev");
    wrap.querySelector("#uf-start").addEventListener("click", async () => {
      try { await App.startCamera(video); video.style.display = "block"; prev.style.display = "none"; wrap.querySelector("#uf-cap").disabled = false; }
      catch (e) { prev.innerHTML = App.alert("error", "Camera access denied."); }
    });
    wrap.querySelector("#uf-cap").addEventListener("click", async () => {
      window.__captureBlob = await App.captureFrame(video);
      App.stopCamera();
      prev.style.display = "block"; prev.innerHTML = `<div class="alert alert-success">Face captured ✓</div>`;
      video.style.display = "none";
    });
  }

  function faceCaptureModal(title, onCapture) {
    App.modal({
      title, size: "lg",
      body: `<video id="fc-video" autoplay playsinline muted style="width:100%;border-radius:12px;background:#000;display:none"></video>
        <div class="empty-state" id="fc-prev">Camera off</div>
        <div class="toolbar mt-2"><button class="btn btn-secondary" id="fc-start">Start Camera</button><button class="btn btn-primary" id="fc-cap" disabled>Capture</button></div>
        <div id="fc-msg"></div>`,
      onOpen: (m) => {
        const video = m.querySelector("#fc-video"); const prev = m.querySelector("#fc-prev");
        m.querySelector("#fc-start").addEventListener("click", async () => {
          try { await App.startCamera(video); video.style.display = "block"; prev.style.display = "none"; m.querySelector("#fc-cap").disabled = false; }
          catch (e) { m.querySelector("#fc-msg").innerHTML = App.alert("error", "Camera access denied."); }
        });
        m.querySelector("#fc-cap").addEventListener("click", async () => {
          const blob = await App.captureFrame(video); App.stopCamera();
          try { await onCapture(blob); App.closeModal(); } catch (e) { m.querySelector("#fc-msg").innerHTML = App.alert("error", e.message); }
        });
      },
    });
  }

  /* ---------------- Routes (admin) ---------------- */
  App.router.add("/dashboard/students", (p) => Admin.studentsPage(p));
  App.router.add("/dashboard/rfid", () => Admin.rfidPage());
  App.router.add("/dashboard/approvals", () => Admin.approvalsPage());
  App.router.add("/dashboard/audit", () => Admin.auditPage());
  App.router.add("/dashboard/settings", () => Admin.settingsPage());
  App.router.add("/dashboard/admin-management", () => {
    if (App.role() !== "ADMIN") { location.hash = "#/dashboard/overview"; return; }
    Admin.adminManagementPage();
  });
  App.router.add("/dashboard/rfid", () => Admin.rfidPage());

  window.Admin = Admin;
})();
