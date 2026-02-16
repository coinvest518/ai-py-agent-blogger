// FDWA AI Agent Dashboard v3 — Full control dashboard
// Chat, individual agent controls, scheduler, settings, memory viewer

let eventSource = null;

// ── Agent definitions ──────────────────────────────────────────────
const AGENTS = [
    { id: 'research',  name: 'Research',      icon: '🔬', type: 'Data',            desc: 'Trend research & topic selection' },
    { id: 'twitter',   name: 'Twitter',       icon: '🐦', type: 'Social Media',    desc: 'Automated tweet posting' },
    { id: 'facebook',  name: 'Facebook',      icon: '📘', type: 'Social Media',    desc: 'Page posts & engagement' },
    { id: 'linkedin',  name: 'LinkedIn',      icon: '💼', type: 'Professional',    desc: 'Professional content distribution' },
    { id: 'instagram', name: 'Instagram',     icon: '📸', type: 'Visual Content',  desc: 'Image posts with captions' },
    { id: 'telegram',  name: 'Telegram',      icon: '💬', type: 'Messaging',       desc: 'Crypto data & group messaging' },
    { id: 'blog',      name: 'Blog/Email',    icon: '📧', type: 'Content',         desc: 'Blog generation & email sending' },
    { id: 'memory',    name: 'Memory Save',   icon: '🧠', type: 'System',          desc: 'Save run results to Astra DB' },
];

// ── Terminal Logger ────────────────────────────────────────────────
class TerminalLogger {
    constructor() { this.output = document.getElementById('terminalOutput'); }
    log(msg, type = 'info') {
        const line = document.createElement('div');
        line.className = 'terminal-line';
        line.innerHTML = `<span class="terminal-prompt">$</span><span class="terminal-text terminal-${type}">${this._esc(msg)}</span>`;
        this.output.appendChild(line);
        this.output.scrollTop = this.output.scrollHeight;
    }
    success(m) { this.log(m, 'success'); }
    error(m)   { this.log(m, 'error'); }
    warning(m) { this.log(m, 'warning'); }
    info(m)    { this.log(m, 'info'); }
    clear() {
        this.output.innerHTML = '<div class="terminal-line"><span class="terminal-prompt">$</span><span class="terminal-text">Terminal cleared…</span></div>';
    }
    _esc(s) { const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }
}
const terminal = new TerminalLogger();

// ── Init ───────────────────────────────────────────────────────────
function initDashboard() {
    terminal.success('Dashboard v3 initialized');
    populateAgentGrid();
    populateAgentControls();
    populateAgentStatusList();
    updateSystemTime();
    setInterval(updateSystemTime, 1000);
    loadStatus();
    loadSchedulerStatus();
    loadMemoryStatus();
    loadSettings();
    connectToStream();
    setInterval(loadStatus, 30000);

    // Wire nav
    document.querySelectorAll('.nav-item[data-section]').forEach(item => {
        item.addEventListener('click', () => showSection(item.dataset.section));
    });

    // Chat enter key
    const chatInput = document.getElementById('chatInput');
    if (chatInput) chatInput.addEventListener('keydown', e => { if (e.key === 'Enter') sendChat(); });

    terminal.success(`${AGENTS.length} agents loaded`);
}

// ── Navigation ─────────────────────────────────────────────────────
const SECTIONS = ['dashboard','agents','chat','terminal','scheduler','memory','settings'];
function showSection(name) {
    SECTIONS.forEach(s => {
        const el = document.getElementById('section-' + s);
        if (el) el.style.display = s === name ? 'block' : 'none';
    });
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    const active = document.querySelector(`.nav-item[data-section="${name}"]`);
    if (active) active.classList.add('active');

    // Lazy-load panel data
    if (name === 'scheduler') loadSchedulerStatus();
    if (name === 'memory') loadMemoryStatus();
    if (name === 'settings') loadSettings();
}

// ── System time ────────────────────────────────────────────────────
function updateSystemTime() {
    document.getElementById('systemTime').textContent = new Date().toLocaleTimeString('en-US', { hour12: false });
}

// ── Agent status list (dashboard card) ─────────────────────────────
function populateAgentStatusList() {
    const el = document.getElementById('agentStatusList');
    if (!el) return;
    el.innerHTML = AGENTS.filter(a => a.id !== 'memory').map(a =>
        `<div class="stat-row"><span class="stat-label">${a.icon} ${a.name}</span><span class="stat-value" style="color:var(--success);">●</span></div>`
    ).join('');
}

