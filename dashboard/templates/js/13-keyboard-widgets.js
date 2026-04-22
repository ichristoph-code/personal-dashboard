// Keyboard shortcuts: 1-0 for tabs, D for dark mode, R for refresh, P for pomodoro, ? for help
var TAB_NAMES = ['today','calendar','tasks','email','news','imessage','financials','notes','contacts','system'];
document.addEventListener('keydown', function(e) {
    // Close shortcut overlay on Escape
    if (e.key === 'Escape') {
        var overlay = document.getElementById('shortcutOverlay');
        if (overlay && overlay.classList.contains('open')) {
            overlay.classList.remove('open');
            return;
        }
    }
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
    // Number keys: 1-9 map to tabs 0-8, 0 maps to tab 9 (System)
    if (e.key === '0') {
        switchTab(TAB_NAMES[9]);
    } else {
        var idx = parseInt(e.key) - 1;
        if (idx >= 0 && idx < TAB_NAMES.length) switchTab(TAB_NAMES[idx]);
    }
    if (e.key === 'd' || e.key === 'D') toggleTheme();
    if (e.key === 'r' || e.key === 'R') {
        var btn = document.querySelector('.refresh-btn:not(.app-launcher-trigger)');
        if (btn && !btn.classList.contains('refreshing')) refreshDashboard(btn);
    }
    if (e.key === 'p' || e.key === 'P') {
        if (typeof togglePomodoro === 'function') togglePomodoro();
    }
    if (e.key === '?') toggleShortcutOverlay();
});

// ── Keyboard Shortcut Help Overlay ──
function toggleShortcutOverlay() {
    var overlay = document.getElementById('shortcutOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'shortcutOverlay';
        overlay.className = 'shortcut-overlay';
        overlay.innerHTML =
            '<div class="shortcut-modal">'
            + '<div class="shortcut-modal-header">'
            + '<h2>Keyboard Shortcuts</h2>'
            + '<button class="shortcut-close-btn" onclick="toggleShortcutOverlay()">&times;</button>'
            + '</div>'
            + '<div class="shortcut-grid">'
            + '<div class="shortcut-section">'
            + '<h3>Navigation</h3>'
            + '<div class="shortcut-row"><kbd>1</kbd><span>Today</span></div>'
            + '<div class="shortcut-row"><kbd>2</kbd><span>Calendar</span></div>'
            + '<div class="shortcut-row"><kbd>3</kbd><span>Tasks</span></div>'
            + '<div class="shortcut-row"><kbd>4</kbd><span>Email</span></div>'
            + '<div class="shortcut-row"><kbd>5</kbd><span>News</span></div>'
            + '<div class="shortcut-row"><kbd>6</kbd><span>iMessage</span></div>'
            + '<div class="shortcut-row"><kbd>7</kbd><span>Financials</span></div>'
            + '<div class="shortcut-row"><kbd>8</kbd><span>Notes</span></div>'
            + '<div class="shortcut-row"><kbd>9</kbd><span>Contacts</span></div>'
            + '<div class="shortcut-row"><kbd>0</kbd><span>System</span></div>'
            + '</div>'
            + '<div class="shortcut-section">'
            + '<h3>Actions</h3>'
            + '<div class="shortcut-row"><kbd>D</kbd><span>Toggle dark mode</span></div>'
            + '<div class="shortcut-row"><kbd>R</kbd><span>Refresh dashboard</span></div>'
            + '<div class="shortcut-row"><kbd>P</kbd><span>Start/pause Pomodoro</span></div>'
            + '<div class="shortcut-row"><kbd>?</kbd><span>Show this help</span></div>'
            + '<div class="shortcut-row"><kbd>Esc</kbd><span>Close overlay</span></div>'
            + '</div>'
            + '</div>'
            + '</div>';
        overlay.addEventListener('click', function(e) {
            if (e.target === overlay) toggleShortcutOverlay();
        });
        document.body.appendChild(overlay);
        // Trigger animation on next frame
        requestAnimationFrame(function() { overlay.classList.add('open'); });
        return;
    }
    if (overlay.classList.contains('open')) {
        overlay.classList.remove('open');
    } else {
        overlay.classList.add('open');
    }
}

