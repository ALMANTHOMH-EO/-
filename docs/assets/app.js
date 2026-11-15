const CONFIG_URL = './config/app-config.json';
const groups = Array.from({ length: 6 }, (_, i) => ({
  id: i + 1,
  start: i * 50 + 1,
  end: (i + 1) * 50,
  label: ['الأولى','الثانية','الثالثة','الرابعة','الخامسة','السادسة'][i]
}));
let selectedGroup = 1;
let appConfig = null;

const $ = (id) => document.getElementById(id);

function renderTabs() {
  const host = $('groupTabs');
  host.innerHTML = '';
  groups.forEach(group => {
    const button = document.createElement('button');
    button.className = `group-tab ${selectedGroup === group.id ? 'active' : ''}`;
    button.type = 'button';
    button.setAttribute('role', 'tab');
    button.setAttribute('aria-selected', selectedGroup === group.id ? 'true' : 'false');
    button.textContent = `المجموعة ${group.id}`;
    button.addEventListener('click', () => {
      selectedGroup = group.id;
      renderTabs();
      renderSlots();
    });
    host.appendChild(button);
  });
}

function renderSlots() {
  const group = groups[selectedGroup - 1];
  $('groupLabel').textContent = `المجموعة ${group.label} · ${String(group.start).padStart(3,'0')}–${String(group.end).padStart(3,'0')}`;
  const grid = $('slotGrid');
  grid.innerHTML = '';
  for (let slot = group.start; slot <= group.end; slot++) {
    const cell = document.createElement('div');
    cell.className = 'slot-cell';
    cell.innerHTML = `<span>${String(slot).padStart(3,'0')}</span><small>غير مفعّلة</small>`;
    cell.title = 'تحتاج إلى ربط خدمة الحجز السحابية';
    grid.appendChild(cell);
  }
}

async function checkConnection() {
  const dot = $('connectionDot');
  const text = $('connectionText');
  if (!navigator.onLine) {
    dot.className = 'status-dot offline';
    text.textContent = 'غير متصل';
    $('offlineGate').classList.remove('hidden');
    return false;
  }
  try {
    const response = await fetch(CONFIG_URL, { cache: 'no-store', credentials: 'same-origin' });
    if (!response.ok) throw new Error('config unavailable');
    appConfig = await response.json();
    dot.className = 'status-dot online';
    text.textContent = 'متصل بالموقع';
    $('offlineGate').classList.add('hidden');
    document.documentElement.dataset.backend = appConfig.backendConfigured ? 'configured' : 'pending';
    return true;
  } catch (error) {
    dot.className = 'status-dot offline';
    text.textContent = 'تعذر التحقق';
    $('offlineGate').classList.remove('hidden');
    return false;
  }
}

$('retryConnection').addEventListener('click', checkConnection);
window.addEventListener('online', checkConnection);
window.addEventListener('offline', checkConnection);

$('previewRegistration').addEventListener('submit', (event) => {
  event.preventDefault();
  const name = $('displayName').value.trim();
  const age = $('ageRange').value;
  if (!name || !age) return;
  $('registrationNotice').textContent = `معاينة فقط: الاسم المعروض ${name}. لم يتم إنشاء حساب ولم يتم إرسال أو حفظ البيانات. سيتم تفعيل التسجيل بعد ربط خدمة الحسابات وسياسة الخصوصية.`;
});

document.querySelectorAll('[data-dialog]').forEach(button => {
  button.addEventListener('click', () => $(button.dataset.dialog).showModal());
});

$('year').textContent = new Date().getFullYear();
renderTabs();
renderSlots();
checkConnection();

if ('serviceWorker' in navigator && location.protocol === 'https:') {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./sw.js').catch(() => {});
  });
}
