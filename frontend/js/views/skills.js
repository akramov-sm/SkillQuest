import { api } from '../api.js';
import { h, icon, iconBox, fmt, progressBar, pct } from '../ui.js';
import { openMissionForm } from '../missionKit.js';
import { setUser } from '../store.js';

export const meta = { title: 'Skill Tree', sub: 'Six paths. Level up every one.' };

export async function render(_, ctx) {
  const { items, user } = await api.skills();
  setUser(user);
  const cards = items.map((s) => {
    const nextTier = s.tiers.find((t) => !t.unlocked);
    const tree = h('div.tree', s.tiers.map((t) => h('div.node', { class: t.unlocked ? 'on' : '', title: `${t.name} — level ${t.required_level}` }, h('i'), h('span', t.name), h('small', `Lv ${t.required_level}`))));
    return h('div.card.hover.skill', { style: { '--c': s.color } },
      h('div.row', iconBox(s.icon, s.color),
        h('div', h('h2', { style: { fontSize: '16px', fontWeight: 600 } }, s.name), h('div.hint', `${s.completed_missions} completed · ${s.active_missions} active`)),
        h('div.lvl', h('b.tnum', `Lv ${s.level}`), h('span.hint', s.maxed ? 'MAX' : `${fmt(s.xp)} XP`))),
      h('p.muted', { style: { marginTop: '12px', fontSize: '13px' } }, s.description),
      tree,
      progressBar(s.progress, '', s.color),
      h('div.row', { style: { justifyContent: 'space-between', marginTop: '8px', fontSize: '12.5px', color: 'var(--text-2)' } },
        h('span.tnum', s.maxed ? 'Max level reached' : `${fmt(s.xp_into_level)} / ${fmt(s.xp_for_next)} XP · ${pct(s.progress)}`),
        h('span', nextTier ? `Next tier: ${nextTier.name} (Lv ${nextTier.required_level})` : 'Master tier unlocked')),
      h('div.row', { style: { marginTop: '16px' } },
        h('button.btn.btn-sm', { type: 'button', onclick: () => openMissionForm({ defaults: { category: s.slug }, onSaved: () => ctx.reload() }) }, icon('plus'), 'Add mission'),
        h('a.btn.btn-sm.btn-ghost', { href: `#/missions?category=${s.slug}&status=all` }, 'View missions')));
  });
  return h('div.skills', cards);
}
