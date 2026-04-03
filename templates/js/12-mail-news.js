// ── Auto-Refresh Timestamp ──
// GENERATED_AT is injected by dashboard.py as a global variable
function updateTimestamp() {
    var el = document.getElementById('headerTime');
    if (!el || !GENERATED_AT) return;
    var diff = Math.floor((Date.now() - GENERATED_AT) / 60000);
    if (diff < 1) {
        el.textContent = 'Updated just now';
    } else if (diff === 1) {
        el.textContent = 'Updated 1 min ago';
    } else if (diff < 60) {
        el.textContent = 'Updated ' + diff + ' min ago';
    } else {
        var hrs = Math.floor(diff / 60);
        el.textContent = 'Updated ' + hrs + (hrs === 1 ? ' hour' : ' hours') + ' ago';
    }
    // Visual staleness warning if data is over 1 hour old
    if (diff > 60) {
        el.style.color = 'rgba(255,200,150,0.7)';
    } else {
        el.style.color = '';
    }
}
updateTimestamp();
setInterval(updateTimestamp, 60000);

// ── Mail: Folder Switching ──
function switchMailFolder(folderId, el) {
    // Update sidebar active state
    document.querySelectorAll('.mail-folder-item').forEach(function(item) {
        item.classList.remove('active');
    });
    if (el) el.classList.add('active');

    // Show correct panel
    document.querySelectorAll('.mail-folder-panel').forEach(function(panel) {
        panel.classList.remove('active');
    });
    var panel = document.querySelector('.mail-folder-panel[data-panel="' + folderId + '"]');
    if (panel) panel.classList.add('active');

    // Clear search
    var search = document.querySelector('.mail-search');
    if (search) { search.value = ''; filterMailMessages(''); }
}

// ── Mail: Search/Filter ──
function filterMailMessages(query) {
    var q = query.toLowerCase().trim();
    var activePanel = document.querySelector('.mail-folder-panel.active');
    if (!activePanel) return;
    activePanel.querySelectorAll('.mail-item').forEach(function(item) {
        if (!q) {
            item.classList.remove('mail-hidden');
            return;
        }
        var subj = (item.dataset.subject || '');
        var sender = (item.dataset.sender || '');
        item.classList.toggle('mail-hidden', !subj.includes(q) && !sender.includes(q));
    });
}

// ── Mail: Move to Folder (searchable popover) ──
var _movePopover = null;
var _moveTargetItem = null;
var _moveEncodedId = null;

function _buildMovePopover() {
    var pop = document.createElement('div');
    pop.className = 'mail-move-popover';
    pop.innerHTML =
        '<input class="mail-move-search" type="text" placeholder="Search folders..." autocomplete="off" />' +
        '<div class="mail-move-list"></div>';
    document.body.appendChild(pop);

    pop.querySelector('.mail-move-search').addEventListener('input', function() {
        _filterMoveList(this.value);
    });
    // Prevent click inside popover from closing it
    pop.addEventListener('mousedown', function(e) { e.stopPropagation(); });
    return pop;
}

function _filterMoveList(query) {
    if (!_movePopover) return;
    var q = query.toLowerCase().trim();
    var folders = window.MAIL_MOVE_FOLDERS || [];
    var list = _movePopover.querySelector('.mail-move-list');
    list.innerHTML = '';
    var matches = q ? folders.filter(function(f) { return f.toLowerCase().includes(q); }) : folders;
    matches.slice(0, 50).forEach(function(folder) {
        var item = document.createElement('div');
        item.className = 'mail-move-option';
        item.textContent = folder;
        item.addEventListener('mousedown', function(e) {
            e.preventDefault();
            _doMoveMail(folder);
        });
        list.appendChild(item);
    });
    if (matches.length === 0) {
        list.innerHTML = '<div class="mail-move-empty">No folders found</div>';
    }
}

