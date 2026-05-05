(function () {
    const DEPARTMENTS = [
        { value: 'rolling_stock', label: 'Rolling Stock' },
        { value: 'guideway', label: 'Guideway' },
        { value: 'power', label: 'Power Systems' },
        { value: 'signal_telecom', label: 'Signal & Telecom' },
        { value: 'facilities', label: 'Facilities' },
        { value: 'elevating_devices', label: 'Elevating Devices' },
    ];

    const store = {
        assets: [],
        workOrders: [],
        locations: [],
        selectedAsset: null,
        selectedAssetId: '',
        draftAsset: null,
        assetPickerIntent: 'select',
        dashboardRequestToken: 0,
        activeDialog: null,
        lastFocusedElement: null,
        pendingConfirmation: null,
    };

    const $ = (id) => document.getElementById(id);

    function formatLabel(value) {
        return String(value || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
    }

    function escapeHtml(value) {
        const node = document.createElement('div');
        node.textContent = String(value || '');
        return node.innerHTML;
    }

    async function apiFetch(url) {
        if (typeof window.apiFetch === 'function') {
            return window.apiFetch(url);
        }
        const token = typeof window.getAuthToken === 'function'
            ? window.getAuthToken()
            : localStorage.getItem('firebase_id_token') || '';
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const response = await fetch(url, { headers });
        return response.json();
    }

    function setHidden(id, hidden) {
        const node = $(id);
        if (node) node.hidden = hidden;
    }

    function getFocusable(container) {
        if (!container) return [];
        return Array.from(
            container.querySelectorAll(
                'button, input, select, textarea, a[href], [tabindex]:not([tabindex="-1"])'
            )
        ).filter((node) => !node.disabled && !node.hidden);
    }

    function focusFirst(container) {
        const focusable = getFocusable(container);
        if (focusable[0]) focusable[0].focus();
    }

    function openDialog(dialogId, backdropId) {
        store.lastFocusedElement = document.activeElement;
        setHidden(backdropId, false);
        setHidden(dialogId, false);
        document.body.classList.add('modal-open');
        store.activeDialog = dialogId;
        focusFirst($(dialogId));
    }

    function closeDialog(dialogId, backdropId) {
        setHidden(dialogId, true);
        setHidden(backdropId, true);
        document.body.classList.remove('modal-open');
        store.activeDialog = null;
        if (store.lastFocusedElement && typeof store.lastFocusedElement.focus === 'function') {
            store.lastFocusedElement.focus();
        }
        store.lastFocusedElement = null;
    }

    function openPanel(panelId) {
        store.lastFocusedElement = document.activeElement;
        setHidden(panelId, false);
        store.activeDialog = panelId;
        focusFirst($(panelId));
    }

    function closePanel(panelId) {
        setHidden(panelId, true);
        store.activeDialog = null;
        if (store.lastFocusedElement && typeof store.lastFocusedElement.focus === 'function') {
            store.lastFocusedElement.focus();
        }
        store.lastFocusedElement = null;
    }

    function populateSelect(select, options) {
        if (!select) return;
        const first = select.options[0]?.outerHTML || '<option value="">All</option>';
        select.innerHTML = first;
        options.forEach((option) => {
            const opt = document.createElement('option');
            opt.value = option.value;
            opt.textContent = option.label;
            select.appendChild(opt);
        });
    }

    function populateAssetPickerFilters() {
        populateSelect($('asset-picker-department'), DEPARTMENTS);
        populateSelect(
            $('asset-picker-location'),
            store.locations.map((loc) => ({ value: loc.station, label: loc.station }))
        );
    }

    async function ensureAssetsLoaded() {
        if (store.assets.length === 0 || store.locations.length === 0) {
            const [assets, locations] = await Promise.all([
                apiFetch('/api/assets'),
                apiFetch('/api/locations'),
            ]);
            store.assets = Array.isArray(assets) ? assets : [];
            store.locations = Array.isArray(locations) ? locations : [];
        }
        populateAssetPickerFilters();
    }

    function assetMatchesFilters(asset) {
        const query = ($('asset-picker-search')?.value || '').trim().toLowerCase();
        const department = $('asset-picker-department')?.value || '';
        const location = $('asset-picker-location')?.value || '';
        const text = [
            asset.asset_id,
            asset.name,
            asset.type,
            asset.department,
            asset.location?.station,
        ].filter(Boolean).join(' ').toLowerCase();
        if (query && !text.includes(query)) return false;
        if (department && asset.department !== department) return false;
        if (location && asset.location?.station !== location) return false;
        return true;
    }

    function renderAssetPickerList() {
        const list = $('asset-picker-list');
        if (!list) return;
        const filtered = store.assets.filter(assetMatchesFilters).slice(0, 60);
        if (filtered.length === 0) {
            list.innerHTML = '<div class="asset-option" aria-disabled="true"><strong>No assets found</strong><span>Try another search or filter.</span></div>';
            return;
        }
        list.innerHTML = filtered.map((asset) => {
            const id = asset.asset_id || '';
            const selected = store.draftAsset?.asset_id === id ? ' is-selected' : '';
            const station = asset.location?.station || 'Unknown station';
            return `
                <button type="button" class="asset-option${selected}" data-asset-id="${escapeHtml(id)}" data-testid="asset-option-${escapeHtml(id)}" aria-pressed="${selected ? 'true' : 'false'}">
                    <span>
                        <strong>${escapeHtml(id)} - ${escapeHtml(asset.name || 'Unnamed Asset')}</strong>
                        <span>${escapeHtml(formatLabel(asset.department))} / ${escapeHtml(asset.type || 'Asset')} / ${escapeHtml(station)}</span>
                    </span>
                    <span>${escapeHtml(formatLabel(asset.status || 'unknown'))}</span>
                </button>
            `;
        }).join('');
    }

    async function openAssetPicker(intent = 'select') {
        try {
            await ensureAssetsLoaded();
        } catch (err) {
            console.warn('[CommandCenter] Failed to load assets:', err);
            store.assets = [];
        }
        store.assetPickerIntent = intent;
        store.draftAsset = store.selectedAsset || store.assets[0] || null;
        renderAssetPickerList();
        openDialog('asset-picker', 'asset-picker-backdrop');
    }

    function closeAssetPicker() {
        closeDialog('asset-picker', 'asset-picker-backdrop');
    }

    function chooseAsset(assetId) {
        store.draftAsset = store.assets.find((asset) => asset.asset_id === assetId) || null;
        renderAssetPickerList();
    }

    function updateSelectedAssetSummary() {
        const asset = store.selectedAsset;
        const name = $('selected-asset-name');
        const meta = $('selected-asset-meta');
        if (!asset) {
            if (name) name.textContent = 'No asset selected';
            if (meta) meta.textContent = 'Choose an asset before starting the live inspection.';
            return;
        }
        const station = asset.location?.station || 'Unknown station';
        if (name) name.textContent = `${asset.asset_id} - ${asset.name || 'Unnamed Asset'}`;
        if (meta) meta.textContent = `${formatLabel(asset.department)} / ${asset.type || 'Asset'} / ${station}`;
    }

    function syncSelectedAssetToInspection() {
        const asset = store.selectedAsset;
        if (!asset) return;
        store.selectedAssetId = asset.asset_id || '';
        if (window.state) {
            window.state.selectedAsset = asset;
            window.state.selectedAssetId = asset.asset_id || '';
        }
        const sessionAsset = $('session-asset');
        if (sessionAsset) {
            sessionAsset.textContent = `${asset.asset_id} / ${asset.name || 'Asset'}`;
        }
    }

    function selectAsset(asset) {
        if (!asset) return;
        store.selectedAsset = asset;
        store.selectedAssetId = asset.asset_id || '';
        updateSelectedAssetSummary();
        syncSelectedAssetToInspection();
    }

    function confirmAssetSelection() {
        if (!store.draftAsset) return;
        selectAsset(store.draftAsset);
        closeAssetPicker();
        if (store.assetPickerIntent === 'start-inspection'
            && typeof window.beginInspectionSession === 'function') {
            window.beginInspectionSession();
        }
        store.assetPickerIntent = 'select';
    }

    function ensureAssetSelectedBeforeInspection() {
        if (store.selectedAsset) {
            syncSelectedAssetToInspection();
            return true;
        }
        void openAssetPicker('start-inspection');
        return false;
    }

    function sendInspectionStartContext() {
        const assetId = store.selectedAsset?.asset_id || window.state?.selectedAssetId || '';
        if (!assetId || !window.state?.ws || window.state.ws.readyState !== WebSocket.OPEN) return;
        window.state.ws.send(JSON.stringify({ type: 'start_session', asset_id: assetId }));
    }

    async function loadDashboardSummary() {
        const token = ++store.dashboardRequestToken;
        const summary = $('dashboard-summary');
        if (summary) summary.hidden = true;
        try {
            const [workOrders, assets, locations] = await Promise.all([
                apiFetch('/api/work-orders'),
                apiFetch('/api/assets'),
                apiFetch('/api/locations'),
            ]);
            if (token !== store.dashboardRequestToken) return;
            store.workOrders = Array.isArray(workOrders) ? workOrders : [];
            store.assets = Array.isArray(assets) ? assets : [];
            store.locations = Array.isArray(locations) ? locations : [];
            const open = store.workOrders.filter((wo) => {
                const status = String(wo.status || '').toLowerCase();
                return ['open', 'in_progress', 'on_hold'].includes(status);
            }).length;
            const high = store.workOrders.filter((wo) => {
                return String(wo.priority || '').toUpperCase() === 'P1';
            }).length;
            const setText = (id, value) => {
                const node = $(id);
                if (node) node.textContent = String(value);
            };
            setText('summary-open-work-orders', open);
            setText('summary-high-priority', high);
            setText('summary-assets', store.assets.length);
            setText('summary-locations', store.locations.length);
            setText('ops-asset-count', `${store.assets.length} loaded`);
            setText('ops-eam-status', 'Synced');
            if (summary) summary.hidden = false;
        } catch (err) {
            console.warn('[CommandCenter] Summary load failed:', err);
            const status = $('ops-eam-status');
            if (status) status.textContent = 'Ready';
            const count = $('ops-asset-count');
            if (count) count.textContent = 'Ready';
            if (summary) summary.hidden = false;
        }
    }

    function openConfirmationEditor(context) {
        store.pendingConfirmation = context;
        const prompt = context.actionData?.confirmation_prompt || context.actionData || {};
        store.pendingConfirmation.originalValues = {
            priority: prompt.priority || '',
            problem_code: '',
            fault_code: '',
            action_code: '',
        };
        const title = $('confirmation-editor-title');
        if (title) {
            title.textContent = context.mode === 'reject'
                ? 'Reject Proposed Action'
                : 'Correct Proposed Action';
        }
        const setValue = (id, value) => {
            const node = $(id);
            if (node) node.value = value || '';
        };
        setValue('editor-priority', prompt.priority || '');
        setValue('editor-problem-code', '');
        setValue('editor-fault-code', '');
        setValue('editor-action-code', '');
        setValue('editor-notes', '');
        const error = $('confirmation-editor-error');
        if (error) {
            error.textContent = '';
            error.hidden = true;
        }
        const isReject = context.mode === 'reject';
        ['editor-priority', 'editor-problem-code', 'editor-fault-code', 'editor-action-code'].forEach((id) => {
            const input = $(id);
            if (input) input.disabled = isReject;
        });
        const save = $('save-confirmation-correction');
        if (save) save.textContent = isReject ? 'Reject Action' : 'Send Correction';
        openPanel('confirmation-editor');
    }

    function closeConfirmationEditor() {
        closePanel('confirmation-editor');
        store.pendingConfirmation = null;
    }

    function submitConfirmationEditor() {
        const context = store.pendingConfirmation;
        if (!context) return;
        const notes = ($('editor-notes')?.value || '').trim();
        if (context.mode === 'reject') {
        context.send('reject', { action_id: context.actionId, notes });
            if (typeof context.remove === 'function') context.remove(context.actionId);
            closeConfirmationEditor();
            return;
        }
        const corrections = {};
        [
            ['priority', 'editor-priority'],
            ['problem_code', 'editor-problem-code'],
            ['fault_code', 'editor-fault-code'],
            ['action_code', 'editor-action-code'],
        ].forEach(([key, id]) => {
            const value = ($(id)?.value || '').trim();
            if (value) corrections[key] = value;
        });
        const original = context.originalValues || {};
        const changed = Object.entries(corrections).some(([key, value]) => {
            return String(original[key] || '') !== String(value || '');
        }) || notes.length > 0;
        if (!changed) {
            const error = $('confirmation-editor-error');
            if (error) {
                error.textContent = 'Change at least one field or add a note before sending a correction.';
                error.hidden = false;
            }
            return;
        }
        context.send('correct', { action_id: context.actionId, corrections, notes });
        if (typeof context.remove === 'function') context.remove(context.actionId);
        closeConfirmationEditor();
    }

    function makeConnectionRetryAccessible() {
        const status = $('connection-status');
        if (!status) return;
        if (!status.dataset.commandCenterBound) {
            status.addEventListener('keydown', (event) => {
                if ((event.key === 'Enter' || event.key === ' ')
                    && status.getAttribute('role') === 'button') {
                    event.preventDefault();
                    status.click();
                }
            });
            status.dataset.commandCenterBound = 'true';
        }
    }

    function trapDialogFocus(event) {
        if (event.key !== 'Tab' || store.activeDialog !== 'asset-picker') return;
        const dialog = $('asset-picker');
        const focusable = getFocusable(dialog);
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    function bindEvents() {
        $('asset-picker-list')?.addEventListener('click', (event) => {
            const button = event.target.closest('[data-asset-id]');
            if (button) chooseAsset(button.dataset.assetId);
        });
        ['asset-picker-search', 'asset-picker-department', 'asset-picker-location'].forEach((id) => {
            $(id)?.addEventListener('input', renderAssetPickerList);
            $(id)?.addEventListener('change', renderAssetPickerList);
        });
        document.addEventListener('keydown', (event) => {
            if (event.key === 'Escape') {
                if (store.activeDialog === 'asset-picker') closeAssetPicker();
                if (store.activeDialog === 'confirmation-editor') closeConfirmationEditor();
            }
            trapDialogFocus(event);
        });
        makeConnectionRetryAccessible();
    }

    function init() {
        bindEvents();
        updateSelectedAssetSummary();
    }

    window.CommandCenter = {
        store,
        init,
        openAssetPicker,
        closeAssetPicker,
        chooseAsset,
        selectAsset,
        confirmAssetSelection,
        ensureAssetSelectedBeforeInspection,
        syncSelectedAssetToInspection,
        sendInspectionStartContext,
        openConfirmationEditor,
        closeConfirmationEditor,
        submitConfirmationEditor,
        loadDashboardSummary,
        makeConnectionRetryAccessible,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
