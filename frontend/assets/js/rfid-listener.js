(function () {
  'use strict';

  var API_BASE = '/api/v1';

  window.__rfidCooldowns = window.__rfidCooldowns || new Map();
  var COOLDOWN_MS = 30000;

  var hiddenInput = null;
  var rfidActive = false;
  var scanning = false;
  var debounceTimer = null;
  var focusInterval = null;
  var lastUid = '';

  function createHiddenInput() {
    if (hiddenInput && document.body.contains(hiddenInput)) return;
    hiddenInput = document.createElement('input');
    hiddenInput.type = 'text';
    hiddenInput.id = 'rfid-global-listener';
    hiddenInput.autocomplete = 'off';
    hiddenInput.inputMode = 'none';
    hiddenInput.spellcheck = false;
    hiddenInput.style.cssText = 'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;z-index:-1;pointer-events:none';
    hiddenInput.setAttribute('aria-hidden', 'true');
    document.body.appendChild(hiddenInput);
  }

  function focusInput() {
    if (hiddenInput && document.body.contains(hiddenInput)) {
      hiddenInput.focus();
    }
  }

  function playBeep(success) {
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var osc = ctx.createOscillator(), gain = ctx.createGain();
      osc.connect(gain); gain.connect(ctx.destination);
      osc.frequency.value = success ? 880 : 220; osc.type = 'sine';
      gain.gain.setValueAtTime(0.25, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + (success ? 0.25 : 0.4));
      osc.start(ctx.currentTime); osc.stop(ctx.currentTime + 0.4);
    } catch {}
  }

  function isOnCooldown(userId) {
    if (!window.__rfidCooldowns.has(userId)) return false;
    return (Date.now() - window.__rfidCooldowns.get(userId)) < COOLDOWN_MS;
  }

  function setCooldown(userId) {
    window.__rfidCooldowns.set(userId, Date.now());
  }

  function getRemainingCooldown(userId) {
    if (!window.__rfidCooldowns.has(userId)) return 0;
    var elapsed = Date.now() - window.__rfidCooldowns.get(userId);
    return Math.max(0, Math.ceil((COOLDOWN_MS - elapsed) / 1000));
  }

  function showToast(msg, type) {
    if (typeof App !== 'undefined' && App.toast) {
      App.toast(msg, type);
    }
  }

  async function processScan(uid) {
    console.log('[RFID] processScan start', { uid: uid, scanning: scanning });
    if (scanning || !uid) return;
    scanning = true;

    document.dispatchEvent(new CustomEvent('rfid:scanning-start', { detail: { uid: uid } }));

    playBeep(true);

    try {
      console.log('[RFID] sending request', { endpoint: API_BASE + '/attendance/rfid', uid: uid });
      var res = await fetch(API_BASE + '/attendance/rfid', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ rfid_uid: uid }),
      });
      console.log('[RFID] response received', { status: res.status, ok: res.ok });
      var ct = res.headers.get('content-type') || '';
      var data = ct.includes('application/json') ? await res.json() : null;
      console.log('[RFID] response parsed', { contentType: ct, hasJson: !!data, dataKeys: data && typeof data === 'object' ? Object.keys(data) : null });

      if (!res.ok) {
        var detail = (data && data.detail) || 'Scan failed';
        if (res.status === 429 && data && data.user_id) {
          document.dispatchEvent(new CustomEvent('rfid:cooldown', {
            detail: Object.assign({}, data, { remaining: data.retry_after || 30 })
          }));
        } else {
          document.dispatchEvent(new CustomEvent('rfid:error', {
            detail: { error: true, detail: detail, rfid_uid: uid }
          }));
        }
        playBeep(false);
      } else {
        var userId = data.user_id;
        if (isOnCooldown(userId)) {
          document.dispatchEvent(new CustomEvent('rfid:cooldown', {
            detail: Object.assign({}, data, { remaining: getRemainingCooldown(userId) })
          }));
        } else {
          document.dispatchEvent(new CustomEvent('rfid:success', { detail: data }));
          setCooldown(userId);
        }
      }
    } catch (e) {
      document.dispatchEvent(new CustomEvent('rfid:error', {
        detail: { error: true, detail: 'Network error. Please try again.', rfid_uid: uid }
      }));
      playBeep(false);
    }

    scanning = false;
    lastUid = uid;
    if (hiddenInput) hiddenInput.value = '';
    setTimeout(focusInput, 100);

    document.dispatchEvent(new CustomEvent('rfid:scanning-end'));
  }

  // Default toast handlers
  document.addEventListener('rfid:success', function (e) {
    var data = e.detail;
    var action = data.scan_action || 'in';
    var isLate = data.attendance_status === 'LATE';
    var badgeText;
    if (action === 'out') badgeText = '✓ Time Out Logged';
    else if (isLate) badgeText = '⏰ Late Check-in';
    else badgeText = '✓ Time In Logged';
    showToast((data.user_name || 'User') + ' — ' + badgeText, isLate ? 'warning' : 'success');
  });

  document.addEventListener('rfid:error', function (e) {
    showToast('✗ ' + e.detail.detail, 'error');
  });

  document.addEventListener('rfid:cooldown', function (e) {
    showToast('⏱ ' + (e.detail.user_name || 'User') + ' — Already scanned recently', 'warning');
  });

  function setupListeners() {
    document.addEventListener('keydown', function (e) {
      if (!rfidActive) return;
      var tag = e.target && e.target.tagName;
      var isFormField = tag === 'INPUT' || tag === 'TEXTAREA' || (e.target && e.target.isContentEditable);
      if (isFormField && e.target !== hiddenInput) return;

      if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null; }

      if (e.key === 'Enter') {
        e.preventDefault();
        var val = (hiddenInput && hiddenInput.value || '').trim();
        if (val) {
          processScan(val);
        }
      }
    });

    document.addEventListener('input', function (e) {
      if (!rfidActive) return;
      if (e.target !== hiddenInput) return;
      if (debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function () {
        var val = (hiddenInput && hiddenInput.value || '').trim();
        if (val.length >= 4) {
          processScan(val);
        }
      }, 250);
    });

    function ensureFocus() {
      if (!rfidActive || scanning) return;
      var active = document.activeElement;
      if (active === hiddenInput) return;
      var tag = active && active.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || (active && active.isContentEditable)) return;
      focusInput();
    }

    document.addEventListener('click', ensureFocus);
    document.addEventListener('touchstart', ensureFocus);
    document.addEventListener('focusin', function (e) {
      if (rfidActive && e.target !== hiddenInput && !scanning) {
        setTimeout(ensureFocus, 10);
      }
    });
  }

  window.RFIDListener = {
    start: function () {
      if (rfidActive) return;
      rfidActive = true;
      createHiddenInput();
      setupListeners();
      focusInput();
      if (focusInterval) clearInterval(focusInterval);
      focusInterval = setInterval(function () {
        if (!rfidActive) return;
        var active = document.activeElement;
        if (active === hiddenInput) return;
        var tag = active && active.tagName;
        if (tag === 'INPUT' || tag === 'TEXTAREA' || (active && active.isContentEditable)) return;
        if (scanning) return;
        focusInput();
      }, 2000);
    },

    stop: function () {
      rfidActive = false;
      if (debounceTimer) { clearTimeout(debounceTimer); debounceTimer = null; }
      if (focusInterval) { clearInterval(focusInterval); focusInterval = null; }
      if (hiddenInput && document.body.contains(hiddenInput)) {
        hiddenInput.value = '';
      }
    },

    isActive: function () { return rfidActive; },

    getLastUid: function () { return lastUid; },

    processManual: function (uid) {
      if (uid && uid.trim()) {
        processScan(uid.trim());
      }
    },
  };
})();
