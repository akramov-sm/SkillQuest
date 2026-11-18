// Shared mission UI: form modal, row, and the complete → celebrate flow.
import { api } from './api.js';
import { store, skillBy } from './store.js';
import { h, icon, svgIcon, toast, openModal, confirmDialog, DIFF, DIFF_XP, fmt, fmtDate, relDay, localISO, iconBox, withLoading } from './ui.js';

export function diffChip(d) { return h('span.chip', { class: d }, DIFF[d]); }
export function catChip(slug) {
  const s = skillBy(slug);
  return h('span.chip.cat-chip', { style: { '--c': s.color } }, h('span.dot'), s.name);
}

// ---------- create / edit form ----------
export function openMissionForm({ mission = null, defaults = {}, onSaved } = {}) {
  const editing = !!mission;
  const init = { title: '', description: '', category: store.skills[0]?.slug, difficulty: 'medium', xp: '', due_date: '', ...defaults, ...(mission || {}) };
  let xpTouched = editing;
  const state = { difficulty: init.difficulty };

  const title = h('input.input', { id: 'f-title', maxlength: 120, placeholder: 'e.g. Solve 3 algorithm problems', value: init.title, autocomplete: 'off', required: true });
  const desc = h('textarea.textarea', { id: 'f-desc', maxlength: 1000, placeholder: 'Optional details…' }, init.description || '');
  const cat = h('select.select', { id: 'f-cat' }, store.skills.map((s) => h('option', { value: s.slug, selected: s.slug === init.category }, s.name)));
  const xp = h('input.input', { id: 'f-xp', type: 'number', min: 1, max: 1000, step: 1, value: editing ? init.xp : DIFF_XP[init.difficulty] });
  const due = h('input.input', { id: 'f-due', type: 'date', value: init.due_date || '' });
  xp.addEventListener('input', () => { xpTouched = true; });
  const segBtns = Object.keys(DIFF).map((d) => h('button', {
    type: 'button', 'aria-pressed': String(d === state.difficulty),
    onclick: () => { state.difficulty = d; segBtns.forEach((b, i) => b.setAttribute('aria-pressed', String(Object.keys(DIFF)[i] === d))); if (!xpTouched) xp.value = DIFF_XP[d]; },
  }, DIFF[d]));
  const field = (label, input, id, cls = '') => h('div.field', { class: cls, 'data-field': id }, h('label', { for: input.id }, label), input, h('div.err', { 'data-err': id }));
  const locked = editing && mission.status === 'completed';
  const form = h('form', { novalidate: true },
    h('div.form-grid',
      field('Title', title, 'title', 'full'),
      field('Description', desc, 'description', 'full'),
      field('Category', cat, 'category'),
      h('div.field', { 'data-field': 'difficulty' }, h('span.label', 'Difficulty'), h('div.seg', { role: 'group', 'aria-label': 'Difficulty' }, segBtns), h('div.err', { 'data-err': 'difficulty' })),
      field('XP reward', xp, 'xp'), field('Due date', due, 'due_date')));
  if (locked) {
    [cat, xp].forEach((el) => { el.disabled = true; });
    segBtns.forEach((b) => { b.disabled = true; b.style.opacity = '.5'; });
  }
  form.append(h('div.hint', { style: { marginTop: '10px' } }, locked ? 'This mission is completed: category, difficulty and XP are locked so your earned XP stays accurate.' : 'XP is suggested from difficulty — adjust it if you like. A streak adds up to +20% bonus.'));

  const setErrors = (fields = {}) => {
    form.querySelectorAll('.field').forEach((f) => {
      const msg = fields[f.dataset.field];
      f.classList.toggle('invalid', !!msg);
      f.querySelector('.err').textContent = msg || '';
    });
    if (fields._) toast({ type: 'error', title: 'Invalid data', text: fields._ });
    form.querySelector('.invalid input, .invalid textarea, .invalid select')?.focus();
  };
  const clientValidate = () => {
    const e = {};
    if (!title.value.trim()) e.title = 'Give your mission a title.';
    else if (title.value.trim().length > 120) e.title = 'Title must be at most 120 characters.';
    const n = Number(xp.value);
    if (xp.value === '' || !Number.isInteger(n) || n < 1 || n > 1000) e.xp = 'XP must be a whole number from 1 to 1000.';
    return e;
  };

  const saveBtn = h('button.btn.btn-primary', { type: 'button' }, editing ? 'Save changes' : 'Create mission');
  const m = openModal({
    title: editing ? 'Edit mission' : 'New mission', body: form,
    footer: [h('button.btn', { type: 'button', onclick: () => m.close() }, 'Cancel'), saveBtn],
  });
  const submit = async (ev) => {
    ev.preventDefault();
    const errs = clientValidate();
    setErrors(errs);
    if (Object.keys(errs).length) return;
    const payload = { title: title.value.trim(), description: desc.value.trim(), category: cat.value, difficulty: state.difficulty, xp: Number(xp.value), due_date: due.value || null };
    try {
      const saved = await withLoading(saveBtn, () => (editing ? api.updateMission(mission.id, payload) : api.createMission(payload)));
      m.close();
      toast({ title: editing ? 'Mission updated' : 'Mission created', text: saved.title, icon: editing ? 'edit' : 'plus' });
      onSaved?.(saved);
    } catch (e) {
      if (e.fields && Object.keys(e.fields).length) setErrors(e.fields);
      else toast({ type: 'error', title: 'Could not save mission', text: e.message });
    }
  };
  form.addEventListener('submit', submit);      // Enter key inside inputs
  saveBtn.addEventListener('click', submit);    // button lives in the footer, outside <form>
  return m;
}

