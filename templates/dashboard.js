// FDWA AI Agent Dashboard JavaScript
// Handles all interactive functionality, API communication, and UI updates

// EventSource for real-time updates
let eventSource = null;

// Agent Configuration
const AGENTS = [
    {
        id: 'twitter',
        name: 'Twitter Agent',
        icon: '🐦',
        type: 'Social Media',
        description: 'Automated tweet posting and engagement',
        status: 'active',
        posts: 0,
        lastActive: 'Never'
    },
    {
        id: 'facebook',
        name: 'Facebook Agent',
        icon: '📘',
        type: 'Social Media',
        description: 'Automated page posts and management',
        status: 'active',
        posts: 0,
        lastActive: 'Never'
    },
    {
        id: 'linkedin',
        name: 'LinkedIn Agent',
        icon: '💼',
        type: 'Professional Network',
        description: 'Professional content distribution',
        status: 'active',
        posts: 0,
        lastActive: 'Never'
    },
    {
        id: 'instagram',
        name: 'Instagram Agent',
        icon: '📸',
        type: 'Visual Content',
        description: 'Image posts with captions',
        status: 'active',
        posts: 0,
        lastActive: 'Never'
    },
    {
        id: 'telegram',
        name: 'Telegram Agent',
        icon: '💬',
        type: 'Messaging',
        description: 'Group messaging and notifications',
        status: 'active',
        posts: 0,
        lastActive: 'Never'
    },
    {
        id: 'blog',
        name: 'Blog/Email Agent',
        icon: '📧',
        type: 'Content Marketing',
        description: 'Blog generation and email distribution',
        status: 'active',
        posts: 0,
        lastActive: 'Never'
    }
];

// Terminal Logger
class TerminalLogger {
    constructor() {
        this.output = document.getElementById('terminalOutput');
    }

    log(message, type = 'info') {
        const line = document.createElement('div');
        line.className = 'terminal-line';
        
        const prompt = document.createElement('span');
        prompt.className = 'terminal-prompt';
        prompt.textContent = '$';
        
        const text = document.createElement('span');
        text.className = `terminal-text terminal-${type}`;
        text.textContent = message;
        
        line.appendChild(prompt);
        line.appendChild(text);
        this.output.appendChild(line);
        
        // Auto-scroll to bottom
        this.output.scrollTop = this.output.scrollHeight;
    }

    success(message) {
        this.log(message, 'success');
    }

    error(message) {
        this.log(message, 'error');
    }

    warning(message) {
        this.log(message, 'warning');
    }

    info(message) {
        this.log(message, 'info');
    }

    clear() {
        this.output.innerHTML = `
            <div class="terminal-line">
                <span class="terminal-prompt">$</span>
                <span class="terminal-text">Terminal cleared...</span>
            </div>
        `;
    }
}

const terminal = new TerminalLogger();

// Initialize Dashboard
function initDashboard() {
    terminal.success('Dashboard initialized');
    terminal.info('Loading AI agents...');
    
    // Populate agent grid
    populateAgentGrid();
    
    // Update system time
    updateSystemTime();
    setInterval(updateSystemTime, 1000);
    
    // Load initial status  
    loadStatus();
    
    // Connect to real-time stream
    connectToStream();
    
    // Auto-refresh every 30 seconds
    setInterval(loadStatus, 30000);
    
    terminal.success(`${AGENTS.length} agents loaded successfully`);
    terminal.info('System ready for operations');
}

// Connect to Real-time Stream
function connectToStream() {
    if (eventSource) {
        eventSource.close();
    }
    
    terminal.info('Connecting to agent activity stream...');
    
    eventSource = new EventSource('/stream');
    
    eventSource.onopen = () => {
        terminal.success('Real-time stream connected');
    };
    
    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleStreamEvent(data);
        } catch (e) {
            console.error('Failed to parse stream event:', e);
        }
    };
    
    eventSource.onerror = (error) => {
        terminal.error('Stream connection lost, reconnecting...');
        eventSource.close();
        // Reconnect after 5 seconds
        setTimeout(connectToStream, 5000);
    };
}

