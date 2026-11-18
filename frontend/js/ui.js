// UI helpers: DOM builder, icons, formatters, toast, modal, confirm.

// h('div.card#id', {onclick, dataset, ...attrs}, ...children) — children are escaped (textContent).
export function h(sel, props, ...kids) {
  if (props && (typeof props !== 'object' || props instanceof Node || Array.isArray(props))) { kids.unshift(props); props = null; }
  const m = sel.match(/^([a-z0-9]+)?((?:[.#][\w-]+)*)$/i) || [];
  const el = document.createElement(m[1] || 'div');
  (m[2] || '').replace(/([.#])([\w-]+)/g, (_, t, n) => { if (t === '.') el.classList.add(n); else el.id = n; });
  for (const [k, v] of Object.entries(props || {})) {
    if (v == null || v === false) continue;
    if (k.startsWith('on')) el.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === 'style' && typeof v === 'object') for (const [sk, sv] of Object.entries(v)) { if (sk.startsWith('--')) el.style.setProperty(sk, sv); else el.style[sk] = sv; }
    else if (k === 'class') el.classList.add(...String(v).split(' ').filter(Boolean));
    else if (k === 'html') el.innerHTML = v;            // only used with trusted static strings (icons)
    else if (k in el && k !== 'list' && typeof v !== 'string') el[k] = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  const add = (c) => {
    if (c == null || c === false) return;
    if (Array.isArray(c)) c.forEach(add);
    else el.append(c instanceof Node ? c : document.createTextNode(String(c)));
  };
  kids.forEach(add);
  return el;
}

const P = {
  dashboard: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  missions: '<path d="M9 11l3 3 8-8"/><path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9"/>',
  skills: '<circle cx="12" cy="5" r="2.5"/><circle cx="5" cy="19" r="2.5"/><circle cx="19" cy="19" r="2.5"/><path d="M12 7.5v4M12 11.5l-5.5 5.2M12 11.5l5.5 5.2"/>',
  achievements: '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3"/>',
  analytics: '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
  profile: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>', x: '<path d="M6 6l12 12M18 6L6 18"/>',
  edit: '<path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17z"/><path d="M14 7l3 3"/>', trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  undo: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>', search: '<circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>',
  calendar: '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>', flame: '<path d="M12 22c4 0 7-2.8 7-6.8 0-3-1.8-5-3.4-6.7C14 7 13.5 5 13.5 3c-3 1.5-5 4.5-5 7.2-1.2-.6-1.8-1.6-2-2.7C4.8 9.5 5 12 5 15.2 5 19.2 8 22 12 22z"/>',
  code: '<path d="M8 7l-5 5 5 5M16 7l5 5-5 5M14 4l-4 16"/>', cpu: '<rect x="6" y="6" width="12" height="12" rx="2"/><rect x="9.5" y="9.5" width="5" height="5" rx="1"/><path d="M9 2v3M15 2v3M9 19v3M15 19v3M2 9h3M2 15h3M19 9h3M19 15h3"/>',
  languages: '<path d="M4 5h9M8.5 3v2M6 5c0 4 3 7 6 8M11 5c0 4-3 7-7 8.5"/><path d="M12 21l4.5-10L21 21M13.5 17.5h6"/>', dumbbell: '<path d="M6.5 6.5v11M17.5 6.5v11M3.5 9v6M20.5 9v6M6.5 12h11"/>',
  wallet: '<path d="M4 7a2 2 0 0 1 2-2h11v4"/><path d="M4 7v11a2 2 0 0 0 2 2h13a1 1 0 0 0 1-1v-9a1 1 0 0 0-1-1H6a2 2 0 0 1-2-2z"/><circle cx="16" cy="14.5" r="1.2"/>',
  sparkles: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z"/>',
  flag: '<path d="M5 21V4M5 4h11l-2 4 2 4H5"/>', target: '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1"/>',
  zap: '<path d="M13 2L4 14h7l-1 8 9-12h-7z"/>', gem: '<path d="M6 3h12l3 6-9 12L3 9z"/><path d="M3 9h18M9 3l-2 6 5 12M15 3l2 6-5 12"/>',
  crown: '<path d="M3 8l4 4 5-7 5 7 4-4-2 11H5z"/>', layers: '<path d="M12 3l9 5-9 5-9-5z"/><path d="M3 13l9 5 9-5M3 17l9 5 9-5" opacity=".6"/>',
  star: '<path d="M12 3l2.9 6 6.6.9-4.8 4.6 1.2 6.5L12 17.8 6.1 21l1.2-6.5L2.5 9.9 9.1 9z"/>', trophy: '<path d="M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M17 5h3v2a3 3 0 0 1-3 3M7 5H4v2a3 3 0 0 0 3 3"/>',
  lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>', alert: '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18h.01"/>',
  inbox: '<path d="M3 13l3-8h12l3 8v6H3z"/><path d="M3 13h5l1 3h6l1-3h5"/>', refresh: '<path d="M20 11a8 8 0 0 0-14-4L4 9M4 4v5h5M4 13a8 8 0 0 0 14 4l2-2M20 20v-5h-5"/>',
};
export const icon = (name, cls = 'ico') => h('span', { class: 'i-wrap', style: { display: 'inline-flex' }, html:
  `<svg class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[name] || P.star}</svg>` });
export const svgIcon = (name) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[name] || P.star}</svg>`;
export const iconBox = (name, color) => h('div.ico-box', { style: { '--c': color || '#8b5cf6' }, html: svgIcon(name) });

// ---------- formatters ----------
export const fmt = (n) => new Intl.NumberFormat('en-US').format(Math.round(n));
export const pct = (x) => Math.round(x * 100) + '%';
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
export function localISO(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
export function fmtDate(iso, withYear = false) {
  if (!iso) return '';
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  return `${MONTHS[m - 1]} ${d}${withYear ? ', ' + y : ''}`;
}
export function relDay(iso) {
  const today = localISO();
  const diff = Math.round((Date.parse(iso + 'T00:00') - Date.parse(today + 'T00:00')) / 864e5);
  if (diff === 0) return 'Today'; if (diff === 1) return 'Tomorrow'; if (diff === -1) return 'Yesterday';
  return fmtDate(iso);
}
export const DIFF = { easy: 'Easy', medium: 'Medium', hard: 'Hard', epic: 'Epic' };
export const DIFF_XP = { easy: 20, medium: 50, hard: 100, epic: 200 };

export function avatar(user, cls = '') {
  return h('div.avatar', { class: cls, style: { '--h': user.avatar_hue } }, user.avatar);
}
export function progressBar(ratio, cls = '', color) {
  const bar = h('i'); const el = h('div.progress', { class: cls, role: 'progressbar', 'aria-valuenow': Math.round(ratio * 100), 'aria-valuemin': 0, 'aria-valuemax': 100 }, bar);
  if (color) el.style.setProperty('--c', color);
  requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.width = Math.max(ratio > 0 ? 2 : 0, ratio * 100) + '%'; }));
  return el;
}

// ---------- states ----------
export const skeleton = (h_ = 120, n = 1) => h('div.stack', Array.from({ length: n }, () => h('div.skeleton', { style: { height: h_ + 'px' } })));
export function emptyState({ icon: ic = 'inbox', title, text, action }) {
  return h('div.card.empty', iconBox(ic, '#8b5cf6'), h('h3', title), text && h('p', text), action);
}
export function errorState(err, retry) {
  return h('div.card.empty', iconBox('alert', '#f87171'), h('h3', 'Something went wrong'), h('p', err?.message || 'Unknown error'),
    h('button.btn', { onclick: retry }, icon('refresh'), 'Try again'));
}

// ---------- toast ----------
export function toast({ title, text, type = 'success', icon: ic, color, duration = 4200 }) {
  const root = document.getElementById('toasts');
  const colors = { success: '#34d399', error: '#f87171', achievement: '#fbbf24', info: '#8b5cf6', level: '#8b5cf6' };
  const el = h('div.toast', { class: type, role: type === 'error' ? 'alert' : 'status' },
    iconBox(ic || (type === 'error' ? 'alert' : 'check'), color || colors[type]),
    h('div', h('b', title), text && h('span', text)),
    h('button.x', { 'aria-label': 'Dismiss', onclick: () => close(), html: svgIcon('x').replace('<svg', '<svg width="16" height="16"') }));
  const close = () => { el.classList.add('out'); setTimeout(() => el.remove(), 250); };
  root.append(el);
  while (root.children.length > 5) root.firstChild.remove();
  setTimeout(close, duration);
  return el;
}

// ---------- modal ----------
let lastFocus = null;
export function openModal({ title, body, footer, className = '', onClose, hideHeader = false }) {
  const root = document.getElementById('modalRoot');
  lastFocus = document.activeElement;
  const close = () => { overlay.remove(); document.removeEventListener('keydown', onKey); document.body.style.overflow = ''; lastFocus?.focus?.(); onClose?.(); };
  const onKey = (e) => {
    if (e.key === 'Escape') { e.stopPropagation(); close(); }
    if (e.key === 'Tab') {            // focus trap
      const f = [...modal.querySelectorAll('button,input,select,textarea,a[href]')].filter((x) => !x.disabled && x.offsetParent !== null);
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    }
  };
  const modal = h('div.modal', { class: className, role: 'dialog', 'aria-modal': 'true', 'aria-label': title },
    !hideHeader && h('div.modal-head', h('h2', title), h('button.btn.btn-ghost.btn-icon', { type: 'button', 'aria-label': 'Close', onclick: close }, icon('x'))),
    h('div.modal-body', body), footer && h('div.modal-foot', footer));
  const overlay = h('div.overlay', { onmousedown: (e) => { if (e.target === overlay) close(); } }, modal);
  root.append(overlay);
  document.body.style.overflow = 'hidden';
  document.addEventListener('keydown', onKey);
  setTimeout(() => (modal.querySelector('[autofocus],input,select,textarea,button.btn-primary') || modal).focus?.(), 30);
  return { close, modal };
}

export function confirmDialog({ title, text, confirmLabel = 'Confirm', danger = false }) {
  return new Promise((resolve) => {
    let done = false;
    const finish = (v) => { if (!done) { done = true; resolve(v); } };
    const m = openModal({
      title, body: h('p.muted', text), onClose: () => finish(false),
      footer: [h('button.btn', { type: 'button', onclick: () => m.close() }, 'Cancel'),
        h('button.btn', { class: danger ? 'btn-danger' : 'btn-primary', type: 'button', onclick: () => { finish(true); m.close(); } }, confirmLabel)],
    });
  });
}

// run async action with loading state on a button
export async function withLoading(btn, fn) {
  const label = btn.cloneNode(true).childNodes;
  btn.classList.add('loading'); btn.disabled = true;
  btn.replaceChildren(h('span.spinner'), 'Working…');
  try { return await fn(); }
  finally { btn.classList.remove('loading'); btn.disabled = false; btn.replaceChildren(...label); }
}
