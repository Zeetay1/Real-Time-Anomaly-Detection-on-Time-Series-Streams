(function () {
  const WS_URL = (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + '/ws';
  const MAX_POINTS = 200;

  const statusEl = document.getElementById('status');
  const totalAnomaliesEl = document.getElementById('total-anomalies');
  const totalDriftEl = document.getElementById('total-drift');
  const precisionEl = document.getElementById('precision');
  const recallEl = document.getElementById('recall');
  const canvas = document.getElementById('chart');

  const buffer = [];

  function setConnected(ok) {
    statusEl.textContent = ok ? 'Connected' : 'Disconnected';
    statusEl.className = ok ? 'connected' : 'disconnected';
  }

  function updateCounters(msg) {
    if (msg.total_anomalies_detected != null) totalAnomaliesEl.textContent = msg.total_anomalies_detected;
    if (msg.total_drift_events != null) totalDriftEl.textContent = msg.total_drift_events;
    precisionEl.textContent = (msg.running_precision ?? 0).toFixed(2);
    recallEl.textContent = (msg.running_recall ?? 0).toFixed(2);
  }

  const driftPlugin = {
    id: 'driftLines',
    afterDraw: function (chart) {
      if (!chart.chartArea) return;
      const driftIndices = buffer.filter(function (p) { return p.drift_event; }).map(function (p) { return p.index; });
      if (driftIndices.length === 0) return;
      const xScale = chart.scales && chart.scales.x;
      if (!xScale) return;
      const ctx = chart.ctx;
      const left = chart.chartArea.left;
      const right = chart.chartArea.right;
      const top = chart.chartArea.top;
      const bottom = chart.chartArea.bottom;
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = '#eab308';
      ctx.lineWidth = 1.5;
      driftIndices.forEach(function (idx) {
        const x = xScale.getPixelForValue(idx);
        if (x >= left && x <= right) {
          ctx.beginPath();
          ctx.moveTo(x, top);
          ctx.lineTo(x, bottom);
          ctx.stroke();
        }
      });
      ctx.restore();
    }
  };

  const chartColors = { temp: '#38bdf8', pressure: '#a78bfa', vibe: '#34d399', danger: '#ef4444' };
  const ctx = canvas.getContext('2d');
  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        { label: 'Temperature', data: [], borderColor: chartColors.temp, backgroundColor: 'transparent', fill: false, tension: 0.15, pointRadius: 0, borderWidth: 2 },
        { label: 'Pressure', data: [], borderColor: chartColors.pressure, backgroundColor: 'transparent', fill: false, tension: 0.15, pointRadius: 0, borderWidth: 2 },
        { label: 'Vibration', data: [], borderColor: chartColors.vibe, backgroundColor: 'transparent', fill: false, tension: 0.15, pointRadius: 0, borderWidth: 2 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      scales: {
        x: {
          display: true,
          title: { display: true, text: 'Observation index', color: '#a1a1aa', font: { family: "'DM Sans', system-ui", size: 12 } },
          grid: { color: 'rgba(255,255,255,0.06)' },
          ticks: { color: '#71717a', maxTicksLimit: 12 }
        },
        y: {
          display: true,
          grid: { color: 'rgba(255,255,255,0.06)' },
          ticks: { color: '#71717a' }
        }
      },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#a1a1aa', font: { family: "'DM Sans', system-ui", size: 12 }, usePointStyle: true, padding: 16 }
        }
      }
    },
    plugins: [driftPlugin]
  });

  function pushPoint(msg) {
    buffer.push({
      index: msg.observation_index,
      temperature: msg.temperature,
      pressure: msg.pressure,
      vibration: msg.vibration,
      alert: msg.alert,
      drift_event: msg.drift_event
    });
    if (buffer.length > MAX_POINTS) buffer.shift();
  }

  function redrawChart() {
    const n = buffer.length;
    if (n === 0) return;
    chart.data.labels = buffer.map(function (p) { return p.index; });
    chart.data.datasets[0].data = buffer.map(function (p) { return p.temperature; });
    chart.data.datasets[1].data = buffer.map(function (p) { return p.pressure; });
    chart.data.datasets[2].data = buffer.map(function (p) { return p.vibration; });
    chart.data.datasets[0].pointRadius = buffer.map(function (p) { return p.alert ? 6 : 0; });
    chart.data.datasets[0].pointBackgroundColor = buffer.map(function (p) { return p.alert ? chartColors.danger : 'transparent'; });
    chart.data.datasets[1].pointRadius = buffer.map(function (p) { return p.alert ? 6 : 0; });
    chart.data.datasets[1].pointBackgroundColor = buffer.map(function (p) { return p.alert ? chartColors.danger : 'transparent'; });
    chart.data.datasets[2].pointRadius = buffer.map(function (p) { return p.alert ? 6 : 0; });
    chart.data.datasets[2].pointBackgroundColor = buffer.map(function (p) { return p.alert ? chartColors.danger : 'transparent'; });
    chart.update('none');
  }

  function connect() {
    const ws = new WebSocket(WS_URL);
    ws.onopen = function () { setConnected(true); };
    ws.onclose = function () {
      setConnected(false);
      setTimeout(connect, 2000);
    };
    ws.onerror = function () { setConnected(false); };
    ws.onmessage = function (ev) {
      try {
        const msg = JSON.parse(ev.data);
        updateCounters(msg);
        pushPoint(msg);
        redrawChart();
      } catch (e) { /* ignore */ }
    };
  }

  (function initWhatSection() {
    var section = document.getElementById('what-section');
    var toggle = document.getElementById('what-toggle');
    if (!section || !toggle) return;
    toggle.addEventListener('click', function () {
      section.classList.toggle('open');
    });
  })();

  connect();
})();