// ── Loading Skeleton on Refresh ──
function _showRefreshToast(msg) {
    var toast = document.createElement('div');
    toast.textContent = msg;
    toast.style.cssText = 'position:fixed;bottom:24px;left:50%;transform:translateX(-50%);'
        + 'background:rgba(220,53,69,0.92);color:#fff;padding:10px 22px;border-radius:8px;'
        + 'font-size:14px;z-index:99999;box-shadow:0 4px 12px rgba(0,0,0,0.3);'
        + 'transition:opacity 0.4s;pointer-events:none;';
    document.body.appendChild(toast);
    setTimeout(function() { toast.style.opacity = '0'; }, 4000);
    setTimeout(function() { toast.remove(); }, 4500);
}

var _refreshInProgress = false;
var _activeRefreshTimeout = null;

function _cleanupRefresh(btn) {
    _refreshInProgress = false;
    btn.classList.remove('refreshing');
    if (_activeRefreshTimeout) {
        clearTimeout(_activeRefreshTimeout);
        _activeRefreshTimeout = null;
    }
    var sk = document.querySelector('.skeleton-overlay');
    if (sk) sk.remove();
}

// Apply fetched tab data to the DOM
function _applyTabData(activeTab, data, btn) {
    var panel = document.getElementById('panel-' + activeTab);
    if (panel && data.html) panel.innerHTML = data.html;
    _updateHeader(data.header);
    _updateBadges(data.badges);
    _setInlineData(activeTab, data);
    if (activeTab === 'financials' && data.chartData) {
        _updateChartGlobals(data.chartData);
        _reinitCharts();
    }
    _reinitTab(activeTab);
    if (data.generated_at) {
        GENERATED_AT = data.generated_at;
        if (typeof updateTimestamp === 'function') updateTimestamp();
    }
    _updateFooter(data);
    _cleanupRefresh(btn);
    // Restore scroll position after the panel HTML has been replaced
    if (typeof _restoreScrollPos === 'function') {
        requestAnimationFrame(function() { _restoreScrollPos(activeTab); });
    }
}

function refreshDashboard(btn) {
    if (_refreshInProgress || btn.classList.contains('refreshing')) return;
    _refreshInProgress = true;
    btn.classList.add('refreshing');

    var activeTab = localStorage.getItem('dashboard-tab') || 'today';

    // Save scroll position before refresh
    if (typeof _saveScrollPos === 'function') _saveScrollPos(activeTab);

    // Show skeleton overlay on the active panel
    var activePanel = document.querySelector('.tab-panel.active');
    if (activePanel) {
        var skeleton = document.createElement('div');
        skeleton.className = 'skeleton-overlay';
        skeleton.innerHTML =
            '<div class="skeleton-line skeleton-line-wide"></div>'
            + '<div class="skeleton-line skeleton-line-medium"></div>'
            + '<div class="skeleton-line skeleton-line-short"></div>'
            + '<div class="skeleton-line skeleton-line-wide"></div>'
            + '<div class="skeleton-line skeleton-line-medium"></div>';
        activePanel.appendChild(skeleton);
        requestAnimationFrame(function() { skeleton.classList.add('active'); });
    }

    // Hard timeout safety net — guarantees cleanup no matter what
    _activeRefreshTimeout = setTimeout(function() {
        if (_refreshInProgress) {
            _cleanupRefresh(btn);
            _showRefreshToast('Refresh timed out — try again');
        }
    }, 90000);

    // AJAX in-place update with single retry on failure
    fetch('/api/tab/' + encodeURIComponent(activeTab))
        .then(function(resp) {
            if (!resp.ok) throw new Error('Server returned ' + resp.status);
            return resp.json();
        })
        .then(function(data) {
            _applyTabData(activeTab, data, btn);
        })
        .catch(function(err) {
            console.warn('AJAX refresh failed, retrying in 2s...', err);
            setTimeout(function() {
                fetch('/api/tab/' + encodeURIComponent(activeTab))
                    .then(function(resp) {
                        if (!resp.ok) throw new Error('Retry failed: ' + resp.status);
                        return resp.json();
                    })
                    .then(function(data) {
                        _applyTabData(activeTab, data, btn);
                    })
                    .catch(function(retryErr) {
                        console.error('Refresh retry failed:', retryErr);
                        _cleanupRefresh(btn);
                        _showRefreshToast('Refresh failed — try again');
                    });
            }, 2000);
        });
}

