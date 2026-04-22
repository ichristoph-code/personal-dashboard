// ── Collapsible finance sections ──
// Persists collapsed state per section in localStorage.

function toggleFinSection(sectionId) {
    var section = document.getElementById(sectionId);
    if (!section) return;
    var header = section.querySelector('.fin-section-header');
    var body = section.querySelector('.fin-section-body');
    if (!header || !body) return;

    var isCollapsed = body.classList.contains('collapsed');
    if (isCollapsed) {
        body.classList.remove('collapsed');
        header.classList.remove('collapsed');
    } else {
        body.classList.add('collapsed');
        header.classList.add('collapsed');
    }

    // Persist state
    try {
        var key = 'fin-section-' + sectionId;
        localStorage.setItem(key, isCollapsed ? 'open' : 'closed');
    } catch(e) {}
}

function restoreFinSections() {
    document.querySelectorAll('.fin-section').forEach(function(section) {
        var id = section.id;
        if (!id) return;
        try {
            var state = localStorage.getItem('fin-section-' + id);
            var header = section.querySelector('.fin-section-header');
            var body = section.querySelector('.fin-section-body');
            if (!header || !body) return;
            if (state === 'closed') {
                body.classList.add('collapsed');
                header.classList.add('collapsed');
            } else if (state === 'open') {
                body.classList.remove('collapsed');
                header.classList.remove('collapsed');
            }
            // If no saved state, keep default from HTML
        } catch(e) {}
    });
}

// ── Additional chart instances ──
var bvaChartInstance = null;
var trendChartInstance = null;
var payeesChartInstance = null;
var nwChartInstance = null;

