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
    currentPlaybackSource: null,
    isPlayingAudio: false,
    isMicActive: true,
    isConnected: false,
    isPanelExpanded: true,
    isStreamingVideo: false,
    videoInterval: null,
    sessionStartTime: null,
    timerInterval: null,
    hudInterval: null,
    // Transcript buffering — accumulate fragments into single bubbles
    currentTranscriptEl: null,       // DOM element for current transcript bubble
    currentTranscriptSpeaker: null,  // 'You' or 'Max'
    transcriptFlushTimer: null,      // Timer to finalize bubble after silence
    // Reconnect state
    reconnectAttempts: 0,
    reconnectTimer: null,
    intentionalClose: false,
};

// Audio config
const SEND_SAMPLE_RATE = 16000;
const RECEIVE_SAMPLE_RATE = 24000;
const CAPTURE_BUFFER_SIZE = 4096;
const VIDEO_FPS = 2;
const VIDEO_QUALITY = 0.65;
const VIDEO_MAX_WIDTH = 640;
const MAX_MESSAGE_ITEMS = 120;
const MAX_RECONNECT_ATTEMPTS = 5;
const RECONNECT_BASE_DELAY = 1000; // 1s, 2s, 4s, max 8s

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
    hudOverlay: () => document.getElementById('hud-overlay'),
};

// ==================== HUD CONTROL ====================

function setHudActive(active) {
    const hud = el.hudOverlay();
    if (!hud) return;
    if (active) {
        hud.classList.add('active');
    } else {
        hud.classList.remove('active');
    }
}

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

async function initPlayback() {
    if (!state.playbackCtx) {
        state.playbackCtx = new (window.AudioContext || window.webkitAudioContext)({
            sampleRate: RECEIVE_SAMPLE_RATE,
        });
    }
    if (state.playbackCtx.state === 'suspended') {
        try {
            await state.playbackCtx.resume();
        } catch (err) {
            console.warn('[Audio] Playback resume failed:', err);
        }
    }
}

function queueAudioPlayback(base64Pcm) {
    if (!state.playbackCtx) return;
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
    if (!state.playbackCtx) {
        state.isPlayingAudio = false;
        return;
    }
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
    state.currentPlaybackSource = source;
    source.onended = () => {
        if (state.currentPlaybackSource === source) {
            state.currentPlaybackSource = null;
        }
        playNextChunk();
    };
    source.start();
}

function clearPlaybackQueue() {
    if (state.currentPlaybackSource) {
        try {
            state.currentPlaybackSource.onended = null;
            state.currentPlaybackSource.stop();
        } catch (err) {
            console.debug('[Audio] Active playback source stop skipped:', err);
        }
        state.currentPlaybackSource = null;
    }
    state.playbackQueue = [];
    state.isPlayingAudio = false;
}

async function stopPlayback() {
    clearPlaybackQueue();
    if (state.playbackCtx) {
        await state.playbackCtx.close();
        state.playbackCtx = null;
    }
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
    const token = getAuthToken();
    const tokenParam = token ? `?token=${encodeURIComponent(token)}` : '';
    const wsUrl = `${protocol}//${window.location.host}/ws/inspect/${state.userId}${tokenParam}`;

    console.log('[WS] Connecting:', wsUrl);
    state.intentionalClose = false;
    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        console.log('[WS] Connected');
        state.isConnected = true;
        state.reconnectAttempts = 0;
        updateConnectionStatus('connected');

        // Start streaming
        startAudioCapture();
        startVideoStreaming();

        if (state.reconnectAttempts === 0 && state.sessionStartTime) {
            addAgentMessage('Session reconnected. Previous context may be lost.');
        }
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
        stopAudioCapture();
        stopVideoStreaming();

        if (!state.intentionalClose) {
            attemptReconnect();
        } else {
            updateConnectionStatus('disconnected');
        }
    };

    state.ws.onerror = (err) => {
        console.error('[WS] Error:', err);
    };
}