// Handle Stream Events
function handleStreamEvent(event) {
    const { type, message, step, progress, data } = event;
    
    switch (type) {
        case 'connected':
            terminal.success(message);
            break;
            
        case 'run_start':
            terminal.info('═'.repeat(50));
            terminal.info(`🚀 ${message}`.toUpperCase());
            terminal.info('═'.repeat(50));
            updateProgressBar(0, progress.total);
            break;
            
        case 'step_start':
            terminal.info(`▶  ${message}`);
            break;
            
        case 'update':
            terminal.info(`   ${message}`);
            break;
            
        case 'step_complete':
            terminal.success(`✓  Completed: ${step}`);
            if (progress) {
                updateProgressBar(progress.current, progress.total);
            }
            if (data && data.preview) {
                terminal.info(`   Preview: ${data.preview}`);
            }
            break;
            
        case 'error':
            terminal.error(`✗  ${message}`);
            break;
            
        case 'run_complete':
            terminal.info('═'.repeat(50));
            if (data && data.success) {
                terminal.success('🎉 AGENT RUN COMPLETED SUCCESSFULLY');
                // Load fresh results
                setTimeout(loadStatus, 1000);
            } else {
                terminal.error('❌ AGENT RUN FAILED');
            }
            terminal.info('═'.repeat(50));
            updateProgressBar(0, 0);
            break;
            
        default:
            terminal.info(message);
    }
}

// Update Progress Bar
function updateProgressBar(current, total) {
    if (total === 0) {
        document.getElementById('progressBar').style.display = 'none';
        return;
    }
    
    const percent = Math.round((current / total) * 100);
    const progressBar = document.getElementById('progressBar');
    const progressFill = document.getElementById('progressFill');
    const progressText = document.getElementById('progressText');
    
    if (!progressBar) {
        // Create progress bar if it doesn't exist
        const bar = document.createElement('div');
        bar.id = 'progressBar';
        bar.style.cssText = 'margin: 16px 0; background: var(--bg-secondary); border-radius: 8px; overflow: hidden; height: 32px; display: flex; align-items: center; position: relative;';
        bar.innerHTML = `
            <div id="progressFill" style="height: 100%; background: linear-gradient(90deg, var(--accent-blue), var(--accent-purple)); transition: width 0.3s ease;"></div>
            <div id="progressText" style="position: absolute; left: 50%; transform: translateX(-50%); color: white; font-weight: 600; font-size: 13px;"></div>
        `;
        document.querySelector('.terminal-output').insertAdjacentElement('beforebegin', bar);
        return updateProgressBar(current, total);
    }
    
    progressBar.style.display = 'flex';
    progressFill.style.width = `${percent}%`;
    progressText.textContent = `${current} / ${total} steps (${percent}%)`;
}

// Update System Time
function updateSystemTime() {
    const now = new Date();
    const timeStr = now.toLocaleTimeString('en-US', { hour12: false });
    document.getElementById('systemTime').textContent = timeStr;
}

// Populate Agent Grid
function populateAgentGrid() {
    const grid = document.getElementById('agentGrid');
    grid.innerHTML = '';
    
    AGENTS.forEach(agent => {
        const card = document.createElement('div');
        card.className = 'agent-card';
        card.innerHTML = `
            <div class="agent-header">
                <div class="agent-info">
                    <div class="agent-avatar">${agent.icon}</div>
                    <div>
                        <div class="agent-name">${agent.name}</div>
                        <div class="agent-type">${agent.type}</div>
                    </div>
                </div>
                <div class="agent-status badge-success">ACTIVE</div>
            </div>
            <div style="color: var(--text-secondary); font-size: 13px; margin-top: 12px; line-height: 1.5;">
                ${agent.description}
            </div>
            <div class="agent-metrics">
                <div class="metric">
                    <div class="metric-value" id="${agent.id}-posts">${agent.posts}</div>
                    <div class="metric-label">Posts</div>
                </div>
                <div class="metric">
                    <div class="metric-value" style="font-size: 12px; color: var(--text-muted);" id="${agent.id}-last">${agent.lastActive}</div>
                    <div class="metric-label">Last Active</div>
                </div>
            </div>
        `;
        grid.appendChild(card);
    });
}

// Load Status from API
async function loadStatus() {
    try {
        terminal.info('Fetching system status...');
        const res = await fetch('/status');
        const data = await res.json();
        
        // Update system status
        const statusBadge = document.getElementById('systemStatus');
        statusBadge.textContent = data.status === 'Success' ? 'ONLINE' : 'ERROR';
        statusBadge.className = 'card-badge ' + (data.status === 'Success' ? 'badge-success' : 'badge-error');
        
        // Update last run time
        if (data.last_run) {
            const date = new Date(data.last_run);
            document.getElementById('lastRun').textContent = date.toLocaleString();
            terminal.success(`Last run: ${date.toLocaleString()}`);
        }
        
        // Update results if available
        if (data.results && Object.keys(data.results).length > 0) {
            displayResults(data.results);
            terminal.success('Results loaded successfully');
        }
        
    } catch (e) {
        terminal.error(`Failed to load status: ${e.message}`);
        console.error('Status load error:', e);
    }
}

