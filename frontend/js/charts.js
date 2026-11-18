// Dependency-free SVG charts.
const NS = 'http://www.w3.org/2000/svg';
const s = (tag, attrs = {}, ...kids) => {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  kids.forEach((k) => el.append(k));
  return el;
};

let tipEl;
export function showTip(e, html) {
  if (!tipEl) { tipEl = document.createElement('div'); tipEl.className = 'tip'; document.body.append(tipEl); }
  tipEl.replaceChildren(...html);
  tipEl.classList.add('show');
  const r = tipEl.getBoundingClientRect();
  tipEl.style.left = Math.max(8, Math.min(innerWidth - r.width - 8, e.clientX - r.width / 2)) + 'px';
  tipEl.style.top = Math.max(8, e.clientY - r.height - 14) + 'px';
}
export const hideTip = () => tipEl?.classList.remove('show');
const tipLines = (title, line) => {
  const b = document.createElement('b'); b.textContent = title;
  const t = document.createElement('span'); t.textContent = line;
  return [b, t];
};

const SHORT = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const parse = (iso) => new Date(iso + 'T00:00:00');
export const weekday = (iso) => SHORT[parse(iso).getDay()];
const niceMax = (v) => { if (v <= 0) return 50; const p = 10 ** Math.floor(Math.log10(v)); return Math.ceil(v / (p / 2)) * (p / 2); };

/** Re-draws an SVG at the real pixel width of its container (keeps text crisp & unscaled). */
function fluid(draw) {
  const box = document.createElement('div');
  box.style.width = '100%';
  let lastW = 0;
  const paint = () => {
    const w = Math.round(box.clientWidth);
    if (!w || w === lastW) return;
    lastW = w; box.replaceChildren(draw(w));
  };
  new ResizeObserver(paint).observe(box);
  requestAnimationFrame(paint);
  setTimeout(paint, 60); // fallback if the observer/frame callback is delayed (hidden or throttled tabs)
  return box;
}

/** series: [{day, xp, missions}] */
export function barChart(series, opts = {}) { return fluid((w) => drawBars(series, w, opts.height || 220)); }

