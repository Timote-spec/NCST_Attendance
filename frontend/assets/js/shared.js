/* =========================================================================
   NCST — Shared portal pages (overview dispatch, attendance, announcements,
   profile, face, notifications, scanner). Role-aware.
   ========================================================================= */
(function () {
  "use strict";
  const App = window.App;
  const I = App.ICON;
  const svg = App.svg;

  /* ---------------- Overview (role dispatch) ---------------- */
  App.router.add("/dashboard/overview", async function () {
    const role = App.role();
    if (role === "ADMIN") return Shared.adminOverview();
    if (role === "STAFF" || role === "FACULTY") return Shared.staffOverview();
    return Shared.studentOverview();
  });

  /* ---------------- Bar chart ---------------- */
  function barChart(series, labelFmt) {
    if (!series || !series.length) return App.emptyState("No data yet", "Attendance activity will appear here as records are captured.", I.calendar);
    const max = Math.max.apply(null, series.map((s) => s.count)) || 1;
    const bars = series.slice(-14).map((s) => {
      const h = Math.max(4, Math.round((s.count / max) * 100));
      const lbl = labelFmt ? labelFmt(s) : String(s.date).slice(5);
      return `<div class="bar-col"><div class="bar" style="height:${h}%" title="${App.esc(s.date)}: ${s.count}"></div><div class="bar-label">${App.esc(lbl)}</div></div>`;
    }).join("");
    return `<div class="bar-chart">${bars}</div>`;
  }

  // eslint-disable-next-line no-unused-vars
  const Shared = {
    /* ---------------- Attendance ---------------- */
    attendancePage(params) {
      const role = App.role();
      const isPersonal = role === "STUDENT" || role === "STAFF" || role === "FACULTY";
      App.setPageTitle(isPersonal ? "My Attendance" : "Attendance");
      const canManage = role === "ADMIN";
      const canExport = true;
      App.content().innerHTML = `
        <div class="page-header">
          <div><h1>${isPersonal ? "My Attendance Records" : "Attendance Records"}</h1>
            <p>${isPersonal ? "Review your time-in and time-out history." : "Monitor and manage attendance across the institution."}</p></div>
          <div class="page-actions">
            ${canExport ? `<button class="btn btn-secondary" onclick="Shared.exportAttendance()">${svg(I.download)} Export CSV</button>` : ""}
            ${canManage ? `<button class="btn btn-secondary" onclick="Shared.refreshAttendance()">${svg(I.refresh)} Refresh</button>` : ""}
          </div>
        </div>
        <div class="card">
          <div class="toolbar">
            ${canManage ? `<div class="search">${svg(I.search)}<input class="form-control" id="att-search" placeholder="Search name or ID…"></div>` : ""}
            <input type="date" class="form-control" id="att-from" style="max-width:170px" title="From date">
            <input type="date" class="form-control" id="att-to" style="max-width:170px" title="To date">
            <select class="form-control" id="att-status" style="max-width:160px">
              <option value="">All statuses</option>
              <option value="PRESENT">Present</option>
              <option value="LATE">Late</option>
              <option value="ABSENT">Absent</option>
            </select>
            <button class="btn btn-primary" onclick="Shared.loadAttendance(1)">${svg(I.search)} Filter</button>
          </div>
          <div id="att-table">${App.loadingBlock("Loading attendance…")}</div>
          <div id="att-pager"></div>
        </div>`;
      if (canManage) App.content().querySelector("#att-search").addEventListener("keydown", (e) => { if (e.key === "Enter") Shared.loadAttendance(1); });
      Shared._attPage = 1;
      Shared.loadAttendance(1);
    },

    async loadAttendance(page) {
      Shared._attPage = page || 1;
      const role = App.role();
      const search = document.getElementById("att-search")?.value || "";
      const from = document.getElementById("att-from")?.value || "";
      const to = document.getElementById("att-to")?.value || "";
      const status = document.getElementById("att-status")?.value || "";
      const pageSize = 25;
      const wrap = document.getElementById("att-table");
      const pager = document.getElementById("att-pager");
      wrap.innerHTML = App.loadingBlock("Loading…");
      try {
        let data, endpoint;
        if (role === "STUDENT") {
          endpoint = `/students/me/attendance?page=${page}&page_size=${pageSize}` + (from ? `&date_from=${from}` : "") + (to ? `&date_to=${to}` : "");
          data = await App.api(endpoint);
        } else if (role === "STAFF" || role === "FACULTY") {
          endpoint = `/staff/attendance?page=${page}&page_size=${pageSize}` + (from ? `&date_from=${from}` : "") + (to ? `&date_to=${to}` : "");
          data = await App.api(endpoint);
        } else {
          endpoint = `/admin/logs?page=${page}&page_size=${pageSize}` + (search ? `&search=${encodeURIComponent(search)}` : "") + (from ? `&date_from=${from}` : "") + (to ? `&date_to=${to}` : "");
          data = await App.api(endpoint);
        }
        const rows = data.items || [];
        if (!rows.length) { wrap.innerHTML = App.emptyState("No attendance records", "No records match the current filters.", I.calendar); pager.innerHTML = ""; return; }
        const photo = (uid) => `<img src="${App.API}/images/${App.esc(uid)}" alt="" style="width:32px;height:32px;border-radius:50%;object-fit:cover;background:var(--surface-2);vertical-align:middle;margin-right:6px;" onerror="this.style.display='none'">`;
        const methodBadge = (m) => {
          const colors = { Face: "primary", QR: "warning", RFID: "primary" };
          return App.badge(colors[m] || "muted", m || "—", true);
        };
        const head = `<thead><tr>
          <th></th><th>${role === "ADMIN" ? "Student" : "Name"}</th><th>ID</th><th>Role</th><th>Date</th><th>Time In</th><th>Time Out</th><th>Status</th><th>Method</th><th>Device</th>
          ${role === "ADMIN" ? "<th></th>" : ""}</tr></thead>`;
        const body = rows.map((r) => `<tr>
          <td>${photo(r.user_id)}</td>
          <td class="cell-strong">${App.esc(r.user_name || (r.first_name + " " + r.last_name) || "—")}</td>
          <td class="cell-sub">${App.esc(r.user_id)}</td>
          <td>${App.badge("muted", r.role || "—")}</td>
          <td>${App.esc(r.date || "—")}</td>
          <td>${App.esc(r.time_in || "—")}</td>
          <td>${App.esc(r.time_out || "—")}</td>
          <td>${App.statusBadge(r.attendance_status)}</td>
          <td>${methodBadge(r.scan_method)}</td>
          <td class="cell-sub">${App.esc(r.device_id || "—")}</td>
          ${role === "ADMIN" ? `<td><button class="btn btn-ghost btn-sm" onclick="Shared.correctAttendance(${r.log_id})">${svg(I.edit)}</button></td>` : ""}
        </tr>`).join("");
        wrap.innerHTML = `<div class="table-wrap"><table class="data">${head}<tbody>${body}</tbody></table></div>`;
        pager.replaceChildren(App.pagination(data.total || rows.length, page, pageSize, (p) => Shared.loadAttendance(p)));
      } catch (err) {
        wrap.innerHTML = App.alert("error", err.message);
      }
    },

    refreshAttendance() { Shared.loadAttendance(Shared._attPage || 1); },

    exportAttendance() {
      const role = App.role();
      const from = document.getElementById("att-from")?.value || "";
      const to = document.getElementById("att-to")?.value || "";
      const q = (from ? `?date_from=${from}` : "") + (to ? (from ? "&" : "?") + `date_to=${to}` : "");
      if (role === "STUDENT") {
        window.location.href = App.API + "/students/me/attendance/export" + q;
      } else if (role === "STAFF" || role === "FACULTY") {
        window.location.href = App.API + "/staff/attendance/export" + q;
      } else {
        window.location.href = App.API + `/reports/export?report_type=daily${from ? "&date_from=" + from : ""}${to ? "&date_to=" + to : ""}`;
      }
    },

    correctAttendance(logId) {
      App.modal({
        title: "Correct Attendance Record",
        body: `<div class="form-group"><label>Time Out</label><input class="form-control" id="corr-timeout" placeholder="HH:MM:SS (leave blank to clear)"></div>
               <div class="form-group"><label>Status</label><select class="form-control" id="corr-status"><option value="PRESENT">PRESENT</option><option value="LATE">LATE</option><option value="ABSENT">ABSENT</option></select></div>`,
        footer: `<button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="corr-save">Save</button>`,
        onOpen: (m) => {
          m.querySelector("#corr-save").addEventListener("click", async () => {
            const timeout = m.querySelector("#corr-timeout").value.trim();
            const status = m.querySelector("#corr-status").value;
            try {
              await App.api(`/admin/logs/${logId}`, { method: "PUT", body: JSON.stringify({ time_out: timeout || null, attendance_status: status }) });
              App.toast("Record updated.", "success"); App.closeModal(); Shared.loadAttendance(Shared._attPage || 1);
            } catch (e) { App.toast(e.message, "error"); }
          });
        },
      });
    },

    /* ---------------- Announcements ---------------- */
    announcementsPage() {
      const role = App.role();
      const isAdmin = role === "ADMIN";
      App.setPageTitle("Announcements");
      App.content().innerHTML = `
        <div class="page-header">
          <div><h1>Announcements</h1><p>Institutional notices and updates.</p></div>
          ${isAdmin ? `<button class="btn btn-primary" onclick="Shared.createAnnouncement()">${svg(I.plus)} New Announcement</button>` : ""}
        </div>
        <div id="ann-list">${App.loadingBlock("Loading announcements…")}</div>`;
      Shared.loadAnnouncements();
    },

    async loadAnnouncements() {
      const wrap = document.getElementById("ann-list");
      try {
        const list = await App.api("/announcements");
        if (!list.length) { wrap.innerHTML = App.emptyState("No announcements", "There are no announcements at this time.", I.megaphone); return; }
        wrap.innerHTML = `<div class="grid grid-2">` + list.map((a) => `
          <div class="card">
            <div class="card-header">
              <div><div class="card-title">${App.esc(a.title)}</div><div class="card-subtitle">${App.esc(a.target_role)} · ${App.fmtDateTime(a.created_at)}</div></div>
              ${a.is_pinned ? App.badge("warning", "Pinned") : ""}
            </div>
            <p class="text-muted" style="white-space:pre-wrap">${App.esc(a.content)}</p>
            ${App.role() === "ADMIN" ? `<div class="mt-2"><button class="btn btn-ghost btn-sm btn-danger" onclick="Shared.deleteAnnouncement(${a.id})">${svg(I.trash)} Delete</button></div>` : ""}
          </div>`).join("") + `</div>`;
      } catch (e) { wrap.innerHTML = App.alert("error", e.message); }
    },

    createAnnouncement() {
      App.modal({
        title: "New Announcement",
        body: `<div class="form-group"><label>Title</label><input class="form-control" id="ann-title" placeholder="e.g. Enrollment Schedule"></div>
               <div class="form-group"><label>Message</label><textarea class="form-control" id="ann-content" rows="4" placeholder="Write the announcement…"></textarea></div>
               <div class="form-row cols-2"><div class="form-group"><label>Audience</label><select class="form-control" id="ann-target"><option value="ALL">Everyone</option><option value="STUDENT">Students</option><option value="STAFF">Staff</option><option value="FACULTY">Faculty</option></select></div>
               <div class="form-group"><label><input type="checkbox" id="ann-pinned"> Pin to top</label></div></div>`,
        footer: `<button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="ann-save">Publish</button>`,
        onOpen: (m) => {
          m.querySelector("#ann-save").addEventListener("click", async () => {
            const title = m.querySelector("#ann-title").value.trim();
            const content = m.querySelector("#ann-content").value.trim();
            if (!title || !content) { App.toast("Title and message are required.", "warning"); return; }
            try {
              await App.api("/announcements", { method: "POST", body: JSON.stringify({ title, content, target_role: m.querySelector("#ann-target").value, is_pinned: m.querySelector("#ann-pinned").checked }) });
              App.toast("Announcement published.", "success"); App.closeModal(); Shared.loadAnnouncements();
            } catch (e) { App.toast(e.message, "error"); }
          });
        },
      });
    },

    async deleteAnnouncement(id) {
      App.confirm("Delete Announcement", "This announcement will be permanently removed.", async () => {
        try { await App.api(`/announcements/${id}`, { method: "DELETE" }); App.toast("Deleted.", "success"); Shared.loadAnnouncements(); }
        catch (e) { App.toast(e.message, "error"); }
      }, true);
    },

    /* ---------------- Profile (student / staff / admin) ---------------- */
    profilePage() {
      App.setPageTitle("My Profile");
      App.content().innerHTML = `<div id="profile-wrap">${App.loadingBlock("Loading profile…")}</div>`;
      Shared.loadProfile();
    },

    async loadProfile() {
      const wrap = document.getElementById("profile-wrap");
      try {
        const role = App.role();
        let p, face;
        if (role === "ADMIN") {
          p = await App.api("/admin/me");
        } else if (role === "STUDENT") {
          p = await App.api("/students/me");
          face = await App.api("/students/me/face");
        } else {
          p = await App.api("/staff/me");
        }

        const uid = p.admin_id || p.user_id;
        const photoUrl = p.photo_url || (uid ? App.API + '/images/' + uid : '');
        const fullName = role === "ADMIN" ? `${p.first_name || ""} ${p.last_name || ""}`.trim() || p.email || p.admin_id : `${p.first_name} ${p.last_name}`;
        const displayRole = role === "ADMIN" ? "Administrator" : (p.role || role);

        const roleIcon = role === "ADMIN" ? I.settings : role === "STUDENT" ? I.user : I.users;

        const infoRows = [
          { label: role === "ADMIN" ? "Admin ID" : "ID Number", value: p.admin_id || p.user_id },
          { label: "Email", value: p.email || "\u2014" },
        ];

        if (role !== "ADMIN") {
          infoRows.push(
            { label: "Department", value: p.department_section || "\u2014" },
            { label: "Contact Number", value: p.contact_number || "\u2014" },
            { label: "Emergency Contact", value: p.emergency_contact || "\u2014" }
          );
        }

        const infoHtml = infoRows.map((r) =>
          `<div class="pf-field"><span class="pf-field-label">${App.esc(r.label)}</span><span class="pf-field-value">${App.esc(r.value)}</span></div>`
        ).join("");
        wrap.innerHTML = `
          <div class="pf-wrap">
            <div class="pf-hero">
              <div class="pf-hero-avatar">
                <img src="${App.esc(photoUrl)}" alt="" id="pf-avatar"
                  onerror="this.src='/static/images/default-avatar.png'">
                <button class="pf-upload-btn" onclick="Shared.openPhotoUpload()" title="Change photo">
                  ${svg(I.camera)}
                </button>
              </div>
              <div class="pf-hero-info">
                <h1>${App.esc(fullName)}</h1>
                <div class="pf-meta">
                  <span class="pf-role">${svg(roleIcon)} ${App.esc(displayRole)}</span>
                  ${p.department_section ? `<span class="pf-dept">${App.esc(p.department_section)}</span>` : ""}
                </div>
                <div class="pf-id">${svg(I.clipboard)} ${App.esc(p.admin_id || p.user_id)}</div>
              </div>
              <div class="pf-hero-actions">
                <button class="btn btn-secondary btn-sm" onclick="Shared.requestProfileUpdate()">${svg(I.edit)} Edit</button>
              </div>
            </div>

            <div class="pf-body">
              <div class="pf-card">
                <div class="pf-card-top"></div>
                <div class="pf-card-body">
                  <div class="pf-card-title">${svg(I.user)} Account Information</div>
                  <div class="pf-grid">${infoHtml}</div>
                </div>
              </div>

              ${role === "STUDENT" ? `
              <div class="pf-card">
                <div class="pf-card-top"></div>
                <div class="pf-card-body">
                  <div class="pf-card-title">${svg(I.face)} Face Registration</div>
                  <div class="pf-face">
                    <div class="pf-face-icon ${face && face.status === "REGISTERED" ? "success" : ""}">
                      ${face && face.status === "REGISTERED" ? svg(I.checkCircle) : svg(I.face)}
                    </div>
                    <div class="pf-face-info">
                      <div class="pf-face-status">${face && face.status === "REGISTERED" ? App.badge("success", "Registered") : App.badge("warning", "Not Registered")}</div>
                      <div class="pf-face-sub">${face && face.status === "REGISTERED" ? "Your face is enrolled and recognized by attendance scanners." : "You have not enrolled your face yet."}</div>
                    </div>
                    <div class="pf-face-actions">
                      <button class="btn btn-secondary btn-sm" onclick="Shared.openFaceUpload()">${svg(I.upload)} Update</button>
                      <button class="btn btn-ghost btn-sm" onclick="Shared.requestFaceReregister()">${svg(I.refresh)} Re-register</button>
                      <a href="#/dashboard/face" class="btn btn-ghost btn-sm">Details \u2192</a>
                    </div>
                  </div>
                </div>
              </div>` : ""}

              <div class="pf-card">
                <div class="pf-card-top"></div>
                <div class="pf-card-body">
                  <div class="pf-card-title">${svg(I.settings)} Security</div>
                  <div class="pf-pw">
                    <div class="form-group">
                      <label>Current Password</label>
                      <div class="input-group">
                        <input class="form-control" id="cp-old" type="password" placeholder="Enter current password">
                        <button class="pw-toggle" type="button" onclick="Shared.togglePassword('cp-old')" title="Toggle visibility">${svg(I.eye)}</button>
                      </div>
                    </div>
                    <div class="form-group">
                      <label>New Password</label>
                      <div class="input-group">
                        <input class="form-control" id="cp-new" type="password" placeholder="Enter new password (min 6 chars)">
                        <button class="pw-toggle" type="button" onclick="Shared.togglePassword('cp-new')" title="Toggle visibility">${svg(I.eye)}</button>
                      </div>
                    </div>
                    <div class="form-group">
                      <label>Confirm New Password</label>
                      <div class="input-group">
                        <input class="form-control" id="cp-confirm" type="password" placeholder="Confirm new password">
                        <button class="pw-toggle" type="button" onclick="Shared.togglePassword('cp-confirm')" title="Toggle visibility">${svg(I.eye)}</button>
                      </div>
                    </div>
                    <div class="pf-pw-actions">
                      <button class="btn btn-primary" id="cp-save">${svg(I.check)} Update Password</button>
                      <span id="cp-msg" class="text-sm text-muted"></span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>`;

        // Bind change password handler
        wrap.querySelector("#cp-save").addEventListener("click", Shared.changePassword);

        // Allow Enter key to submit password
        wrap.querySelectorAll("#cp-old, #cp-new, #cp-confirm").forEach(el => {
          el.addEventListener("keydown", (e) => { if (e.key === "Enter") Shared.changePassword(); });
        });

      } catch (e) { wrap.innerHTML = App.alert("error", e.message); }
    },

    togglePassword(id) {
      const el = document.getElementById(id);
      if (!el) return;
      const isPassword = el.type === "password";
      el.type = isPassword ? "text" : "password";
      const btn = el.parentElement.querySelector(".pw-toggle");
      if (btn) btn.innerHTML = isPassword ? svg(I.eyeOff) : svg(I.eye);
    },

    async changePassword() {
      const oldp = document.getElementById("cp-old")?.value;
      const newp = document.getElementById("cp-new")?.value;
      const confirm = document.getElementById("cp-confirm")?.value;
      const msg = document.getElementById("cp-msg");
      const btn = document.getElementById("cp-save");
      if (!oldp || !newp) { App.toast("Please fill in all password fields.", "warning"); return; }
      if (newp.length < 6) { App.toast("New password must be at least 6 characters.", "warning"); return; }
      if (newp !== confirm) { App.toast("Passwords do not match.", "warning"); return; }
      try {
        btn.disabled = true; btn.innerHTML = App.spinner() + " Updating…";
        await App.api("/auth/change-password", { method: "POST", body: JSON.stringify({ old_password: oldp, new_password: newp }) });
        App.toast("Password updated successfully.", "success");
        document.getElementById("cp-old").value = "";
        document.getElementById("cp-new").value = "";
        document.getElementById("cp-confirm").value = "";
        if (msg) msg.textContent = "";
      } catch (e) {
        App.toast(e.message, "error");
      } finally {
        btn.disabled = false; btn.innerHTML = `${svg(I.check)} Update Password`;
      }
    },

    openPhotoUpload() {
      const existing = document.getElementById("pf-photo-input");
      if (existing) existing.remove();
      const input = document.createElement("input");
      input.type = "file";
      input.id = "pf-photo-input";
      input.className = "pf-photo-input";
      input.accept = "image/jpeg,image/png,image/jpg";
      input.addEventListener("change", async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        if (file.size > 5 * 1024 * 1024) { App.toast("Image must be under 5MB.", "warning"); return; }
        const validTypes = ["image/jpeg", "image/png", "image/jpg"];
        if (!validTypes.includes(file.type)) { App.toast("Only JPG and PNG images are allowed.", "warning"); return; }
        const fd = new FormData();
        fd.append("image", file);
        try {
          await App.api("/upload/photo", { method: "POST", body: fd });
          App.toast("Profile photo updated.", "success");
          // Use the current user id directly (stable even after token refresh).
          const uid = App.uid();
          const img = document.getElementById("pf-avatar");
          if (img && uid) img.src = App.API + "/images/" + uid + "?t=" + Date.now();
        } catch (e) { App.toast(e.message, "error"); }
      });
      input.click();
    },

    requestProfileUpdate() {
      const role = App.role();
      if (role === "ADMIN") {
        App.toast("Admin profile editing is not available yet.", "info");
        return;
      }
      App.modal({
        title: "Request Profile Changes",
        body: `<p class="form-hint">Changes are applied only after administrator approval.</p>
          <div id="pu-fields"></div>
          <button class="btn btn-secondary btn-sm mt-1" type="button" onclick="Shared.addProfileField()">${svg(I.plus)} Add field</button>`,
        footer: `<button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="pu-save">Submit Request</button>`,
        onOpen: (m) => {
          Shared.addProfileField();
          m.querySelector("#pu-save").addEventListener("click", async () => {
            const rows = m.querySelectorAll(".pu-row");
            let submitted = 0;
            for (const row of rows) {
              const field = row.querySelector(".pu-field").value;
              const val = row.querySelector(".pu-value").value.trim();
              if (!val) continue;
              try { await App.api("/students/me", { method: "PUT", body: JSON.stringify({ [field]: val }) }); submitted++; }
              catch (e) { App.toast(e.message, "error"); }
            }
            if (submitted) { App.toast(`${submitted} change request(s) submitted.`, "success"); App.closeModal(); }
            else App.toast("Enter at least one value.", "warning");
          });
        },
      });
    },

    addProfileField() {
      const fields = [["first_name", "First Name"], ["last_name", "Last Name"], ["email", "Email"], ["contact_number", "Contact Number"], ["emergency_contact", "Emergency Contact"]];
      const wrap = document.getElementById("pu-fields");
      if (!wrap) return;
      const row = document.createElement("div");
      row.className = "pu-row form-row cols-2 mb-1";
      row.innerHTML = `<select class="form-control pu-field">${fields.map(([v, l]) => `<option value="${v}">${l}</option>`).join("")}</select>
        <input class="form-control pu-value" placeholder="New value">`;
      wrap.appendChild(row);
    },

    openFaceUpload() {
      App.modal({
        title: "Update Face Image",
        body: `<p class="form-hint">Capture a clear, front-facing photo with good lighting.</p>
          <video id="face-video" autoplay playsinline muted style="width:100%;border-radius:12px;background:#000;display:none"></video>
          <div id="face-preview" class="empty-state">Camera off</div>
          <div class="toolbar mt-2"><button class="btn btn-secondary" id="face-start">Start Camera</button>
          <button class="btn btn-primary" id="face-capture" disabled>Capture & Save</button></div>
          <div id="face-msg"></div>`,
        size: "lg",
        onOpen: (m) => {
          const video = m.querySelector("#face-video");
          const preview = m.querySelector("#face-preview");
          const start = m.querySelector("#face-start");
          const cap = m.querySelector("#face-capture");
          let blob = null;
          start.addEventListener("click", async () => {
            try { await App.startCamera(video); video.style.display = "block"; preview.style.display = "none"; cap.disabled = false; }
            catch (e) { m.querySelector("#face-msg").innerHTML = App.alert("error", "Camera access denied."); }
          });
          cap.addEventListener("click", async () => {
            blob = await App.captureFrame(video);
            cap.disabled = true; cap.innerHTML = App.spinner() + " Saving…";
            const fd = new FormData(); fd.append("image", blob, "face.jpg");
            try {
              await App.api("/students/me/face", { method: "POST", body: fd });
              App.toast("Face updated.", "success"); App.stopCamera(); App.closeModal();
            } catch (e) { App.toast(e.message, "error"); cap.disabled = false; cap.textContent = "Capture & Save"; }
          });
        },
      });
    },

    async requestFaceReregister() {
      try { await App.api("/students/me/face-reregister-request", { method: "POST" }); App.toast("Re-registration requested.", "success"); }
      catch (e) { App.toast(e.message, "error"); }
    },

    /* ---------------- Face (student) ---------------- */
    facePage() {
      App.setPageTitle("Face Profile");
      App.content().innerHTML = `<div id="face-wrap">${App.loadingBlock("Loading…")}</div>`;
      Shared.loadFaceProfile();
    },

    async loadFaceProfile() {
      const wrap = document.getElementById("face-wrap");
      try {
        const face = await App.api("/students/me/face");
        const reqs = await App.api("/students/me/requests");
        const qrResp = await App.api("/students/me/qr").catch(() => null);
        const qrToken = qrResp ? qrResp.message : null;
        const registered = face.status === "REGISTERED";
        const approvals = (reqs.approvals || []).filter((a) => a.request_type === "FACE_REREGISTER");
        wrap.innerHTML = `
          <div class="page-header"><div><h1>Face & QR Profile</h1><p>Manage your biometric enrollment and QR attendance code.</p></div>
            <button class="btn btn-secondary" onclick="Shared.openFaceUpload()">${svg(I.upload)} Update Face</button></div>
          <div class="grid grid-3">
            <div class="card"><div class="card-header"><div class="card-title">Enrollment Status</div></div>
              <div class="d-flex align-center gap-2">${registered ? App.badge("success", "Registered") : App.badge("warning", "Not Registered")}</div>
              <p class="text-muted text-sm mt-2">${registered ? "Your face is enrolled and recognized by attendance scanners." : "You are not yet enrolled. Please update your face image."}</p>
            </div>
            <div class="card"><div class="card-header"><div class="card-title">QR Attendance Code</div></div>
              ${qrToken ? `<div class="d-flex flex-column align-center" style="padding:0.5rem 0"><img src="${App.API}/qr/${App.uid()}" alt="QR Code" style="width:140px;height:140px;border-radius:8px;background:#fff;padding:4px;"><div class="text-xs text-muted mt-1">Show this at the scanner</div></div>` : App.emptyState("No QR code", "Contact your administrator.", I.face)}
            </div>
            <div class="card"><div class="card-header"><div class="card-title">Re-registration Requests</div></div>
              ${approvals.length ? approvals.map((a) => `<div class="timeline-item ${a.status === "APPROVED" ? "success" : a.status === "REJECTED" ? "warning" : ""}"><span class="tl-dot"></span><div class="tl-title">${App.esc(a.request_type)}</div><div class="tl-sub">${App.statusBadge(a.status)} · ${App.fmtDateTime(a.requested_at)}</div></div>`).join("") : App.emptyState("No requests", "Request re-registration if your face is not recognized.", I.face)}
              <button class="btn btn-ghost mt-2" onclick="Shared.requestFaceReregister()">${svg(I.refresh)} Request Re-registration</button>
            </div>
          </div>`;
      } catch (e) { wrap.innerHTML = App.alert("error", e.message); }
    },

    /* ---------------- Notifications (student) ---------------- */
    notificationsPage() {
      App.setPageTitle("Notifications");
      App.content().innerHTML = `
        <div class="page-header"><div><h1>Notifications</h1><p>Your alerts and approval updates.</p></div>
          <button class="btn btn-secondary" onclick="Shared.markAllRead()">${svg(I.check)} Mark all read</button></div>
        <div id="notif-list">${App.loadingBlock("Loading…")}</div>`;
      Shared.loadNotifications();
    },

    async loadNotifications() {
      const wrap = document.getElementById("notif-list");
      try {
        const list = await App.api("/students/me/notifications");
        if (!list.length) { wrap.innerHTML = App.emptyState("No notifications", "You're all caught up.", I.bell); return; }
        wrap.innerHTML = `<div class="card" style="padding:0;overflow:hidden">` + list.map((n) => `
          <div class="d-flex gap-2 align-center" style="padding:.9rem 1.1rem;border-bottom:1px solid var(--border);${n.is_read ? "opacity:.6" : ""}">
            <span class="avatar-sm" style="background:${n.notification_type === "APPROVAL" ? "var(--info-50)" : "var(--surface-2)"};color:${n.notification_type === "APPROVAL" ? "var(--info-700)" : "var(--muted)"}">${svg(I.bell, 16)}</span>
            <div class="flex-1"><div class="fw-600">${App.esc(n.title)}</div><div class="text-muted text-sm">${App.esc(n.message)}</div><div class="text-xs text-muted">${App.fmtDateTime(n.created_at)}</div></div>
            ${n.is_read ? "" : `<button class="btn btn-ghost btn-sm" onclick="Shared.markRead(${n.id})">Mark read</button>`}
          </div>`).join("") + `</div>`;
        App.refreshNotifBadge();
      } catch (e) { wrap.innerHTML = App.alert("error", e.message); }
    },

    async markRead(id) { try { await App.api(`/students/me/notifications/${id}/read`, { method: "POST" }); Shared.loadNotifications(); } catch (e) { App.toast(e.message, "error"); } },
    async markAllRead() { try { await App.api("/notifications/mark-all-read", { method: "POST" }); App.toast("All marked read.", "success"); Shared.loadNotifications(); } catch (e) { App.toast(e.message, "error"); } },

    async refreshNotifBadge() {
      try {
        const list = await App.api("/students/me/notifications");
        const unread = list.filter((n) => !n.is_read).length;
        const dot = document.getElementById("notif-dot");
        if (dot) dot.style.display = unread ? "block" : "none";
      } catch (e) {}
    },

    /* ---------------- Scanner embed ---------------- */
    scannerPage() {
      App.setPageTitle("Live Scanner");
      App.content().innerHTML = `
        <div class="page-header"><div><h1>Live Attendance Scanner</h1><p>Full-screen kiosk mode is available for entrance terminals.</p></div>
          <a class="btn btn-secondary" href="/scanner" target="_blank">${svg(I.camera)} Open Kiosk Mode</a></div>
        <iframe class="embed-frame" src="/scanner" title="Scanner"></iframe>`;
    },

    /* ---------------- Overview renderers ---------------- */
    async studentOverview() {
      App.setPageTitle("Student Dashboard");
      App.content().innerHTML = `<div id="ov">${App.loadingBlock("Loading your dashboard…")}</div>`;
      if (window._liveTimer) clearInterval(window._liveTimer);
      await Shared._loadStudentDashboard();
      window._liveTimer = setInterval(() => Shared._loadStudentDashboard(true), 15000);
    },

    async _loadStudentDashboard(silent) {
      const el = document.getElementById("ov");
      if (!el) return;
      try {
        const [live, d] = await Promise.all([
          App.api("/dashboard/live"),
          silent ? null : App.api("/students/me/dashboard").catch(() => null),
        ]);
        if (silent && !d) return;
        if (!d) return;
        el.innerHTML = `
          <div class="grid grid-4 mb-3">
            ${Shared.statCard("Attendance Rate", d.attendance_rate + "%", "success", I.clock, `Based on ${d.total} records`)}
            ${Shared.statCard("Present", d.present, "success", I.check, "Sessions marked present")}
            ${Shared.statCard("This Week", d.week_count, "primary", I.calendar, "Attendance days this week")}
            ${Shared.statCard("Unread", d.unread_notifications, d.unread_notifications ? "warning" : "muted", I.bell, "Notifications")}
          </div>
          <div class="grid grid-3">
            <div class="chart-card"><div class="card-title mb-2">Last 30 Days</div>${barChart(d.series, (s) => String(s.date).slice(5))}</div>
            <div class="card"><div class="card-header"><div class="card-title">Face & Status</div></div>
              <div class="mb-2">${d.face_status === "REGISTERED" ? App.badge("success", "Face Registered") : App.badge("warning", "Face Not Registered")}</div>
              <div class="text-sm text-muted">Attendance rate: <b>${d.attendance_rate}%</b></div>
              <div class="progress mt-1"><div class="progress-bar ${d.attendance_rate >= 75 ? "success" : d.attendance_rate >= 50 ? "warning" : "danger"}" style="width:${d.attendance_rate}%"></div></div>
            </div>
            <div class="card"><div class="card-header"><div class="card-title">Summary</div></div>
              <div class="timeline">
                <div class="timeline-item"><span class="tl-dot"></span><div class="tl-title">Total Records</div><div class="tl-sub">${d.total}</div></div>
                <div class="timeline-item success"><span class="tl-dot"></span><div class="tl-title">Present</div><div class="tl-sub">${d.present}</div></div>
                <div class="timeline-item warning"><span class="tl-dot"></span><div class="tl-title">Late</div><div class="tl-sub">${d.late}</div></div>
                <div class="timeline-item"><span class="tl-dot"></span><div class="tl-title">This Month</div><div class="tl-sub">${d.month_count}</div></div>
              </div>
            </div>
          </div>
          <div class="card mt-3"><div class="card-header"><div class="card-title">Recent Attendance</div><a href="#/dashboard/attendance">View all →</a></div>
            ${d.recent.length ? `<div class="table-wrap"><table class="data"><thead><tr><th>Name</th><th>Date</th><th>Time In</th><th>Time Out</th><th>Status</th></tr></thead><tbody>` +
              d.recent.map((r) => `<tr><td class="cell-strong">${App.esc(r.user_name)}</td><td>${App.esc(r.date)}</td><td>${App.esc(r.time_in || "—")}</td><td>${App.esc(r.time_out || "—")}</td><td>${App.statusBadge(r.attendance_status)}</td></tr>`).join("") +
              `</tbody></table></div>` : App.emptyState("No recent activity", "Your attendance will appear here.", I.calendar)}
          </div>`;
      } catch (e) { document.getElementById("ov").innerHTML = App.alert("error", e.message); }
    },

    async staffOverview() {
      App.setPageTitle("Staff Dashboard");
      App.content().innerHTML = `<div id="ov">${App.loadingBlock("Loading dashboard…")}</div>`;
      try {
        const d = await App.api("/staff/dashboard/stats");
        document.getElementById("ov").innerHTML = `
          <div class="grid grid-4 mb-3">
            ${Shared.statCard("Today", d.attendance_today, "primary", I.calendar, "My attendance today")}
            ${Shared.statCard("Total", d.total_attendance, "success", I.users, "My total attendance")}
            ${Shared.statCard("This Month", d.month_attendance, "warning", I.clock, "My attendance this month")}
            ${Shared.statCard("Announcements", d.announcements, "muted", I.megaphone, "Published")}
          </div>
          <div class="grid grid-3">
            <div class="chart-card" style="grid-column:span 2"><div class="card-title mb-2">Attendance — Last 14 Days</div>${barChart(d.series, (s) => String(s.date).slice(5))}</div>
            <div class="card"><div class="card-header"><div class="card-title">Recent Activity</div></div>
              ${d.recent.length ? `<div class="timeline">` + d.recent.map((r) => `<div class="timeline-item success"><span class="tl-dot"></span><div class="tl-title">${App.esc(r.user_name)}</div><div class="tl-sub">${App.esc(r.date)} · ${App.esc(r.time_in || "")} · ${App.statusBadge(r.attendance_status)}</div></div>`).join("") + `</div>` : App.emptyState("No activity", "No recent attendance.", I.calendar)}
            </div>
          </div>`;
      } catch (e) { document.getElementById("ov").innerHTML = App.alert("error", e.message); }
    },

    async adminOverview() {
      App.setPageTitle("Administrator Dashboard");
      App.content().innerHTML = `<div id="ov">${App.loadingBlock("Loading dashboard…")}</div>`;
      if (window._liveTimer) clearInterval(window._liveTimer);
      await Shared._loadAdminDashboard();
      window._liveTimer = setInterval(() => Shared._loadAdminDashboard(true), 10000);
    },

    async _loadAdminDashboard(silent) {
      const wrap = document.getElementById("ov");
      if (!wrap) return;
      try {
        const [live, d] = await Promise.all([
          App.api("/dashboard/live"),
          App.api("/admin/dashboard/stats").catch(() => null),
        ]);
        if (silent && !d) return;
        const dist = (d && d.role_distribution) || [];
        const donut = buildDonut(dist);
        const methodBadge = (m) => {
          const colors = { Face: "primary", QR: "warning", RFID: "primary" };
          return App.badge(colors[m] || "muted", m || "—", true);
        };
        wrap.innerHTML = `
          <div class="grid grid-4 mb-3">
            ${Shared.statCard("Total Students", live.total_students, "primary", I.users, "Active")}
            ${Shared.statCard("Present Today", live.present_today, "success", I.checkCircle, "Checked in today")}
            ${Shared.statCard("Absent Today", live.absent_today, live.absent_today > 0 ? "danger" : "muted", I.xCircle, "No attendance today")}
            ${Shared.statCard("Late Today", live.late_today, live.late_today > 0 ? "warning" : "muted", I.clock, "Arrived after cutoff")}
          </div>
          ${d ? `<div class="grid grid-4 mb-3">
            ${Shared.statCard("RFID Today", d.rfid_today, "primary", I.plus, "RFID scans today")}
            ${Shared.statCard("RFID Weekly", d.rfid_weekly_scans, "primary", I.plus, "RFID scans (last 7 days)")}
            ${Shared.statCard("RFID Monthly", d.rfid_monthly_scans, "primary", I.plus, "RFID scans (this month)")}
            ${Shared.statCard("Total Today", d.rfid_today + d.face_today + d.qr_today, "success", I.check, "All methods")}
          </div>` : ""}

          <div style="font-size:0.8rem;color:var(--muted);text-align:right;margin-bottom:0.5rem">Last updated: ${live.timestamp} · <a href="#" onclick="Shared._loadAdminDashboard();return false" style="color:var(--accent)">Refresh now</a></div>
          <div class="grid grid-3">
            <div class="chart-card" style="grid-column:span 2"><div class="card-header"><div class="card-title">RFID Attendance — Last 14 Days</div><span class="text-xs text-muted">RFID scan volume</span></div>${barChart(d ? (d.rfid_series || d.series) : [])}</div>

            <div class="card"><div class="card-header"><div class="card-title">Population</div></div>${donut}${d ? `<div class="mt-2 text-xs text-muted">Attended today: <b>${live.unique_attendees}</b> · Total: <b>${live.total_students}</b></div>` : ""}</div>
          </div>
          ${d ? `<div class="card mt-3"><div class="card-header"><div class="card-title">Recent Attendance</div><a href="#/dashboard/attendance">View all →</a></div>
            ${d.recent && d.recent.length ? `<div class="table-wrap"><table class="data"><thead><tr><th>Name</th><th>ID</th><th>Date</th><th>Time In</th><th>Status</th><th>Method</th><th>Device</th></tr></thead><tbody>` +
              d.recent.map((r) => `<tr><td class="cell-strong">${App.esc(r.user_name)}</td><td class="cell-sub">${App.esc(r.user_id)}</td><td>${App.esc(r.date)}</td><td>${App.esc(r.time_in || "—")}</td><td>${App.statusBadge(r.attendance_status)}</td><td>${methodBadge(r.scan_method)}</td><td class="cell-sub">${App.esc(r.device_id)}</td></tr>`).join("") +
              `</tbody></table></div>` : App.emptyState("No recent activity", "Attendance records will appear here.", I.calendar)}
          </div>` : ""}`;
      } catch (e) { if (!silent) wrap.innerHTML = App.alert("error", e.message); }
    },

    statCard(label, value, tone, icon, meta) {
      return `<div class="stat ${tone}"><div class="stat-icon">${svg(icon)}</div>
        <div class="stat-label">${App.esc(label)}</div><div class="stat-value">${App.esc(value)}</div>
        <div class="stat-meta">${App.esc(meta || "")}</div></div>`;
    },
  };

  function buildDonut(dist) {
    if (!dist.length) return App.emptyState("No data", "No active users.", I.users);
    const total = dist.reduce((s, d) => s + d.count, 0) || 1;
    const colors = { STUDENT: "var(--secondary)", STAFF: "var(--success)", FACULTY: "var(--warning)" };
    let acc = 0; const segs = dist.map((d) => {
      const start = (acc / total) * 360; acc += d.count; const end = (acc / total) * 360;
      return `<stop offset="${(start / 360) * 100}%" stop-color="${colors[d.role] || "var(--accent)"}"/><stop offset="${(end / 360) * 100}%" stop-color="${colors[d.role] || "var(--accent)"}"/>`;
    }).join("");
    const legend = dist.map((d) => `<div class="item"><span class="swatch" style="background:${colors[d.role] || "var(--accent)"}"></span>${App.esc(d.role)} — ${d.count}</div>`).join("");
    return `<div class="donut-wrap"><div class="donut" style="background:conic-gradient(${dist.map((d, i) => `${colors[d.role] || "var(--accent)"} ${(i === 0 ? 0 : dist.slice(0, i).reduce((s, x) => s + x.count, 0) / total * 100)}% ${dist.slice(0, i + 1).reduce((s, x) => s + x.count, 0) / total * 100}%`).join(",")})"></div><div class="legend">${legend}</div></div>`;
  }

  /* ---------------- Route registration (shared) ---------------- */
  App.router.add("/dashboard/attendance", (p) => Shared.attendancePage(p));
  App.router.add("/dashboard/announcements", () => Shared.announcementsPage());
  App.router.add("/dashboard/profile", () => Shared.profilePage());
  App.router.add("/dashboard/face", () => Shared.facePage());
  App.router.add("/dashboard/notifications", () => Shared.notificationsPage());
  App.router.add("/dashboard/scanner", () => Shared.scannerPage());
  // /dashboard/students and /dashboard/overview dispatched elsewhere / above.

  // --- Global Attendance Success Modal (Face / QR / RFID unified) ---
  // Used by all scanner pages (including RFID global listener) to show immediate feedback.
  // This modal is a lightweight overlay implemented using a plain DOM container,
  // so it works even when the scanner page does not use App.modal().
  (function attachUnifiedAttendanceModal() {
    const WIN = window;
    WIN.__attendanceSuccessModal = WIN.__attendanceSuccessModal || {
      _el: null,
      _timer: null,
      _cooldownKey: null,
      cooldownMs: 10000,
      lastShownAt: 0,
    };

    function ensureEl() {
      const state = WIN.__attendanceSuccessModal;
      if (state._el && document.body.contains(state._el)) return state._el;

      const el = document.createElement('div');
      el.id = 'attendance-success-modal';
      el.style.position = 'fixed';
      el.style.inset = '0';
      el.style.zIndex = '99999';
      el.style.display = 'none';
      el.style.alignItems = 'center';
      el.style.justifyContent = 'center';
      el.style.padding = '1.5rem';
      el.style.background = 'rgba(10,14,26,0.86)';
      el.style.backdropFilter = 'blur(14px)';
      el.style.opacity = '0';
      el.style.transform = 'translateY(10px) scale(0.98)';
      el.style.transition = 'opacity .25s ease, transform .25s ease';
      el.innerHTML = `
        <div style="width: min(520px, 94vw); border-radius: 18px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); padding: 1.25rem 1.25rem 1rem; box-shadow: 0 12px 70px rgba(0,0,0,0.35);">
          <div style="display:flex; align-items:center; justify-content:space-between; gap: 1rem;">
            <div style="display:flex; align-items:center; gap: 0.9rem;">
              <div id="att-success-icon" style="width:64px; height:64px; border-radius:50%; display:flex; align-items:center; justify-content:center; background: rgba(34,197,94,0.15);">
                <svg id="att-success-svg" width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" style="color:#22c55e">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"/>
                </svg>
              </div>
              <div>
                <div id="att-success-title" style="font-size:1.15rem; font-weight:800; letter-spacing:-0.02em">Attendance Recorded</div>
                <div id="att-success-sub" style="font-size:0.85rem; color: rgba(255,255,255,0.55); margin-top:0.15rem">—</div>
              </div>
            </div>
            <button id="att-success-close" aria-label="Close" style="border:none; background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.7); border-radius: 10px; padding: 0.35rem 0.55rem; cursor:pointer; font-size: 1rem; line-height: 1;">✕</button>
          </div>

          <div style="display:flex; gap: 1rem; align-items:center; margin-top: 1rem;">
            <div style="width:76px; height:76px; border-radius:50%; overflow:hidden; background: rgba(255,255,255,0.05); border: 4px solid rgba(34,197,94,0.55); display:flex; align-items:center; justify-content:center;">
              <img id="att-success-photo" src="/static/images/default-avatar.png" alt="" style="width:100%; height:100%; object-fit:cover; display:block;" onerror="this.src='/static/images/default-avatar.png'"/>
            </div>
            <div style="flex:1; min-width:0;">
              <div id="att-success-name" style="font-size:1.35rem; font-weight:900; white-space:nowrap; overflow:hidden; text-overflow:ellipsis">User</div>
              <div id="att-success-meta" style="margin-top:0.25rem; font-size:0.9rem; color: rgba(255,255,255,0.55)">ID: —</div>
              <div id="att-success-details" style="margin-top:0.3rem; font-size:0.82rem; color: rgba(255,255,255,0.45); line-height: 1.35; max-width: 360px;">—</div>
            </div>
          </div>

          <div style="margin-top: 1rem; display:grid; grid-template-columns: 1fr 1fr; gap: 0.6rem;">
            <div style="padding: 0.6rem 0.7rem; border-radius: 12px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);">
              <div style="font-size:0.65rem; color: rgba(255,255,255,0.35); text-transform:uppercase; letter-spacing:0.04em">Attendance</div>
              <div id="att-success-attendance" style="font-size:0.95rem; font-weight:800; margin-top:0.15rem">Time In</div>
            </div>
            <div style="padding: 0.6rem 0.7rem; border-radius: 12px; background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.06);">
              <div style="font-size:0.65rem; color: rgba(255,255,255,0.35); text-transform:uppercase; letter-spacing:0.04em">Date & Time</div>
              <div id="att-success-datetime" style="font-size:0.95rem; font-weight:800; margin-top:0.15rem">—</div>
            </div>
          </div>

          <div id="att-success-countdown" style="margin-top:0.75rem; text-align:right; font-size:0.75rem; color: rgba(255,255,255,0.35)">Closing…</div>
        </div>
      `;
      el.addEventListener('click', (e) => {
        if (e.target === el) hide();
      });
      el.querySelector('#att-success-close').addEventListener('click', () => hide());
      document.body.appendChild(el);
      state._el = el;
      return el;
    }

    function hide() {
      const state = WIN.__attendanceSuccessModal;
      if (state._timer) { clearInterval(state._timer); state._timer = null; }
      if (!state._el) return;
      state._el.style.display = 'none';
      state._el.style.opacity = '0';
      state._el.style.transform = 'translateY(10px) scale(0.98)';
    }

    function show(data, kind /* success | error */, ttlSeconds = 4) {
      const state = WIN.__attendanceSuccessModal;
      const el = ensureEl();

      const now = Date.now();
      const userId = data && (data.user_id || data.userId || data.uid || 'unknown');
      const scanAction = data && (data.scan_action || data.action || 'in');
      const stableKey = String(userId) + ':' + String(scanAction) + ':' + kind;
      // prevent duplicates during cooldown
      if (state._cooldownKey === stableKey && now - state.lastShownAt < state.cooldownMs) return;
      state._cooldownKey = stableKey;
      state.lastShownAt = now;

      const photo = data && (data.photo_url || data.photoUrl || null);
      const name = data && (data.user_name || data.full_name || (data.first_name && data.last_name ? (data.first_name + ' ' + data.last_name).trim() : null) || 'User');
      const idNum = data && (data.user_id || '');
      const role = data && (data.role || data.user_role || '');
      const section = data && (data.section || data.department_section || data.department || data.department_section || '');
      const status = data && (data.attendance_status || data.status || 'PRESENT');
      const action = data && (data.scan_action || 'in');
      const course = data && (data.course || '');
      const yearLevel = data && (data.year_level || '');

      const badgeText = action === 'out' ? 'Time Out' : (status === 'LATE' ? 'Late Check-in' : 'Time In');
      const dateStr = new Date().toLocaleString('en-US', { timeZone: 'Asia/Manila' });

      const detailsParts = [];
      if (role) detailsParts.push('Role: ' + role);
      if (section) detailsParts.push(section.indexOf('Role:') === 0 ? section : ('Section/Dept: ' + section));
      if (course) detailsParts.push('Course: ' + course);
      if (yearLevel) detailsParts.push('Year: ' + yearLevel);
      const details = detailsParts.length ? detailsParts.join(' · ') : '—';

      el.querySelector('#att-success-photo').src = photo || '/static/images/default-avatar.png';
      el.querySelector('#att-success-name').textContent = name;
      el.querySelector('#att-success-meta').textContent = 'ID: ' + (idNum || '—');
      el.querySelector('#att-success-details').textContent = details;
      el.querySelector('#att-success-attendance').textContent = badgeText;
      el.querySelector('#att-success-datetime').textContent = dateStr;

      const titleEl = el.querySelector('#att-success-title');
      const subEl = el.querySelector('#att-success-sub');
      const iconWrap = el.querySelector('#att-success-icon');
      const svgEl = el.querySelector('#att-success-svg');
      const headerPhotoBorder = el.querySelector('div[style*="border: 4px solid"]');

      if (kind === 'success') {
        titleEl.textContent = 'Attendance Successful';
        subEl.textContent = (action === 'out' ? 'Time Out logged successfully' : (status === 'LATE' ? 'Late check-in recorded' : 'Time In recorded'));
        iconWrap.style.background = 'rgba(34,197,94,0.15)';
        svgEl.style.color = '#22c55e';
        if (headerPhotoBorder) headerPhotoBorder.style.border = '4px solid rgba(34,197,94,0.55)';
      } else {
        titleEl.textContent = 'Unregistered RFID';
        subEl.textContent = (data && data.detail ? data.detail : 'This RFID card is not registered.');
        iconWrap.style.background = 'rgba(239,68,68,0.15)';
        svgEl.innerHTML = '<path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>';
        svgEl.style.color = '#ef4444';
        if (headerPhotoBorder) headerPhotoBorder.style.border = '4px solid rgba(239,68,68,0.55)';
      }

      el.style.display = 'flex';
      // animate in
      requestAnimationFrame(() => {
        el.style.opacity = '1';
        el.style.transform = 'translateY(0) scale(1)';
      });

      let seconds = ttlSeconds;
      const cdEl = el.querySelector('#att-success-countdown');
      cdEl.textContent = 'Closing in ' + seconds + 's…';
      if (state._timer) clearInterval(state._timer);
      state._timer = setInterval(() => {
        seconds--;
        if (seconds <= 0) { hide(); return; }
        cdEl.textContent = 'Closing in ' + seconds + 's…';
      }, 1000);
    }

    WIN.AttendanceSuccessModal = {
      showSuccess: (data, ttlSeconds) => show(data, 'success', ttlSeconds || 4),
      showError: (data, ttlSeconds) => show(data, 'error', ttlSeconds || 4),
      hide,
    };
  })();

  // --- Unified RFID global listener => show modal ---
  document.addEventListener('rfid:success', function (e) {
    try {
      if (window.AttendanceSuccessModal && typeof window.AttendanceSuccessModal.showSuccess === 'function') {
        const data = e.detail || {};
        // Some backends may return unregistered via res.ok false (handled by rfid:error),
        // but in case success payload contains an error marker, treat as error.
        if (data && (data.error || data.detail === 'RFID card not recognized' || data.unregistered === true)) {
          window.AttendanceSuccessModal.showError(data);
        } else {
          window.AttendanceSuccessModal.showSuccess(data);
        }
      }
    } catch {}
  });

  document.addEventListener('rfid:error', function (e) {
    try {
      if (window.AttendanceSuccessModal && typeof window.AttendanceSuccessModal.showError === 'function') {
        const detail = (e && e.detail) || {};
        window.AttendanceSuccessModal.showError(detail);
      }
    } catch {}
  });

  window.Shared = Shared;
  App.refreshNotifBadge = Shared.refreshNotifBadge;
})();
