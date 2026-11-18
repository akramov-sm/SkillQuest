// App shell: hash router, navigation, sidebar level card, global actions.
import { api } from './api.js';
import { store, setUser } from './store.js';
import { h, icon, svgIcon, avatar, progressBar, skeleton, errorState, fmt, toast } from './ui.js';
import { openMissionForm } from './missionKit.js';

const ROUTES = {
  dashboard: () => import('./views/dashboard.js'),
  missions: () => import('./views/missions.js'),
  skills: () => import('./views/skills.js'),
  achievements: () => import('./views/achievements.js'),
  analytics: () => import('./views/analytics.js'),
  profile: () => import('./views/profile.js'),
};
const NAV = [['dashboard', 'Dashboard'], ['missions', 'Missions'], ['skills', 'Skill Tree'], ['achievements', 'Achievements'], ['analytics', 'Analytics'], ['profile', 'Profile']];
const BOTTOM = { dashboard: 'Home', missions: 'Missions', skills: 'Skills', achievements: 'Awards', analytics: 'Stats', profile: 'Profile' };

const $ = (id) => document.getElementById(id);
let current = { name: null, params: {} };
let newDefaults = {};
let token = 0;

function parseHash() {
  const [path, query = ''] = (location.hash.replace(/^#\/?/, '') || 'dashboard').split('?');
  const name = path in ROUTES ? path : 'dashboard';
  return { name, params: Object.fromEntries(new URLSearchParams(query)) };
}

function buildNav() {
  $('nav').replaceChildren(...NAV.map(([k, label]) => h('a', { href: `#/${k}`, 'data-route': k }, h('span.nav-ico', { html: svgIcon(k).replace('<svg', '<svg width="18" height="18"') }), h('span.nav-label', label))));
  $('bottomNav').replaceChildren(...NAV.map(([k]) => h('a', { href: `#/${k}`, 'data-route': k, 'aria-label': NAV.find((n) => n[0] === k)[1] }, h('span', { html: svgIcon(k) }), BOTTOM[k])));
  const btn = $('newMissionBtn');
  btn.replaceChildren(icon('plus'), h('span.lbl', 'New mission'));
  btn.onclick = () => openMissionForm({ defaults: newDefaults, onSaved: reload });
}

function renderSideLevel(u) {
  if (!u) return;
  $('sideLevel').replaceChildren(
    h('div.row', avatar(u, 'sm'), h('div', h('div.name', u.name), h('div.sub.tnum', `Level ${u.level} · ${fmt(u.xp)} XP`))),
    progressBar(u.progress, 'sm'));
}
store.listeners.add(renderSideLevel);

async function navigate(soft = false) {
  const { name, params } = parseHash();
  current = { name, params };
  newDefaults = {};
  const my = ++token;
  document.querySelectorAll('[data-route]').forEach((a) => a.classList.toggle('active', a.dataset.route === name));
  const view = $('view');
  if (!soft) view.replaceChildren(skeleton(120, 3));
  view.classList.toggle('soft', soft);
  try {
    const mod = await ROUTES[name]();
    if (my !== token) return;
    $('pageTitle').textContent = mod.meta.title; $('pageSub').textContent = mod.meta.sub;
    document.title = `${mod.meta.title} · SkillQuest`;
    const node = await mod.render(params, { reload, setNewMissionDefaults: (d) => { newDefaults = d; } });
    if (my !== token) return;
    view.replaceChildren(node);
    if (!soft) { view.style.animation = 'none'; void view.offsetWidth; view.style.animation = ''; }
  } catch (e) {
    if (my !== token) return;
    console.error(e);
    const friendly = e.name === 'ApiError' || e.status !== undefined ? e : new Error('Could not load this page. Check that the SkillQuest server is running, then try again.');
    view.replaceChildren(errorState(friendly, () => navigate()));
  }
}
// Re-render the current view while keeping scroll position.
async function reload() {
  const y = window.scrollY;
  await navigate(true);
  window.scrollTo(0, y);
}

async function boot() {
  buildNav();
  try {
    const { items, user } = await api.skills();
    store.skills = items; setUser(user);
  } catch (e) {
    $('view').replaceChildren(errorState(e, () => location.reload()));
    return;
  }
  window.addEventListener('hashchange', () => { window.scrollTo(0, 0); navigate(); });
  navigate();
}
boot();