// ---------- completion flow ----------
export function celebrate(res) {
  const sk = skillBy(res.reward.skill);
  const r = res.reward;
  toast({ title: `+${fmt(r.total_xp)} XP`, type: 'success', icon: 'zap', color: '#8b5cf6',
    text: `${sk.name}${r.bonus_xp ? ` · includes +${r.bonus_xp} streak bonus` : ''}` });
  if (res.skill_level.leveled_up) {
    toast({ title: `${sk.name} reached level ${res.skill_level.after}`, text: 'Skill level up!', icon: sk.icon, color: sk.color, duration: 5200 });
  }
  res.new_achievements.forEach((a, i) => setTimeout(() => toast({
    type: 'achievement', title: `Achievement unlocked: ${a.title}`, text: `${a.description} +${a.reward_xp} XP`, icon: a.icon, duration: 6500 }), 350 + i * 450));
  if (res.level.leveled_up) setTimeout(() => levelUpModal(res), 500);
}

function levelUpModal(res) {
  const colors = ['#8b5cf6', '#3b82f6', '#22d3ee', '#f472b6', '#fbbf24'];
  const sparks = Array.from({ length: 22 }, (_, i) => {
    const a = (i / 22) * Math.PI * 2, d = 90 + Math.random() * 90;
    return h('i.spark', { style: { background: colors[i % 5], '--x': Math.cos(a) * d + 'px', '--y': Math.sin(a) * d + 'px' } });
  });
  const m = openModal({
    title: 'Level up', hideHeader: true,
    body: h('div.celebrate', sparks, h('div.level-orb', String(res.level.after)),
      h('h2', 'Level up!'), h('p', `You reached level ${res.level.after}. Keep the momentum going.`)),
    footer: h('button.btn.btn-primary', { type: 'button', autofocus: true, onclick: () => m.close() }, 'Awesome'),
  });
}

export async function completeMission(id, btn) {
  const run = async () => {
    const res = await api.complete(id);
    celebrate(res);
    return res;
  };
  try { return await (btn ? withLoading(btn, run) : run()); }
  catch (e) { toast({ type: 'error', title: 'Could not complete mission', text: e.message }); return null; }
}

export async function reopenMission(id) {
  try {
    const res = await api.reopen(id);
    toast({ title: 'Mission reopened', text: 'The XP for this mission was removed.', icon: 'undo', type: 'info' });
    return res;
  } catch (e) { toast({ type: 'error', title: 'Could not reopen mission', text: e.message }); return null; }
}

export async function deleteMission(m) {
  const ok = await confirmDialog({
    title: 'Delete mission?', danger: true, confirmLabel: 'Delete',
    text: m.status === 'completed' ? `"${m.title}" will be removed. The XP you already earned stays in your history.` : `"${m.title}" will be permanently removed.`,
  });
  if (!ok) return false;
  try { await api.deleteMission(m.id); toast({ title: 'Mission deleted', text: m.title, icon: 'trash', type: 'info' }); return true; }
  catch (e) { toast({ type: 'error', title: 'Could not delete mission', text: e.message }); return false; }
}

// ---------- row ----------
export function missionRow(m, { onChange, compact = false } = {}) {
  const done = m.status === 'completed';
  const check = h('button.check', {
    class: done ? 'on' : '', type: 'button', 'aria-label': done ? `Reopen "${m.title}"` : `Complete "${m.title}"`, title: done ? 'Mark as active' : 'Complete mission',
    html: svgIcon('check'),
    onclick: async () => {
      check.disabled = true;
      const res = done ? await reopenMission(m.id) : await completeMission(m.id);
      if (res) onChange?.(res); else check.disabled = false;
    },
  });
  const meta = h('div.m-meta', catChip(m.category), diffChip(m.difficulty), h('span.chip.xp', `${done ? '' : '+'}${fmt(m.xp)} XP`));
  if (m.due_date && !done) {
    meta.append(h('span.date', { class: m.overdue ? 'chip overdue' : '' }, icon('calendar', 'ico'), m.overdue ? `Overdue · ${fmtDate(m.due_date)}` : relDay(m.due_date)));
  }
  if (done) meta.append(h('span.chip.done', 'Completed ' + relDay(m.completed_at.slice(0, 10))));
  const actions = compact ? null : h('div.m-actions',
    h('button.btn.btn-ghost.btn-icon', { type: 'button', 'aria-label': `Edit "${m.title}"`, title: 'Edit', onclick: () => openMissionForm({ mission: m, onSaved: () => onChange?.() }) }, icon('edit')),
    h('button.btn.btn-ghost.btn-icon', { type: 'button', 'aria-label': `Delete "${m.title}"`, title: 'Delete', onclick: async () => { if (await deleteMission(m)) onChange?.(); } }, icon('trash')));
  return h('div.mission', { class: done ? 'done' : '' }, check,
    h('div.m-body', h('div.m-title', { title: m.title }, m.title), !compact && m.description && h('div.m-desc', m.description), meta), actions);
}
