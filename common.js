// common.js — utilerias compartidas
const $ = (s, e = document) => e.querySelector(s);
const $$ = (s, e = document) => [...e.querySelectorAll(s)];
const fmt = n => '$' + Number(n || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fdate = s => (s || '').slice(0, 10);
const currentUser = () => { try { return JSON.parse(localStorage.getItem('user')); } catch { return null; } };
const EST = {
  pendiente_agente: 'Pendiente · Agente', pendiente_gerente: 'Pendiente · Gerente',
  pendiente_admin: 'Pendiente · Director', aprobada: 'Aprobada',
  desembolsada: 'Desembolsada', rechazada: 'Rechazada'
};
const folio = id => 'SOL-' + String(id).padStart(5, '0');
const badge = s => `<span class="estado est ${s}">${EST[s] || s}</span>`;

function logout() { localStorage.removeItem('token'); localStorage.removeItem('user'); location.href = 'login.html'; }
function guard(rol) {
  const u = currentUser();
  if (!localStorage.getItem('token')) { location.href = 'login.html'; return; }
  if (rol && u && u.rol !== rol) { location.href = u.rol + '.html'; }
}
function toast(msg) {
  const t = $('#toast');
  if (!t) return;
  t.textContent = msg;
  t.style.display = 'block';
  clearTimeout(t._h);
  t._h = setTimeout(() => t.style.display = 'none', 3200);
}
function panel(id) {
  $$('.panel').forEach(p => p.style.display = p.id === id ? 'block' : 'none');
  $$('nav.side button').forEach(b => b.classList.toggle('activo', b.dataset.panel === id));
}
function tabla(headers, rows) {
  if (!rows || !rows.length) return '<p class="nota">Sin registros que mostrar.</p>';
  return `<div style="overflow:auto"><table><thead><tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr></thead>
  <tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function kpiCards(items) {
  return `<div class="kpis">${items.map(([l, v]) => `<div class="kpi"><span>${l}</span><b>${v}</b></div>`).join('')}</div>`;
}
async function abrirPDF(path) {
  try {
    const url = await API.file(path);
    window.open(url, '_blank');
  } catch (e) { toast(e.message); }
}