function attemptReconnect() {
    if (state.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        updateConnectionStatus('failed');
        return;
    }
    state.reconnectAttempts++;
    const delay = Math.min(RECONNECT_BASE_DELAY * Math.pow(2, state.reconnectAttempts - 1), 8000);
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${state.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
    updateConnectionStatus('reconnecting');
    state.reconnectTimer = setTimeout(() => connectWebSocket(), delay);
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

        case 'turn_complete':
            _finalizeTranscriptBubble();
            setAgentStatus('Listening...');
            break;

        case 'interrupted':
            _finalizeTranscriptBubble();
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
            _finalizeTranscriptBubble();
            setAgentStatus('Using tool...');
            setHudActive(true);
            break;

        case 'tool_result':
            setAgentStatus('Processing...');
            setHudActive(false);
            break;

        case 'media_card':
            renderMediaCard(msg.data);
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

function _buildConfirmationCard(actionData, { idPrefix, onConfirm, onReject, onCorrect }) {
    const prompt = actionData.confirmation_prompt || actionData;
    const actionId = actionData.action_id;
    const actionType = prompt.action_type || 'action';
    const description = prompt.description || prompt.message || '';
    const priority = prompt.priority || '';
    const confidence = prompt.confidence || '';
    const codes = prompt.codes || '';
    const priorityClass = /^P[1-5]$/.test(priority) ? priority : '';

    const card = document.createElement('div');
    card.className = 'confirmation-card';
    card.id = `${idPrefix}${actionId}`;

    const header = document.createElement('div');
    header.className = 'confirm-header';

    const badge = document.createElement('span');
    badge.className = 'confirm-badge';
    badge.textContent = formatActionType(actionType);
    header.appendChild(badge);

    if (priority) {
        const priorityEl = document.createElement('span');
        priorityEl.className = `confirm-priority${priorityClass ? ` ${priorityClass}` : ''}`;
        priorityEl.textContent = priority;
        header.appendChild(priorityEl);
    }

    if (confidence) {
        const confidenceEl = document.createElement('span');
        confidenceEl.className = 'confirm-confidence';
        confidenceEl.textContent = confidence;
        header.appendChild(confidenceEl);
    }

    const descEl = document.createElement('p');
    descEl.className = 'confirm-description';
    descEl.textContent = description;

    const actions = document.createElement('div');
    actions.className = 'confirm-actions';

    const confirmBtn = document.createElement('button');
    confirmBtn.className = 'confirm-btn confirm-yes';
    confirmBtn.textContent = 'Confirm';
    confirmBtn.addEventListener('click', () => onConfirm(actionId));

    const rejectBtn = document.createElement('button');
    rejectBtn.className = 'confirm-btn confirm-no';
    rejectBtn.textContent = 'Reject';
    rejectBtn.addEventListener('click', () => onReject(actionId));

    const correctBtn = document.createElement('button');
    correctBtn.className = 'confirm-btn confirm-edit';
    correctBtn.textContent = 'Correct';
    correctBtn.addEventListener('click', () => onCorrect(actionId));

    actions.appendChild(confirmBtn);
    actions.appendChild(rejectBtn);
    actions.appendChild(correctBtn);

    card.appendChild(header);
    card.appendChild(descEl);
    if (codes) {
        const codesEl = document.createElement('p');
        codesEl.className = 'confirm-codes';
        codesEl.textContent = codes;
        card.appendChild(codesEl);
    }
    card.appendChild(actions);
    return { card, description };
}

function renderConfirmationCard(actionData) {
    const container = el.confirmationContainer();
    if (!container) return;

    const { card, description } = _buildConfirmationCard(actionData, {
        idPrefix: 'confirm-',
        onConfirm: confirmAction,
        onReject: rejectAction,
        onCorrect: correctAction,
    });

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
    // Show feedback on splash screen while initializing
    const splashStatus = document.getElementById('splash-status');
    if (splashStatus) {
        splashStatus.textContent = 'Initializing camera and microphone...';
        splashStatus.style.display = 'block';
    }

    await initPlayback();

    const ready = await initCamera();
    if (!ready) {
        // Show error on splash screen (user can still see it)
        if (splashStatus) {
            splashStatus.textContent = 'Camera/mic access failed. Please allow permissions and try again.';
            splashStatus.className = 'splash-status error';
        }
        return;
    }

    if (splashStatus) splashStatus.style.display = 'none';

    el.splashScreen().classList.remove('active');
    el.inspectionScreen().classList.add('active');

    state.sessionStartTime = Date.now();
    state.timerInterval = setInterval(updateTimer, 1000);
    state.hudInterval = setInterval(updateHudData, 1000);

    connectWebSocket();
}

function trimMessageHistory() {
    const container = el.agentMessages();
    if (!container) return;
    while (container.childElementCount > MAX_MESSAGE_ITEMS) {
        container.removeChild(container.firstElementChild);
    }
}

function waitMs(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

async function sendEndSessionAndFlush(timeoutMs = 500) {
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
    wsSend('end_session', {});

    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
        if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return;
        if (state.ws.bufferedAmount === 0) {
            await waitMs(100);
            return;
        }
        await waitMs(50);
    }
}

async function endInspection() {
    await sendEndSessionAndFlush();

    stopVideoStreaming();
    stopAudioCapture();
    clearPlaybackQueue();
    void stopPlayback();
    stopCamera();
    clearInterval(state.timerInterval);
    if (state.hudInterval) {
        clearInterval(state.hudInterval);
        state.hudInterval = null;
    }

    state.intentionalClose = true;
    clearTimeout(state.reconnectTimer);
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
    overlay.style.background = 'rgba(255, 255, 255, 0.8)';
    setTimeout(() => { overlay.style.background = 'transparent'; }, 150);

    addUserMessage('📸 Photo captured and sent');
}

function requestReport() {
    wsSend('text', 'Generate an inspection report for this session');
    addUserMessage('📄 Requesting inspection report...');
}

// ==================== MEDIA CARDS ====================

function renderMediaCard(data) {
    const container = el.agentMessages();
    if (!container) return;

    const card = document.createElement('div');
    card.className = 'media-card fade-in';

    if (data.image_url) {
        const img = document.createElement('img');
        img.className = 'media-card-img';
        img.src = data.image_url;
        img.alt = data.title || 'Media';
        card.appendChild(img);
    }

    const content = document.createElement('div');
    content.className = 'media-card-content';

    if (data.title) {
        const title = document.createElement('h4');
        title.className = 'media-card-title';
        title.textContent = data.title;
        content.appendChild(title);
    }

    if (data.description) {
        const desc = document.createElement('p');
        desc.className = 'media-card-desc';
        desc.textContent = data.description;
        content.appendChild(desc);
    }

    if (data.details && data.details.length) {
        const detailsGrid = document.createElement('div');
        detailsGrid.className = 'media-card-details';
        data.details.forEach(item => {
            if (!item.value) return;
            const detail = document.createElement('div');
            detail.className = 'media-card-detail';
            const label = document.createElement('span');
            label.className = 'detail-label';
            label.textContent = item.label;
            const value = document.createElement('span');
            value.className = 'detail-value';
            value.textContent = item.value;
            detail.appendChild(label);
            detail.appendChild(value);
            detailsGrid.appendChild(detail);
        });
        content.appendChild(detailsGrid);
    }

    if (data.action_link) {
        const link = document.createElement('a');
        link.className = 'media-card-link';
        link.href = data.action_link;
        link.target = '_blank';
        link.textContent = data.action_label || 'View Details';
        content.appendChild(link);
    }

    card.appendChild(content);
    container.appendChild(card);
    trimMessageHistory();
    container.scrollTop = container.scrollHeight;
}

// ==================== UI HELPERS ====================

function addAgentMessage(text) {
    const container = el.agentMessages();
    const div = document.createElement('div');
    div.className = 'message agent-message fade-in';
    const content = document.createElement('div');
    content.className = 'markdown-content';
    content.innerHTML = renderMarkdown(text);
    div.appendChild(content);
    container.appendChild(div);
    trimMessageHistory();
    container.scrollTop = container.scrollHeight;
}

function addUserMessage(text) {
    const container = el.agentMessages();
    const div = document.createElement('div');
    div.className = 'message user-message fade-in';
    const p = document.createElement('p');
    p.textContent = text;
    div.appendChild(p);
    container.appendChild(div);
    trimMessageHistory();
    container.scrollTop = container.scrollHeight;
}

function addTranscript(speaker, text) {
    if (!text || !text.trim()) return;
    const container = el.agentMessages();
    const cls = speaker === 'You' ? 'transcript-user' : 'transcript-agent';

    // If speaker changed or no active bubble, start a new one
    if (state.currentTranscriptSpeaker !== speaker || !state.currentTranscriptEl
        || !container.contains(state.currentTranscriptEl)) {
        _finalizeTranscriptBubble();
        const div = document.createElement('div');
        div.className = `message transcript ${cls} fade-in`;
        const speakerEl = document.createElement('span');
        speakerEl.className = 'transcript-speaker';
        speakerEl.textContent = `${speaker}:`;
        div.appendChild(speakerEl);
        const textNode = document.createElement('span');
        textNode.className = 'transcript-text';
        textNode.dataset.rawText = text;
        if (speaker === 'You') {
            textNode.textContent = ` ${text}`;
        } else {
            textNode.innerHTML = renderMarkdown(text);
        }
        div.appendChild(textNode);
        container.appendChild(div);
        state.currentTranscriptEl = div;
        state.currentTranscriptSpeaker = speaker;
    } else {
        // Append to existing bubble
        const textSpan = state.currentTranscriptEl.querySelector('.transcript-text');
        if (textSpan) {
            const current = textSpan.dataset.rawText || '';
            const next = current ? `${current} ${text}` : text;
            textSpan.dataset.rawText = next;
            if (speaker === 'You') {
                textSpan.textContent = ` ${next}`;
            } else {
                textSpan.innerHTML = renderMarkdown(next);
            }
        }
    }

    // Reset flush timer — finalize bubble after 3s of silence (turn boundary)
    if (state.transcriptFlushTimer) clearTimeout(state.transcriptFlushTimer);
    state.transcriptFlushTimer = setTimeout(() => _finalizeTranscriptBubble(), 3000);

    trimMessageHistory();
    container.scrollTop = container.scrollHeight;
}

function _finalizeTranscriptBubble() {
    if (state.transcriptFlushTimer) {
        clearTimeout(state.transcriptFlushTimer);
        state.transcriptFlushTimer = null;
    }
    state.currentTranscriptEl = null;
    state.currentTranscriptSpeaker = null;
}

function addFinding(finding) {
    const container = el.findingsContainer();
    const severity = finding.severity || 'P3';
    const confidence = finding.confidence ? `${Math.round(finding.confidence * 100)}%` : '';
    const severityClass = /^P[1-5]$/.test(severity) ? severity : 'P3';

    const div = document.createElement('div');
    div.className = `finding-card severity-${severityClass} fade-in`;

    const severityEl = document.createElement('span');
    severityEl.className = `finding-severity ${severityClass}`;
    severityEl.textContent = severity;

    const textEl = document.createElement('span');
    textEl.className = 'finding-text';
    textEl.textContent = finding.description || '';

    div.appendChild(severityEl);
    div.appendChild(textEl);

    if (confidence) {
        const confidenceEl = document.createElement('span');
        confidenceEl.className = 'finding-confidence';
        confidenceEl.textContent = confidence;
        div.appendChild(confidenceEl);
    }
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

function updateHudData() {
    const latEl = document.getElementById('hud-lat');
    const lngEl = document.getElementById('hud-lng');
    const fpsEl = document.getElementById('hud-fps');
    const bitEl = document.getElementById('hud-bit');

    if (latEl && Math.random() > 0.5) {
        const baseLat = 49.2827;
        const jitter = (Math.random() - 0.5) * 0.0005;
        latEl.textContent = `LAT: ${(baseLat + jitter).toFixed(4)}`;
    }
    if (lngEl && Math.random() > 0.5) {
        const baseLng = -123.1207;
        const jitter = (Math.random() - 0.5) * 0.0005;
        lngEl.textContent = `LNG: ${(baseLng + jitter).toFixed(4)}`;
    }
    if (fpsEl) {
        fpsEl.textContent = `FPS: ${Math.floor(28 + Math.random() * 4)}`;
    }
    if (bitEl) {
        bitEl.textContent = `BIT: ${(2.0 + Math.random() * 0.6).toFixed(1)}Mb`;
    }
}

function updateConnectionStatus(status) {
    const statusEl = el.connectionStatus();
    // Support legacy boolean calls
    if (status === true) status = 'connected';
    if (status === false) status = 'disconnected';

    statusEl.classList.remove('connected', 'reconnecting');
    const textEl = statusEl.querySelector('span:last-child');

    switch (status) {
        case 'connected':
            statusEl.classList.add('connected');
            textEl.textContent = 'Connected to Max';
            break;
        case 'reconnecting':
            statusEl.classList.add('reconnecting');
            textEl.textContent = `Reconnecting... (${state.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`;
            break;
        case 'failed':
            textEl.textContent = 'Connection lost. Tap to retry.';
            statusEl.onclick = () => {
                state.reconnectAttempts = 0;
                connectWebSocket();
                statusEl.onclick = null;
            };
            break;
        default:
            textEl.textContent = 'Ready to connect';
            break;
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

// ==================== CHAT MODE ====================

const chatState = {
    ws: null,
    isConnected: false,
    isVoiceMode: false,
    attachedImageB64: null,
    recognition: null,  // Web Speech API
    reconnectAttempts: 0,
    reconnectTimer: null,
    intentionalClose: false,
};

function toggleChatPanel() {
    const panel = document.getElementById('chat-panel');
    const btn = document.getElementById('btn-chat-toggle');
    if (panel.style.display === 'none') {
        panel.style.display = 'flex';
        btn.style.display = 'none';
        connectChatWebSocket();
    } else {
        closeChatPanel();
    }
}

function closeChatPanel() {
    const panel = document.getElementById('chat-panel');
    const btn = document.getElementById('btn-chat-toggle');
    panel.style.display = 'none';
    btn.style.display = '';
    disconnectChat();
    stopChatVoice();
    closeChatImageSourcePicker();
}

function connectChatWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const token = getAuthToken();
    const params = new URLSearchParams();
    if (token) params.set('token', token);
    const wsUrl = `${protocol}//${window.location.host}/ws/chat/${state.userId}?${params}`;

    console.log('[Chat WS] Connecting:', wsUrl);
    chatState.intentionalClose = false;
    chatState.ws = new WebSocket(wsUrl);

    chatState.ws.onopen = () => {
        console.log('[Chat WS] Connected');
        chatState.isConnected = true;
        chatState.reconnectAttempts = 0;
        setChatStatus('Online');
        updateConnectionStatus('connected');
    };

    chatState.ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleChatServerMessage(msg);
        } catch (err) {
            console.error('[Chat WS] Parse error:', err);
        }
    };

    chatState.ws.onclose = () => {
        console.log('[Chat WS] Disconnected');
        chatState.isConnected = false;

        if (!chatState.intentionalClose) {
            setChatStatus('Reconnecting...');
            attemptChatReconnect();
        } else {
            setChatStatus('Offline');
            updateConnectionStatus('disconnected');
        }
    };

    chatState.ws.onerror = (err) => {
        console.error('[Chat WS] Error:', err);
    };
}

function attemptChatReconnect() {
    if (chatState.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        setChatStatus('Offline');
        return;
    }
    chatState.reconnectAttempts++;
    const delay = Math.min(RECONNECT_BASE_DELAY * Math.pow(2, chatState.reconnectAttempts - 1), 8000);
    console.log(`[Chat WS] Reconnecting in ${delay}ms (attempt ${chatState.reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
    chatState.reconnectTimer = setTimeout(() => connectChatWebSocket(), delay);
}

function chatWsSend(type, data) {
    if (chatState.ws && chatState.ws.readyState === WebSocket.OPEN) {
        chatState.ws.send(JSON.stringify({ type, data }));
    }
}

function disconnectChat() {
    chatState.intentionalClose = true;
    clearTimeout(chatState.reconnectTimer);
    if (chatState.ws) {
        chatWsSend('end_session', {});
        chatState.ws.close();
        chatState.ws = null;
    }
    chatState.isConnected = false;
    updateConnectionStatus('disconnected');
}

function handleChatServerMessage(msg) {
    switch (msg.type) {
        case 'text':
            addChatMessage('agent', msg.data);
            setChatStatus('Online');
            break;

        case 'confirmation_request':
            renderChatConfirmationCard(msg.data);
            break;

        case 'confirmation_result':
            removeChatConfirmationCard(msg.data.action_id);
            break;

        case 'work_order':
            addChatMessage('agent', `Work order ${msg.data.wo_id || ''} created: ${msg.data.description || ''}`);
            break;

        case 'tool_call':
            setChatStatus('Searching...');
            break;

        case 'tool_result':
            setChatStatus('Processing...');
            break;

        case 'media_card':
            renderChatMediaCard(msg.data);
            break;

        case 'status':
            setChatStatus(msg.data);
            if (msg.session_id) chatState.sessionId = msg.session_id;
            break;

        case 'error':
            addChatMessage('agent', msg.data);
            setChatStatus('Online');
            break;

        default:
            console.log('[Chat WS] Unknown:', msg.type, msg);
    }
}

// --- Chat Send ---

function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const text = (input.value || '').trim();
    if (!text && !chatState.attachedImageB64) return;
    closeChatImageSourcePicker();

    if (chatState.attachedImageB64) {
        chatWsSend('image', chatState.attachedImageB64);
        // Show thumbnail in chat
        const container = document.getElementById('chat-messages');
        const div = document.createElement('div');
        div.className = 'message user-message fade-in';
        const img = document.createElement('img');
        img.src = document.getElementById('chat-preview-img').src;
        img.className = 'chat-msg-img';
        img.alt = 'Attached image';
        div.appendChild(img);
        container.appendChild(div);
        container.scrollTop = container.scrollHeight;
        removeAttachedImage();
    }

    if (text) {
        chatWsSend('text', text);
        addChatMessage('user', text);
        input.value = '';
    }
}

// --- Image Attachment ---

function attachImage() {
    const picker = document.getElementById('chat-image-source-picker');
    if (!picker) return;
    picker.style.display = picker.style.display === 'none' ? 'flex' : 'none';
}

function closeChatImageSourcePicker() {
    const picker = document.getElementById('chat-image-source-picker');
    if (picker) picker.style.display = 'none';
}

function selectChatImageFromCamera() {
    closeChatImageSourcePicker();
    document.getElementById('chat-file-input-camera').click();
}

function selectChatImageFromGallery() {
    closeChatImageSourcePicker();
    document.getElementById('chat-file-input-gallery').click();
}

function handleImageSelected(event) {
    const file = event.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (e) => {
        const dataUrl = e.target.result;
        const previewContainer = document.getElementById('chat-image-preview');
        const previewImg = document.getElementById('chat-preview-img');
        previewImg.src = dataUrl;
        previewContainer.style.display = 'flex';
        chatState.attachedImageB64 = dataUrl.split(',')[1];
    };
    reader.readAsDataURL(file);
    event.target.value = '';
}

function removeAttachedImage() {
    chatState.attachedImageB64 = null;
    document.getElementById('chat-image-preview').style.display = 'none';
}

// --- Voice Mode (Web Speech API — browser-native speech-to-text) ---

function toggleChatVoice() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        addChatMessage('agent', 'Voice input is not supported in this browser. Try Chrome or Edge.');
        return;
    }

    chatState.isVoiceMode = !chatState.isVoiceMode;
    const btn = document.getElementById('btn-chat-voice');

    if (chatState.isVoiceMode) {
        btn.classList.add('active');
        chatState.recognition = new SpeechRecognition();
        chatState.recognition.continuous = false;
        chatState.recognition.interimResults = true;
        chatState.recognition.lang = 'en-US';

        const input = document.getElementById('chat-input');

        chatState.recognition.onresult = (event) => {
            let transcript = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                transcript += event.results[i][0].transcript;
            }
            input.value = transcript;
            // Auto-send on final result
            if (event.results[event.results.length - 1].isFinal) {
                sendChatMessage();
                // Restart listening
                if (chatState.isVoiceMode) {
                    setTimeout(() => {
                        try { chatState.recognition.start(); } catch (e) { /* already started */ }
                    }, 300);
                }
            }
        };

        chatState.recognition.onerror = (event) => {
            console.warn('[Voice] Recognition error:', event.error);
            if (event.error === 'not-allowed') {
                addChatMessage('agent', 'Microphone access denied. Please allow mic permissions.');
                stopChatVoice();
            }
        };

        chatState.recognition.onend = () => {
            // Restart if still in voice mode (recognition auto-stops after silence)
            if (chatState.isVoiceMode) {
                try { chatState.recognition.start(); } catch (e) { /* ignore */ }
            }
        };

        try {
            chatState.recognition.start();
            setChatStatus('Listening...');
            input.placeholder = 'Listening... speak now';
        } catch (err) {
            console.error('[Voice] Start failed:', err);
            stopChatVoice();
        }
    } else {
        stopChatVoice();
    }
}

function stopChatVoice() {
    chatState.isVoiceMode = false;
    const btn = document.getElementById('btn-chat-voice');
    if (btn) btn.classList.remove('active');
    if (chatState.recognition) {
        try { chatState.recognition.stop(); } catch (e) { /* ignore */ }
        chatState.recognition = null;
    }
    const input = document.getElementById('chat-input');
    if (input) input.placeholder = 'Ask Max anything...';
    setChatStatus(chatState.isConnected ? 'Online' : 'Offline');
}

// --- Chat UI Helpers ---

function addChatMessage(role, text) {
    const container = document.getElementById('chat-messages');
    if (!container) return;
    const div = document.createElement('div');

    if (role === 'user') {
        div.className = 'message user-message fade-in';
    } else if (role === 'agent') {
        div.className = 'message agent-message fade-in';
    } else if (role === 'user-transcript') {
        div.className = 'message transcript transcript-user fade-in';
    } else if (role === 'agent-transcript') {
        div.className = 'message transcript transcript-agent fade-in';
    }

    const content = document.createElement('div');
    content.className = 'markdown-content';
    if (role === 'agent' || role === 'agent-transcript') {
        content.innerHTML = renderMarkdown(text);
    } else {
        content.textContent = text;
    }
    div.appendChild(content);
    container.appendChild(div);

    while (container.childElementCount > MAX_MESSAGE_ITEMS) {
        container.removeChild(container.firstElementChild);
    }
    container.scrollTop = container.scrollHeight;
}

function setChatStatus(text) {
    const el = document.getElementById('chat-agent-status');
    if (el) el.textContent = text;
}

// --- Chat Confirmation Cards ---

function renderChatConfirmationCard(actionData) {
    const container = document.getElementById('chat-confirmation-container');
    if (!container) return;

    const { card, description } = _buildConfirmationCard(actionData, {
        idPrefix: 'chat-confirm-',
        onConfirm: chatConfirmAction,
        onReject: chatRejectAction,
        onCorrect: chatCorrectAction,
    });

    container.prepend(card);
    addChatMessage('agent', `Action proposed: ${description}`);
}

function chatConfirmAction(actionId) {
    chatWsSend('confirm', { action_id: actionId });
    removeChatConfirmationCard(actionId);
    addChatMessage('agent', 'You confirmed the action.');
}

function chatRejectAction(actionId) {
    const notes = prompt('Reason for rejection (optional):') || '';
    chatWsSend('reject', { action_id: actionId, notes });
    removeChatConfirmationCard(actionId);
    addChatMessage('agent', 'You rejected the action.');
}

function chatCorrectAction(actionId) {
    const input = prompt('What should be changed? (e.g., "priority: P2, problem_code: ME-005")');
    if (!input) return;
    const corrections = {};
    input.split(',').forEach(part => {
        const [key, val] = part.split(':').map(s => s.trim());
        if (key && val) corrections[key] = val;
    });
    chatWsSend('correct', { action_id: actionId, corrections, notes: input });
    removeChatConfirmationCard(actionId);
    addChatMessage('agent', `You corrected the action: ${input}`);
}

function removeChatConfirmationCard(actionId) {
    const card = document.getElementById(`chat-confirm-${actionId}`);
    if (card) {
        card.style.animation = 'fadeOut 0.3s ease forwards';
        setTimeout(() => card.remove(), 300);
    }
}

// --- Chat Media Cards ---

function renderChatMediaCard(data) {
    const container = document.getElementById('chat-messages');
    if (!container) return;

    const card = document.createElement('div');
    card.className = 'media-card fade-in';

    if (data.image_url) {
        const img = document.createElement('img');
        img.className = 'media-card-img';
        img.src = data.image_url;
        img.alt = data.title || 'Media';
        card.appendChild(img);
    }

    const content = document.createElement('div');
    content.className = 'media-card-content';

    if (data.title) {
        const title = document.createElement('h4');
        title.className = 'media-card-title';
        title.textContent = data.title;
        content.appendChild(title);
    }

    if (data.description) {
        const desc = document.createElement('p');
        desc.className = 'media-card-desc';
        desc.textContent = data.description;
        content.appendChild(desc);
    }

    if (data.details && data.details.length) {
        const detailsGrid = document.createElement('div');
        detailsGrid.className = 'media-card-details';
        data.details.forEach(item => {
            if (!item.value) return;
            const detail = document.createElement('div');
            detail.className = 'media-card-detail';
            const label = document.createElement('span');
            label.className = 'detail-label';
            label.textContent = item.label;
            const value = document.createElement('span');
            value.className = 'detail-value';
            value.textContent = item.value;
            detail.appendChild(label);
            detail.appendChild(value);
            detailsGrid.appendChild(detail);
        });
        content.appendChild(detailsGrid);
    }

    if (data.action_link) {
        const link = document.createElement('a');
        link.className = 'media-card-link';
        link.href = data.action_link;
        link.target = '_blank';
        link.textContent = data.action_label || 'View Details';
        content.appendChild(link);
    }

    card.appendChild(content);
    container.appendChild(card);

    while (container.childElementCount > MAX_MESSAGE_ITEMS) {
        container.removeChild(container.firstElementChild);
    }
    container.scrollTop = container.scrollHeight;
}

// ==================== DASHBOARD ====================

let currentPage = 'work-orders';
let _pageSearchTimeouts = {};
let _filtersLoaded = false;

function showDashboard() {
    document.getElementById('splash-screen').classList.remove('active');
    document.getElementById('dashboard-screen').classList.add('active');
    if (!_filtersLoaded) {
        loadFilterOptions();
        _filtersLoaded = true;
    }
    navigateTo('work-orders');
}

window.hideDashboard = function hideDashboard() {
    document.getElementById('dashboard-screen').classList.remove('active');
    document.getElementById('splash-screen').classList.add('active');
}

document.addEventListener('DOMContentLoaded', () => {
    const backBtn = document.getElementById('btn-back');
    if (backBtn) {
        backBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            window.hideDashboard();
        });
    }
});

// --- Navigation ---

function navigateTo(page) {
    currentPage = page;

    // Update sidebar active
    document.querySelectorAll('.nav-item').forEach(b => {
        b.classList.toggle('active', b.dataset.page === page);
    });
    // Update bottom nav active
    document.querySelectorAll('.bnav-item').forEach(b => {
        b.classList.toggle('active', b.dataset.page === page);
    });
    // Show/hide pages
    document.querySelectorAll('.dash-page').forEach(p => {
        p.classList.toggle('active', p.id === `page-${page}`);
    });

    // Trigger data load
    switch (page) {
        case 'work-orders': loadWorkOrders(); break;
        case 'assets': loadAssets(); break;
        case 'locations': loadLocations(); break;
        case 'knowledge': loadKnowledge(); break;
        case 'eam-codes': loadEAMCodes(); break;
    }
}

// --- Utilities ---

function escapeHtml(str) {
    const d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

function renderInlineMarkdown(text) {
    return text
        .replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*\n]+)\*/g, (match, inner) => {
            // Treat `*text*` as italic only when stars touch content.
            if (inner.startsWith(' ') || inner.endsWith(' ')) {
                return match;
            }
            return `<em>${inner}</em>`;
        });
}

function normalizeMarkdownBlocks(text) {
    return text
        // Split inline bullets into real lines so list parsing works.
        .replace(/([:;.!?)])\s+([*-]\s+(?=\S))/g, '$1\n$2')
        // Same for numbered list markers emitted inline.
        .replace(/([:;.!?)])\s+(\d+\.\s+(?=\S))/g, '$1\n$2');
}

function renderMarkdown(text) {
    if (!text) return '';

    const safe = normalizeMarkdownBlocks(
        escapeHtml(String(text)).replace(/\r\n/g, '\n')
    );
    const lines = safe.split('\n');
    const html = [];
    let inUnorderedList = false;
    let inOrderedList = false;

    for (const line of lines) {
        const trimmed = line.trim();
        const unorderedListMatch = trimmed.match(/^[-*]\s+(.+)$/);
        const orderedListMatch = trimmed.match(/^\d+\.\s+(.+)$/);

        if (unorderedListMatch) {
            if (inOrderedList) {
                html.push('</ol>');
                inOrderedList = false;
            }
            if (!inUnorderedList) {
                html.push('<ul>');
                inUnorderedList = true;
            }
            html.push(`<li>${renderInlineMarkdown(unorderedListMatch[1])}</li>`);
            continue;
        }

        if (orderedListMatch) {
            if (inUnorderedList) {
                html.push('</ul>');
                inUnorderedList = false;
            }
            if (!inOrderedList) {
                html.push('<ol>');
                inOrderedList = true;
            }
            html.push(`<li>${renderInlineMarkdown(orderedListMatch[1])}</li>`);
            continue;
        }

        if (inUnorderedList) {
            html.push('</ul>');
            inUnorderedList = false;
        }
        if (inOrderedList) {
            html.push('</ol>');
            inOrderedList = false;
        }

        if (!trimmed) continue;
        html.push(`<p>${renderInlineMarkdown(trimmed)}</p>`);
    }

    if (inUnorderedList) {
        html.push('</ul>');
    }
    if (inOrderedList) {
        html.push('</ol>');
    }

    return html.join('');
}

function formatLabel(str) {
    if (!str) return '';
    return String(str).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function formatDate(str) {
    if (!str) return '';
    try {
        const d = new Date(str);
        return d.toLocaleDateString('en-CA'); // YYYY-MM-DD
    } catch { return str; }
}

function populateDropdown(selectId, options, labelFn) {
    const el = document.getElementById(selectId);
    if (!el) return;
    const current = el.value;
    const firstOpt = el.options[0]?.text || 'All';
    el.innerHTML = `<option value="">${escapeHtml(firstOpt)}</option>`;
    options.forEach(opt => {
        const val = typeof opt === 'string' ? opt : opt.value;
        const label = labelFn ? labelFn(opt) : (typeof opt === 'string' ? formatLabel(opt) : opt.label);
        el.innerHTML += `<option value="${escapeHtml(val)}">${escapeHtml(label)}</option>`;
    });
    if (current) el.value = current;
}

function showPageState(pageId, state) {
    const page = document.getElementById(pageId);
    if (!page) return;
    const loading = page.querySelector('.dash-loading');
    const empty = page.querySelector('.dash-empty');
    const error = page.querySelector('.dash-error');
    const table = page.querySelector('.data-table');
    const grid = page.querySelector('.data-grid');
    const list = page.querySelector('.locations-list');
    if (loading) loading.style.display = state === 'loading' ? 'flex' : 'none';
    if (empty) empty.style.display = state === 'empty' ? 'flex' : 'none';
    if (error) error.style.display = state === 'error' ? 'flex' : 'none';
    if (table) table.style.display = state === 'data' ? 'table' : 'none';
    if (grid && state !== 'data') grid.innerHTML = '';
    if (list) list.style.display = state === 'data' ? 'block' : 'none';
}

async function apiFetch(url) {
    const token = getAuthToken();
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const resp = await fetch(url, { headers });
    return resp.json();
}

// --- Filter Options Loader ---

async function loadFilterOptions() {
    const DEPARTMENTS = [
        { value: 'rolling_stock', label: 'Rolling Stock' },
        { value: 'guideway', label: 'Guideway' },
        { value: 'power', label: 'Power Systems' },
        { value: 'signal_telecom', label: 'Signal & Telecom' },
        { value: 'facilities', label: 'Facilities' },
        { value: 'elevating_devices', label: 'Elevating Devices' },
    ];
    const PRIORITIES = ['P1', 'P2', 'P3', 'P4', 'P5'];
    const STATUSES = ['open', 'in_progress', 'on_hold', 'completed', 'cancelled'];
    const CODE_TYPES = ['Problem Code', 'Fault Code', 'Action Code'];

    // WO filters
    populateDropdown('wo-filter-status', STATUSES, s => formatLabel(s));
    populateDropdown('wo-filter-priority', PRIORITIES, p => p);
    populateDropdown('wo-filter-department', DEPARTMENTS);
    // Asset filters
    populateDropdown('asset-filter-department', DEPARTMENTS);
    // KB filter
    populateDropdown('kb-filter-department', DEPARTMENTS);
    // EAM filters
    populateDropdown('eam-filter-type', CODE_TYPES, t => formatLabel(t));
    populateDropdown('eam-filter-department', DEPARTMENTS);

    // Load locations for WO filter + asset station filter
    try {
        const locations = await apiFetch('/api/locations');
        if (Array.isArray(locations)) {
            populateDropdown('wo-filter-location', locations.map(l => ({ value: l.station, label: l.station })));
            populateDropdown('asset-filter-station', locations.map(l => ({ value: l.station, label: l.station })));
        }
    } catch (e) {
        console.warn('Failed to load locations for filters:', e);
    }

    // Load asset types
    try {
        const assets = await apiFetch('/api/assets');
        if (Array.isArray(assets)) {
            const types = [...new Set(assets.map(a => a.type).filter(Boolean))].sort();
            populateDropdown('asset-filter-type', types, t => t);
        }
    } catch (e) {
        console.warn('Failed to load asset types:', e);
    }
}

// --- Debounced Page Search ---

function debouncePageSearch(page) {
    clearTimeout(_pageSearchTimeouts[page]);
    _pageSearchTimeouts[page] = setTimeout(() => {
        switch (page) {
            case 'work-orders': loadWorkOrders(); break;
            case 'assets': loadAssets(); break;
            case 'knowledge': loadKnowledge(); break;
            case 'eam-codes': loadEAMCodes(); break;
        }
    }, 300);
}

// --- Generic page data loader ---

async function loadPageData(pageId, endpoint, getFilters, renderFn, postFilter) {
    showPageState(pageId, 'loading');
    try {
        const params = new URLSearchParams();
        const filters = getFilters();
        for (const [key, val] of Object.entries(filters)) {
            if (val) params.set(key, val);
        }
        const data = await apiFetch(`${endpoint}?${params}`);
        let items = Array.isArray(data) ? data : [];
        if (postFilter) items = postFilter(items);
        if (items.length === 0) { showPageState(pageId, 'empty'); return; }
        renderFn(items);
        showPageState(pageId, 'data');
    } catch (err) {
        showPageState(pageId, 'error');
        console.error(`Error loading ${pageId}:`, err);
    }
}

// --- Work Orders ---

function loadWorkOrders() {
    loadPageData('page-work-orders', '/api/work-orders', () => ({
        q: (document.getElementById('wo-search')?.value || '').trim(),
        status: document.getElementById('wo-filter-status')?.value || '',
        priority: document.getElementById('wo-filter-priority')?.value || '',
        department: document.getElementById('wo-filter-department')?.value || '',
        location: document.getElementById('wo-filter-location')?.value || '',
    }), renderWorkOrderTable);
}

function renderWorkOrderTable(orders) {
    const tbody = document.getElementById('wo-tbody');
    tbody.innerHTML = '';
    orders.forEach(wo => {
        const pr = String(wo.priority || 'P3').toUpperCase();
        const st = String(wo.status || 'open').toLowerCase();
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="cell-mono">${escapeHtml(wo.wo_id || '')}</td>
            <td><span class="badge priority-${escapeHtml(pr)}">${escapeHtml(pr)}</span></td>
            <td class="cell-truncate">${escapeHtml(wo.description || '')}</td>
            <td class="cell-mono">${escapeHtml(wo.asset_id || '')}</td>
            <td><span class="badge status-${escapeHtml(st)}">${escapeHtml(formatLabel(st))}</span></td>
            <td class="cell-mono">${escapeHtml(wo.problem_code || '')}</td>
            <td>${escapeHtml(formatDate(wo.created_date || wo.created_at || ''))}</td>
        `;
        tbody.appendChild(tr);
    });
}

// --- Assets ---

function loadAssets() {
    loadPageData('page-assets', '/api/assets', () => ({
        q: (document.getElementById('asset-search')?.value || '').trim(),
        department: document.getElementById('asset-filter-department')?.value || '',
        asset_type: document.getElementById('asset-filter-type')?.value || '',
        station: document.getElementById('asset-filter-station')?.value || '',
    }), renderAssetsGrid);
}

function renderAssetsGrid(assets) {
    const grid = document.getElementById('asset-grid');
    grid.innerHTML = '';
    assets.forEach(item => {
        const card = document.createElement('div');
        card.className = 'data-card fade-in';
        const statusClass = String(item.status || '').toLowerCase().replace(/[^a-z0-9_-]/g, '');
        card.innerHTML = `
            <div class="card-header">
                <span class="card-badge">${escapeHtml(item.type || 'Asset')}</span>
                <span class="card-id">${escapeHtml(item.asset_id || '')}</span>
            </div>
            <h3 class="card-title">${escapeHtml(item.name || item.asset_id || 'Unknown')}</h3>
            <div class="card-meta">
                ${item.department ? `<span>${escapeHtml(item.department)}</span>` : ''}
                ${item.location?.station ? `<span>${escapeHtml(item.location.station)}</span>` : ''}
            </div>
            ${item.manufacturer ? `<div class="card-detail">Mfg: ${escapeHtml(item.manufacturer)}</div>` : ''}
            ${item.status ? `<div class="card-status status-${statusClass}">${escapeHtml(String(item.status).toUpperCase())}</div>` : ''}
        `;
        grid.appendChild(card);
    });
}

// --- Locations ---

function loadLocations() {
    loadPageData('page-locations', '/api/locations', () => ({}), renderLocationsPage);
}

function renderLocationsPage(locations) {
    const container = document.getElementById('locations-list');
    container.innerHTML = '';

    // Group by zone
    const zones = {};
    locations.forEach(loc => {
        const zone = loc.zone || 'Other';
        if (!zones[zone]) zones[zone] = [];
        zones[zone].push(loc);
    });

    Object.keys(zones).sort().forEach(zone => {
        const group = document.createElement('div');
        group.className = 'zone-group';
        group.innerHTML = `<div class="zone-label">${escapeHtml(zone)}</div>`;
        zones[zone].forEach(loc => {
            const row = document.createElement('div');
            row.className = 'location-row';
            row.innerHTML = `
                <div>
                    <span class="location-name">${escapeHtml(loc.station)}</span>
                    <span class="location-code">${escapeHtml(loc.station_code || '')}</span>
                </div>
                <span class="location-count">${loc.asset_count} asset${loc.asset_count !== 1 ? 's' : ''}</span>
            `;
            group.appendChild(row);
        });
        container.appendChild(group);
    });
}

// --- Knowledge Base ---

function loadKnowledge() {
    loadPageData('page-knowledge', '/api/knowledge', () => ({
        q: (document.getElementById('kb-search')?.value || '').trim() || 'maintenance',
        department: document.getElementById('kb-filter-department')?.value || '',
    }), renderKnowledgeGrid);
}

function renderKnowledgeGrid(entries) {
    const grid = document.getElementById('kb-grid');
    grid.innerHTML = '';
    entries.forEach(item => {
        const card = document.createElement('div');
        card.className = 'data-card fade-in';
        const preview = String(item.content || '').substring(0, 200);
        card.innerHTML = `
            <div class="card-header">
                <span class="card-badge">Knowledge</span>
            </div>
            <h3 class="card-title">${escapeHtml(item.title || 'Article')}</h3>
            <div class="card-meta">
                ${item.department ? `<span>${escapeHtml(item.department)}</span>` : ''}
                ${(item.tags || []).slice(0, 3).map(t => `<span>${escapeHtml(t)}</span>`).join('')}
            </div>
            ${preview ? `<div class="card-detail card-content">${escapeHtml(preview)}${item.content?.length > 200 ? '...' : ''}</div>` : ''}
        `;
        grid.appendChild(card);
    });
}

// --- EAM Codes ---

function loadEAMCodes() {
    const q = (document.getElementById('eam-search')?.value || '').trim();
    loadPageData('page-eam-codes', '/api/eam-codes', () => ({
        code_type: document.getElementById('eam-filter-type')?.value || '',
        department: document.getElementById('eam-filter-department')?.value || '',
    }), renderEAMCodesTable, q ? (items) => {
        const ql = q.toLowerCase();
        return items.filter(c =>
            (c.code || '').toLowerCase().includes(ql) ||
            (c.description || '').toLowerCase().includes(ql) ||
            (c.code_type || '').toLowerCase().includes(ql)
        );
    } : null);
}

function renderEAMCodesTable(codes) {
    const tbody = document.getElementById('eam-tbody');
    tbody.innerHTML = '';
    codes.forEach(c => {
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td class="cell-mono">${escapeHtml(c.code || '')}</td>
            <td>${escapeHtml(formatLabel(c.code_type || ''))}</td>
            <td class="cell-truncate">${escapeHtml(c.description || '')}</td>
            <td>${escapeHtml(c.department || '')}</td>
            <td>${escapeHtml((c.asset_types || []).join(', '))}</td>
        `;
        tbody.appendChild(tr);
    });
}

function getAuthToken() {
    return window.localStorage.getItem('firebase_id_token') || '';
}

// ==================== SERVICE WORKER ====================

if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(() => console.log('[SW] Registered'))
            .catch((err) => console.error('[SW] Registration failed:', err));
    });
}
