/**
 * Phase 3 Dashboard Enhancements - JavaScript
 * Provides UI functionality for Synthesis Plans, Memory Explorer, Metrics, and Code Evolution
 */

// ==================== SYNTHESIS PLAN VIEWER ====================

class SynthesisPlanViewer {
    constructor() {
        this.currentPlan = null;
        this.updateInterval = null;
    }

    async loadActivePlans() {
        try {
            const response = await fetch('/synthesis/plans');
            const data = await response.json();

            if (data.active_plans && data.active_plans.length > 0) {
                this.displayPlan(data.active_plans[0]);
                this.startAutoUpdate();
            } else {
                this.displayNoPlan();
            }
        } catch (error) {
            console.error('Error loading synthesis plans:', error);
        }
    }

    async loadPlanStatus(planId) {
        try {
            const response = await fetch(`/synthesis/plans/${planId}`);
            const data = await response.json();
            this.displayPlan(data);
        } catch (error) {
            console.error('Error loading plan status:', error);
        }
    }

    displayPlan(plan) {
        this.currentPlan = plan;
        const container = document.getElementById('synthesis-viewer');
        if (!container) return;

        const progress = plan.completed_tasks || 0;
        const total = plan.total_tasks || 0;
        const percentage = total > 0 ? (progress / total * 100).toFixed(0) : 0;

        container.innerHTML = `
            <div class="synthesis-panel fade-in">
                <div class="synthesis-header">
                    <div class="synthesis-title">
                        <span>🎯</span>
                        <span>Synthesis Plan: ${plan.plan_id || 'Active'}</span>
                    </div>
                    <div class="plan-status ${plan.status || 'pending'}">
                        ${plan.status || 'Pending'}
                    </div>
                </div>

                <div class="plan-progress">
                    <div class="progress-bar-container">
                        <div class="progress-bar" style="width: ${percentage}%"></div>
                    </div>
                    <div class="progress-text">
                        ${progress} / ${total} tasks completed (${percentage}%)
                    </div>
                </div>

                <div class="task-list">
                    ${this.renderTasks(plan.subtasks || [])}
                </div>

                <div class="plan-controls">
                    ${this.renderControls(plan.status)}
                </div>
            </div>
        `;
    }

    renderTasks(tasks) {
        if (!tasks || tasks.length === 0) {
            return '<div class="task-item pending">No tasks available</div>';
        }

        return tasks.map((task, index) => {
            const status = task.status || 'pending';
            const icon = this.getTaskIcon(status);

            return `
                <div class="task-item ${status}">
                    <div class="task-header">
                        <div class="task-title">
                            <span>${icon}</span>
                            <span>${task.description || `Task ${index + 1}`}</span>
                        </div>
                        <div class="task-meta">
                            ${task.agent || 'N/A'} • ${task.tool || 'N/A'}
                        </div>
                    </div>
                    ${task.error ? `<div style="color: #f44336; font-size: 11px; margin-top: 5px;">Error: ${task.error}</div>` : ''}
                </div>
            `;
        }).join('');
    }

    getTaskIcon(status) {
        const icons = {
            'pending': '⏳',
            'running': '▶️',
            'completed': '✅',
            'failed': '❌'
        };
        return icons[status] || '⏳';
    }

    renderControls(status) {
        if (status === 'running') {
            return `
                <button class="plan-btn pause" onclick="synthesisViewer.pausePlan()">
                    ⏸️ Pause
                </button>
                <button class="plan-btn cancel" onclick="synthesisViewer.cancelPlan()">
                    ⏹️ Cancel
                </button>
            `;
        } else if (status === 'paused') {
            return `
                <button class="plan-btn resume" onclick="synthesisViewer.resumePlan()">
                    ▶️ Resume
                </button>
                <button class="plan-btn cancel" onclick="synthesisViewer.cancelPlan()">
                    ⏹️ Cancel
                </button>
            `;
        }
        return '';
    }

    displayNoPlan() {
        const container = document.getElementById('synthesis-viewer');
        if (!container) return;

        container.innerHTML = `
            <div class="synthesis-panel">
                <div class="synthesis-header">
                    <div class="synthesis-title">
                        <span>🎯</span>
                        <span>Synthesis Plan Viewer</span>
                    </div>
                </div>
                <div style="text-align: center; padding: 40px; color: rgba(255,255,255,0.5);">
                    <div style="font-size: 48px; margin-bottom: 15px;">📋</div>
                    <div>No active synthesis plans</div>
                    <div style="font-size: 12px; margin-top: 10px;">Plans will appear here when created</div>
                </div>
            </div>
        `;
    }

