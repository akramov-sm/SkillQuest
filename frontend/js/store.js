// Tiny shared state: skills metadata (names/colors) and current user summary.
export const store = { skills: [], user: null, listeners: new Set() };
export const skillBy = (slug) => store.skills.find((s) => s.slug === slug) || { name: slug, color: '#8b5cf6', icon: 'star' };
export function setUser(u) { store.user = u; store.listeners.forEach((f) => f(u)); }
