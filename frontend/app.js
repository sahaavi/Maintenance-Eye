/**
 * Maintenance-Eye — PWA Client Application
 * Real-time audio/video streaming to Gemini Live API via ADK bidi-streaming.
 *
 * Features:
 *   - Mic capture → PCM 16kHz → base64 → WebSocket
 *   - Camera frames → JPEG → base64 → WebSocket (2 fps)
 *   - Agent audio playback (PCM 24kHz)
 *   - Human-in-the-loop confirmation cards
 *   - Input/output transcript display
 */

// ==================== STATE ====================

const state = {
    ws: null,
    sessionId: null,
    userId: `tech-${crypto.randomUUID().slice(0, 8)}`,
    mediaStream: null,
    audioContext: null,
    scriptProcessor: null,
    playbackCtx: null,
    playbackQueue: [],
    isPlayingAudio: false,
    isMicActive: true,
    isConnected: false,
    isPanelExpanded: true,
    isStreamingVideo: false,
    videoInterval: null,
    sessionStartTime: null,
    timerInterval: null,
};

// Audio config
const SEND_SAMPLE_RATE = 16000;
const RECEIVE_SAMPLE_RATE = 24000;
const CAPTURE_BUFFER_SIZE = 4096;
const VIDEO_FPS = 2;
const VIDEO_QUALITY = 0.65;
const VIDEO_MAX_WIDTH = 640;

// ==================== DOM ELEMENTS ====================

const el = {
    splashScreen: () => document.getElementById('splash-screen'),
    inspectionScreen: () => document.getElementById('inspection-screen'),
    cameraFeed: () => document.getElementById('camera-feed'),
    agentMessages: () => document.getElementById('agent-messages'),
    agentStatus: () => document.getElementById('agent-status'),
    sessionAsset: () => document.getElementById('session-asset'),
    sessionTimer: () => document.getElementById('session-timer'),
    connectionStatus: () => document.getElementById('connection-status'),
    btnMic: () => document.getElementById('btn-mic'),
    agentPanel: () => document.getElementById('agent-panel'),
    findingsContainer: () => document.getElementById('findings-container'),
    confirmationContainer: () => document.getElementById('confirmation-container'),
    recordingIndicator: () => document.getElementById('recording-indicator'),
};

// ==================== CAMERA ====================

async function initCamera() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                facingMode: 'environment',
                width: { ideal: 1280 },
                height: { ideal: 720 },
            },
            audio: {
                sampleRate: SEND_SAMPLE_RATE,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true,
            },
        });

        state.mediaStream = stream;
        el.cameraFeed().srcObject = stream;
        console.log('[Camera] Ready');
        return true;
    } catch (err) {
        console.error('[Camera] Init failed:', err);
        addAgentMessage('Camera and mic access required. Please allow permissions and reload.');
        return false;
    }
}

function stopCamera() {
    if (state.mediaStream) {
        state.mediaStream.getTracks().forEach(t => t.stop());
        state.mediaStream = null;
    }
}

// ==================== AUDIO CAPTURE (Mic → PCM 16kHz → WS) ====================

function startAudioCapture() {
    if (!state.mediaStream) return;

    const audioTrack = state.mediaStream.getAudioTracks()[0];
    if (!audioTrack) {
        console.warn('[Audio] No audio track available');
        return;
    }

    state.audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: SEND_SAMPLE_RATE,
    });

    const source = state.audioContext.createMediaStreamSource(state.mediaStream);

    // ScriptProcessorNode for raw PCM access
    state.scriptProcessor = state.audioContext.createScriptProcessor(
        CAPTURE_BUFFER_SIZE, 1, 1
    );

    state.scriptProcessor.onaudioprocess = (e) => {
        if (!state.isMicActive || !state.isConnected) return;

        const inputData = e.inputBuffer.getChannelData(0);
        // Convert Float32 → Int16 PCM
        const pcm16 = float32ToInt16(inputData);
        // Base64 encode and send
        const b64 = arrayBufferToBase64(pcm16.buffer);
        wsSend('audio', b64);
    };

    source.connect(state.scriptProcessor);
    state.scriptProcessor.connect(state.audioContext.destination);
    console.log('[Audio] Capture started @ ' + SEND_SAMPLE_RATE + 'Hz');
}