// ── Agent Grid (dashboard overview) ────────────────────────────────
function populateAgentGrid() {
    const grid = document.getElementById('agentGrid');
    if (!grid) return;
    grid.innerHTML = '';
    AGENTS.filter(a => a.id !== 'memory').forEach(agent => {
        const card = document.createElement('div');
        card.className = 'agent-card';
        card.innerHTML = `
            <div class="agent-header">
                <div class="agent-info">
                    <div class="agent-avatar">${agent.icon}</div>
                    <div><div class="agent-name">${agent.name}</div><div class="agent-type">${agent.type}</div></div>
                </div>
                <div class="agent-status badge-success">ACTIVE</div>
            </div>
            <div style="color:var(--text-secondary);font-size:13px;margin-top:12px;line-height:1.5;">${agent.desc}</div>
            <div class="agent-metrics">
                <div class="metric"><div class="metric-value" id="${agent.id}-posts">0</div><div class="metric-label">Posts</div></div>
                <div class="metric"><div class="metric-value" style="font-size:12px;color:var(--text-muted);" id="${agent.id}-last">Never</div><div class="metric-label">Last Active</div></div>
            </div>`;
        grid.appendChild(card);
    });
}

// ── Agent Controls (individual run page) ───────────────────────────
function populateAgentControls() {
    const grid = document.getElementById('agentControlsGrid');
    if (!grid) return;
    grid.innerHTML = '';
    AGENTS.forEach(agent => {
        const card = document.createElement('div');
        card.className = 'agent-control-card';
        card.innerHTML = `
            <div class="agent-ctrl-header">
                <span class="agent-ctrl-icon">${agent.icon}</span>
                <div>
                    <div class="agent-ctrl-name">${agent.name}</div>
                    <div class="agent-ctrl-type">${agent.type}</div>
                </div>
            </div>
            <p class="agent-ctrl-desc">${agent.desc}</p>
            <button class="btn btn-primary agent-run-btn" id="run-${agent.id}" onclick="runSingleAgent('${agent.id}')">
                ▶ Run ${agent.name}
            </button>`;
        grid.appendChild(card);
    });
}

