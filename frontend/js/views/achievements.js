import { api } from '../api.js';
import { h, icon, iconBox, fmtDate, progressBar } from '../ui.js';

export const meta = { title: 'Achievements', sub: 'Milestones earned along the way' };

export async function render() {
  const data = await api.achievements();
  let filter = 'all';
  const grid = h('div.ach-grid');
  const draw = () => {
    grid.replaceChildren(...data.items.filter((a) => filter === 'all' || (filter === 'unlocked') === a.unlocked).map((a) => {
      const card = h('div.card.ach', { class: a.unlocked ? 'unlocked' : 'locked' },
        h('div.row', iconBox(a.unlocked ? a.icon : 'lock', '#fbbf24'), h('span.chip.xp', { style: { marginLeft: 'auto' } }, `+${a.reward_xp} XP`)),
        h('div', h('h3', a.title), h('p', a.description)),
        a.unlocked
          ? h('div.hint', `Unlocked ${fmtDate(a.unlocked_at, true)}`)
          : h('div', progressBar(a.progress / a.target, 'sm'), h('div.hint.tnum', { style: { marginTop: '6px' } }, `${a.progress.toLocaleString('en-US')} / ${a.target.toLocaleString('en-US')}`)));
      return card;
    }));
    if (!grid.children.length) grid.append(h('div.card.empty.compact', { style: { gridColumn: '1/-1' } }, h('p', 'Nothing here yet.')));
  };
  const tabs = h('div.tabs', { role: 'tablist' }, [['all', 'All'], ['unlocked', 'Unlocked'], ['locked', 'Locked']].map(([v, l]) =>
    h('button', { type: 'button', role: 'tab', 'aria-selected': String(v === filter), onclick: (e) => { filter = v; tabs.querySelectorAll('button').forEach((b) => b.setAttribute('aria-selected', String(b === e.currentTarget))); draw(); } }, l)));
  draw();
  const pctDone = data.total ? data.unlocked / data.total : 0;
  return h('div.stack',
    h('div.card.row.wrap', { style: { gap: '24px' } },
      h('div', h('div.eyebrow', 'Unlocked'), h('div.big.tnum', `${data.unlocked} / ${data.total}`)),
      h('div', { style: { flex: 1, minWidth: '200px' } }, progressBar(pctDone, 'lg')), tabs),
    grid);
}
