import { api } from '../api.js';
import { h, icon, iconBox, fmt, pct, progressBar, emptyState, avatar } from '../ui.js';
import { miniBars, weekday } from '../charts.js';
import { missionRow, openMissionForm } from '../missionKit.js';
import { setUser } from '../store.js';

export const meta = { title: 'Dashboard', sub: 'Your progress at a glance' };

export async function render(_, ctx) {
  const d = await api.dashboard();
  setUser(d.user);
  const u = d.user;
  const reload = () => ctx.reload();

  const hero = h('div.card.hero.span-8',
    h('div.hero-top',
      h('div.level-orb', String(u.level)),
      h('div', h('div.eyebrow', 'Current level'),
        h('div.big.tnum', `${fmt(u.xp)} XP`),
        h('div.muted', u.maxed ? 'Max level' : `${fmt(u.xp_for_next - u.xp_into_level)} XP to level ${u.level + 1}`))),
    progressBar(u.progress, 'lg'),
    h('div.hero-meta', h('span.tnum', `${fmt(u.xp_into_level)} / ${fmt(u.xp_for_next)} XP`), h('span', `Level ${u.level} → ${u.level + 1} · ${pct(u.progress)}`)));

  const s = d.streak;
  const days = d.week.series.map((x) => h('span', h('b', { class: x.missions ? 'on' : '' }), weekday(x.day).slice(0, 2)));
  const streak = h('div.card.span-4',
    h('div.card-head', h('h2', 'Streak')),
    h('div.streak',
      h('div.flame', { class: s.active_today ? 'on' : '', html: icon('flame').innerHTML }),
      h('div', h('div.big.tnum', `${s.current} day${s.current === 1 ? '' : 's'}`),
        h('div.muted', s.active_today ? 'Active today — nice!' : s.current ? 'Complete a mission to keep it alive' : 'Complete a mission to start a streak'))),
    h('div.week-days', days),
    h('div.hint', { style: { marginTop: '12px' } }, `Best streak: ${s.best} day${s.best === 1 ? '' : 's'}`));

  const todayDone = d.today.filter((m) => m.status === 'completed').length;
  const todayCard = h('div.card.span-7', h('div.card-head',
    h('div', h('h2', "Today's missions"), h('div.hint', d.today.length ? `${todayDone} of ${d.today.length} done` : 'Nothing scheduled')),
    h('button.btn.btn-sm', { type: 'button', onclick: () => openMissionForm({ defaults: { due_date: new Date().toLocaleDateString('en-CA') }, onSaved: reload }) }, icon('plus'), 'Add')));
  if (!d.today.length) {
    todayCard.append(d.pending_total
      ? h('div.empty.compact', h('p', 'No missions are due today. Browse your backlog or add a new one.'), h('a.btn.btn-sm', { href: '#/missions' }, 'Open missions'))
      : h('div.empty.compact', iconBox('missions', '#8b5cf6'), h('h3', 'Create your first mission'), h('p', 'Turn something real — a workout, a chapter, a bug fix — into XP.'),
        h('button.btn.btn-primary', { type: 'button', onclick: () => openMissionForm({ onSaved: reload }) }, icon('plus'), 'New mission')));
  } else {
    todayCard.append(h('div.mlist', d.today.map((m) => missionRow(m, { onChange: reload, compact: true }))));
  }

  const week = h('div.card.span-5',
    h('div.card-head', h('h2', 'This week'), h('a.link', { href: '#/analytics' }, 'Analytics →')),
    h('div.row', { style: { gap: '28px', marginBottom: '16px' } },
      h('div', h('div.eyebrow', 'XP earned'), h('div.big.tnum', { style: { fontSize: '30px' } }, fmt(d.week.xp))),
      h('div', h('div.eyebrow', 'Missions'), h('div.big.tnum', { style: { fontSize: '30px' } }, String(d.week.missions)))),
    miniBars(d.week.series, 72),
    h('div.row.tnum', { style: { justifyContent: 'space-between', marginTop: '6px', color: 'var(--text-3)', fontSize: '11px' } }, d.week.series.map((x) => h('span', weekday(x.day).slice(0, 3)))));

  const ach = h('div.card.span-6.keep',
    h('div.card-head', h('div', h('h2', 'Recent achievements'), h('div.hint', `${d.achievements.unlocked} of ${d.achievements.total} unlocked`)), h('a.link', { href: '#/achievements' }, 'View all →')));
  ach.append(d.recent_achievements.length
    ? h('div.stack', { style: { gap: '12px' } }, d.recent_achievements.map((a) => h('div.row', iconBox(a.icon, '#fbbf24'),
      h('div', { style: { minWidth: 0 } }, h('div', { style: { fontWeight: 600 } }, a.title), h('div.hint', a.description)),
      h('span.chip.xp.spacer-l', { style: { marginLeft: 'auto' } }, `+${a.reward_xp} XP`))))
    : h('div.empty.compact', iconBox('achievements', '#fbbf24'), h('p', 'Complete your first mission to unlock your first achievement.')));

  const skills = h('div.card.span-6.keep',
    h('div.card-head', h('h2', 'Skills'), h('a.link', { href: '#/skills' }, 'Skill tree →')),
    h('div.stack', { style: { gap: '14px' } }, d.skills.map((sk) => h('a.row', { href: '#/skills', style: { display: 'grid', gridTemplateColumns: '120px 1fr 44px', gap: '12px', fontSize: '13px' } },
      h('span', { style: { overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' } }, sk.name),
      progressBar(sk.progress, 'sm', sk.color), h('b.tnum', { style: { textAlign: 'right' } }, `L${sk.level}`)))));
  skills.querySelectorAll('.progress > i').forEach((i, n) => { i.style.background = d.skills[n].color; i.style.boxShadow = `0 0 10px ${d.skills[n].color}80`; });

  return h('div.grid.g-12', hero, streak, todayCard, week, ach, skills);
}