function openMovePopover(btn, encodedId) {
    if (!_movePopover) _movePopover = _buildMovePopover();

    _moveEncodedId = encodedId;
    _moveTargetItem = btn.closest('.mail-item');

    // Position below the button
    var rect = btn.getBoundingClientRect();
    _movePopover.style.display = 'block';
    var popW = 240;
    var left = Math.min(rect.left + window.scrollX, window.innerWidth - popW - 8);
    _movePopover.style.left = Math.max(8, left) + 'px';
    _movePopover.style.top = (rect.bottom + window.scrollY + 4) + 'px';
    _movePopover.style.width = popW + 'px';

    // Reset & focus search
    var search = _movePopover.querySelector('.mail-move-search');
    search.value = '';
    _filterMoveList('');
    setTimeout(function() { search.focus(); }, 50);
}

function _doMoveMail(targetFolder) {
    _closeMovePopover();

    var mailItem = _moveTargetItem;
    if (mailItem) {
        mailItem.style.opacity = '0.4';
        mailItem.style.pointerEvents = 'none';
    }

    var url = 'mailhelper://move?id=' + _moveEncodedId + '&folder=' + encodeURIComponent(targetFolder);
    var iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = url;
    document.body.appendChild(iframe);
    setTimeout(function() { iframe.remove(); }, 3000);

    setTimeout(function() {
        if (mailItem) {
            mailItem.style.transition = 'all 0.3s ease';
            mailItem.style.maxHeight = mailItem.offsetHeight + 'px';
            requestAnimationFrame(function() {
                mailItem.style.maxHeight = '0';
                mailItem.style.paddingTop = '0';
                mailItem.style.paddingBottom = '0';
                mailItem.style.overflow = 'hidden';
                mailItem.style.opacity = '0';
                setTimeout(function() { mailItem.remove(); }, 320);
            });
        }
    }, 600);
}

function _closeMovePopover() {
    if (_movePopover) _movePopover.style.display = 'none';
}

document.addEventListener('mousedown', function(e) {
    if (_movePopover && _movePopover.style.display !== 'none') {
        if (!e.target.closest('.mail-move-btn') && !e.target.closest('.mail-move-popover')) {
            _closeMovePopover();
        }
    }
});

// ── Mail: Delete (delegated — reads id from data-mail-id attribute) ──
document.addEventListener('click', function(e) {
    var btn = e.target.closest('.mail-delete-btn[data-mail-id]');
    if (!btn) return;
    var messageId = btn.dataset.mailId;
    var mailItem = btn.closest('.mail-item');
    if (mailItem) {
        mailItem.style.opacity = '0.4';
        mailItem.style.pointerEvents = 'none';
    }
    var iframe = document.createElement('iframe');
    iframe.style.display = 'none';
    iframe.src = 'mailhelper://delete?id=' + encodeURIComponent(messageId);
    document.body.appendChild(iframe);
    setTimeout(function() { iframe.remove(); }, 3000);
    setTimeout(function() {
        if (mailItem) {
            mailItem.style.transition = 'all 0.3s ease';
            mailItem.style.maxHeight = '0';
            mailItem.style.padding = '0';
            mailItem.style.margin = '0';
            mailItem.style.overflow = 'hidden';
            mailItem.style.opacity = '0';
            setTimeout(function() { mailItem.remove(); }, 300);
        }
    }, 1000);
});

// ── Mail: Single-Click to Open ──
document.addEventListener('click', function(e) {
    var mailItem = e.target.closest('.mail-item[data-open-url]');
    if (!mailItem) return;
    if (e.target.closest('.mail-actions')) return;
    window.location.href = mailItem.dataset.openUrl;
});

// ── News Read/Save Tracking ──
var NEWS_READ_KEY = 'dashboard-news-read';
var NEWS_SAVED_KEY = 'dashboard-news-saved';

function getNewsState(key) {
    try { var s = localStorage.getItem(key); return s ? JSON.parse(s) : {}; } catch(e) { return {}; }
}