function drawBars(series, W, height) {
  const H = height, pad = { l: 38, r: 6, t: 10, b: 24 };
  const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b;
  const max = niceMax(Math.max(...series.map((d) => d.xp), 0));
  const svg = s('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: 'img', 'aria-label': 'XP earned per day' });
  const defs = s('defs');
  const g = s('linearGradient', { id: 'barGrad', x1: 0, y1: 0, x2: 0, y2: 1 });
  g.append(s('stop', { offset: 0, 'stop-color': '#8b5cf6' }), s('stop', { offset: 1, 'stop-color': '#3b82f6' }));
  defs.append(g); svg.append(defs);
  for (let i = 0; i <= 4; i++) {
    const y = pad.t + ih - (ih * i) / 4;
    svg.append(s('line', { class: 'grid-line', x1: pad.l, x2: W - pad.r, y1: y, y2: y }));
    const t = s('text', { x: pad.l - 8, y: y + 4, 'text-anchor': 'end' }); t.textContent = Math.round((max * i) / 4); svg.append(t);
  }
  const n = series.length, slot = iw / n, bw = Math.min(40, slot * 0.62);
  const every = n > 14 ? Math.ceil((n * 56) / iw) : 1;
  series.forEach((d, i) => {
    const x = pad.l + slot * i + (slot - bw) / 2;
    const bh = d.xp > 0 ? Math.max(4, (d.xp / max) * ih) : 0;
    const hit = s('rect', { x: pad.l + slot * i, y: pad.t, width: slot, height: ih, fill: 'transparent' });
    const date = parse(d.day);
    const label = `${SHORT[date.getDay()]}, ${MON[date.getMonth()]} ${date.getDate()}`;
    const bar = s('rect', { class: 'bar', x, y: pad.t + ih - bh, width: bw, height: bh, rx: Math.min(6, bw / 3), fill: 'url(#barGrad)', style: `animation-delay:${i * 25}ms; transform-box: fill-box;` });
    if (!bh) bar.setAttribute('opacity', 0);
    hit.addEventListener('mousemove', (e) => showTip(e, tipLines(label, `${d.xp} XP · ${d.missions} mission${d.missions === 1 ? '' : 's'}`)));
    hit.addEventListener('mouseleave', hideTip);
    svg.append(bar, hit);
    if (i % every === 0) {
      const t = s('text', { x: x + bw / 2, y: H - 6, 'text-anchor': 'middle' });
      t.textContent = n > 10 ? `${date.getDate()} ${MON[date.getMonth()]}` : SHORT[date.getDay()];
      svg.append(t);
    }
  });
  return svg;
}

/** Tiny bar sparkline for dashboard. */
export function miniBars(series, height = 64) {
  const W = 280, H = height, n = series.length, gap = 8, bw = (W - gap * (n - 1)) / n;
  const max = Math.max(...series.map((d) => d.xp), 1);
  const svg = s('svg', { class: 'chart', viewBox: `0 0 ${W} ${H}`, role: 'img', 'aria-label': 'XP over the last 7 days', preserveAspectRatio: 'none' });
  const g = s('linearGradient', { id: 'miniGrad', x1: 0, y1: 0, x2: 0, y2: 1 });
  g.append(s('stop', { offset: 0, 'stop-color': '#8b5cf6' }), s('stop', { offset: 1, 'stop-color': '#3b82f6' }));
  svg.append(s('defs', {}, g));
  series.forEach((d, i) => {
    const bh = d.xp ? Math.max(5, (d.xp / max) * H) : 4;
    const r = s('rect', { class: 'bar', x: i * (bw + gap), y: H - bh, width: bw, height: bh, rx: 4, fill: d.xp ? 'url(#miniGrad)' : 'rgba(255,255,255,.08)', style: `animation-delay:${i * 40}ms; transform-box: fill-box;` });
    r.addEventListener('mousemove', (e) => showTip(e, tipLines(`${weekday(d.day)}, ${d.day.slice(5)}`, `${d.xp} XP · ${d.missions} missions`)));
    r.addEventListener('mouseleave', hideTip);
    svg.append(r);
  });
  return svg;
}

/** items: [{name,color,xp,share}] */
export function donut(items, { size = 180, center } = {}) {
  const R = 70, r = 48, C = 90;
  const svg = s('svg', { class: 'chart', viewBox: '0 0 180 180', width: size, height: size, role: 'img', 'aria-label': 'XP by category', style: 'width:' + size + 'px;flex:none' });
  const total = items.reduce((a, b) => a + b.xp, 0);
  svg.append(s('circle', { cx: C, cy: C, r: (R + r) / 2, fill: 'none', stroke: 'rgba(255,255,255,.06)', 'stroke-width': R - r }));
  if (total > 0) {
    const mid = (R + r) / 2, circ = 2 * Math.PI * mid;
    let acc = 0;
    items.filter((i) => i.xp > 0).forEach((it) => {
      const len = (it.xp / total) * circ, gap = items.filter((i) => i.xp > 0).length > 1 ? 2.5 : 0;
      const c = s('circle', { cx: C, cy: C, r: mid, fill: 'none', stroke: it.color, 'stroke-width': R - r, 'stroke-dasharray': `${Math.max(0, len - gap)} ${circ}`, 'stroke-dashoffset': -acc, transform: `rotate(-90 ${C} ${C})`, style: 'cursor:pointer;transition:opacity .15s' });
      c.addEventListener('mousemove', (e) => showTip(e, tipLines(it.name, `${it.xp} XP · ${Math.round(it.share * 100)}%`)));
      c.addEventListener('mouseleave', hideTip);
      svg.append(c); acc += len;
    });
  }
  const t1 = s('text', { x: C, y: C + 4, 'text-anchor': 'middle', style: 'font-size:24px;font-weight:700;fill:#ececf3' }); t1.textContent = center?.value ?? total;
  const t2 = s('text', { x: C, y: C + 22, 'text-anchor': 'middle' }); t2.textContent = center?.label ?? 'XP';
  svg.append(t1, t2);
  return svg;
}
