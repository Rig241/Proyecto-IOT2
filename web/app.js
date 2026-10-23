'use strict';

const MAX_POINTS = 60;
const RECONNECT_DELAY = 3000;
// El mismo host sirve la página y /ws. No hay IP ni contraseña MQTT en el navegador.
const WS_URL = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`;
const FIELDS = ['voltaje', 'corriente', 'resistencia', 'fase'];
const COLORS = { voltaje: '#00d4ff', corriente: '#ff6b6b', resistencia: '#ffd93d', fase: '#6bcb77' };
const LABELS = { voltaje: 'Voltaje (V)', corriente: 'Corriente (A)', resistencia: 'Resistencia (Ω)', fase: 'Fase (°)' };
const IDS = { voltaje: 'valVoltaje', corriente: 'valCorriente', resistencia: 'valResistencia', fase: 'valFase' };
const DECIMALS = { voltaje: 2, corriente: 3, resistencia: 2, fase: 1 };
const state = { labels: [], voltaje: [], corriente: [], resistencia: [], fase: [] };
let socketOpen = false;
let serverStatus = null;
let lastStatusAt = 0;
let ws;
let reconnectTimer;

Chart.defaults.color = '#8899a8';
Chart.defaults.borderColor = '#2a3a4f';
Chart.defaults.font.family = "'Segoe UI', Roboto, sans-serif";

function options(single = false) {
  return {
    responsive: true, maintainAspectRatio: false, animation: false,
    interaction: { mode: 'index', intersect: false },
    plugins: { legend: { display: !single, labels: { color: '#e8eef5', boxWidth: 12, padding: 12 } } },
    scales: {
      x: { grid: { color: 'rgba(42,58,79,0.5)' }, ticks: { maxTicksLimit: 8 } },
      y: { grid: { color: 'rgba(42,58,79,0.5)' }, beginAtZero: false }
    }
  };
}

function dataset(field) {
  return {
    label: LABELS[field], data: state[field], borderColor: COLORS[field],
    backgroundColor: COLORS[field] + '18', borderWidth: 2, tension: 0,
    pointRadius: 0, fill: false
  };
}

const mainChart = new Chart(document.getElementById('mainChart'), {
  type: 'line', data: { labels: state.labels, datasets: FIELDS.map(dataset) }, options: options()
});
const allCharts = [mainChart, ...FIELDS.map(field => new Chart(
  document.getElementById('chart' + field[0].toUpperCase() + field.slice(1)),
  { type: 'line', data: { labels: state.labels, datasets: [dataset(field)] }, options: options(true) }
))];

function pushData(message) {
  const data = message.data;
  if (!data || !FIELDS.every(field => typeof data[field] === 'number' && Number.isFinite(data[field]))) {
    throw new Error('Medición inválida');
  }
  const received = new Date(message.received_at);
  if (!Number.isFinite(received.getTime())) throw new Error('Hora inválida');
  const label = received.toLocaleTimeString();
  state.labels.push(label);
  FIELDS.forEach(field => {
    state[field].push(data[field]);
    document.getElementById(IDS[field]).textContent = data[field].toFixed(DECIMALS[field]);
  });
  if (state.labels.length > MAX_POINTS) {
    state.labels.shift();
    FIELDS.forEach(field => state[field].shift());
  }
  document.getElementById('lastUpdate').textContent = 'Última lectura: ' + received.toLocaleString();
  allCharts.forEach(chart => chart.update('none'));
}

function renderStatus() {
  let label, detail, style = '';
  if (!socketOpen) {
    label = 'Servidor desconectado';
    detail = 'Reconectando al servidor. Los valores visibles corresponden a la última lectura recibida.';
  } else if (!serverStatus || Date.now() - lastStatusAt > 5000) {
    label = 'Esperando respuesta'; style = 'warning';
    detail = 'La conexión está abierta, pero no hay un estado reciente del servidor.';
  } else if (!serverStatus.mqtt_connected) {
    label = 'MQTT desconectado'; style = 'warning';
    detail = 'La página está conectada. El servidor está intentando conectar con el broker MQTT.';
  } else if (!serverStatus.data_fresh) {
    label = serverStatus.last_update ? 'Sin lecturas recientes' : 'Esperando mediciones'; style = 'warning';
    detail = serverStatus.last_update
      ? `No se han recibido lecturas nuevas en los últimos ${serverStatus.stale_seconds} segundos. Los valores visibles pueden estar desactualizados.`
      : 'MQTT está conectado. Esperando que el dispositivo publique sus primeras mediciones.';
  } else {
    label = 'Recibiendo datos'; style = 'connected';
    detail = 'Panel actualizado con las últimas lecturas recibidas.';
  }
  document.getElementById('statusDot').className = 'dot' + (style ? ' ' + style : '');
  document.getElementById('statusText').textContent = label;
  document.getElementById('connectionDetail').textContent = detail;
}

function connect() {
  ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    socketOpen = true; serverStatus = null; lastStatusAt = 0; renderStatus();
  };
  ws.onmessage = event => {
    try {
      const message = JSON.parse(event.data);
      if (message.type === 'status') {
        if (typeof message.mqtt_connected !== 'boolean' || typeof message.data_fresh !== 'boolean') return;
        serverStatus = message; lastStatusAt = Date.now(); renderStatus();
      } else if (message.type === 'measurement') {
        pushData(message);
      }
    } catch (error) {
      console.error('Mensaje descartado:', error.message);
    }
  };
  ws.onclose = () => {
    socketOpen = false; serverStatus = null; renderStatus();
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, RECONNECT_DELAY);
  };
  ws.onerror = () => ws.close();
}

if (location.protocol === 'file:') {
  document.getElementById('statusText').textContent = 'Abre el servidor local';
  document.getElementById('connectionDetail').textContent = 'Accede mediante http://IP_DEL_EQUIPO:8080; abrir el HTML con doble clic no conecta con MQTT.';
} else {
  connect();
  setInterval(renderStatus, 1000);
}
