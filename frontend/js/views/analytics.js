import { api } from '../api.js';
import { h, icon, iconBox, fmt, pct, fmtDate, progressBar, skeleton, errorState, emptyState } from '../ui.js';
import { barChart, donut } from '../charts.js';

export const meta = { title: 'Analytics', sub: 'Understand how you grow' };

export async function render(params, ctx) {
  let range = params.range === 'month' ? 'month' : 'week';
  const body = h('div.stack');
  const tabs = h('div.tabs', { role: 'tablist' }, [['week', 'Last 7 days'], ['month', 'Last 30 days']].map(([v, l]) =>
    h('button', { type: 'button', role: 'tab', 'data-v': v, onclick: () => { range = v; sync(); load(); } }, l)));
  const sync = () => tabs.querySelectorAll('button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.v === range)));
  let seq = 0;

  async function load() {
    const my = ++seq;
    body.replaceChildren(skeleton(110), skeleton(280));
    try {
      const [a, hist] = await Promise.all([api.analytics(range), api.xpHistory(8, 0)]);
      if (my !== seq) return;
      body.replaceChildren(view(a, hist));
    } catch (e) { if (my === seq) body.replaceChildren(errorState(e, load)); }
  }

  const view = (a, hist) => {
    const t = a.totals, label = a.range === 'week' ? 'last 7 days' : 'last 30 days';
    const stat = (name, value, sub) => h('div.card.stat', h('div.eyebrow', name), h('div.v.tnum', value), h('div.s', sub));
    const stats = h('div.stats',
      stat('XP earned', fmt(t.xp), label), stat('Missions completed', String(t.missions), `${a.all_time.missions} all time`),
      stat('Active days', `${t.active_days} / ${a.days}`, `${fmt(t.avg_xp_per_day)} XP per day avg`),
      stat('Best day', t.best_day ? `${fmt(t.best_day.xp)} XP` : '—', t.best_day ? fmtDate(t.best_day.day) : 'No activity yet'));

    const empty = t.xp === 0;
    const activity = h('div.card', h('div.card-head', h('div', h('h2', 'Activity'), h('div.hint', 'XP earned per day'))),
      empty ? h('div.empty.compact', h('p', `No activity in the ${label}. Complete a mission to see your chart come alive.`), h('a.btn.btn-sm.btn-primary', { href: '#/missions' }, 'Go to missions')) : barChart(a.series));

    const cats = h('div.card.span-5', h('div.card-head', h('h2', 'By category'), h('span.hint', 'share of XP')));
    cats.append(empty ? h('div.empty.compact', h('p', 'No data for this period.')) : h('div.donut-wrap', donut(a.categories, { center: { value: fmt(t.category_xp), label: 'mission XP' } }),
      h('div.legend', a.categories.map((c) => h('div', h('i', { style: { background: c.color } }), c.name, h('b.tnum', pct(c.share)))))));

    const skills = h('div.card.span-7', h('div.card-head', h('h2', 'Skill progress'), h('span.hint', 'all time')),
      a.skills.map((s) => { const row = h('div.skill-row', { style: { '--c': s.color } }, h('span', s.name), progressBar(s.progress, 'sm'), h('span.tnum.muted', { style: { textAlign: 'right' } }, `Lv ${s.level} · ${fmt(s.xp)}`)); return row; }));

    const items = h('div.hist');
    let offset = 0;
    const more = h('button.btn.btn-sm', { type: 'button', style: { marginTop: '12px' } }, 'Load more');
    const append = (res) => {
      res.items.forEach((e) => items.append(h('div.hist-item',
        iconBox(e.source === 'achievement' ? 'trophy' : 'zap', e.skill_color || '#fbbf24'),
        h('div', { style: { minWidth: 0 } }, h('div.t', e.label), h('div.hint', `${fmtDate(e.day)}${e.skill_name ? ' · ' + e.skill_name : ''}${e.bonus_xp ? ` · +${e.bonus_xp} streak bonus` : ''}`)),
        h('span.amt', `+${fmt(e.amount)} XP`))));
      offset += res.items.length; more.hidden = !res.has_more;
    };
    more.onclick = async () => { more.disabled = true; try { append(await api.xpHistory(10, offset)); } catch (e) { more.textContent = 'Retry'; } more.disabled = false; };
    const histCard = h('div.card', h('div.card-head', h('h2', 'XP history')));
    if (!hist.items.length) histCard.append(h('div.empty.compact', h('p', 'Your XP history will appear here.')));
    else { append(hist); histCard.append(items, more); }
    return h('div.stack', stats, activity, h('div.grid.g-12', cats, skills), histCard);
  };

  sync(); load();
  return h('div.stack', h('div.row', tabs), body);
}
