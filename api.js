// api.js — cliente HTTP con token de sesion
const API = {
  token: () => localStorage.getItem('token') || '',
  async req(method, path, body) {
    const opts = { method, headers: { 'Authorization': 'Bearer ' + this.token() } };
    if (body !== undefined) { opts.headers['Content-Type'] = 'application/json'; opts.body = JSON.stringify(body); }
    const res = await fetch('/api' + path, opts);
    if (res.status === 401) { localStorage.removeItem('token'); localStorage.removeItem('user'); location.href = 'login.html'; throw new Error('Sesion expirada'); }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || 'Error ' + res.status);
    return data;
  },
  get: (p) => API.req('GET', p),
  post: (p, b) => API.req('POST', p, b),
  // Descarga de archivos (PDF) con sesion
  async file(path) {
    const res = await fetch('/api' + path, { headers: { 'Authorization': 'Bearer ' + this.token() } });
    if (!res.ok) throw new Error('No se pudo descargar el archivo');
    return URL.createObjectURL(await res.blob());
  }
};