    async cancelPlan() {
        if (!this.currentPlan || !this.currentPlan.plan_id) return;

        try {
            await fetch(`/synthesis/plans/${this.currentPlan.plan_id}`, {
                method: 'DELETE'
            });
            this.stopAutoUpdate();
            this.displayNoPlan();
        } catch (error) {
            console.error('Error cancelling plan:', error);
        }
    }

    startAutoUpdate() {
        if (this.updateInterval) return;

        this.updateInterval = setInterval(() => {
            if (this.currentPlan && this.currentPlan.plan_id) {
                this.loadPlanStatus(this.currentPlan.plan_id);
            }
        }, 2000); // Update every 2 seconds
    }

    stopAutoUpdate() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
}

// ==================== MEMORY EXPLORER ====================

class MemoryExplorer {
    constructor() {
        this.activeLayer = null;
    }

    async loadMemoryStats() {
        try {
            const response = await fetch('/memory/stats');
            const data = await response.json();
            this.displayMemoryLayers(data);
        } catch (error) {
            console.error('Error loading memory stats:', error);
        }
    }

    displayMemoryLayers(stats) {
        const container = document.getElementById('memory-explorer');
        if (!container) return;

        const layers = stats.layer_breakdown || {};

        container.innerHTML = `
            <div class="memory-panel fade-in">
                <div class="synthesis-header">
                    <div class="synthesis-title">
                        <span>🧠</span>
                        <span>Memory System</span>
                    </div>
                    <div class="progress-text">
                        Total: ${stats.total_memories || 0} memories
                    </div>
                </div>

                <div class="memory-layers">
                    ${this.renderLayers(layers)}
                </div>

                <div class="memory-timeline" id="memory-timeline">
                    <h4 style="color: #8a2be2; margin-bottom: 15px;">Recent Memories</h4>
                    ${this.renderTimeline([])}
                </div>
            </div>
        `;
    }

    renderLayers(layers) {
        const layerNames = ['critical', 'operational', 'learning', 'experience', 'knowledge'];
        const layerIcons = {
            'critical': '🔴',
            'operational': '🟢',
            'learning': '🟡',
            'experience': '🔵',
            'knowledge': '🟣'
        };

        return layerNames.map(name => {
            const layer = layers[name] || { count: 0, priority: 0 };
            return `
                <div class="memory-layer ${this.activeLayer === name ? 'active' : ''}" 
                     onclick="memoryExplorer.selectLayer('${name}')">
                    <div class="layer-name">
                        ${layerIcons[name]} ${name.toUpperCase()}
                    </div>
                    <div class="layer-count">${layer.count}</div>
                    <div class="layer-description">Priority ${layer.priority}</div>
                </div>
            `;
        }).join('');
    }

    renderTimeline(memories) {
        if (!memories || memories.length === 0) {
            return '<div style="text-align: center; color: rgba(255,255,255,0.5); padding: 20px;">No recent memories</div>';
        }

        return memories.map(memory => `
            <div class="timeline-item">
                <div class="timeline-time">${this.formatTime(memory.timestamp)}</div>
                <div class="timeline-content">${memory.content}</div>
            </div>
        `).join('');
    }

    async selectLayer(layerName) {
        this.activeLayer = layerName;

        try {
            const response = await fetch(`/memory/layer/${layerName}`);
            const data = await response.json();

            // Update timeline with layer-specific memories
            const timeline = document.getElementById('memory-timeline');
            if (timeline) {
                timeline.innerHTML = `
                    <h4 style="color: #8a2be2; margin-bottom: 15px;">
                        ${layerName.toUpperCase()} Layer Memories
                    </h4>
                    ${this.renderTimeline(data.recent_entries || [])}
                `;
            }
        } catch (error) {
            console.error('Error loading layer data:', error);
        }
    }

    formatTime(timestamp) {
        if (!timestamp) return 'Unknown';
        const date = new Date(timestamp);
        return date.toLocaleTimeString();
    }
}

// ==================== METRICS DASHBOARD ====================

class MetricsDashboard {
    constructor() {
        this.updateInterval = null;
    }

    async loadMetrics() {
        try {
            const [metricsRes, perfRes] = await Promise.all([
                fetch('/metrics'),
                fetch('/performance')
            ]);

            const metrics = await metricsRes.json();
            const performance = await perfRes.json();

            this.displayMetrics(metrics, performance);
            this.startAutoUpdate();
        } catch (error) {
            console.error('Error loading metrics:', error);
        }
    }