function initFinancialCharts() {
    var colors = getThemeColors();

    // ── Budget vs Actual (grouped horizontal bar) ──
    var bvaCanvas = document.getElementById('bvaChart');
    if (bvaCanvas && typeof __BVA_NAMES__ !== 'undefined' && __BVA_NAMES__.length > 0) {
        var bvaCtx = bvaCanvas.getContext('2d');
        bvaChartInstance = new Chart(bvaCtx, {
            type: 'bar',
            data: {
                labels: __BVA_NAMES__,
                datasets: [
                    {
                        label: 'Budgeted',
                        data: __BVA_BUDGETED__,
                        backgroundColor: colors.bvaBudgeted || 'rgba(160, 174, 192, 0.5)',
                        borderRadius: 4,
                        borderSkipped: false
                    },
                    {
                        label: 'Spent',
                        data: __BVA_SPENT__,
                        // Color red if over budget, accent if under
                        backgroundColor: __BVA_SPENT__.map(function(spent, i) {
                            return spent > __BVA_BUDGETED__[i]
                                ? 'rgba(229, 62, 62, 0.75)'
                                : (colors.barGradientStart || 'rgba(102, 126, 234, 0.75)');
                        }),
                        borderRadius: 4,
                        borderSkipped: false
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: {
                        labels: { color: colors.textMuted, usePointStyle: true, pointStyle: 'circle' }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                return ctx.dataset.label + ': $' + ctx.parsed.x.toLocaleString(undefined, {maximumFractionDigits: 0});
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: { color: colors.grid },
                        ticks: {
                            color: colors.textMuted,
                            callback: function(v) { return '$' + v.toLocaleString(); }
                        }
                    },
                    y: { grid: { display: false }, ticks: { color: colors.textMuted, font: { size: 11 } } }
                }
            }
        });
    }

    // ── Monthly Income vs Spending Trend (line chart) ──
    var trendCanvas = document.getElementById('trendChart');
    if (trendCanvas && typeof __TREND_LABELS__ !== 'undefined' && __TREND_LABELS__.length > 0) {
        var trendCtx = trendCanvas.getContext('2d');
        trendChartInstance = new Chart(trendCtx, {
            type: 'line',
            data: {
                labels: __TREND_LABELS__,
                datasets: [
                    {
                        label: 'Income',
                        data: __TREND_INCOME__,
                        borderColor: 'rgba(72, 187, 120, 0.9)',
                        backgroundColor: 'rgba(72, 187, 120, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    },
                    {
                        label: 'Spending',
                        data: __TREND_SPENDING__,
                        borderColor: 'rgba(229, 62, 62, 0.9)',
                        backgroundColor: 'rgba(229, 62, 62, 0.1)',
                        fill: true,
                        tension: 0.3,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: colors.textMuted, usePointStyle: true, pointStyle: 'circle' }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                return ctx.dataset.label + ': $' + ctx.parsed.y.toLocaleString(undefined, {maximumFractionDigits: 0});
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: colors.grid },
                        ticks: { color: colors.textMuted }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: colors.grid },
                        ticks: {
                            color: colors.textMuted,
                            callback: function(v) { return '$' + v.toLocaleString(); }
                        }
                    }
                }
            }
        });
    }

    // ── Top Payees (horizontal bar) ──
    var payeesCanvas = document.getElementById('payeesChart');
    if (payeesCanvas && typeof __PAYEE_NAMES__ !== 'undefined' && __PAYEE_NAMES__.length > 0) {
        var payCtx = payeesCanvas.getContext('2d');
        var payGrad = payCtx.createLinearGradient(0, 0, payeesCanvas.width, 0);
        payGrad.addColorStop(0, colors.barGradientStart);
        payGrad.addColorStop(1, colors.barGradientEnd);

        payeesChartInstance = new Chart(payCtx, {
            type: 'bar',
            data: {
                labels: __PAYEE_NAMES__,
                datasets: [{
                    label: 'Total Spent',
                    data: __PAYEE_AMOUNTS__,
                    backgroundColor: payGrad,
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                indexAxis: 'y',
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                return '$' + ctx.parsed.x.toLocaleString(undefined, {maximumFractionDigits: 0});
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        beginAtZero: true,
                        grid: { color: colors.grid },
                        ticks: {
                            color: colors.textMuted,
                            callback: function(v) { return '$' + v.toLocaleString(); }
                        }
                    },
                    y: { grid: { display: false }, ticks: { color: colors.textMuted, font: { size: 11 } } }
                }
            }
        });
    }

    // ── Net Worth Over Time (line chart) ──
    var nwCanvas = document.getElementById('nwChart');
    if (nwCanvas && typeof __NW_HISTORY__ !== 'undefined' && __NW_HISTORY__.length > 0) {
        var nwCtx = nwCanvas.getContext('2d');

        // Build gradient fill
        var nwGrad = nwCtx.createLinearGradient(0, 0, 0, nwCanvas.height);
        nwGrad.addColorStop(0, 'rgba(102, 126, 234, 0.25)');
        nwGrad.addColorStop(1, 'rgba(102, 126, 234, 0.02)');

        var nwLabels = __NW_HISTORY__.map(function(d) {
            // Format "2025-02-27" -> "Feb 27"
            var parts = d.date.split('-');
            var dt = new Date(parts[0], parts[1] - 1, parts[2]);
            return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        });
        var nwValues = __NW_HISTORY__.map(function(d) { return d.value; });

        nwChartInstance = new Chart(nwCtx, {
            type: 'line',
            data: {
                labels: nwLabels,
                datasets: [{
                    label: 'Net Worth',
                    data: nwValues,
                    borderColor: colors.barGradientStart || 'rgba(102, 126, 234, 0.9)',
                    backgroundColor: nwGrad,
                    fill: true,
                    tension: 0.3,
                    pointRadius: nwValues.length > 30 ? 0 : 3,
                    pointHoverRadius: 5,
                    borderWidth: 2.5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                return 'Net Worth: $' + ctx.parsed.y.toLocaleString(undefined, {maximumFractionDigits: 0});
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: colors.grid },
                        ticks: {
                            color: colors.textMuted,
                            maxTicksLimit: 12,
                            maxRotation: 0
                        }
                    },
                    y: {
                        grid: { color: colors.grid },
                        ticks: {
                            color: colors.textMuted,
                            callback: function(v) { return '$' + v.toLocaleString(); }
                        }
                    }
                }
            }
        });
    }
}

