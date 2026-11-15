'use strict';
const $ = (id) => document.getElementById(id);
let csrfToken = '';
let currentUser = null;
let selectedGroup = 1;
let slotsCache = [];
let toastTimer = null;

function showToast(message, error = false) {
  const box = $('toast');
  box.textContent = message;
  box.classList.toggle('error', error);
  box.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.remove('show'), 3200);
}
function setMessage(message, error = false) {
  $('authMessage').textContent = message || '';
  $('authMessage').classList.toggle('error', error);
}
async function api(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase();
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken) headers.set('X-CSRF-Token', csrfToken);
  const response = await fetch(path, { ...options, method, headers, credentials: 'same-origin', cache: 'no-store' });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || `تعذر تنفيذ الطلب (${response.status})`);
  return data;
}
async function refreshCsrf() {
  const data = await api('/api/auth/csrf');
  csrfToken = data.csrfToken;
}
function authMode(mode) {
  const login = mode === 'login';
  $('loginForm').classList.toggle('hidden', !login);
  $('registerForm').classList.toggle('hidden', login);
  $('showLogin').classList.toggle('selected', login);
  $('showRegister').classList.toggle('selected', !login);
  setMessage('');
}
$('showLogin').addEventListener('click', () => authMode('login'));
$('showRegister').addEventListener('click', () => authMode('register'));
$('menuButton').addEventListener('click', () => $('account').scrollIntoView({ behavior: 'smooth' }));

$('registerForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  const body = {
    username: $('regUsername').value.trim(), display_name: $('regName').value.trim(),
    age_band: $('regAge').value, password: $('regPassword').value
  };
  try {
    const data = await api('/api/auth/register', { method: 'POST', body: JSON.stringify(body) });
    $('registerForm').reset(); authMode('login'); $('loginUsername').value = body.username;
    setMessage(data.message); showToast('تم إنشاء الحساب');
  } catch (error) { setMessage(error.message, true); }
});

$('loginForm').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const body = { username: $('loginUsername').value.trim(), password: $('loginPassword').value };
    await api('/api/auth/login', { method: 'POST', body: JSON.stringify(body) });
    $('loginPassword').value = '';
    await loadAccount(); await loadSlots(); showToast('تم تسجيل الدخول بنجاح');
  } catch (error) { setMessage(error.message, true); }
});

async function loadAccount() {
  try {
    currentUser = await api('/api/me');
    $('authPanel').classList.add('hidden'); $('profilePanel').classList.remove('hidden');
    $('profileName').textContent = currentUser.displayName;
    $('profileHandle').textContent = '@' + currentUser.username;
    $('roleBadge').textContent = currentUser.role.toUpperCase();
    $('mySlot').textContent = currentUser.reservedSlot ? String(currentUser.reservedSlot).padStart(3, '0') : 'لا يوجد';
    $('myUsage').textContent = currentUser.role === 'admin' ? 'مفتوح للمطور' : `${formatHours(currentUser.dailyUsageSeconds)} / 6 ساعات`;
    $('createPairing').disabled = !currentUser.reservedSlot;
    $('accountAlert').classList.toggle('hidden', currentUser.inactiveDays < 10);
    if (currentUser.inactiveDays >= 13) $('accountAlert').textContent = 'تنبيه أخير: اقتربت جلسة الحساب من الانتهاء بسبب عدم النشاط.';
    else if (currentUser.inactiveDays >= 10) $('accountAlert').textContent = 'تنبيه: لم يُسجّل نشاط للحساب منذ 10 أيام. سجّل نشاطًا للحفاظ على الجلسة.';
    if (currentUser.role === 'admin') { $('adminPanel').classList.remove('hidden'); await loadAdmin(); }
    else $('adminPanel').classList.add('hidden');
  } catch (_) {
    currentUser = null; $('authPanel').classList.remove('hidden'); $('profilePanel').classList.add('hidden'); $('adminPanel').classList.add('hidden');
  }
}
function formatHours(seconds) {
  const minutes = Math.floor((seconds || 0) / 60);
  return `${Math.floor(minutes / 60)}س ${minutes % 60}د`;
}
$('refreshAccount').addEventListener('click', async () => { await loadAccount(); await loadSlots(); showToast('تم تحديث الحساب'); });
$('logoutButton').addEventListener('click', async () => {
  try { await api('/api/auth/logout', { method: 'POST' }); } catch (_) {}
  currentUser = null; $('pairingResult').classList.add('hidden'); await loadAccount(); await loadSlots(); showToast('تم تسجيل الخروج');
});