    displayMetrics(metrics, performance) {
        const container = document.getElementById('metrics-dashboard');
        if (!container) return;

        container.innerHTML = `
            <div class="metrics-grid fade-in">
                ${this.renderMetricCard('Total Requests', performance.total_requests || 0, '+12%', true)}
                ${this.renderMetricCard('Success Rate', ((performance.success_rate || 0) * 100).toFixed(1) + '%', '+2.3%', true)}
                ${this.renderMetricCard('Avg Duration', (performance.avg_duration || 0).toFixed(2) + 's', '-0.5s', true)}
                ${this.renderMetricCard('Total Tokens', performance.total_tokens || 0, '+1.2K', true)}
            </div>

            <div class="synthesis-panel fade-in" style="margin-top: 20px;">
                <div class="synthesis-header">
                    <div class="synthesis-title">
                        <span>📊</span>
                        <span>Performance Trends</span>
                    </div>
                </div>
                <div class="chart-container">
                    ${this.renderChart(metrics)}
                </div>
            </div>
        `;
    }

    renderMetricCard(label, value, change, positive) {
        return `
            <div class="metric-card">
                <div class="metric-label">${label}</div>
                <div class="metric-value">${value}</div>
                <div class="metric-change ${positive ? 'positive' : 'negative'}">
                    <span>${positive ? '↑' : '↓'}</span>
                    <span>${change}</span>
                </div>
            </div>
        `;
    }

    renderChart(metrics) {
        // Generate sample chart bars (in production, use real data)
        const bars = Array.from({ length: 20 }, (_, i) => {
            const height = Math.random() * 100;
            return `<div class="chart-bar" style="height: ${height}%"></div>`;
        });
        return bars.join('');
    }

    startAutoUpdate() {
        if (this.updateInterval) return;

        this.updateInterval = setInterval(() => {
            this.loadMetrics();
        }, 5000); // Update every 5 seconds
    }

    stopAutoUpdate() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }
}

// ==================== CODE EVOLUTION HISTORY ====================

class EvolutionHistory {
    constructor() {
        this.modifications = [];
    }

    async loadHistory() {
        try {
            const response = await fetch('/evolution/history');
            const data = await response.json();
            this.modifications = data.modifications || [];
            this.displayHistory();
        } catch (error) {
            console.error('Error loading evolution history:', error);
        }
    }

    displayHistory() {
        const container = document.getElementById('evolution-history');
        if (!container) return;

        container.innerHTML = `
            <div class="evolution-panel fade-in">
                <div class="synthesis-header">
                    <div class="synthesis-title">
                        <span>🔧</span>
                        <span>Code Evolution History</span>
                    </div>
                    <div class="progress-text">
                        ${this.modifications.length} modifications
                    </div>
                </div>

                <div class="modification-list">
                    ${this.renderModifications()}
                </div>
            </div>
        `;
    }

    renderModifications() {
        if (this.modifications.length === 0) {
            return `
                <div style="text-align: center; padding: 40px; color: rgba(255,255,255,0.5);">
                    <div style="font-size: 48px; margin-bottom: 15px;">🔧</div>
                    <div>No code modifications yet</div>
                    <div style="font-size: 12px; margin-top: 10px;">Modifications will appear here</div>
                </div>
            `;
        }

        return this.modifications.map(mod => `
            <div class="modification-item">
                <div class="mod-header">
                    <div class="mod-id">#${mod.id}</div>
                    <div class="mod-type ${mod.type}">${mod.type.toUpperCase()}</div>
                </div>
                <div class="mod-file">📄 ${mod.file}</div>
                <div class="mod-timestamp">🕒 ${new Date(mod.timestamp).toLocaleString()}</div>
                <div class="mod-actions">
                    <button class="mod-btn view" onclick="evolutionHistory.viewDiff('${mod.id}')">
                        👁️ View Diff
                    </button>
                    ${mod.applied ? `
                        <button class="mod-btn rollback" onclick="evolutionHistory.rollback('${mod.id}')">
                            ↩️ Rollback
                        </button>
                    ` : ''}
                </div>
            </div>
        `).join('');
    }

    async viewDiff(modId) {
        // In production, fetch actual diff
        alert(`Viewing diff for modification ${modId}`);
    }

    async rollback(modId) {
        if (!confirm(`Are you sure you want to rollback modification ${modId}?`)) {
            return;
        }

        try {
            await fetch(`/evolution/rollback/${modId}`, { method: 'POST' });
            this.loadHistory(); // Reload
        } catch (error) {
            console.error('Error rolling back:', error);
            alert('Failed to rollback modification');
        }
    }
}

// ==================== INITIALIZATION ====================

// Global instances
let synthesisViewer, memoryExplorer, metricsDashboard, evolutionHistory;

function initializeDashboardEnhancements() {
    synthesisViewer = new SynthesisPlanViewer();
    memoryExplorer = new MemoryExplorer();
    metricsDashboard = new MetricsDashboard();
    evolutionHistory = new EvolutionHistory();

    // Load initial data
    synthesisViewer.loadActivePlans();
    memoryExplorer.loadMemoryStats();
    metricsDashboard.loadMetrics();
    evolutionHistory.loadHistory();
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboardEnhancements);
} else {
    initializeDashboardEnhancements();
}