function toggleNewsRead(hash, el) {
    var state = getNewsState(NEWS_READ_KEY);
    var item = el.closest('.news-item');
    if (state[hash]) {
        // Un-read: restore the item
        delete state[hash];
        item.classList.remove('news-read', 'news-dismissed');
        item.style.maxHeight = '';
        item.style.opacity = '';
        item.style.padding = '';
        item.style.margin = '';
        item.style.borderBottom = '';
        item.style.overflow = '';
    } else {
        // Mark read: fade out and collapse
        state[hash] = Date.now();
        item.classList.add('news-read');
        setTimeout(function() {
            item.style.transition = 'opacity 0.4s ease, max-height 0.4s ease, padding 0.4s ease, margin 0.4s ease';
            item.style.opacity = '0';
            item.style.maxHeight = '0';
            item.style.padding = '0';
            item.style.margin = '0';
            item.style.borderBottom = 'none';
            item.style.overflow = 'hidden';
            item.classList.add('news-dismissed');
        }, 600);
    }
    try { localStorage.setItem(NEWS_READ_KEY, JSON.stringify(state)); } catch(e) {}
}

function toggleNewsSaved(hash, el) {
    var state = getNewsState(NEWS_SAVED_KEY);
    var item = el.closest('.news-item');
    if (state[hash]) {
        delete state[hash];
        item.classList.remove('news-saved');
        el.classList.remove('news-save-active');
    } else {
        state[hash] = Date.now();
        item.classList.add('news-saved');
        el.classList.add('news-save-active');
    }
    try { localStorage.setItem(NEWS_SAVED_KEY, JSON.stringify(state)); } catch(e) {}
}

function initNewsState() {
    var readState = getNewsState(NEWS_READ_KEY);
    var savedState = getNewsState(NEWS_SAVED_KEY);
    // Prune read entries older than 7 days to avoid unbounded growth
    var now = Date.now();
    var pruneCutoff = now - 7 * 24 * 60 * 60 * 1000;
    var pruned = false;
    Object.keys(readState).forEach(function(k) {
        if (readState[k] < pruneCutoff) { delete readState[k]; pruned = true; }
    });
    if (pruned) {
        try { localStorage.setItem(NEWS_READ_KEY, JSON.stringify(readState)); } catch(e) {}
    }
    document.querySelectorAll('.news-item[data-hash]').forEach(function(item) {
        var hash = item.dataset.hash;
        if (readState[hash]) {
            // Hide previously-read items immediately (no animation on load)
            item.classList.add('news-read', 'news-dismissed');
            item.style.display = 'none';
        }
        if (savedState[hash]) {
            item.classList.add('news-saved');
            var saveBtn = item.querySelector('.news-save-btn');
            if (saveBtn) saveBtn.classList.add('news-save-active');
        }
    });
    // Show/hide saved filter button
    var savedCount = Object.keys(savedState).length;
    var filterBtn = document.getElementById('newsFilterSaved');
    if (filterBtn && savedCount > 0) filterBtn.style.display = '';
}

var newsShowSavedOnly = false;
function toggleNewsSavedFilter() {
    newsShowSavedOnly = !newsShowSavedOnly;
    var filterBtn = document.getElementById('newsFilterSaved');
    if (filterBtn) filterBtn.classList.toggle('active', newsShowSavedOnly);
    var savedState = getNewsState(NEWS_SAVED_KEY);
    var readState = getNewsState(NEWS_READ_KEY);
    document.querySelectorAll('.news-item[data-hash]').forEach(function(item) {
        var hash = item.dataset.hash;
        var isDismissed = item.classList.contains('news-dismissed');
        if (newsShowSavedOnly) {
            // Show saved items (even if read), hide everything else
            item.style.display = savedState[hash] ? '' : 'none';
        } else {
            // Normal view: hide read/dismissed items
            item.style.display = isDismissed ? 'none' : '';
        }
    });
}

initNewsState();