// ── AJAX refresh helper functions ──

function _updateHeader(header) {
    if (!header) return;
    var greetEl = document.querySelector('.greeting');
    if (greetEl && header.greeting) greetEl.textContent = header.greeting;

    var dateEl = document.querySelector('.header-date');
    if (dateEl && header.date) dateEl.textContent = header.date;

    var timeEl = document.getElementById('headerTime');
    if (timeEl && header.time) timeEl.textContent = 'Updated ' + header.time;

    // Weather widget
    var oldWeather = document.querySelector('.weather-widget');
    if (header.weather_widget) {
        if (oldWeather) {
            oldWeather.outerHTML = header.weather_widget;
        } else {
            var meta = document.querySelector('.header-meta');
            if (meta) meta.insertAdjacentHTML('beforeend', header.weather_widget);
        }
    } else if (oldWeather) {
        oldWeather.remove();
    }

    // Next event pill
    var oldPill = document.querySelector('.next-event-pill');
    if (oldPill) oldPill.remove();
    if (header.next_event) {
        var headerDiv = document.querySelector('.top-bar-inner > div:first-child');
        if (headerDiv) headerDiv.insertAdjacentHTML('beforeend', header.next_event);
    }
}

function _updateBadges(badges) {
    if (!badges) return;
    var map = { tasks: 'tasks', email: 'email', imessage: 'imessage', contacts: 'contacts' };
    Object.keys(map).forEach(function(key) {
        var btn = document.querySelector('[data-tab="' + map[key] + '"]');
        if (!btn) return;
        var existing = btn.querySelector('.tab-badge');
        var count = badges[key] || 0;
        if (count > 0) {
            if (existing) {
                existing.textContent = count;
            } else {
                btn.insertAdjacentHTML('beforeend',
                    '<span class="tab-badge">' + count + '</span>');
            }
        } else if (existing) {
            existing.remove();
        }
    });
}

function _updateChartGlobals(chartData) {
    if (!chartData) return;
    if (chartData.pieNames !== undefined) __PIE_NAMES__ = chartData.pieNames;
    if (chartData.pieBalances !== undefined) __PIE_BALANCES__ = chartData.pieBalances;
    if (chartData.pieBg !== undefined) __PIE_BG__ = chartData.pieBg;
    if (chartData.pieBorder !== undefined) __PIE_BORDER__ = chartData.pieBorder;
    if (chartData.catNames !== undefined) __CAT_NAMES__ = chartData.catNames;
    if (chartData.catActivity !== undefined) __CAT_ACTIVITY__ = chartData.catActivity;
    if (chartData.bvaNames !== undefined) __BVA_NAMES__ = chartData.bvaNames;
    if (chartData.bvaBudgeted !== undefined) __BVA_BUDGETED__ = chartData.bvaBudgeted;
    if (chartData.bvaSpent !== undefined) __BVA_SPENT__ = chartData.bvaSpent;
    if (chartData.trendLabels !== undefined) __TREND_LABELS__ = chartData.trendLabels;
    if (chartData.trendIncome !== undefined) __TREND_INCOME__ = chartData.trendIncome;
    if (chartData.trendSpending !== undefined) __TREND_SPENDING__ = chartData.trendSpending;
    if (chartData.payeeNames !== undefined) __PAYEE_NAMES__ = chartData.payeeNames;
    if (chartData.payeeAmounts !== undefined) __PAYEE_AMOUNTS__ = chartData.payeeAmounts;
    if (chartData.nwHistory !== undefined) __NW_HISTORY__ = chartData.nwHistory;
}

