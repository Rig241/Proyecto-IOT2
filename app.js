// ============================================
// CONFIGURACIÓN
// ============================================
const MAX_POINTS = 60;                          // últimos 60 puntos visibles
const WS_URL = 'ws://raspberrypi.local:8765';   // ajusta a tu IP
const RECONNECT_DELAY = 3000;                   // ms

// Colores de las señales
const COLORS = {
  voltaje: '#00d4ff',
  corriente: '#ff6b6b',
  resistencia: '#ffd93d',
  fase: '#6bcb77'
};

// ============================================
// ESTADO DE DATOS
// ============================================
const state = {
  labels: [],
  voltaje: [],
  corriente: [],
  resistencia: [],
  fase: []
};

// ============================================
// CONFIGURACIÓN COMÚN DE CHART.JS
// ============================================
Chart.defaults.color = '#8899a8';
Chart.defaults.borderColor = '#2a3a4f';
Chart.defaults.font.family = "'Segoe UI', Roboto, sans-serif";

const commonOptions = {
  responsive: true,
  maintainAspectRatio: false,
  animation: { duration: 300 },
  interaction: { mode: 'index', intersect: false },
  plugins: {
    legend: {
      labels: { color: '#e8eef5', boxWidth: 12, padding: 12 }
    }
  },
  scales: {
    x: {
      grid: { color: 'rgba(42, 58, 79, 0.5)' },
      ticks: { maxTicksLimit: 8 }
    },
    y: {
      grid: { color: 'rgba(42, 58, 79, 0.5)' },
      beginAtZero: false
    }
  }
};

// ============================================
// GRÁFICA PRINCIPAL (multilínea)
// ============================================
const mainChart = new Chart(document.getElementById('mainChart'), {
  type: 'line',
  data: {
    labels: state.labels,
    datasets: [
      {
        label: 'Voltaje (V)',
        data: state.voltaje,
        borderColor: COLORS.voltaje,
        backgroundColor: 'rgba(0,212,255,0.1)',
        borderWidth: 2, tension: 0.4, pointRadius: 0, fill: true
      },
      {
        label: 'Corriente (A)',
        data: state.corriente,
        borderColor: COLORS.corriente,
        backgroundColor: 'rgba(255,107,107,0.1)',
        borderWidth: 2, tension: 0.4, pointRadius: 0, fill: true
      },
      {
        label: 'Resistencia (Ω)',
        data: state.resistencia,
        borderColor: COLORS.resistencia,
        backgroundColor: 'rgba(255,217,61,0.1)',
        borderWidth: 2, tension: 0.4, pointRadius: 0, fill: true
      },
      {
        label: 'Fase (°)',
        data: state.fase,
        borderColor: COLORS.fase,
        backgroundColor: 'rgba(107,203,119,0.1)',
        borderWidth: 2, tension: 0.4, pointRadius: 0, fill: true
      }
    ]
  },
  options: commonOptions
});

// ============================================
// GRÁFICAS INDIVIDUALES
// ============================================
function createSingleChart(canvasId, label, color, dataRef) {
  return new Chart(document.getElementById(canvasId), {
    type: 'line',
    data: {
      labels: state.labels,
      datasets: [{
        label,
        data: dataRef,
        borderColor: color,
        backgroundColor: color + '22',
        borderWidth: 2, tension: 0.4, pointRadius: 0, fill: true
      }]
    },
    options: {
      ...commonOptions,
      plugins: { legend: { display: false } }
    }
  });
}

const chartVoltaje = createSingleChart('chartVoltaje', 'Voltaje (V)', COLORS.voltaje, state.voltaje);
const chartCorriente = createSingleChart('chartCorriente', 'Corriente (A)', COLORS.corriente, state.corriente);
const chartResistencia = createSingleChart('chartResistencia', 'Resistencia (Ω)', COLORS.resistencia, state.resistencia);
const chartFase = createSingleChart('chartFase', 'Fase (°)', COLORS.fase, state.fase);

// Guardamos referencias para actualizar eficientemente
const allCharts = [mainChart, chartVoltaje, chartCorriente, chartResistencia, chartFase];

// ============================================
// ACTUALIZAR DATOS
// ============================================
function pushData(data) {
  const now = new Date().toLocaleTimeString();

  // Añadir nuevos datos
  state.labels.push(now);
  state.voltaje.push(data.voltaje);
  state.corriente.push(data.corriente);
  state.resistencia.push(data.resistencia);
  state.fase.push(data.fase);

  // Limitar puntos (ventana deslizante)
  if (state.labels.length > MAX_POINTS) {
    state.labels.shift();
    state.voltaje.shift();
    state.corriente.shift();
    state.resistencia.shift();
    state.fase.shift();
  }

  // Actualizar tarjetas de métricas
  document.getElementById('valVoltaje').textContent = data.voltaje.toFixed(2);
  document.getElementById('valCorriente').textContent = data.corriente.toFixed(3);
  document.getElementById('valResistencia').textContent = data.resistencia.toFixed(2);
  document.getElementById('valFase').textContent = data.fase.toFixed(1);
  document.getElementById('lastUpdate').textContent = now;

  // Refrescar todas las gráficas sin animación (más fluido)
  allCharts.forEach(chart => chart.update('none'));
}

// ============================================
// UI: ESTADO DE CONEXIÓN
// ============================================
function setConnected(isConnected) {
  const dot = document.getElementById('statusDot');
  const text = document.getElementById('statusText');

  if (isConnected) {
    dot.classList.add('connected');
    text.textContent = 'Conectado';
  } else {
    dot.classList.remove('connected');
    text.textContent = 'Reconectando...';
  }
}

// ============================================
// CONEXIÓN WEBSOCKET
// ============================================
let ws;
let reconnectTimer;

function connect() {
  ws = new WebSocket(WS_URL);

  ws.onopen = () => {
    setConnected(true);
    console.log('✅ WebSocket conectado');
  };

  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      // Formato esperado:
      // { voltaje: 220.5, corriente: 1.23, resistencia: 179.3, fase: 45.2 }
      pushData(data);
    } catch (e) {
      console.error('Error parseando datos:', e);
    }
  };

  ws.onclose = () => {
    setConnected(false);
    clearTimeout(reconnectTimer);
    reconnectTimer = setTimeout(connect, RECONNECT_DELAY);
  };

  ws.onerror = (err) => {
    console.error('WebSocket error:', err);
    ws.close();
  };
}

connect();

// ============================================
// MODO DEMO (descomentar si no hay Raspberry aún)
// ============================================

setInterval(() => {
  pushData({
    voltaje: 220 + Math.random() * 10 - 5,
    corriente: 1.5 + Math.random() * 0.5,
    resistencia: 150 + Math.random() * 20,
    fase: 45 + Math.random() * 10
  });
}, 1000);