var NEWS_COLLAPSED_KEY = 'dashboard-news-collapsed';
function toggleNewsSection(sectionId) {
    var body = document.getElementById('news-section-' + sectionId);
    var chevron = document.getElementById('chevron-' + sectionId);
    if (!body) return;
    var isCollapsed = body.classList.contains('collapsed');
    if (isCollapsed) {
        body.classList.remove('collapsed');
        body.style.maxHeight = '';        // clear inline constraint first
        var h = body.scrollHeight;        // reads true content height
        body.style.maxHeight = '0';       // reset for animation start
        body.offsetHeight;               // force reflow
        body.style.maxHeight = h + 'px'; // CSS transition: 0 → h
        if (chevron) chevron.classList.remove('collapsed');
    } else {
        body.style.maxHeight = body.scrollHeight + 'px';
        // Force reflow then collapse
        body.offsetHeight;
        body.classList.add('collapsed');
        body.style.maxHeight = '0';
        if (chevron) chevron.classList.add('collapsed');
    }
    // Persist collapsed state
    try {
        var state = JSON.parse(localStorage.getItem(NEWS_COLLAPSED_KEY) || '{}');
        if (isCollapsed) { delete state[sectionId]; } else { state[sectionId] = true; }
        localStorage.setItem(NEWS_COLLAPSED_KEY, JSON.stringify(state));
    } catch(e) {}
}
function initNewsSections() {
    try {
        var state = JSON.parse(localStorage.getItem(NEWS_COLLAPSED_KEY) || '{}');
        Object.keys(state).forEach(function(sectionId) {
            var body = document.getElementById('news-section-' + sectionId);
            var chevron = document.getElementById('chevron-' + sectionId);
            if (body) {
                body.classList.add('collapsed');
                body.style.maxHeight = '0';
            }
            if (chevron) chevron.classList.add('collapsed');
        });
    } catch(e) {}
    // Set initial max-height for open sections
    document.querySelectorAll('.news-section-body:not(.collapsed)').forEach(function(body) {
        body.style.maxHeight = body.scrollHeight + 'px';
    });
}
// ── News Section Drag-to-Reorder ──
var NEWS_ORDER_KEY = 'dashboard-news-order';
var _newsDragFromHandle = false;

function initNewsDrag() {
    var panel = document.getElementById('panel-news');
    if (!panel) return;
    var cards = panel.querySelectorAll('.news-section-card[data-source-id]');
    if (cards.length < 2) return;

    var draggedCard = null;

    // Track mousedown on drag handles to gate drag initiation
    panel.addEventListener('mousedown', function(e) {
        _newsDragFromHandle = !!e.target.closest('.news-drag-handle');
    });
    document.addEventListener('mouseup', function() {
        _newsDragFromHandle = false;
    });

    cards.forEach(function(card) {
        card.addEventListener('dragstart', function(e) {
            if (!_newsDragFromHandle) {
                e.preventDefault();
                return;
            }
            draggedCard = card;
            card.classList.add('news-dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', card.dataset.sourceId);
        });

        card.addEventListener('dragend', function() {
            card.classList.remove('news-dragging');
            draggedCard = null;
            _newsDragFromHandle = false;
            panel.querySelectorAll('.news-section-card').forEach(function(c) {
                c.classList.remove('news-drag-over', 'news-drag-over-bottom');
            });
        });

        card.addEventListener('dragover', function(e) {
            if (!draggedCard || draggedCard === card) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            panel.querySelectorAll('.news-section-card').forEach(function(c) {
                c.classList.remove('news-drag-over', 'news-drag-over-bottom');
            });
            // Determine direction: dragging down → item lands after target (border-bottom)
            //                      dragging up   → item lands before target (border-top)
            var allCards = Array.from(panel.querySelectorAll('.news-section-card[data-source-id]'));
            var fromIdx = allCards.indexOf(draggedCard);
            var toIdx   = allCards.indexOf(card);
            card.classList.add(fromIdx < toIdx ? 'news-drag-over-bottom' : 'news-drag-over');
        });

        card.addEventListener('dragleave', function() {
            card.classList.remove('news-drag-over', 'news-drag-over-bottom');
        });

        card.addEventListener('drop', function(e) {
            e.preventDefault();
            card.classList.remove('news-drag-over');
            if (!draggedCard || draggedCard === card) return;
            var allCards = Array.from(panel.querySelectorAll('.news-section-card[data-source-id]'));
            var fromIdx = allCards.indexOf(draggedCard);
            var toIdx = allCards.indexOf(card);
            if (fromIdx < toIdx) {
                card.parentNode.insertBefore(draggedCard, card.nextSibling);
            } else {
                card.parentNode.insertBefore(draggedCard, card);
            }
            saveNewsOrder();
        });
    });
}