// ── Theme update for new charts ──
function updateFinancialChartTheme() {
    var colors = getThemeColors();

    if (bvaChartInstance) {
        bvaChartInstance.options.plugins.legend.labels.color = colors.textMuted;
        bvaChartInstance.options.scales.x.grid.color = colors.grid;
        bvaChartInstance.options.scales.x.ticks.color = colors.textMuted;
        bvaChartInstance.options.scales.y.ticks.color = colors.textMuted;
        // Re-color spent bars
        if (typeof __BVA_BUDGETED__ !== 'undefined') {
            bvaChartInstance.data.datasets[0].backgroundColor = 'rgba(160, 174, 192, 0.5)';
            bvaChartInstance.data.datasets[1].backgroundColor = __BVA_SPENT__.map(function(spent, i) {
                return spent > __BVA_BUDGETED__[i]
                    ? 'rgba(229, 62, 62, 0.75)'
                    : (colors.barGradientStart || 'rgba(102, 126, 234, 0.75)');
            });
        }
        bvaChartInstance.update();
    }

    if (trendChartInstance) {
        trendChartInstance.options.scales.x.grid.color = colors.grid;
        trendChartInstance.options.scales.x.ticks.color = colors.textMuted;
        trendChartInstance.options.scales.y.grid.color = colors.grid;
        trendChartInstance.options.scales.y.ticks.color = colors.textMuted;
        trendChartInstance.options.plugins.legend.labels.color = colors.textMuted;
        trendChartInstance.update();
    }

    if (payeesChartInstance) {
        var payCanvas = document.getElementById('payeesChart');
        if (payCanvas) {
            var pCtx = payCanvas.getContext('2d');
            var pGrad = pCtx.createLinearGradient(0, 0, payCanvas.width, 0);
            pGrad.addColorStop(0, colors.barGradientStart);
            pGrad.addColorStop(1, colors.barGradientEnd);
            payeesChartInstance.data.datasets[0].backgroundColor = pGrad;
        }
        payeesChartInstance.options.scales.x.grid.color = colors.grid;
        payeesChartInstance.options.scales.x.ticks.color = colors.textMuted;
        payeesChartInstance.options.scales.y.ticks.color = colors.textMuted;
        payeesChartInstance.update();
    }

    if (nwChartInstance) {
        var nwCanvas = document.getElementById('nwChart');
        if (nwCanvas) {
            var nCtx = nwCanvas.getContext('2d');
            var nGrad = nCtx.createLinearGradient(0, 0, 0, nwCanvas.height);
            nGrad.addColorStop(0, 'rgba(102, 126, 234, 0.25)');
            nGrad.addColorStop(1, 'rgba(102, 126, 234, 0.02)');
            nwChartInstance.data.datasets[0].backgroundColor = nGrad;
            nwChartInstance.data.datasets[0].borderColor = colors.barGradientStart || 'rgba(102, 126, 234, 0.9)';
        }
        nwChartInstance.options.scales.x.grid.color = colors.grid;
        nwChartInstance.options.scales.x.ticks.color = colors.textMuted;
        nwChartInstance.options.scales.y.grid.color = colors.grid;
        nwChartInstance.options.scales.y.ticks.color = colors.textMuted;
        nwChartInstance.update();
    }
}

// ── Claude financial chat ──
function sendClaudeQuery() {
    var input = document.getElementById('claudeChatInput');
    var sendBtn = document.getElementById('claudeChatSend');
    var messages = document.getElementById('claudeChatMessages');
    if (!input || !messages) return;

    var question = input.value.trim();
    if (!question) return;

    // Remove welcome message if present
    var welcome = messages.querySelector('.claude-chat-welcome');
    if (welcome) welcome.remove();

    // Add user message
    var userMsg = document.createElement('div');
    userMsg.className = 'claude-chat-msg user';
    userMsg.textContent = question;
    messages.appendChild(userMsg);

    // Clear input and disable send
    input.value = '';
    if (sendBtn) sendBtn.disabled = true;

    // Add loading indicator
    var loadingMsg = document.createElement('div');
    loadingMsg.className = 'claude-chat-msg assistant loading';
    loadingMsg.textContent = 'Thinking...';
    messages.appendChild(loadingMsg);
    messages.scrollTop = messages.scrollHeight;

    // POST to /claude-query
    fetch('/claude-query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: question })
    })
    .then(function(resp) { return resp.json(); })
    .then(function(data) {
        loadingMsg.remove();
        var reply = document.createElement('div');
        reply.className = 'claude-chat-msg assistant';
        if (data.html) {
            reply.innerHTML = data.html;
        } else {
            reply.textContent = data.error || 'Sorry, something went wrong.';
        }
        messages.appendChild(reply);
        messages.scrollTop = messages.scrollHeight;
    })
    .catch(function(err) {
        loadingMsg.remove();
        var errMsg = document.createElement('div');
        errMsg.className = 'claude-chat-msg assistant';
        errMsg.textContent = 'Error: could not reach the server. Make sure the dashboard is running with --serve.';
        messages.appendChild(errMsg);
        messages.scrollTop = messages.scrollHeight;
    })
    .finally(function() {
        if (sendBtn) sendBtn.disabled = false;
        input.focus();
    });
}

// ── Generic section drag-to-reorder (works for any panel with .fin-section) ──
var _sectionDragFromHandle = false;

