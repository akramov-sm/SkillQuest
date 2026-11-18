import { api } from '../api.js';
import { h, icon, iconBox, fmt, fmtDate, avatar, progressBar, openModal, confirmDialog, toast, withLoading } from '../ui.js';
import { setUser } from '../store.js';

export const meta = { title: 'Profile', sub: 'Your character sheet' };
const AVATARS = ['🚀', '🦊', '🐺', '🦉', '🐉', '🧙', '🥷', '🤖', '👾', '🦁', '🐼', '⚡', '🔥', '🌙', '🎯', '🧠'];

export async function render(_, ctx) {
  const p = await api.profile();
  setUser(p.user);
  const u = p.user, st = p.stats;

  const head = h('div.card.hero',
    h('div.profile-head', avatar(u, 'xl'),
      h('div', { style: { flex: 1, minWidth: '200px' } },
        h('div.eyebrow', 'Adventurer'), h('h2', { style: { fontSize: '28px', fontWeight: 700, letterSpacing: '-.03em' } }, u.name),
        h('div.muted', `Member since ${fmtDate(u.created_at, true)} · ${st.days_with_us} day${st.days_with_us === 1 ? '' : 's'}`)),
      h('button.btn', { type: 'button', onclick: () => editProfile(u, ctx) }, icon('edit'), 'Edit profile')),
    h('div.row', { style: { marginTop: '24px', gap: '16px' } }, h('div.level-orb', { style: { width: '56px', height: '56px', fontSize: '26px', borderRadius: '18px' } }, String(u.level)),
      h('div', { style: { flex: 1 } }, h('div.row', { style: { justifyContent: 'space-between', marginBottom: '8px' } }, h('b.tnum', `${fmt(u.xp)} XP total`), h('span.muted.tnum', `${fmt(u.xp_into_level)} / ${fmt(u.xp_for_next)} to level ${u.level + 1}`)), progressBar(u.progress, 'lg'))));

  const stat = (name, v, sub) => h('div.card.stat', h('div.eyebrow', name), h('div.v.tnum', v), h('div.s', sub));
  const stats = h('div.stats',
    stat('Level', String(u.level), `${fmt(u.xp)} XP total`),
    stat('Missions', String(st.missions_completed), 'completed'),
    stat('Best streak', `${st.best_streak}d`, `current ${st.current_streak}d`),
    stat('Achievements', `${st.achievements_unlocked}/${st.achievements_total}`, 'unlocked'),
    stat('Top skill', st.top_skill || '—', 'most XP'));
  stats.lastChild.querySelector('.v').style.fontSize = '18px';

  const ach = h('div.card', h('div.card-head', h('h2', 'Unlocked achievements'), h('a.link', { href: '#/achievements' }, 'All achievements →')),
    p.achievements.length
      ? h('div.row.wrap', p.achievements.map((a) => h('div.row.chip.xp', { style: { height: '34px', padding: '0 14px 0 8px', gap: '8px' }, title: a.description }, iconBox(a.icon, '#fbbf24', ), a.title)))
      : h('div.empty.compact', h('p', 'No achievements yet — complete a mission to earn your first.')));
  ach.querySelectorAll('.ico-box').forEach((b) => { b.style.width = b.style.height = '22px'; b.style.borderRadius = '7px'; b.querySelector('svg').style.cssText = 'width:13px;height:13px'; });

  const danger = h('div.card.danger-zone', h('div.card-head', h('div', h('h2', 'Danger zone'), h('div.hint', 'Deletes all missions, XP and achievements. Your name and avatar stay.'))),
    h('button.btn.btn-danger', { type: 'button', onclick: async (e) => {
      const btn = e.currentTarget;
      if (!await confirmDialog({ title: 'Reset all progress?', danger: true, confirmLabel: 'Reset everything', text: 'All missions, XP, levels, streaks and achievements will be permanently deleted. This cannot be undone.' })) return;
      try { await withLoading(btn, () => api.reset()); toast({ title: 'Progress reset', text: 'You are back at level 1.', icon: 'refresh', type: 'info' }); ctx.reload(); }
      catch (err) { toast({ type: 'error', title: 'Reset failed', text: err.message }); }
    } }, icon('trash'), 'Reset progress'));
  return h('div.stack', head, stats, ach, danger);
}

function editProfile(u, ctx) {
  const st = { avatar: u.avatar, hue: u.avatar_hue };
  const name = h('input.input', { id: 'p-name', maxlength: 40, value: u.name, autocomplete: 'off' });
  const err = h('div.err');
  const preview = h('div');
  const drawPreview = () => preview.replaceChildren(avatar({ avatar: st.avatar, avatar_hue: st.hue }, 'xl'));
  const pickers = AVATARS.map((a) => h('button', { type: 'button', 'aria-pressed': String(a === st.avatar), 'aria-label': `Avatar ${a}`, onclick: () => { st.avatar = a; pickers.forEach((b, i) => b.setAttribute('aria-pressed', String(AVATARS[i] === a))); drawPreview(); } }, a));
  const hue = h('input', { type: 'range', min: 0, max: 360, value: st.hue, 'aria-label': 'Avatar color', oninput: () => { st.hue = Number(hue.value); drawPreview(); } });
  drawPreview();
  const field = h('div.field', h('label', { for: 'p-name' }, 'Display name'), name, err);
  const saveBtn = h('button.btn.btn-primary', { type: 'button' }, 'Save');
  const m = openModal({
    title: 'Edit profile',
    body: h('div.stack', h('div.row', { style: { justifyContent: 'center' } }, preview), field,
      h('div.field', h('span.label', 'Avatar'), h('div.picker', pickers)), h('div.field', h('span.label', 'Color'), hue)),
    footer: [h('button.btn', { type: 'button', onclick: () => m.close() }, 'Cancel'), saveBtn],
  });
  const save = async () => {
    const v = name.value.trim();
    field.classList.toggle('invalid', !v || v.length > 40);
    if (!v) { err.textContent = 'Name is required.'; return; }
    err.textContent = '';
    try {
      await withLoading(saveBtn, () => api.updateProfile({ name: v, avatar: st.avatar, avatar_hue: st.hue }));
      m.close(); toast({ title: 'Profile updated', icon: 'profile' }); ctx.reload();
    } catch (e) { field.classList.add('invalid'); err.textContent = e.fields?.name || e.message; }
  };
  saveBtn.onclick = save;
  name.addEventListener('keydown', (e) => { if (e.key === 'Enter') save(); });
}