function saveNewsOrder() {
    var panel = document.getElementById('panel-news');
    if (!panel) return;
    var order = [];
    panel.querySelectorAll('.news-section-card[data-source-id]').forEach(function(card) {
        order.push(card.dataset.sourceId);
    });
    try { localStorage.setItem(NEWS_ORDER_KEY, JSON.stringify(order)); } catch(e) {}
}

function applyNewsOrder() {
    try {
        var order = JSON.parse(localStorage.getItem(NEWS_ORDER_KEY) || '[]');
        if (!order.length) return;
        var panel = document.getElementById('panel-news');
        if (!panel) return;
        var cardMap = {};
        panel.querySelectorAll('.news-section-card[data-source-id]').forEach(function(card) {
            cardMap[card.dataset.sourceId] = card;
        });
        // Find the insertion point (after the global header)
        var globalHeader = panel.querySelector('.news-global-header');
        var refNode = globalHeader ? globalHeader.nextSibling : panel.firstChild;
        // Reorder: insert saved-order cards first, then any new ones
        var inserted = {};
        order.forEach(function(id) {
            if (cardMap[id]) {
                panel.insertBefore(cardMap[id], null); // append to end
                inserted[id] = true;
            }
        });
        // Append any cards not in saved order (new feeds)
        Object.keys(cardMap).forEach(function(id) {
            if (!inserted[id]) {
                panel.insertBefore(cardMap[id], null);
            }
        });
    } catch(e) {}
}

applyNewsOrder();
initNewsSections();
initNewsDrag();

// ── Feed Manager ──
function openFeedManager() {
    var overlay = document.getElementById('feedManagerOverlay');
    if (!overlay) return;
    var body = document.getElementById('feedManagerBody');
    if (body) body.innerHTML = '';

    // Populate from global NEWS_FEEDS (injected by dashboard.py)
    var feeds = (typeof NEWS_FEEDS !== 'undefined') ? NEWS_FEEDS : [];
    feeds.forEach(function(f) {
        _appendFeedRow(f.name, f.url);
    });

    overlay.style.display = 'flex';
    // Focus the "Add" name input
    setTimeout(function() {
        var nameInput = document.getElementById('feedNewName');
        if (nameInput) nameInput.focus();
    }, 80);
}

function closeFeedManager() {
    var overlay = document.getElementById('feedManagerOverlay');
    if (overlay) overlay.style.display = 'none';
}

