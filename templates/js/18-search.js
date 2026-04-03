/* ── Global Search (Cmd+K / /) ── */
(function () {
    'use strict';

    var overlay, input, results;
    var index = [];
    var activeIdx = -1;

    var TAB_LABELS = {
        today:      'Today',
        calendar:   'Calendar',
        tasks:      'Tasks',
        email:      'Email',
        news:       'News',
        imessage:   'iMessage',
        financials: 'Financials',
        notes:      'Notes',
        contacts:   'Contacts',
        system:     'System',
        events:     'SF Events',
        journals:   'Journals',
    };

    var TAB_ICONS = {
        calendar:  '📅',
        tasks:     '✅',
        email:     '📧',
        news:      '📰',
        imessage:  '💬',
        financials:'💰',
        notes:     '📝',
        contacts:  '👤',
        events:    '📍',
        journals:  '🩺',
    };

    /* ── Build search index from DOM ── */
    function buildIndex() {
        index = [];

        function add(selector, tab, icon) {
            document.querySelectorAll(selector).forEach(function (el) {
                var text = el.textContent.trim();
                if (text && text.length > 1) {
                    index.push({ text: text, tab: tab, icon: icon || TAB_ICONS[tab] || '🔍', el: el });
                }
            });
        }

        add('.cal-event-title',    'calendar');
        add('.today-event-title',  'calendar');
        add('.task-title',         'tasks');
        add('.today-task-title',   'tasks');
        add('.mail-subject',       'email');
        add('.news-title, .news-item span', 'news', '📰');
        add('.imessage-name, .convo-name',  'imessage');
        add('.note-title',         'notes');
        add('.contact-name',       'contacts');
        add('.event-name',         'events');
        add('.journal-title',      'journals');
    }

    /* ── Render results ── */
    function render(query) {
        results.innerHTML = '';
        activeIdx = -1;
        if (!query.trim()) return;

        var q = query.toLowerCase();
        var matches = index.filter(function (item) {
            return item.text.toLowerCase().includes(q);
        }).slice(0, 12);

        if (!matches.length) {
            results.innerHTML = '<div class="search-empty">No results for "' + escHtml(query) + '"</div>';
            return;
        }

        matches.forEach(function (item, i) {
            var div = document.createElement('div');
            div.className = 'search-result';
            div.dataset.idx = i;
            div.innerHTML =
                '<span class="search-result-icon">' + item.icon + '</span>' +
                '<span class="search-result-text">' +
                '<div class="search-result-title">' + escHtml(item.text.slice(0, 80)) + '</div>' +
                '<div class="search-result-tab">' + (TAB_LABELS[item.tab] || item.tab) + '</div>' +
                '</span>';
            div.addEventListener('click', function () { goTo(item); });
            results.appendChild(div);
        });
    }

    function goTo(item) {
        close();
        if (typeof switchTab === 'function') switchTab(item.tab);
        // Scroll element into view after tab switch
        setTimeout(function () {
            if (item.el && item.el.scrollIntoView) {
                item.el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                item.el.classList.add('search-highlight');
                setTimeout(function () { item.el.classList.remove('search-highlight'); }, 2000);
            }
        }, 150);
    }

    function escHtml(s) {
        return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    /* ── Keyboard navigation ── */
    function moveActive(dir) {
        var items = results.querySelectorAll('.search-result');
        if (!items.length) return;
        items[activeIdx] && items[activeIdx].classList.remove('search-active');
        activeIdx = Math.max(0, Math.min(items.length - 1, activeIdx + dir));
        items[activeIdx].classList.add('search-active');
        items[activeIdx].scrollIntoView({ block: 'nearest' });
    }

    function selectActive() {
        var item = results.querySelector('.search-result.search-active');
        if (item) item.click();
    }

    /* ── Open / close ── */
    function open() {
        buildIndex();
        overlay.classList.add('search-open');
        input.value = '';
        results.innerHTML = '';
        input.focus();
    }

    function close() {
        overlay.classList.remove('search-open');
        input.blur();
    }

    /* ── Init ── */
    function init() {
        // Create overlay DOM
        overlay = document.createElement('div');
        overlay.id = 'searchOverlay';
        overlay.innerHTML =
            '<div id="searchBox">' +
            '<input id="searchInput" type="text" placeholder="Search calendar, tasks, contacts, notes…" autocomplete="off">' +
            '<div id="searchResults"></div>' +
            '<div class="search-hint"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>↵</kbd> open</span><span><kbd>Esc</kbd> close</span></div>' +
            '</div>';
        document.body.appendChild(overlay);

        input = document.getElementById('searchInput');
        results = document.getElementById('searchResults');

        overlay.addEventListener('click', function (e) {
            if (e.target === overlay) close();
        });

        input.addEventListener('input', function () { render(input.value); });

        input.addEventListener('keydown', function (e) {
            if (e.key === 'ArrowDown') { e.preventDefault(); moveActive(1); }
            else if (e.key === 'ArrowUp') { e.preventDefault(); moveActive(-1); }
            else if (e.key === 'Enter') { e.preventDefault(); selectActive(); }
            else if (e.key === 'Escape') close();
        });

        // Global shortcuts
        document.addEventListener('keydown', function (e) {
            // Cmd+K or Ctrl+K
            if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
                e.preventDefault();
                overlay.classList.contains('search-open') ? close() : open();
            }
            // '/' when not in an input
            if (e.key === '/' && document.activeElement.tagName === 'BODY') {
                e.preventDefault();
                open();
            }
        });

        // Expose for external use
        window.openSearch = open;
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
