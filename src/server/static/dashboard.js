(function () {
  const WS_URL = (location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + location.host + '/ws';
  const MAX_POINTS = 200;

  const statusEl = document.getElementById('status');
  const totalAnomaliesEl = document.getElementById('total-anomalies');
  const totalDriftEl = document.getElementById('total-drift');
  const precisionEl = document.getElementById('precision');
  const recallEl = document.getElementById('recall');
  const canvas = document.getElementById('chart');

  let totalAnomalies = 0;
  let totalDrift = 0;
  const buffer = [];

  function setConnected(ok) {
    statusEl.textContent = ok ? 'Connected' : 'Disconnected';
    statusEl.className = ok ? 'connected' : 'disconnected';
  }

  function updateCounters(msg) {
    totalAnomalies += msg.alert ? 1 : 0;
    if (msg.drift_event) totalDrift += 1;
    totalAnomaliesEl.textContent = totalAnomalies;
    totalDriftEl.textContent = totalDrift;
    precisionEl.textContent = (msg.running_precision ?? 0).toFixed(2);
    recallEl.textContent = (msg.running_recall ?? 0).toFixed(2);
  }

  const driftPlugin = {
    id: 'driftLines',
    afterDraw: function (chart) {
      const driftIndices = buffer.filter(function (p) { return p.drift_event; }).map(function (p) { return p.index; });
      if (driftIndices.length === 0) return;
      const meta = chart.getDatasetMeta(0);
      if (!meta || !meta.data.length) return;
      const xScale = chart.scales.x;
      const yScale = chart.scales.y;
      const ctx = chart.ctx;
      ctx.save();
      ctx.setLineDash([4, 4]);
      ctx.strokeStyle = '#fbbf24';
      ctx.lineWidth = 1.5;
      driftIndices.forEach(function (idx) {
        const x = xScale.getPixelForValue(idx);
        if (x >= chart.chartArea.left && x <= chart.chartArea.right) {
          ctx.beginPath();
          ctx.moveTo(x, chart.chartArea.top);
          ctx.lineTo(x, chart.chartArea.bottom);
          ctx.stroke();
        }
      });
      ctx.restore();
    }
  };

  const ctx = canvas.getContext('2d');
  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: [],
      datasets: [
        { label: 'Temperature', data: [], borderColor: '#60a5fa', backgroundColor: 'transparent', fill: false, tension: 0.1, pointRadius: 0 },
        { label: 'Pressure', data: [], borderColor: '#a78bfa', backgroundColor: 'transparent', fill: false, tension: 0.1, pointRadius: 0 },
        { label: 'Vibration', data: [], borderColor: '#34d399', backgroundColor: 'transparent', fill: false, tension: 0.1, pointRadius: 0 }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { intersect: false, mode: 'index' },
      scales: {
        x: { display: true, title: { display: true, text: 'Observation index' } },
        y: { display: true }
      },
      plugins: {
        legend: { position: 'top' }
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
    chart.data.datasets[0].pointBackgroundColor = buffer.map(function (p) { return p.alert ? '#ef4444' : 'transparent'; });
    chart.data.datasets[1].pointRadius = buffer.map(function (p) { return p.alert ? 6 : 0; });
    chart.data.datasets[1].pointBackgroundColor = buffer.map(function (p) { return p.alert ? '#ef4444' : 'transparent'; });
    chart.data.datasets[2].pointRadius = buffer.map(function (p) { return p.alert ? 6 : 0; });
    chart.data.datasets[2].pointBackgroundColor = buffer.map(function (p) { return p.alert ? '#ef4444' : 'transparent'; });
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

  connect();
})();