// ── Run single agent ───────────────────────────────────────────────
async function runSingleAgent(agentId) {
    const btn = document.getElementById('run-' + agentId);
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = '⏳ Running…';
    terminal.info(`Running ${agentId} agent…`);

    try {
        const res = await fetch(`/agent/run/${agentId}`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            terminal.success(`${agentId} agent completed`);
            const out = document.getElementById('singleAgentOutput');
            const card = document.getElementById('singleAgentResult');
            if (out && card) {
                out.textContent = JSON.stringify(data.result, null, 2);
                card.style.display = 'block';
            }
        } else {
            terminal.error(`${agentId} failed: ${data.error}`);
        }
    } catch (e) {
        terminal.error(`${agentId} error: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = `▶ Run ${agentId.charAt(0).toUpperCase() + agentId.slice(1)}`;
    }
}

// ── SSE Stream ─────────────────────────────────────────────────────
function connectToStream() {
    if (eventSource) eventSource.close();
    eventSource = new EventSource('/stream');
    eventSource.onopen = () => terminal.success('Real-time stream connected');
    eventSource.onmessage = (event) => {
        try { handleStreamEvent(JSON.parse(event.data)); } catch (e) { /* skip */ }
    };
    eventSource.onerror = () => {
        terminal.error('Stream lost, reconnecting in 5s…');
        eventSource.close();
        setTimeout(connectToStream, 5000);
    };
}

function handleStreamEvent(ev) {
    const { type, message, step, progress, data } = ev;
    switch (type) {
        case 'connected':     terminal.success(message); break;
        case 'run_start':     terminal.info('═'.repeat(50)); terminal.info(`🚀 ${message}`); break;
        case 'step_start':    terminal.info(`▶  ${message}`); break;
        case 'update':        terminal.info(`   ${message}`); break;
        case 'step_complete': terminal.success(`✓  ${step}`); break;
        case 'error':         terminal.error(`✗  ${message}`); break;
        case 'run_complete':
            terminal.info('═'.repeat(50));
            if (data && data.success) { terminal.success('🎉 AGENT RUN COMPLETED'); setTimeout(loadStatus, 1000); }
            else terminal.error('❌ AGENT RUN FAILED');
            break;
        default: if (message) terminal.info(message);
    }
}

// ── Load Status ────────────────────────────────────────────────────
async function loadStatus() {
    try {
        const res = await fetch('/status');
        const data = await res.json();
        const badge = document.getElementById('systemStatus');
        badge.textContent = data.status === 'Success' ? 'ONLINE' : (data.status || 'IDLE');
        badge.className = 'card-badge ' + (data.status === 'Success' ? 'badge-success' : 'badge-warning');

        if (data.last_run) {
            document.getElementById('lastRun').textContent = new Date(data.last_run).toLocaleString();
        }
        if (data.results && Object.keys(data.results).length > 0) {
            displayResults(data.results);
        }
    } catch (e) {
        terminal.error('Status fetch failed: ' + e.message);
    }
}

function displayResults(r) {
    const card = document.getElementById('resultsCard');
    if (card) card.style.display = 'block';
    if (r.image) { const img = document.getElementById('generatedImage'); img.src = r.image; img.style.display = 'block'; }
    if (r.tweet) document.getElementById('twitterPost').textContent = r.tweet;
    if (r.facebook) document.getElementById('facebookPost').textContent = r.facebook;
    if (r.linkedin) document.getElementById('linkedinPost').textContent = r.linkedin;
    if (r.telegram) document.getElementById('telegramPost').textContent = r.telegram;
    if (r.instagram) document.getElementById('instagramPost').textContent = r.instagram;
    updateAgentMetrics(r);
}

function updateAgentMetrics(r) {
    const now = new Date().toLocaleTimeString();
    ['twitter','facebook','linkedin','instagram','telegram'].forEach(id => {
        const key = id === 'linkedin' ? 'linkedin_status' : (id === 'instagram' ? 'instagram_status' : id);
        if (r[key] || r[id]) {
            const p = document.getElementById(id + '-posts');
            const l = document.getElementById(id + '-last');
            if (p) p.textContent = parseInt(p.textContent || 0) + 1;
            if (l) l.textContent = now;
        }
    });
}

// ── Run Full Pipeline ──────────────────────────────────────────────
async function runAgent() {
    const btn = document.getElementById('runBtn');
    const loading = document.getElementById('loading');
    btn.disabled = true;
    loading.classList.add('show');
    terminal.info('Starting full agent pipeline…');

    try {
        const res = await fetch('/run', { method: 'POST' });
        await res.json();
        terminal.success('Pipeline completed');
        await loadStatus();
        showNotification('Run Complete', 'All agents finished', 'success');
    } catch (e) {
        terminal.error('Pipeline failed: ' + e.message);
        showNotification('Error', e.message, 'error');
    } finally {
        btn.disabled = false;
        loading.classList.remove('show');
    }
}

// ── Chat ───────────────────────────────────────────────────────────
async function sendChat() {
    const input = document.getElementById('chatInput');
    const messages = document.getElementById('chatMessages');
    const msg = input.value.trim();
    if (!msg) return;

    // User bubble
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-msg chat-msg-user';
    userDiv.textContent = msg;
    messages.appendChild(userDiv);
    input.value = '';
    messages.scrollTop = messages.scrollHeight;

    // Loading indicator
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'chat-msg chat-msg-ai chat-loading';
    loadingDiv.textContent = 'Thinking…';
    messages.appendChild(loadingDiv);
    messages.scrollTop = messages.scrollHeight;

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: msg })
        });
        const data = await res.json();
        loadingDiv.remove();

        const aiDiv = document.createElement('div');
        aiDiv.className = 'chat-msg chat-msg-ai';
        aiDiv.textContent = data.reply || data.error || 'No response';
        messages.appendChild(aiDiv);
    } catch (e) {
        loadingDiv.remove();
        const errDiv = document.createElement('div');
        errDiv.className = 'chat-msg chat-msg-ai chat-msg-error';
        errDiv.textContent = 'Error: ' + e.message;
        messages.appendChild(errDiv);
    }
    messages.scrollTop = messages.scrollHeight;
}

// ── Scheduler ──────────────────────────────────────────────────────
async function loadSchedulerStatus() {
    try {
        const res = await fetch('/scheduler');
        const data = await res.json();
        const running = data.running;
        document.getElementById('schedRunning').textContent = running ? 'RUNNING' : 'PAUSED';
        document.getElementById('schedRunning').style.color = running ? 'var(--success)' : 'var(--warning)';
        document.getElementById('schedInterval').textContent = (data.interval_minutes || 80) + ' min';

        const badge = document.getElementById('schedulerStatusBadge');
        badge.textContent = running ? 'ACTIVE' : 'PAUSED';
        badge.className = 'card-badge ' + (running ? 'badge-success' : 'badge-warning');

        // Dashboard badge
        const dashBadge = document.getElementById('schedulerBadge');
        if (dashBadge) {
            dashBadge.textContent = running ? 'ACTIVE' : 'PAUSED';
            dashBadge.style.color = running ? 'var(--success)' : 'var(--warning)';
        }

        if (data.jobs && data.jobs.length > 0 && data.jobs[0].next_run) {
            const nr = new Date(data.jobs[0].next_run).toLocaleString();
            document.getElementById('schedNextRun').textContent = nr;
            const dashNext = document.getElementById('nextRun');
            if (dashNext) dashNext.textContent = nr;
        }
    } catch (e) { /* ignore */ }
}

async function toggleScheduler() {
    try {
        const res = await fetch('/scheduler/toggle', { method: 'POST' });
        const data = await res.json();
        terminal.info('Scheduler: ' + (data.message || JSON.stringify(data)));
        loadSchedulerStatus();
    } catch (e) {
        terminal.error('Scheduler toggle failed: ' + e.message);
    }
}

// ── Memory / Astra ─────────────────────────────────────────────────
async function loadMemoryStatus() {
    try {
        const res = await fetch('/memory/status');
        const data = await res.json();
        const el = document.getElementById('memoryStatusContent');
        if (!el) return;
        el.innerHTML = `
            <div class="stat-row"><span class="stat-label">Status</span><span class="stat-value" style="color:${data.astra === 'configured' ? 'var(--success)' : 'var(--warning)'};">${data.astra || 'unknown'}</span></div>
            <div class="stat-row"><span class="stat-label">Collection</span><span class="stat-value">${data.collection || '—'}</span></div>
            <div class="stat-row"><span class="stat-label">Ready</span><span class="stat-value">${data.collection_ready ? '✓' : '✗'}</span></div>
            <div class="stat-row"><span class="stat-label">Endpoint</span><span class="stat-value" style="font-size:11px;">${data.endpoint || '—'}</span></div>`;

        // Update dashboard integration badge
        const badge = document.getElementById('astraIntBadge');
        if (badge) {
            badge.textContent = data.collection_ready ? '✓' : (data.astra === 'configured' ? '◐' : '✗');
            badge.style.color = data.collection_ready ? 'var(--success)' : 'var(--warning)';
        }
    } catch (e) {
        const el = document.getElementById('memoryStatusContent');
        if (el) el.innerHTML = '<p style="color:var(--error);">Failed to load</p>';
    }
}

// ── Settings ───────────────────────────────────────────────────────
async function loadSettings() {
    try {
        const res = await fetch('/settings');
        const data = await res.json();
        const el = document.getElementById('settingsContent');
        if (!el || !data.settings) return;
        el.innerHTML = data.settings.map(s => `
            <div class="stat-row">
                <span class="stat-label" style="font-family:monospace;font-size:12px;">${s.key}</span>
                <span class="stat-value" style="color:${s.set ? 'var(--success)' : 'var(--error)'};">${s.set ? '✓ ' + s.preview : '✗ NOT SET'}</span>
            </div>`).join('');
    } catch (e) {
        const el = document.getElementById('settingsContent');
        if (el) el.innerHTML = '<p style="color:var(--error);">Failed to load settings</p>';
    }
}

// ── Utilities ──────────────────────────────────────────────────────
function clearTerminal() { terminal.clear(); terminal.info('Ready'); }

function showNotification(title, message, type = 'info') {
    const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
    const colors = { success: 'var(--success)', error: 'var(--error)', warning: 'var(--warning)', info: 'var(--accent-blue)' };
    const n = document.createElement('div');
    n.className = 'toast-notification';
    n.innerHTML = `
        <div style="display:flex;align-items:flex-start;gap:12px;">
            <div style="font-size:24px;">${icons[type] || 'ℹ️'}</div>
            <div style="flex:1;">
                <div style="font-weight:600;color:${colors[type]};margin-bottom:4px;">${title}</div>
                <div style="color:var(--text-secondary);font-size:14px;">${message}</div>
            </div>
        </div>`;
    document.body.appendChild(n);
    setTimeout(() => { n.style.animation = 'slideOut 0.3s ease-out'; setTimeout(() => n.remove(), 300); }, 5000);
}

// ── Boot ───────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', initDashboard);

// Inject toast animations
const _style = document.createElement('style');
_style.textContent = `
@keyframes slideIn{from{transform:translateX(400px);opacity:0}to{transform:translateX(0);opacity:1}}
@keyframes slideOut{from{transform:translateX(0);opacity:1}to{transform:translateX(400px);opacity:0}}
`;
document.head.appendChild(_style);