function _appendFeedRow(name, url) {
    var body = document.getElementById('feedManagerBody');
    if (!body) return;
    var row = document.createElement('div');
    row.className = 'feed-mgr-row';
    row.innerHTML = '<input type="text" class="feed-mgr-input feed-mgr-name" value="' + (name || '').replace(/"/g, '&quot;') + '" placeholder="Name">'
        + '<input type="text" class="feed-mgr-input feed-mgr-url" value="' + (url || '').replace(/"/g, '&quot;') + '" placeholder="RSS URL">'
        + '<button class="feed-mgr-del-btn" onclick="this.closest(\'.feed-mgr-row\').remove()" title="Remove">&times;</button>';
    body.appendChild(row);
}

function addFeedRow() {
    var nameInput = document.getElementById('feedNewName');
    var urlInput = document.getElementById('feedNewUrl');
    var name = nameInput ? nameInput.value.trim() : '';
    var url = urlInput ? urlInput.value.trim() : '';
    if (!name && !url) return;
    _appendFeedRow(name, url);
    if (nameInput) nameInput.value = '';
    if (urlInput) urlInput.value = '';
    if (nameInput) nameInput.focus();
}

function saveFeedChanges() {
    var rows = document.querySelectorAll('#feedManagerBody .feed-mgr-row');
    var feeds = [];
    rows.forEach(function(row) {
        var name = row.querySelector('.feed-mgr-name').value.trim();
        var url = row.querySelector('.feed-mgr-url').value.trim();
        if (name && url) feeds.push({ name: name, url: url });
    });

    // Disable save button while saving
    var saveBtn = document.querySelector('.feed-mgr-save');
    if (saveBtn) { saveBtn.disabled = true; saveBtn.textContent = 'Saving\u2026'; }

    fetch('/manage-feeds', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ feeds: feeds })
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
        if (data.ok) {
            closeFeedManager();
            // Update the global so the next open reflects changes
            if (typeof NEWS_FEEDS !== 'undefined') NEWS_FEEDS = feeds;
            // Trigger a full dashboard refresh
            var refreshBtn = document.querySelector('.refresh-btn[onclick*="refreshDashboard"]');
            if (refreshBtn) refreshDashboard(refreshBtn);
        } else {
            alert('Error: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(function(err) {
        alert('Failed to save: ' + err.message);
    })
    .finally(function() {
        if (saveBtn) { saveBtn.disabled = false; saveBtn.textContent = 'Save'; }
    });
}

// Enter in add-feed inputs triggers add
document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && (e.target.id === 'feedNewName' || e.target.id === 'feedNewUrl')) {
        addFeedRow();
    }
    if (e.key === 'Escape') {
        var overlay = document.getElementById('feedManagerOverlay');
        if (overlay && overlay.style.display !== 'none') closeFeedManager();
    }
});

// ── iMessage ──
function switchImsgConvo(cid, el) {
    // Update sidebar active state
    document.querySelectorAll('.imsg-convo-item').forEach(function(item) {
        item.classList.remove('active');
    });
    if (el) el.classList.add('active');

    // Show correct thread
    document.querySelectorAll('.imsg-thread').forEach(function(t) {
        t.classList.remove('active');
    });
    var thread = document.querySelector('.imsg-thread[data-thread="' + cid + '"]');
    if (thread) {
        thread.classList.add('active');
        // Scroll to bottom of messages
        var msgs = thread.querySelector('.imsg-messages');
        if (msgs) msgs.scrollTop = msgs.scrollHeight;
    }
}

function filterImessages(query) {
    var q = query.toLowerCase().trim();
    document.querySelectorAll('.imsg-convo-item').forEach(function(item) {
        if (!q) {
            item.classList.remove('imsg-hidden');
            return;
        }
        var name = item.dataset.name || '';
        item.classList.toggle('imsg-hidden', !name.includes(q));
    });
}

// ── iMessage: Search within thread ──
function searchImsgThread(input) {
    var q = input.value.toLowerCase().trim();
    var thread = input.closest('.imsg-thread');
    if (!thread) return;
    var msgs = thread.querySelector('.imsg-messages');
    if (!msgs) return;

    // Filter message rows
    msgs.querySelectorAll('.imsg-row[data-search]').forEach(function(row) {
        if (!q) {
            row.classList.remove('imsg-search-hidden', 'imsg-search-hit');
            return;
        }
        var text = row.dataset.search || '';
        var matches = text.includes(q);
        row.classList.toggle('imsg-search-hidden', !matches);
        row.classList.toggle('imsg-search-hit', matches);
    });

    // Hide sender labels whose next sibling row is hidden
    msgs.querySelectorAll('.imsg-sender-label').forEach(function(label) {
        if (!q) { label.style.display = ''; return; }
        var nextRow = label.nextElementSibling;
        label.style.display = (nextRow && nextRow.classList.contains('imsg-search-hidden')) ? 'none' : '';
    });

    // Hide receipts when searching
    msgs.querySelectorAll('.imsg-receipt').forEach(function(r) {
        r.style.display = q ? 'none' : '';
    });
}

// Scroll active thread to bottom on load
(function() {
    var active = document.querySelector('.imsg-thread.active .imsg-messages');
    if (active) active.scrollTop = active.scrollHeight;
})();
