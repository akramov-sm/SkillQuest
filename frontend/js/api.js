// Thin fetch wrapper. Throws ApiError with message + per-field errors.
export class ApiError extends Error {
  constructor(status, code, message, fields = {}) {
    super(message); this.status = status; this.code = code; this.fields = fields;
  }
}

async function request(method, path, body) {
  let res;
  try {
    res = await fetch('/api' + path, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'network', 'Cannot reach the SkillQuest server. Is it running?');
  }
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* non-JSON */ }
  if (!res.ok) {
    const e = data?.error || {};
    throw new ApiError(res.status, e.code || 'error', e.message || `Request failed (${res.status})`, e.fields || {});
  }
  return data;
}

const qs = (o = {}) => {
  const p = new URLSearchParams();
  Object.entries(o).forEach(([k, v]) => { if (v !== '' && v != null) p.set(k, v); });
  const s = p.toString();
  return s ? '?' + s : '';
};

export const api = {
  dashboard: () => request('GET', '/dashboard'),
  missions: (f) => request('GET', '/missions' + qs(f)),
  createMission: (d) => request('POST', '/missions', d),
  updateMission: (id, d) => request('PUT', `/missions/${id}`, d),
  deleteMission: (id) => request('DELETE', `/missions/${id}`),
  complete: (id) => request('POST', `/missions/${id}/complete`, {}),
  reopen: (id) => request('POST', `/missions/${id}/reopen`, {}),
  skills: () => request('GET', '/skills'),
  achievements: () => request('GET', '/achievements'),
  analytics: (range) => request('GET', '/analytics' + qs({ range })),
  xpHistory: (limit, offset) => request('GET', '/xp-history' + qs({ limit, offset })),
  profile: () => request('GET', '/profile'),
  updateProfile: (d) => request('PUT', '/profile', d),
  reset: () => request('POST', '/profile/reset', { confirm: true }),
};