function _initPanelDrag(panelId, storageKey) {
    var panel = document.getElementById(panelId);
    if (!panel) return;
    var sections = panel.querySelectorAll('.fin-section[data-section-id]');
    if (sections.length < 2) return;

    var draggedSection = null;

    panel.addEventListener('mousedown', function(e) {
        _sectionDragFromHandle = !!e.target.closest('.fin-drag-handle');
    });
    document.addEventListener('mouseup', function() {
        _sectionDragFromHandle = false;
    });

    sections.forEach(function(section) {
        section.addEventListener('dragstart', function(e) {
            if (!_sectionDragFromHandle) {
                e.preventDefault();
                return;
            }
            draggedSection = section;
            section.classList.add('fin-dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', section.dataset.sectionId);
        });

        section.addEventListener('dragend', function() {
            section.classList.remove('fin-dragging');
            draggedSection = null;
            _sectionDragFromHandle = false;
            panel.querySelectorAll('.fin-section').forEach(function(s) {
                s.classList.remove('fin-drag-over');
            });
        });

        section.addEventListener('dragover', function(e) {
            if (!draggedSection || draggedSection === section) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            panel.querySelectorAll('.fin-section').forEach(function(s) {
                s.classList.remove('fin-drag-over');
            });
            section.classList.add('fin-drag-over');
        });

        section.addEventListener('dragleave', function() {
            section.classList.remove('fin-drag-over');
        });

        section.addEventListener('drop', function(e) {
            e.preventDefault();
            section.classList.remove('fin-drag-over');
            if (!draggedSection || draggedSection === section) return;
            var allSections = Array.from(panel.querySelectorAll('.fin-section[data-section-id]'));
            var fromIdx = allSections.indexOf(draggedSection);
            var toIdx = allSections.indexOf(section);
            if (fromIdx < toIdx) {
                section.parentNode.insertBefore(draggedSection, section.nextSibling);
            } else {
                section.parentNode.insertBefore(draggedSection, section);
            }
            _savePanelOrder(panelId, storageKey);
        });
    });
}

function _savePanelOrder(panelId, storageKey) {
    var panel = document.getElementById(panelId);
    if (!panel) return;
    var order = [];
    panel.querySelectorAll('.fin-section[data-section-id]').forEach(function(section) {
        order.push(section.dataset.sectionId);
    });
    try { localStorage.setItem(storageKey, JSON.stringify(order)); } catch(e) {}
}

function _applyPanelOrder(panelId, storageKey) {
    try {
        var order = JSON.parse(localStorage.getItem(storageKey) || '[]');
        if (!order.length) return;
        var panel = document.getElementById(panelId);
        if (!panel) return;
        var sectionMap = {};
        panel.querySelectorAll('.fin-section[data-section-id]').forEach(function(section) {
            sectionMap[section.dataset.sectionId] = section;
        });
        var inserted = {};
        order.forEach(function(id) {
            if (sectionMap[id]) {
                panel.appendChild(sectionMap[id]);
                inserted[id] = true;
            }
        });
        // Append any new sections not in saved order
        Object.keys(sectionMap).forEach(function(id) {
            if (!inserted[id]) {
                panel.appendChild(sectionMap[id]);
            }
        });
    } catch(e) {}
}

// Backward-compatible wrappers for Financial tab
var FIN_ORDER_KEY = 'dashboard-fin-order';
function initFinDrag() { _initPanelDrag('panel-financials', FIN_ORDER_KEY); }
function saveFinOrder() { _savePanelOrder('panel-financials', FIN_ORDER_KEY); }
function applyFinOrder() { _applyPanelOrder('panel-financials', FIN_ORDER_KEY); }

// System tab drag/order
var SYS_ORDER_KEY = 'dashboard-sys-order';
function initSysDrag() { _initPanelDrag('panel-system', SYS_ORDER_KEY); }
function applySysOrder() { _applyPanelOrder('panel-system', SYS_ORDER_KEY); }

// ── Wire up header click-to-collapse (excluding drag handle) ──
function initFinHeaders() {
    document.querySelectorAll('.fin-section-header').forEach(function(header) {
        header.addEventListener('click', function(e) {
            // Don't toggle when clicking the drag handle
            if (e.target.closest('.fin-drag-handle')) return;
            var section = header.closest('.fin-section');
            if (section && section.id) toggleFinSection(section.id);
        });
    });
}

// ── Restore section states and order on load ──
function _initFinAll() {
    restoreFinSections();
    applyFinOrder();
    applySysOrder();
    initFinHeaders();
    initFinDrag();
    initSysDrag();
}

// Run immediately if DOM already parsed, otherwise wait for event
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _initFinAll);
} else {
    _initFinAll();
}
