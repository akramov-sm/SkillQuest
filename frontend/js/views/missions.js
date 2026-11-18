import { api } from '../api.js';
import { h, icon, emptyState, skeleton } from '../ui.js';
import { store } from '../store.js';
import { missionRow, openMissionForm } from '../missionKit.js';

export const meta = { title: 'Missions', sub: 'Plan, complete and earn XP' };
const STATUS = [['all', 'All'], ['active', 'Active'], ['overdue', 'Overdue'], ['completed', 'Completed']];

export async function render(params, ctx) {
  const f = { status: params.status || 'active', category: params.category || '', q: params.q || '', sort: params.sort || 'due' };
  const list = h('div.mlist');
  const count = h('span.hint');
  let seq = 0;

  const load = async () => {
    const my = ++seq;
    list.replaceChildren(skeleton(76, 4));
    try {
      const { items, truncated } = await api.missions(f);
      if (my !== seq) return;
      count.textContent = `${items.length}${truncated ? '+' : ''} mission${items.length === 1 && !truncated ? '' : 's'}${truncated ? ' (showing the first 500 — narrow your filters)' : ''}`;
      list.replaceChildren();
      if (!items.length) {
        const filtered = f.q || f.category;
        const label = { active: 'No active missions', overdue: 'Nothing overdue', completed: 'No completed missions yet' }[f.status];
        list.append(emptyState({
          icon: 'missions', title: filtered ? 'No missions match' : (label || 'No missions yet'),
          text: filtered ? 'Try different filters or search terms.' : (f.status === 'overdue' ? 'Great — you are on top of your deadlines.' : 'Create a mission and start earning XP.'),
          action: filtered
            ? h('button.btn', { type: 'button', onclick: () => { Object.assign(f, { status: 'all', category: '', q: '' }); sync(); load(); } }, 'Clear filters')
            : h('button.btn.btn-primary', { type: 'button', onclick: () => openMissionForm({ onSaved: load }) }, icon('plus'), 'New mission'),
        }));
      } else {
        items.forEach((m, i) => { const row = missionRow(m, { onChange: load }); row.style.animationDelay = Math.min(i, 10) * 30 + 'ms'; list.append(row); });
      }
    } catch (e) {
      if (my !== seq) return;
      list.replaceChildren(h('div.card.empty', h('h3', 'Could not load missions'), h('p', e.message), h('button.btn', { type: 'button', onclick: load }, 'Try again')));
    }
  };

  const search = h('input.input', { type: 'search', placeholder: 'Search missions…', 'aria-label': 'Search missions', value: f.q });
  let t;
  search.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => { f.q = search.value; load(); }, 220); });
  const tabs = h('div.tabs', { role: 'tablist' }, STATUS.map(([v, l]) => h('button', { type: 'button', role: 'tab', 'data-v': v, onclick: () => { f.status = v; sync(); load(); } }, l)));
  const cat = h('select.select', { 'aria-label': 'Category' }, h('option', { value: '' }, 'All categories'), store.skills.map((s) => h('option', { value: s.slug }, s.name)));
  cat.onchange = () => { f.category = cat.value; load(); };
  const sort = h('select.select', { 'aria-label': 'Sort' }, [['due', 'Sort: Due date'], ['newest', 'Sort: Newest'], ['xp', 'Sort: Highest XP']].map(([v, l]) => h('option', { value: v }, l)));
  sort.onchange = () => { f.sort = sort.value; load(); };
  const sync = () => {
    tabs.querySelectorAll('button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.v === f.status)));
    cat.value = f.category; sort.value = f.sort; search.value = f.q;
  };
  sync();
  ctx.setNewMissionDefaults(f.category ? { category: f.category } : {});
  load();
  return h('div', h('div.toolbar', h('div.search', icon('search'), search), tabs, cat, sort, h('div.spacer'), count), list);
}