// Display Run Results
function displayResults(results) {
    const resultsCard = document.getElementById('resultsCard');
    resultsCard.style.display = 'block';
    
    // Show generated image
    if (results.image) {
        const img = document.getElementById('generatedImage');
        img.src = results.image;
        img.style.display = 'block';
    }
    
    // Show posts
    if (results.tweet) {
        document.getElementById('twitterPost').textContent = results.tweet;
    }
    if (results.facebook) {
        document.getElementById('facebookPost').textContent = results.facebook;
    }
    if (results.linkedin) {
        document.getElementById('linkedinPost').textContent = results.linkedin;
    }
    if (results.telegram) {
        document.getElementById('telegramPost').textContent = results.telegram;
    }
    if (results.instagram) {
        document.getElementById('instagramPost').textContent = results.instagram;
    }
    
    // Update agent metrics
    updateAgentMetrics(results);
}

// Update Agent Metrics
function updateAgentMetrics(results) {
    const now = new Date().toLocaleTimeString();
    
    if (results.twitter) {
        const postsEl = document.getElementById('twitter-posts');
        const lastEl = document.getElementById('twitter-last');
        if (postsEl && lastEl) {
            postsEl.textContent = parseInt(postsEl.textContent) + 1;
            lastEl.textContent = now;
        }
    }
    
   if (results.facebook) {
        const postsEl = document.getElementById('facebook-posts');
        const lastEl = document.getElementById('facebook-last');
        if (postsEl && lastEl) {
            postsEl.textContent = parseInt(postsEl.textContent) + 1;
            lastEl.textContent = now;
        }
    }
    
    if (results.linkedin_status) {
        const postsEl = document.getElementById('linkedin-posts');
        const lastEl = document.getElementById('linkedin-last');
        if (postsEl && lastEl) {
            postsEl.textContent = parseInt(postsEl.textContent) + 1;
            lastEl.textContent = now;
        }
    }
    
    if (results.instagram_status) {
        const postsEl = document.getElementById('instagram-posts');
        const lastEl = document.getElementById('instagram-last');
        if (postsEl && lastEl) {
            postsEl.textContent = parseInt(postsEl.textContent) + 1;
            lastEl.textContent = now;
        }
    }
}

// Run Agent
async function runAgent() {
    const btn = document.getElementById('runBtn');
    const loading = document.getElementById('loading');
    
    btn.disabled = true;
    loading.classList.add('show');
    
    terminal.info('Starting agent run...');
    terminal.warning('This may take 30-60 seconds');
    
    try {
        terminal.info('Executing research phase...');
        const res = await fetch('/run', { method: 'POST' });
        const data = await res.json();
        
        terminal.success('Agent execution completed!');
        terminal.info('Generating content...');
        
        // Reload status to get new results
        await loadStatus();
        
        terminal.success('All agents completed successfully');
        terminal.info('Posts published to all platforms');
        
        // Show notification
        showNotification('Agent Run Complete', 'Check results below for details', 'success');
        
    } catch (e) {
        terminal.error(`Agent execution failed: ${e.message}`);
        showNotification('Error', e.message, 'error');
    } finally {
        btn.disabled = false;
        loading.classList.remove('show');
    }
}

// Show Section
function showSection(sectionName) {
    // Hide all sections
    const sections = ['dashboard', 'agents', 'terminal', 'connections'];
    sections.forEach(s => {
        const section = document.getElementById(`section-${s}`);
        if (section) section.style.display = 'none';
    });
    
    // Show selected section (dashboard is default content)
    const targetSection = document.getElementById(`section-${sectionName}`);
    if (targetSection) {
        targetSection.style.display = 'block';
    } else if (sectionName === 'dashboard') {
        document.getElementById('section-dashboard').style.display = 'block';
    }
    
    // Update active nav item
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
    });
    
    event.target.closest('.nav-item').classList.add('active');
    
    terminal.info(`Switched to ${sectionName} view`);
}

// Clear Terminal
function clearTerminal() {
    terminal.clear();
    terminal.info('Ready for new operations');
}

// Show Notification
function showNotification(title, message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.style.cssText = `
        position: fixed;
        top: 24px;
        right: 24px;
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        padding: 20px;
        max-width: 400px;
        z-index: 9999;
        animation: slideIn 0.3s ease-out;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.3);
    `;
    
    const typeColor = {
        success: 'var(--success)',
        error: 'var(--error)',
        warning: 'var(--warning)',
        info: 'var(--accent-blue)'
    }[type];
    
    notification.innerHTML = `
        <div style="display: flex; align-items: flex-start; gap: 12px;">
            <div style="font-size: 24px;">${type === 'success' ? '✅' : type === 'error' ? '❌' : type === 'warning' ? '⚠️' : 'ℹ️'}</div>
            <div style="flex: 1;">
                <div style="font-weight: 600; color: ${typeColor}; margin-bottom: 4px;">${title}</div>
                <div style="color: var(--text-secondary); font-size: 14px;">${message}</div>
            </div>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', initDashboard);

// Add slideIn/slideOut animations
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