function _reinitCharts() {
    // Destroy all existing chart instances
    if (typeof pieChartInstance !== 'undefined' && pieChartInstance) {
        pieChartInstance.destroy(); pieChartInstance = null;
    }
    if (typeof barChartInstance !== 'undefined' && barChartInstance) {
        barChartInstance.destroy(); barChartInstance = null;
    }
    if (typeof bvaChartInstance !== 'undefined' && bvaChartInstance) {
        bvaChartInstance.destroy(); bvaChartInstance = null;
    }
    if (typeof trendChartInstance !== 'undefined' && trendChartInstance) {
        trendChartInstance.destroy(); trendChartInstance = null;
    }
    if (typeof payeesChartInstance !== 'undefined' && payeesChartInstance) {
        payeesChartInstance.destroy(); payeesChartInstance = null;
    }
    if (typeof nwChartInstance !== 'undefined' && nwChartInstance) {
        nwChartInstance.destroy(); nwChartInstance = null;
    }
    // Reset init flag and re-create
    chartsInitialized = true;
    initCharts();
    if (typeof initFinancialCharts === 'function') initFinancialCharts();
}

function _setInlineData(tabName, data) {
    // Scripts embedded in innerHTML don't execute, so set globals manually
    if (tabName === 'calendar' && data.calendarData) {
        if (data.calendarData.eventsJson !== undefined)
            window.CALENDAR_EVENTS = data.calendarData.eventsJson;
        if (data.calendarData.weatherForecast !== undefined)
            window.WEATHER_FORECAST = data.calendarData.weatherForecast;
        if (data.calendarData.calendarList !== undefined)
            window.CALENDAR_LIST = data.calendarData.calendarList;
    }
    if (tabName === 'notes' && data.notesIndex !== undefined) {
        window.ANOTES_INDEX = data.notesIndex;
        window._currentNoteId = null;
    }
    if (tabName === 'email' && data.mailFolders !== undefined) {
        window.MAIL_MOVE_FOLDERS = data.mailFolders;
    }
    if (tabName === 'contacts' && data.contactsIndex !== undefined) {
        window.CONTACTS_INDEX = data.contactsIndex;
    }
}

function _reinitTab(tabName) {
    switch(tabName) {
        case 'today':
            if (typeof initTodayFinancePrivacy === 'function') initTodayFinancePrivacy();
            break;
        case 'calendar':
            // Re-init calendar view state and restore saved view preference
            if (typeof initCalView === 'function') initCalView();
            break;
        case 'tasks':
            if (typeof applyDeletedTasks === 'function') applyDeletedTasks();
            if (typeof applyCompletedTasks === 'function') applyCompletedTasks();
            if (typeof injectPendingTasks === 'function') injectPendingTasks();
            if (typeof applyWidgetOrder === 'function') applyWidgetOrder();
            if (typeof initWidgetDrag === 'function') initWidgetDrag();
            if (typeof renderWeeklySummary === 'function') renderWeeklySummary();
            break;
        case 'email':
            // Mail uses mostly inline onclick and delegated events
            break;
        case 'news':
            if (typeof initNewsState === 'function') initNewsState();
            if (typeof applyNewsOrder === 'function') applyNewsOrder();
            if (typeof initNewsSections === 'function') initNewsSections();
            if (typeof initNewsDrag === 'function') initNewsDrag();
            newsSectionsHeightSet = false;
            // Fix max-height on open sections
            document.querySelectorAll('.news-section-body:not(.collapsed)').forEach(function(body) {
                body.style.maxHeight = body.scrollHeight + 'px';
            });
            newsSectionsHeightSet = true;
            break;
        case 'imessage':
            // Scroll active thread to bottom
            var active = document.querySelector('.imsg-thread.active .imsg-messages');
            if (active) active.scrollTop = active.scrollHeight;
            break;
        case 'financials':
            if (typeof restoreFinSections === 'function') restoreFinSections();
            if (typeof applyFinOrder === 'function') applyFinOrder();
            if (typeof initFinHeaders === 'function') initFinHeaders();
            if (typeof initFinDrag === 'function') initFinDrag();
            if (typeof initPrivacy === 'function') initPrivacy();
            break;
        case 'notes':
            if (typeof _initNotesDrag === 'function') _initNotesDrag();
            // Select first note
            var firstNote = document.querySelector('.anotes-item');
            if (firstNote && firstNote.dataset.nid && typeof selectNote === 'function') {
                selectNote(firstNote.dataset.nid);
            }
            break;
        case 'contacts':
            if (typeof initContactsList === 'function') initContactsList();
            break;
        case 'system':
            if (typeof applySysOrder === 'function') applySysOrder();
            if (typeof initSysDrag === 'function') initSysDrag();
            break;
    }
}