function stopAudioCapture() {
    if (state.scriptProcessor) {
        state.scriptProcessor.disconnect();
        state.scriptProcessor = null;
    }
    if (state.audioContext) {
        state.audioContext.close();
        state.audioContext = null;
    }
}

function float32ToInt16(float32Array) {
    const int16 = new Int16Array(float32Array.length);
    for (let i = 0; i < float32Array.length; i++) {
        const s = Math.max(-1, Math.min(1, float32Array[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }
    return int16;
}

// ==================== AUDIO PLAYBACK (PCM 24kHz → Speaker) ====================

function initPlayback() {
    state.playbackCtx = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: RECEIVE_SAMPLE_RATE,
    });
}

function queueAudioPlayback(base64Pcm) {
    const raw = base64ToArrayBuffer(base64Pcm);
    const int16 = new Int16Array(raw);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 0x7FFF;
    }
    state.playbackQueue.push(float32);
    if (!state.isPlayingAudio) {
        playNextChunk();
    }
}

function playNextChunk() {
    if (state.playbackQueue.length === 0) {
        state.isPlayingAudio = false;
        return;
    }
    state.isPlayingAudio = true;
    const samples = state.playbackQueue.shift();

    const buffer = state.playbackCtx.createBuffer(1, samples.length, RECEIVE_SAMPLE_RATE);
    buffer.getChannelData(0).set(samples);

    const source = state.playbackCtx.createBufferSource();
    source.buffer = buffer;
    source.connect(state.playbackCtx.destination);
    source.onended = playNextChunk;
    source.start();
}

function clearPlaybackQueue() {
    state.playbackQueue = [];
    state.isPlayingAudio = false;
}

// ==================== VIDEO STREAMING (Camera → JPEG → WS) ====================

function startVideoStreaming() {
    if (state.isStreamingVideo) return;
    state.isStreamingVideo = true;

    const video = el.cameraFeed();
    const canvas = document.createElement('canvas');
    const ctx = canvas.getContext('2d');

    state.videoInterval = setInterval(() => {
        if (!state.isConnected || !video.videoWidth) return;

        // Scale down for bandwidth
        const scale = Math.min(1, VIDEO_MAX_WIDTH / video.videoWidth);
        canvas.width = video.videoWidth * scale;
        canvas.height = video.videoHeight * scale;
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        // JPEG → base64 (strip data URL prefix)
        const dataUrl = canvas.toDataURL('image/jpeg', VIDEO_QUALITY);
        const b64 = dataUrl.split(',')[1];
        wsSend('video', b64);
    }, 1000 / VIDEO_FPS);

    console.log(`[Video] Streaming @ ${VIDEO_FPS} fps`);
}

function stopVideoStreaming() {
    if (state.videoInterval) {
        clearInterval(state.videoInterval);
        state.videoInterval = null;
    }
    state.isStreamingVideo = false;
}

// ==================== WEBSOCKET ====================

function connectWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/inspect/${state.userId}`;

    console.log('[WS] Connecting:', wsUrl);
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        console.log('[WS] Connected');
        state.isConnected = true;
        updateConnectionStatus(true);

        // Start streaming
        startAudioCapture();
        initPlayback();
        startVideoStreaming();
    };

    state.ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleServerMessage(msg);
        } catch (err) {
            console.error('[WS] Parse error:', err);
        }
    };

    state.ws.onclose = () => {
        console.log('[WS] Disconnected');
        state.isConnected = false;
        updateConnectionStatus(false);
        stopAudioCapture();
        stopVideoStreaming();
    };

    state.ws.onerror = (err) => {
        console.error('[WS] Error:', err);
    };
}

function wsSend(type, data) {
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ type, data }));
    }
}

// ==================== MESSAGE HANDLER ====================

function handleServerMessage(msg) {
    switch (msg.type) {
        case 'text':
            addAgentMessage(msg.data);
            setAgentStatus('Speaking...');
            break;

        case 'audio':
            queueAudioPlayback(msg.data);
            setAgentStatus('Speaking...');
            break;

        case 'transcript_input':
            addTranscript('You', msg.data);
            break;

        case 'transcript_output':
            addTranscript('Max', msg.data);
            setAgentStatus('Listening...');
            break;

        case 'status':
            setAgentStatus(msg.data);
            if (msg.session_id) {
                state.sessionId = msg.session_id;
            }
            break;

        case 'interrupted':
            clearPlaybackQueue();
            setAgentStatus('Listening...');
            break;

        case 'confirmation_request':
            renderConfirmationCard(msg.data);
            break;

        case 'confirmation_result':
            handleConfirmationResult(msg.data);
            break;

        case 'finding':
            addFinding(msg.data);
            break;

        case 'work_order':
            addAgentMessage(`✅ Work order ${msg.data.wo_id || ''} created: ${msg.data.description || ''}`);
            break;

        case 'tool_call':
            setAgentStatus('Using tool...');
            break;

        case 'tool_result':
            setAgentStatus('Processing...');
            break;

        case 'session_summary':
            showSessionSummary(msg.data);
            break;

        case 'error':
            addAgentMessage(`⚠️ ${msg.data}`);
            break;

        default:
            console.log('[WS] Unknown:', msg.type, msg);
    }
}

// ==================== CONFIRMATION UI ====================

function renderConfirmationCard(actionData) {
    const container = el.confirmationContainer();
    if (!container) return;

    const prompt = actionData.confirmation_prompt || actionData;
    const actionId = actionData.action_id;
    const actionType = prompt.action_type || 'action';
    const description = prompt.description || prompt.message || '';
    const priority = prompt.priority || '';
    const confidence = prompt.confidence || '';
    const codes = prompt.codes || '';

    const card = document.createElement('div');
    card.className = 'confirmation-card';
    card.id = `confirm-${actionId}`;
    card.innerHTML = `
        <div class="confirm-header">
            <span class="confirm-badge">${formatActionType(actionType)}</span>
            ${priority ? `<span class="confirm-priority ${priority}">${priority}</span>` : ''}
            ${confidence ? `<span class="confirm-confidence">${confidence}</span>` : ''}
        </div>
        <p class="confirm-description">${description}</p>
        ${codes ? `<p class="confirm-codes">${codes}</p>` : ''}
        <div class="confirm-actions">
            <button class="confirm-btn confirm-yes" onclick="confirmAction('${actionId}')">
                ✅ Confirm
            </button>
            <button class="confirm-btn confirm-no" onclick="rejectAction('${actionId}')">
                ❌ Reject
            </button>
            <button class="confirm-btn confirm-edit" onclick="correctAction('${actionId}')">
                ✏️ Correct
            </button>
        </div>
    `;

    container.prepend(card);
    // Auto-expand panel
    const panel = el.agentPanel();
    if (panel.classList.contains('collapsed')) {
        panel.classList.remove('collapsed');
        state.isPanelExpanded = true;
    }

    addAgentMessage(`🔔 Action proposed: ${description}`);
}

function confirmAction(actionId) {
    wsSend('confirm', { action_id: actionId });
    removeConfirmationCard(actionId);
    addAgentMessage('✅ You confirmed the action.');
}

function rejectAction(actionId) {
    const notes = prompt('Reason for rejection (optional):') || '';
    wsSend('reject', { action_id: actionId, notes });
    removeConfirmationCard(actionId);
    addAgentMessage('❌ You rejected the action.');
}

function correctAction(actionId) {
    const input = prompt('What should be changed? (e.g., "priority: P2, problem_code: ME-005")');
    if (!input) return;

    // Parse simple key: value pairs
    const corrections = {};
    input.split(',').forEach(part => {
        const [key, val] = part.split(':').map(s => s.trim());
        if (key && val) corrections[key] = val;
    });

    wsSend('correct', { action_id: actionId, corrections, notes: input });
    removeConfirmationCard(actionId);
    addAgentMessage(`✏️ You corrected the action: ${input}`);
}

function removeConfirmationCard(actionId) {
    const card = document.getElementById(`confirm-${actionId}`);
    if (card) {
        card.style.animation = 'fadeOut 0.3s ease forwards';
        setTimeout(() => card.remove(), 300);
    }
}

function handleConfirmationResult(data) {
    removeConfirmationCard(data.action_id);
}

function formatActionType(type) {
    const labels = {
        'create_work_order': '📋 Create WO',
        'update_work_order': '🔄 Update WO',
        'escalate_priority': '🔺 Escalate',
        'close_work_order': '✔️ Close WO',
        'change_classification': '🏷️ Reclassify',
    };
    return labels[type] || type;
}

// ==================== UI ACTIONS ====================

async function startInspection() {
    const ready = await initCamera();
    if (!ready) return;

    el.splashScreen().classList.remove('active');
    el.inspectionScreen().classList.add('active');

    state.sessionStartTime = Date.now();
    state.timerInterval = setInterval(updateTimer, 1000);

    connectWebSocket();
}

function endInspection() {
    wsSend('end_session', {});

    stopVideoStreaming();
    stopAudioCapture();
    clearPlaybackQueue();
    stopCamera();
    clearInterval(state.timerInterval);

    if (state.ws) {
        state.ws.close();
        state.ws = null;
    }

    el.inspectionScreen().classList.remove('active');
    el.splashScreen().classList.add('active');

    // Reset
    state.sessionId = null;
    state.sessionStartTime = null;
    el.agentMessages().innerHTML = `
        <div class="message agent-message">
            <p>Ready for inspection. What equipment are we looking at today?</p>
        </div>`;
    el.findingsContainer().innerHTML = '';
    el.confirmationContainer().innerHTML = '';
}

function toggleMic() {
    state.isMicActive = !state.isMicActive;
    const btn = el.btnMic();

    if (state.isMicActive) {
        btn.classList.add('active');
        btn.classList.remove('muted');
        setAgentStatus('Listening...');
    } else {
        btn.classList.remove('active');
        btn.classList.add('muted');
        setAgentStatus('Mic muted');
    }

    if (state.mediaStream) {
        state.mediaStream.getAudioTracks().forEach(t => {
            t.enabled = state.isMicActive;
        });
    }
}

function togglePanel() {
    const panel = el.agentPanel();
    panel.classList.toggle('collapsed');
    state.isPanelExpanded = !panel.classList.contains('collapsed');
}

function capturePhoto() {
    const video = el.cameraFeed();
    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);

    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
    const b64 = dataUrl.split(',')[1];
    wsSend('video', b64);

    // Flash effect
    const overlay = document.getElementById('camera-overlay');
    overlay.style.background = 'rgba(255, 255, 255, 0.3)';
    setTimeout(() => { overlay.style.background = 'transparent'; }, 150);

    addUserMessage('📸 Photo captured and sent');
}

function requestReport() {
    wsSend('text', 'Generate an inspection report for this session');
    addUserMessage('📄 Requesting inspection report...');
}

// ==================== UI HELPERS ====================

function addAgentMessage(text) {
    const container = el.agentMessages();
    const div = document.createElement('div');
    div.className = 'message agent-message fade-in';
    div.innerHTML = `<p>${text}</p>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function addUserMessage(text) {
    const container = el.agentMessages();
    const div = document.createElement('div');
    div.className = 'message user-message fade-in';
    div.innerHTML = `<p>${text}</p>`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function addTranscript(speaker, text) {
    if (!text || !text.trim()) return;
    const container = el.agentMessages();
    const cls = speaker === 'You' ? 'transcript-user' : 'transcript-agent';
    const div = document.createElement('div');
    div.className = `message transcript ${cls} fade-in`;
    div.innerHTML = `<span class="transcript-speaker">${speaker}:</span> ${text}`;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

function addFinding(finding) {
    const container = el.findingsContainer();
    const severity = finding.severity || 'P3';
    const confidence = finding.confidence ? `${Math.round(finding.confidence * 100)}%` : '';

    const div = document.createElement('div');
    div.className = `finding-card severity-${severity} fade-in`;
    div.innerHTML = `
        <span class="finding-severity ${severity}">${severity}</span>
        <span class="finding-text">${finding.description}</span>
        ${confidence ? `<span class="finding-confidence">${confidence}</span>` : ''}
    `;
    container.appendChild(div);
}

function setAgentStatus(text) {
    el.agentStatus().textContent = text;
}

function updateTimer() {
    if (!state.sessionStartTime) return;
    const elapsed = Math.floor((Date.now() - state.sessionStartTime) / 1000);
    const mins = String(Math.floor(elapsed / 60)).padStart(2, '0');
    const secs = String(elapsed % 60).padStart(2, '0');
    el.sessionTimer().textContent = `${mins}:${secs}`;
}

function updateConnectionStatus(connected) {
    const statusEl = el.connectionStatus();
    if (connected) {
        statusEl.classList.add('connected');
        statusEl.querySelector('span:last-child').textContent = 'Connected to Max';
    } else {
        statusEl.classList.remove('connected');
        statusEl.querySelector('span:last-child').textContent = 'Disconnected';
    }
}

function showSessionSummary(data) {
    const stats = data.confirmation_stats || {};
    addAgentMessage(
        `📊 Session complete — ${data.findings_count || 0} findings. ` +
        `Actions: ${stats.confirmed || 0} confirmed, ${stats.rejected || 0} rejected, ` +
        `${stats.corrected || 0} corrected.`
    );
}

// ==================== UTILITIES ====================

function arrayBufferToBase64(buffer) {
    const bytes = new Uint8Array(buffer);
    let binary = '';
    for (let i = 0; i < bytes.byteLength; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

function base64ToArrayBuffer(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes.buffer;
}

// ==================== DASHBOARD ====================

let currentTab = 'assets';
let searchTimeout = null;

function showDashboard() {
    document.getElementById('splash-screen').classList.remove('active');
    document.getElementById('dashboard-screen').classList.add('active');
    loadTabData('assets');
}

window.hideDashboard = function hideDashboard() {
    console.log('hideDashboard called');
    document.getElementById('dashboard-screen').classList.remove('active');
    document.getElementById('splash-screen').classList.add('active');
}

// Bind back button via addEventListener (fallback for inline onclick)
document.addEventListener('DOMContentLoaded', () => {
    const backBtn = document.getElementById('btn-back');
    if (backBtn) {
        backBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            hideDashboard();
        });
    }
});

function switchTab(tab) {
    currentTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`[data-tab="${tab}"]`).classList.add('active');
    document.getElementById('search-input').value = '';
    loadTabData(tab);
}

function debounceSearch() {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(() => {
        loadTabData(currentTab, document.getElementById('search-input').value);
    }, 300);
}

async function loadTabData(tab, query = '') {
    const grid = document.getElementById('data-grid');
    const loading = document.getElementById('data-loading');
    const empty = document.getElementById('data-empty');

    grid.innerHTML = '';
    loading.style.display = 'flex';
    empty.style.display = 'none';

    try {
        let url = '';
        switch (tab) {
            case 'assets':
                url = `/api/assets?q=${encodeURIComponent(query)}`;
                break;
            case 'work-orders':
                url = `/api/work-orders?asset_id=${encodeURIComponent(query)}`;
                break;
            case 'knowledge':
                url = `/api/knowledge?q=${encodeURIComponent(query || 'maintenance')}`;
                break;
            case 'eam-codes':
                url = `/api/eam-codes?code_type=${encodeURIComponent(query)}`;
                break;
        }

        const resp = await fetch(url);
        const data = await resp.json();
        loading.style.display = 'none';

        const items = Array.isArray(data) ? data : [];
        if (items.length === 0) {
            empty.style.display = 'flex';
            return;
        }

        items.forEach(item => {
            grid.appendChild(createDataCard(tab, item));
        });
    } catch (err) {
        loading.style.display = 'none';
        grid.innerHTML = `<div class="data-error">Error loading data: ${err.message}</div>`;
    }
}

function createDataCard(tab, item) {
    const card = document.createElement('div');
    card.className = 'data-card fade-in';

    switch (tab) {
        case 'assets':
            card.innerHTML = `
                <div class="card-header">
                    <span class="card-badge">${item.type || item.asset_type || 'Asset'}</span>
                    <span class="card-id">${item.asset_id || ''}</span>
                </div>
                <h3 class="card-title">${item.name || item.asset_id || 'Unknown'}</h3>
                <div class="card-meta">
                    ${item.department ? `<span>📍 ${item.department}</span>` : ''}
                    ${item.location && item.location.station ? `<span>📌 ${item.location.station}</span>` : ''}
                </div>
                ${item.manufacturer ? `<div class="card-detail">Manufacturer: ${item.manufacturer}</div>` : ''}
                ${item.status ? `<div class="card-status status-${item.status}">${item.status.toUpperCase()}</div>` : ''}
            `;
            break;

        case 'work-orders':
            const priorityClass = item.priority || 'P3';
            card.innerHTML = `
                <div class="card-header">
                    <span class="card-badge priority-${priorityClass}">${priorityClass}</span>
                    <span class="card-id">${item.wo_id || ''}</span>
                </div>
                <h3 class="card-title">${item.description || 'Work Order'}</h3>
                <div class="card-meta">
                    ${item.asset_id ? `<span>🔧 ${item.asset_id}</span>` : ''}
                    ${item.status ? `<span>📋 ${item.status}</span>` : ''}
                </div>
                ${item.problem_code ? `<div class="card-detail">Problem: ${item.problem_code}</div>` : ''}
                ${item.created_date ? `<div class="card-detail">Created: ${item.created_date}</div>` : ''}
            `;
            break;

        case 'knowledge':
            card.innerHTML = `
                <div class="card-header">
                    <span class="card-badge">📖 Knowledge</span>
                </div>
                <h3 class="card-title">${item.title || item.topic || 'Article'}</h3>
                <div class="card-meta">
                    ${item.asset_type ? `<span>🔧 ${item.asset_type}</span>` : ''}
                    ${item.department ? `<span>📍 ${item.department}</span>` : ''}
                </div>
                ${item.content ? `<div class="card-detail card-content">${item.content.substring(0, 200)}${item.content.length > 200 ? '...' : ''}</div>` : ''}
            `;
            break;

        case 'eam-codes':
            card.innerHTML = `
                <div class="card-header">
                    <span class="card-badge">${item.code_type || 'Code'}</span>
                    <span class="card-id">${item.code || ''}</span>
                </div>
                <h3 class="card-title">${item.description || item.code || 'EAM Code'}</h3>
                <div class="card-meta">
                    ${item.department ? `<span>📍 ${item.department}</span>` : ''}
                    ${item.asset_type ? `<span>🔧 ${item.asset_type}</span>` : ''}
                </div>
            `;
            break;
    }

    return card;
}

// ==================== SERVICE WORKER ====================

if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then(function (registrations) {
        for (let registration of registrations) {
            registration.unregister();
            console.log('[SW] Unregistered to clear aggressive cache');
        }
    });
    // Clear all caches manually
    caches.keys().then(keys => {
        keys.forEach(key => caches.delete(key));
    });
}
