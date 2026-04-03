var chartsInitialized = false;
var newsSectionsHeightSet = false;
var SCROLL_POS_KEY = 'dashboard-scroll-pos';

function _saveScrollPos(tabName) {
    try {
        var state = JSON.parse(localStorage.getItem(SCROLL_POS_KEY) || '{}');
        state[tabName] = window.scrollY;
        localStorage.setItem(SCROLL_POS_KEY, JSON.stringify(state));
    } catch(e) {}
}

function _restoreScrollPos(tabName) {
    try {
        var state = JSON.parse(localStorage.getItem(SCROLL_POS_KEY) || '{}');
        var pos = state[tabName];
        if (pos !== undefined && pos > 0) {
            requestAnimationFrame(function() { window.scrollTo(0, pos); });
        }
    } catch(e) {}
}

function switchTab(tabName) {
    // Save scroll position of outgoing tab
    var currentBtn = document.querySelector('.tab-btn.active');
    if (currentBtn && currentBtn.dataset.tab) {
        _saveScrollPos(currentBtn.dataset.tab);
    }
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(function(btn) {
        btn.classList.toggle('active', btn.dataset.tab === tabName);
    });
    // Update panels
    document.querySelectorAll('.tab-panel').forEach(function(panel) {
        panel.classList.remove('active');
    });
    document.getElementById('panel-' + tabName).classList.add('active');
    // Restore scroll position for incoming tab
    _restoreScrollPos(tabName);
    // Always reset privacy blur when switching to financials or today
    if (tabName === 'financials' && typeof initPrivacy === 'function') initPrivacy();
    if (tabName === 'today' && typeof initTodayFinancePrivacy === 'function') initTodayFinancePrivacy();
    // Lazy-init charts when financials first shown
    if (tabName === 'financials' && !chartsInitialized) {
        chartsInitialized = true;
        setTimeout(function() {
            initCharts();
            if (typeof initFinancialCharts === 'function') initFinancialCharts();
        }, 50);
    }
    // Fix max-height on open news sections the first time news tab is shown
    if (tabName === 'news' && !newsSectionsHeightSet) {
        newsSectionsHeightSet = true;
        document.querySelectorAll('.news-section-body:not(.collapsed)').forEach(function(body) {
            body.style.maxHeight = body.scrollHeight + 'px';
        });
    }
    // Save preference
    try { localStorage.setItem('dashboard-tab', tabName); } catch(e) {}
}

function initCharts() {
    var colors = getThemeColors();

    // ── Pie chart ──
    pieChartInstance = new Chart(document.getElementById('accountChart').getContext('2d'), {
        type: 'pie',
        data: {
            labels: __PIE_NAMES__,
            datasets: [{
                data: __PIE_BALANCES__,
                backgroundColor: __PIE_BG__,
                borderColor: __PIE_BORDER__,
                borderWidth: 2,
                hoverOffset: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        padding: 14,
                        usePointStyle: true,
                        pointStyle: 'circle',
                        font: { size: 12 },
                        color: colors.textMuted
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            var v = ctx.parsed;
                            var t = ctx.dataset.data.reduce(function(a,b){ return a+b; }, 0);
                            var p = ((v / t) * 100).toFixed(1);
                            return ctx.label + ': $' + v.toLocaleString(undefined, {maximumFractionDigits:0}) + ' (' + p + '%)';
                        }
                    }
                }
            }
        }
    });

    // ── Bar chart with gradient fill and rounded bars ──
    var barCanvas = document.getElementById('categoryChart');
    var barCtx = barCanvas.getContext('2d');
    var barGradient = barCtx.createLinearGradient(0, 0, barCanvas.width, 0);
    barGradient.addColorStop(0, colors.barGradientStart);
    barGradient.addColorStop(1, colors.barGradientEnd);

    barChartInstance = new Chart(barCtx, {
        type: 'bar',
        data: {
            labels: __CAT_NAMES__,
            datasets: [{
                label: 'Spending ($)',
                data: __CAT_ACTIVITY__,
                backgroundColor: barGradient,
                borderColor: 'transparent',
                borderWidth: 0,
                borderRadius: 6,
                borderSkipped: false
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            indexAxis: 'y',
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(ctx) {
                            return '$' + ctx.parsed.x.toLocaleString(undefined, {maximumFractionDigits:0});
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
                        callback: function(value) { return '$' + value.toLocaleString(); }
                    }
                },
                y: { grid: { display: false }, ticks: { color: colors.textMuted } }
            }
        }
    });
}