function _updateFooter(data) {
    var timeEl = document.querySelector('.footer-time');
    if (timeEl && data.header && data.header.time) {
        timeEl.textContent = 'Updated ' + data.header.time;
    }
    if (data.gen_elapsed !== undefined) {
        var genEl = document.querySelector('.footer-gen');
        if (genEl) genEl.textContent = 'Generated in ' + data.gen_elapsed + 's';
    }
}

// ── Auto-Refresh Timer (visibility-aware) ──
(function() {
    if (typeof AUTO_REFRESH_MINS === 'undefined' || AUTO_REFRESH_MINS <= 0) return;

    var _autoRefreshTimer = null;
    var _lastRefreshTime = Date.now();
    var _intervalMs = AUTO_REFRESH_MINS * 60 * 1000;

    function _triggerRefresh() {
        var btn = document.querySelector('.refresh-btn:not(.app-launcher-trigger)');
        if (btn && !_refreshInProgress) {
            _lastRefreshTime = Date.now();
            refreshDashboard(btn);
        }
    }

    function _startTimer() {
        if (_autoRefreshTimer) clearInterval(_autoRefreshTimer);
        _autoRefreshTimer = setInterval(_triggerRefresh, _intervalMs);
    }

    _startTimer();

    // Pause when hidden, refresh on return if stale
    document.addEventListener('visibilitychange', function() {
        if (document.hidden) {
            if (_autoRefreshTimer) {
                clearInterval(_autoRefreshTimer);
                _autoRefreshTimer = null;
            }
        } else {
            var elapsed = Date.now() - _lastRefreshTime;
            if (elapsed >= _intervalMs) {
                _triggerRefresh();
            }
            _startTimer();
        }
    });
})();

// ── Drag-to-Reorder Widget Cards ──
var WIDGET_ORDER_KEY = 'dashboard-widget-order';

function initWidgetDrag() {
    document.querySelectorAll('.tab-panel').forEach(function(panel) {
        var panelId = panel.id;
        var cards = panel.querySelectorAll(':scope > .card:not(.news-section-card), :scope > .cal-view-bar, :scope > .weekly-summary-card, :scope > .habits-card, :scope > .forecast-card');
        if (cards.length < 2) return; // Nothing to reorder

        var draggedCard = null;

        cards.forEach(function(card, idx) {
            // Add drag handle to card header
            if (!card.querySelector('.widget-drag-handle')) {
                var handle = document.createElement('span');
                handle.className = 'widget-drag-handle';
                handle.innerHTML = '&#x2807;';
                handle.title = 'Drag to reorder';
                // Insert at start of card
                var h3 = card.querySelector('h3');
                if (h3) {
                    h3.parentNode.insertBefore(handle, h3);
                } else {
                    card.insertBefore(handle, card.firstChild);
                }
            }
            card.setAttribute('draggable', 'true');
            card.dataset.widgetIdx = idx;

            card.addEventListener('dragstart', function(e) {
                if (!e.target.closest('.widget-drag-handle')) {
                    e.preventDefault();
                    return;
                }
                draggedCard = card;
                card.classList.add('widget-dragging');
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', idx);
            });
            card.addEventListener('dragend', function() {
                card.classList.remove('widget-dragging');
                panel.querySelectorAll('.card').forEach(function(c) { c.classList.remove('widget-drag-over'); });
                draggedCard = null;
            });
            card.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                if (card !== draggedCard && draggedCard) {
                    panel.querySelectorAll('.card').forEach(function(c) { c.classList.remove('widget-drag-over'); });
                    card.classList.add('widget-drag-over');
                }
            });
            card.addEventListener('dragleave', function() {
                card.classList.remove('widget-drag-over');
            });
            card.addEventListener('drop', function(e) {
                e.preventDefault();
                card.classList.remove('widget-drag-over');
                if (!draggedCard || draggedCard === card) return;
                var allCards = Array.from(panel.querySelectorAll(':scope > [draggable]'));
                var fromIdx = allCards.indexOf(draggedCard);
                var toIdx = allCards.indexOf(card);
                if (fromIdx < toIdx) {
                    panel.insertBefore(draggedCard, card.nextSibling);
                } else {
                    panel.insertBefore(draggedCard, card);
                }
                saveWidgetOrder(panelId);
            });
        });
    });
}