function buildTabs() {
  $('groupTabs').innerHTML = '';
  for (let group = 1; group <= 6; group++) {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = `المجموعة ${group}`;
    button.classList.toggle('selected', group === selectedGroup);
    button.setAttribute('aria-selected', String(group === selectedGroup));
    button.addEventListener('click', () => { selectedGroup = group; buildTabs(); renderSlots(); });
    $('groupTabs').appendChild(button);
  }
}
async function loadSlots() {
  if (!currentUser) {
    $('slotGrid').innerHTML = '<div class="loading">سجّل الدخول لعرض الحالة الحقيقية وإدارة الحجز.</div>';
    $('slotHint').textContent = 'يلزم تسجيل الدخول'; return;
  }
  $('slotGrid').innerHTML = '<div class="loading">جاري تحديث حالة قاعدة البيانات…</div>';
  try {
    const data = await api(`/api/slots?group=${selectedGroup}`);
    slotsCache = data.slots; renderSlots();
    $('slotHint').textContent = 'الحجوزات مشتركة ومحفوظة على الخادم';
  } catch (error) { $('slotGrid').innerHTML = `<div class="loading">${escapeHtml(error.message)}</div>`; }
}
function renderSlots() {
  const start = ((selectedGroup - 1) * 50) + 1;
  $('groupLabel').textContent = `المجموعة ${selectedGroup} · ${String(start).padStart(3,'0')}–${String(start + 49).padStart(3,'0')}`;
  if (!currentUser) return;
  const grid = $('slotGrid'); grid.innerHTML = '';
  slotsCache.forEach(slot => {
    const button = document.createElement('button'); button.type = 'button'; button.className = 'slot-cell';
    const number = String(slot.id).padStart(3, '0');
    button.innerHTML = `<span>${number}</span><small>${slot.mine ? 'حجزك' : !slot.active ? 'موقوفة' : slot.reserved ? 'محجوزة' : 'متاحة'}</small>`;
    if (slot.mine) button.classList.add('mine'); else if (!slot.active) button.classList.add('off'); else if (slot.reserved) button.classList.add('taken'); else button.classList.add('free');
    button.disabled = !slot.active || (slot.reserved && !slot.mine);
    button.addEventListener('click', async () => {
      try {
        if (slot.mine) {
          if (!confirm(`تحرير الخانة ${number}؟`)) return;
          await api(`/api/slots/${slot.id}/reserve`, { method: 'DELETE' });
          showToast('تم تحرير الخانة');
        } else {
          if (!confirm(`حجز الخانة ${number} لحسابك؟`)) return;
          await api(`/api/slots/${slot.id}/reserve`, { method: 'POST', body: '{}' });
          showToast('تم حجز الخانة');
        }
        await loadAccount(); await loadSlots();
      } catch (error) { showToast(error.message, true); }
    });
    grid.appendChild(button);
  });
}
function escapeHtml(value) { return String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

$('createPairing').addEventListener('click', async () => {
  if (!currentUser?.reservedSlot) return;
  try {
    const data = await api(`/api/pairings?slot_id=${currentUser.reservedSlot}`, { method: 'POST', body: '{}' });
    const box = $('pairingResult'); box.classList.remove('hidden'); box.innerHTML = `<b>رمز مؤقت — صالح ${data.expiresInMinutes} دقيقة</b><p><code id="pairCode"></code></p><button type="button" id="copyPairCode" class="btn secondary">نسخ الرمز</button><p>${escapeHtml(data.notice)}</p>`;
    $('pairCode').textContent = data.code;
    $('copyPairCode').addEventListener('click', async () => { try { await navigator.clipboard.writeText(data.code); showToast('تم نسخ الرمز'); } catch (_) { showToast('تعذر النسخ؛ حدد الرمز يدويًا', true); } });
  } catch (error) { showToast(error.message, true); }
});

async function loadAdmin() {
  try {
    const data = await api('/api/admin/overview');
    $('adminOverview').innerHTML = [
      ['الحسابات', data.users], ['النشطة', data.activeUsers], ['الخانات المحجوزة', data.reservedSlots], ['الجلسات', data.activeSessions]
    ].map(([label, value]) => `<div class="admin-stat"><small>${label}</small><b>${value}</b></div>`).join('');
    await searchAdminUsers('');
  } catch (error) { $('adminOverview').textContent = error.message; }
}
async function searchAdminUsers(query) {
  const data = await api(`/api/admin/users?q=${encodeURIComponent(query)}`);
  $('adminUsers').innerHTML = '';
  data.users.forEach(user => {
    const item = document.createElement('div'); item.className = 'admin-user';
    const info = document.createElement('div'); info.innerHTML = `<b>${escapeHtml(user.displayName)}</b><small>@${escapeHtml(user.username)} · ${escapeHtml(user.status)} · ID ${user.id}</small>`;
    const actions = document.createElement('div'); actions.className = 'admin-user-actions';
    const revoke = document.createElement('button'); revoke.className = 'btn secondary'; revoke.type = 'button'; revoke.textContent = 'إنهاء الجلسات';
    revoke.addEventListener('click', async () => { try { await api(`/api/admin/users/${user.id}/revoke-sessions`, {method:'POST',body:'{}'}); showToast('تم إنهاء الجلسات'); await loadAdmin(); } catch(e){showToast(e.message,true);} });
    actions.appendChild(revoke);
    if (user.role !== 'admin') {
      const statusBtn = document.createElement('button'); statusBtn.className = 'btn danger'; statusBtn.type = 'button'; statusBtn.textContent = user.status === 'blocked' ? 'إلغاء الحظر' : 'حظر';
      statusBtn.addEventListener('click', async () => { const next = user.status === 'blocked' ? 'active' : 'blocked'; if(!confirm(`تغيير حالة ${user.username} إلى ${next}؟`)) return; try { await api(`/api/admin/users/${user.id}/status`, {method:'POST',body:JSON.stringify({status:next})}); showToast('تم تحديث حالة الحساب'); await loadAdmin(); } catch(e){showToast(e.message,true);} });
      actions.appendChild(statusBtn);
    }
    item.append(info, actions); $('adminUsers').appendChild(item);
  });
}
$('adminSearchForm').addEventListener('submit', async (event) => { event.preventDefault(); try { await searchAdminUsers($('adminQuery').value.trim()); } catch(error) { showToast(error.message,true); } });

let heartbeatBusy = false;
async function sendHeartbeat() {
  if (!currentUser || document.visibilityState !== 'visible' || heartbeatBusy) return;
  heartbeatBusy = true;
  try {
    const data = await api('/api/usage/heartbeat', { method: 'POST', body: '{}' });
    currentUser.dailyUsageSeconds = data.usedSeconds;
    $('myUsage').textContent = data.unlimited ? 'مفتوح للمطور' : `${formatHours(data.usedSeconds)} / 6 ساعات`;
    if (data.limitReached) { showToast('وصلت إلى حد الاستخدام اليومي. يمكنك تسجيل الخروج والعودة بعد إعادة الضبط اليومي.', true); }
  } catch (error) { if (error.message.includes('6 ساعات')) showToast(error.message, true); }
  finally { heartbeatBusy = false; }
}
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') sendHeartbeat(); });
setInterval(sendHeartbeat, 60_000);

async function init() {
  try {
    await refreshCsrf();
    const health = await api('/api/health');
    $('apiState').className = 'state-dot online'; $('apiStateText').textContent = 'الخادم متصل'; $('dbState').textContent = '● متصلة';
    await loadAccount(); await loadSlots();
    if (currentUser) sendHeartbeat();
  } catch (error) {
    $('apiState').className = 'state-dot offline'; $('apiStateText').textContent = 'الخادم غير مربوط'; $('dbState').textContent = '● غير متصلة';
    $('slotGrid').innerHTML = '<div class="loading">هذه الصفحة تحتاج إلى تشغيل خادم ALMANTHOMH EO CN. رفع مجلد docs إلى GitHub Pages وحده لا يشغّل الحسابات أو قاعدة البيانات. راجع DEPLOY_AR.md.</div>';
    setMessage('الخادم غير متاح. شغّل النسخة الكاملة من خلال إعداد Docker.', true);
  }
  if ('serviceWorker' in navigator && location.protocol === 'https:') navigator.serviceWorker.register('./sw.js').catch(() => {});
}
buildTabs(); init();
