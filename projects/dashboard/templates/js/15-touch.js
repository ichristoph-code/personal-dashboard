// 15-touch.js — Touch/swipe handlers for mobile
(function() {
    'use strict';

    // Only activate on touch devices
    var isTouchDevice = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
    if (!isTouchDevice) return;

    // ── Configuration ──
    var SWIPE_THRESHOLD = 50;     // min px for a swipe
    var SWIPE_RESTRAINT = 100;    // max perpendicular movement
    var SWIPE_TIMEOUT = 300;      // max ms

    // ── Helper: get live tab order ──
    function getTabNames() {
        var names = [];
        document.querySelectorAll('.tab-bar .tab-btn').forEach(function(btn) {
            if (btn.dataset.tab) names.push(btn.dataset.tab);
        });
        return names;
    }

    function getActiveTabIndex(tabs) {
        var activeBtn = document.querySelector('.tab-btn.active');
        if (!activeBtn) return 0;
        return tabs.indexOf(activeBtn.dataset.tab);
    }

    // ── Auto-scroll tab bar to keep active tab visible ──
    function scrollActiveTabIntoView() {
        var activeBtn = document.querySelector('.tab-btn.active');
        if (activeBtn) {
            activeBtn.scrollIntoView({
                behavior: 'smooth',
                block: 'nearest',
                inline: 'center'
            });
        }
    }

    // ════════════════════════════════════════
    // Tab Swipe Navigation
    // ════════════════════════════════════════
    var container = document.querySelector('.container');
    if (!container) return;

    var touchStartX = 0;
    var touchStartY = 0;
    var touchStartTime = 0;

    container.addEventListener('touchstart', function(e) {
        var target = e.target;
        // Don't capture swipes on form elements
        if (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' ||
            target.tagName === 'SELECT' || target.tagName === 'CANVAS') return;
        // Don't capture on scrollable sub-areas
        if (target.closest('.cal-week-grid') || target.closest('.cal-week-body') ||
            target.closest('.cal-week-header') || target.closest('.txn-list') ||
            target.closest('.imsg-messages') || target.closest('.imsg-convo-list') ||
            target.closest('.anotes-list') || target.closest('.anotes-reader-content') ||
            target.closest('.web-panel-frame') || target.closest('iframe') ||
            target.closest('.tab-bar')) return;

        var touch = e.touches[0];
        touchStartX = touch.clientX;
        touchStartY = touch.clientY;
        touchStartTime = Date.now();
    }, { passive: true });

    container.addEventListener('touchmove', function(e) {
        if (touchStartX === 0) return;
        var touch = e.touches[0];
        var dx = touch.clientX - touchStartX;
        var dy = touch.clientY - touchStartY;

        // Visual feedback if horizontal swipe detected
        if (Math.abs(dx) > 20 && Math.abs(dx) > Math.abs(dy) * 1.5) {
            var activePanel = document.querySelector('.tab-panel.active');
            if (activePanel) {
                if (dx < -10) {
                    activePanel.classList.add('swiping-left');
                    activePanel.classList.remove('swiping-right');
                } else if (dx > 10) {
                    activePanel.classList.remove('swiping-left');
                    activePanel.classList.add('swiping-right');
                }
            }
        }
    }, { passive: true });

    container.addEventListener('touchend', function(e) {
        // Clear visual feedback
        var activePanel = document.querySelector('.tab-panel.active');
        if (activePanel) {
            activePanel.classList.remove('swiping-left', 'swiping-right');
        }

        if (touchStartX === 0) return;

        var touch = e.changedTouches[0];
        var dx = touch.clientX - touchStartX;
        var dy = touch.clientY - touchStartY;
        var dt = Date.now() - touchStartTime;

        // Reset
        touchStartX = 0;
        touchStartY = 0;
        touchStartTime = 0;

        // Validate swipe gesture
        if (dt > SWIPE_TIMEOUT) return;
        if (Math.abs(dx) < SWIPE_THRESHOLD) return;
        if (Math.abs(dy) > SWIPE_RESTRAINT) return;

        var tabs = getTabNames();
        var currentIdx = getActiveTabIndex(tabs);

        if (dx < -SWIPE_THRESHOLD && currentIdx < tabs.length - 1) {
            // Swipe left → next tab
            switchTab(tabs[currentIdx + 1]);
            scrollActiveTabIntoView();
        } else if (dx > SWIPE_THRESHOLD && currentIdx > 0) {
            // Swipe right → previous tab
            switchTab(tabs[currentIdx - 1]);
            scrollActiveTabIntoView();
        }
    }, { passive: true });


    // ════════════════════════════════════════
    // Calendar Swipe Navigation
    // ════════════════════════════════════════
    var calPanel = document.getElementById('panel-calendar');
    if (calPanel) {
        var calStartX = 0;
        var calStartY = 0;
        var calStartTime = 0;

        calPanel.addEventListener('touchstart', function(e) {
            var target = e.target;
            // Only swipe on the alt view container (week/month/year)
            if (!target.closest('#calAltView')) return;
            // Don't intercept on the scrollable week grid
            if (target.closest('.cal-week-body') || target.closest('.cal-week-header')) return;

            var touch = e.touches[0];
            calStartX = touch.clientX;
            calStartY = touch.clientY;
            calStartTime = Date.now();
        }, { passive: true });

        calPanel.addEventListener('touchend', function(e) {
            if (calStartX === 0) return;

            var touch = e.changedTouches[0];
            var dx = touch.clientX - calStartX;
            var dy = touch.clientY - calStartY;
            var dt = Date.now() - calStartTime;

            calStartX = 0;
            calStartY = 0;
            calStartTime = 0;

            if (dt > SWIPE_TIMEOUT) return;
            if (Math.abs(dx) < SWIPE_THRESHOLD) return;
            if (Math.abs(dy) > SWIPE_RESTRAINT) return;

            // Only navigate in week/month/year views (not day)
            if (typeof currentCalView !== 'undefined' && currentCalView === 'day') return;

            if (dx < -SWIPE_THRESHOLD) {
                navigateCal(1);   // Forward
            } else if (dx > SWIPE_THRESHOLD) {
                navigateCal(-1);  // Back
            }
        }, { passive: true });
    }


    // ════════════════════════════════════════
    // Touch cleanup
    // ════════════════════════════════════════

    // Remove draggable attributes on touch devices
    document.querySelectorAll('[draggable="true"]').forEach(function(el) {
        el.removeAttribute('draggable');
    });

    // Scroll active tab into view on initial load
    requestAnimationFrame(function() {
        scrollActiveTabIntoView();
    });

})();