function saveWidgetOrder(panelId) {
    try {
        var order = JSON.parse(localStorage.getItem(WIDGET_ORDER_KEY) || '{}');
        var indices = [];
        var panel = document.getElementById(panelId);
        if (panel) {
            panel.querySelectorAll(':scope > [draggable]').forEach(function(card) {
                indices.push(card.dataset.widgetIdx || '0');
            });
        }
        order[panelId] = indices;
        localStorage.setItem(WIDGET_ORDER_KEY, JSON.stringify(order));
    } catch(e) {}
}

function applyWidgetOrder() {
    try {
        var order = JSON.parse(localStorage.getItem(WIDGET_ORDER_KEY) || '{}');
        Object.keys(order).forEach(function(panelId) {
            var panel = document.getElementById(panelId);
            if (!panel) return;
            var savedOrder = order[panelId];
            var cards = panel.querySelectorAll(':scope > [draggable]');
            var cardMap = {};
            cards.forEach(function(card) {
                cardMap[card.dataset.widgetIdx] = card;
            });
            savedOrder.forEach(function(idx) {
                if (cardMap[idx]) panel.appendChild(cardMap[idx]);
            });
        });
    } catch(e) {}
}

applyWidgetOrder();
initWidgetDrag();
initPrivacy();
initTodayFinancePrivacy();

// One-time migration: clear saved tab when new tabs are added so the
// HTML default ('today') takes effect instead of the stale saved value.
(function() {
    var _TAB_VERSION = 2;  // bump this when tab layout changes
    var savedVer = parseInt(localStorage.getItem('dashboard-tab-version') || '1');
    if (savedVer < _TAB_VERSION) {
        localStorage.removeItem('dashboard-tab');
        localStorage.setItem('dashboard-tab-version', String(_TAB_VERSION));
    }
})();

// Restore last tab — DEFAULT_TAB from --tab flag overrides on first load
// Default is now 'today' instead of 'calendar'
(function() {
    try {
        var saved = localStorage.getItem('dashboard-tab');
        var targetTab;
        if (typeof DEFAULT_TAB !== 'undefined' && DEFAULT_TAB) {
            // CLI --tab flag: use it once, then clear
            targetTab = DEFAULT_TAB;
        } else if (saved && TAB_NAMES.indexOf(saved) !== -1) {
            targetTab = saved;
        }
        if (targetTab) {
            switchTab(targetTab);
            // Restore scroll position after layout settles
            requestAnimationFrame(function() {
                if (typeof _restoreScrollPos === 'function') _restoreScrollPos(targetTab);
            });
        }
    } catch(e) {}
})();

// ── Auto-refresh on stale first load ──
(function() {
    if (typeof GENERATED_AT !== 'undefined') {
        var age = Date.now() - GENERATED_AT;
        if (age > 120000) { // Stale if > 2 minutes old
            setTimeout(function() {
                var btn = document.querySelector('.refresh-btn:not(.app-launcher-trigger)');
                if (btn && !_refreshInProgress) {
                    refreshDashboard(btn);
                }
            }, 1000);
        }
    }
})();
