document.addEventListener('DOMContentLoaded', () => {

    const btnLive    = document.getElementById('btn-source-live');
    const btnLocal   = document.getElementById('btn-source-local');
    const sourceBadge = document.getElementById('source-badge');

    const modal       = document.getElementById('source-modal');
    const modalLive   = document.getElementById('modal-pick-live');
    const modalLocal  = document.getElementById('modal-pick-local');

    const sidePhase     = document.getElementById('side-phase');
    const sidePeds      = document.getElementById('side-peds');
    const sideEmergency = document.getElementById('side-emergency');
    const sideCounts = {
        norte: document.getElementById('side-norte'),
        sur:   document.getElementById('side-sur'),
        este:  document.getElementById('side-este'),
        oeste: document.getElementById('side-oeste'),
    };

    let hasLocal = false;

    fetch('/source_status')
        .then(res => res.json())
        .then(data => {
            hasLocal = !!data.has_local;
            if (!hasLocal) {
                btnLocal.disabled = true;
                modalLocal.disabled = true;
                btnLocal.title = 'Video local no encontrado en static/';
            }
            if (data.mode === 'idle') {
                modal.hidden = false;
                applySourceUI('idle');
            } else {
                applySourceUI(data.mode);
                startStatsPolling();
            }
        })
        .catch(() => {});

    function applySourceUI(mode) {
        if (mode === 'idle') {
            sourceBadge.textContent = '● INACTIVO';
            sourceBadge.classList.remove('live-badge--local');
            btnLive.classList.remove('source-btn--active');
            btnLocal.classList.remove('source-btn--active');
            return;
        }
        const isLive = mode === 'youtube';
        btnLive.classList.toggle('source-btn--active', isLive);
        btnLocal.classList.toggle('source-btn--active', !isLive);
        sourceBadge.textContent  = isLive ? '● EN VIVO' : '● VIDEO LOCAL';
        sourceBadge.classList.toggle('live-badge--local', !isLive);
    }

    function switchSource(mode) {
        fetch('/set_source', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode })
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) return console.error('[Source]', data.error);
            applySourceUI(data.mode);
            modal.hidden = true;
            if (data.mode !== 'idle') startStatsPolling();
        })
        .catch(err => console.error('[Source]', err));
    }

    btnLive.addEventListener('click',  () => switchSource('youtube'));
    btnLocal.addEventListener('click', () => switchSource('local'));
    modalLive.addEventListener('click',  () => switchSource('youtube'));
    modalLocal.addEventListener('click', () => switchSource('local'));

    const inputs = {
        norte: document.getElementById('input-north'),
        sur:   document.getElementById('input-south'),
        este:  document.getElementById('input-east'),
        oeste: document.getElementById('input-west')
    };

    const valueDisplays = {
        norte: document.getElementById('val-north'),
        sur:   document.getElementById('val-south'),
        este:  document.getElementById('val-east'),
        oeste: document.getElementById('val-west')
    };

    const carsVisuals = {
        norte: document.getElementById('cars-north'),
        sur:   document.getElementById('cars-south'),
        este:  document.getElementById('cars-east'),
        oeste: document.getElementById('cars-west')
    };

    const lights = {
        0: document.getElementById('light-north'),
        1: document.getElementById('light-south'),
        2: document.getElementById('light-east'),
        3: document.getElementById('light-west')
    };

    const priorityResult  = document.getElementById('priority-result');
    const liveToggle      = document.getElementById('live-mode-toggle');
    const cvButton        = document.getElementById('activate-cv');
    const pedestrianCount = document.getElementById('pedestrian-count');
    const emergencyStatus = document.getElementById('emergency-status');

    let liveInterval  = null;
    let statsInterval = null;
    let cvModeActive  = false;

    Object.keys(inputs).forEach(key => {
        inputs[key].addEventListener('input', e => {
            valueDisplays[key].textContent = e.target.value;
            updateVisualDensity(key, e.target.value);
            if (!cvModeActive) updatePrediction();
        });
    });

    liveToggle.addEventListener('change', () => {
        cvModeActive = liveToggle.checked;
        stopLiveLoop();
        Object.values(inputs).forEach(i => i.disabled = cvModeActive);

        if (cvButton) {
            cvButton.textContent = cvModeActive ? 'Desactivar Control' : 'Activar Control';
            cvButton.classList.toggle('active', cvModeActive);
        }

        if (cvModeActive) startLiveLoop();
        updatePrediction();
    });

    if (cvButton) {
        cvButton.addEventListener('click', () => {
            liveToggle.checked = !liveToggle.checked;
            liveToggle.dispatchEvent(new Event('change'));
        });
    }

    function startLiveLoop() {
        stopLiveLoop();
        liveInterval = setInterval(updatePrediction, 2000);
    }

    function stopLiveLoop() {
        if (liveInterval) clearInterval(liveInterval);
        liveInterval = null;
    }

    function startStatsPolling() {
        if (statsInterval) return;
        statsInterval = setInterval(fetchStats, 1500);
        fetchStats();
    }

    function fetchStats() {
        fetch('/stats')
            .then(res => res.json())
            .then(s => {
                sideCounts.norte.textContent = s.norte;
                sideCounts.sur.textContent   = s.sur;
                sideCounts.este.textContent  = s.este;
                sideCounts.oeste.textContent = s.oeste;
                sidePeds.textContent  = s.pedestrians;
                sidePhase.textContent = s.priority || '--';

                const em = !!s.emergency;
                sideEmergency.textContent = em ? 'SÍ' : 'NO';
                sideEmergency.style.color = em ? '#b64400' : '#1d1d1f';

                if (!cvModeActive && typeof s.priority_idx === 'number' && s.priority_idx >= 0) {
                    setLights(s.priority_idx);
                }
            })
            .catch(() => {});
    }

    function updateVisualDensity(direction, value) {
        if (carsVisuals[direction]) {
            carsVisuals[direction].style.opacity = 0.05 + (value / 100) * 0.6;
        }
    }

    function updatePrediction() {
        const payload = cvModeActive
            ? { live_mode: true }
            : {
                norte: inputs.norte.value,
                sur:   inputs.sur.value,
                este:  inputs.este.value,
                oeste: inputs.oeste.value
            };

        fetch('/predict', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        })
        .then(res => res.json())
        .then(data => {
            if (data.error) return console.error(data.error);

            if (data.traffic_data) {
                ['norte', 'sur', 'este', 'oeste'].forEach(k => {
                    inputs[k].value = data.traffic_data[k];
                    valueDisplays[k].textContent = data.traffic_data[k];
                    updateVisualDensity(k, data.traffic_data[k]);
                });

                if (pedestrianCount)
                    pedestrianCount.textContent = data.traffic_data.pedestrians ?? 0;

                if (emergencyStatus) {
                    const isEmergency = !!data.traffic_data.emergency;
                    emergencyStatus.textContent = isEmergency ? 'SÍ' : 'NO';
                    emergencyStatus.style.color = isEmergency ? '#b64400' : '#1d1d1f';
                }
            }

            setLights(data.prediction);

            if (data.traffic_data?.emergency) {
                priorityResult.textContent = 'EMERGENCIA';
                priorityResult.style.color = '#b64400';
            } else if (data.traffic_data?.pedestrians > 5) {
                priorityResult.textContent = 'PEATONES';
                priorityResult.style.color = '#707070';
            }
        })
        .catch(err => console.error('Prediction error:', err));
    }

    function setLights(winnerIndex) {
        document.querySelectorAll('.bulb.green').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.bulb.red').forEach(b => b.classList.add('active'));
        document.querySelectorAll('.road').forEach(r => r.classList.remove('active-road'));

        const names = ['NORTE', 'SUR', 'ESTE', 'OESTE'];
        const roads = ['.road.north', '.road.south', '.road.east', '.road.west'];

        lights[winnerIndex]?.querySelector('.bulb.green').classList.add('active');
        lights[winnerIndex]?.querySelector('.bulb.red').classList.remove('active');
        document.querySelector(roads[winnerIndex])?.classList.add('active-road');

        priorityResult.textContent = names[winnerIndex];
        priorityResult.style.color = '#0071e3';
    }

    updatePrediction();
});
