// forms.js — formulario completo de solicitud de credito (app del cliente/usuario)
let PRODS = [];

function hallarProd(id) { return PRODS.find(p => p.producto === id); }

async function renderSolicitudForm(container) {
  PRODS = await API.get('/productos');
  container.innerHTML = `
  <h2>Nueva solicitud de crédito</h2>
  <div class="nota">Al enviar se genera automáticamente un <b>PDF de solicitud</b> con datos del titular y aval, información
  laboral, económica y financiera, monto y plazo. El PDF viaja por la cadena: <b>Agente → Gerente → Director</b>.</div>

  <div class="card"><h3>1. Datos del titular</h3><div class="grid">
    <div><label>Nombre completo</label><input id="tit_nombre"></div>
    <div><label>CURP</label><input id="tit_curp"></div>
    <div><label>Fecha de nacimiento</label><input id="tit_fecha_nac" type="date"></div>
    <div><label>Teléfono</label><input id="tit_telefono"></div>
    <div><label>Domicilio</label><input id="tit_direccion" style="grid-column:span 2"></div>
  </div></div>

  <div class="card"><h3>2. Datos del aval</h3><div class="grid">
    <div><label>Nombre completo</label><input id="av_nombre"></div>
    <div><label>CURP</label><input id="av_curp"></div>
    <div><label>Parentesco</label><input id="av_parentesco"></div>
    <div><label>Teléfono</label><input id="av_telefono"></div>
    <div><label>Domicilio</label><input id="av_direccion" style="grid-column:span 2"></div>
  </div></div>

  <div class="card"><h3>3. Información laboral</h3><div class="grid">
    <div><label>Empresa</label><input id="lab_empresa"></div>
    <div><label>Puesto</label><input id="lab_puesto"></div>
    <div><label>Antigüedad (años)</label><input id="lab_antiguedad" type="number"></div>
    <div><label>Salario mensual ($)</label><input id="lab_salario" type="number"></div>
    <div><label>Dirección de la empresa</label><input id="lab_direccion"></div>
    <div><label>Teléfono de la empresa</label><input id="lab_telefono"></div>
  </div></div>

  <div class="card"><h3>4. Información económica y financiera</h3><div class="grid">
    <div><label>Ingresos mensuales ($)</label><input id="eco_ingresos" type="number"></div>
    <div><label>Egresos mensuales ($)</label><input id="eco_egresos" type="number"></div>
    <div><label>Otros ingresos ($)</label><input id="eco_otros" type="number"></div>
    <div><label>Banco / cuenta</label><input id="fin_banco"></div>
    <div><label>Tarjeta / línea</label><input id="fin_tarjeta"></div>
    <div><label>Referencia 1</label><input id="fin_ref1"></div>
    <div><label>Referencia 2</label><input id="fin_ref2"></div>
  </div></div>

  <div class="card"><h3>5. Monto y plazo solicitado</h3><div class="grid">
    <div><label>Producto</label><select id="prodSel">
      ${PRODS.map(p => `<option value="${p.producto}">${p.nombre} — ${p.pagos} pagos ${p.frecuencia} · $${p.cuota_por_mil}/mil</option>`).join('')}
    </select></div>
    <div><label>Monto solicitado</label>
      <input id="montoRange" type="range" min="1000" max="15000" step="1000" value="1000">
      <span id="montoLbl" style="font-weight:700;color:var(--azul);font-size:16px">$1,000</span>
    </div>
  </div></div>
  <div id="planBox" class="card"></div>
  <button class="btn" id="btnSolicitar" onclick="enviarSolicitud()">Enviar solicitud</button>
  <div id="resSolicitud" style="margin-top:14px"></div>`;

  $('#prodSel').onchange = recalc;
  $('#montoRange').oninput = () => { $('#montoLbl').textContent = fmt($('#montoRange').value); recalc(); };
  recalc();
}

function recalc() {
  const p = hallarProd($('#prodSel').value);
  const r = $('#montoRange');
  r.min = p.monto_min; r.max = p.monto_max;
  if (parseInt(r.value) > p.monto_max) r.value = p.monto_max;
  if (parseInt(r.value) < p.monto_min) r.value = p.monto_min;
  $('#montoLbl').textContent = fmt(r.value);
  const monto = parseFloat(r.value);
  const cuota = monto / 1000 * p.cuota_por_mil;
  const total = cuota * p.pagos;
  const costo = total - monto;
  $('#planBox').innerHTML = `<h3>Resumen del plan</h3><div class="grid">
    <div><label>Cuota</label><b>${fmt(cuota)} ${p.frecuencia}</b></div>
    <div><label>Pagos</label><b>${p.pagos}</b></div>
    <div><label>Total a pagar</label><b>${fmt(total)}</b></div>
    <div><label>Costo financiero</label><b>${fmt(costo)} (${(costo / monto * 100).toFixed(2)}%)</b></div>
    <div><label>Rango del producto</label><b>${fmt(p.monto_min)} – ${fmt(p.monto_max)}</b></div>
  </div>`;
}

async function enviarSolicitud() {
  const val = id => ($('#' + id).value || '').trim();
  if (!val('tit_nombre') || !val('av_nombre')) { toast('Completa al menos los datos del titular y del aval'); return; }
  const body = {
    id_cliente: currentUser().id,
    producto: $('#prodSel').value,
    monto: parseFloat($('#montoRange').value),
    titular: { nombre: val('tit_nombre'), curp: val('tit_curp'), direccion: val('tit_direccion'), telefono: val('tit_telefono'), fecha_nac: val('tit_fecha_nac') },
    aval: { nombre: val('av_nombre'), curp: val('av_curp'), direccion: val('av_direccion'), telefono: val('av_telefono'), parentesco: val('av_parentesco') },
    laboral: { empresa: val('lab_empresa'), puesto: val('lab_puesto'), antiguedad: val('lab_antiguedad'), salario: val('lab_salario'), direccion: val('lab_direccion'), telefono: val('lab_telefono') },
    economica: { ingresos: val('eco_ingresos'), egresos: val('eco_egresos'), otros: val('eco_otros') },
    financiera: { banco: val('fin_banco'), tarjeta: val('fin_tarjeta'), ref1: val('fin_ref1'), ref2: val('fin_ref2') }
  };
  try {
    const r = await API.post('/solicitudes', body);
    $('#resSolicitud').innerHTML = `<div class="card"><h3>✅ Solicitud ${folio(r.id)} enviada</h3>
      <p>${r.mensaje}</p>
      <button class="btn dorado" onclick="abrirPDF('/solicitud/${r.id}/pdf')">📄 Descargar PDF de solicitud</button></div>`;
    toast('Solicitud enviada al agente');
  } catch (e) { toast(e.message); }
}
