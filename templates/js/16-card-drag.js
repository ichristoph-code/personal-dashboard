// ── Drag-to-Reorder Cards within Tab Panels ──
// Works for any panel that has children with class "draggable-card" and data-card-id.
var CARD_ORDER_KEY_PREFIX = 'dashboard-card-order-';
var _cardDragFromHandle = false;

function _initCardDrag(panelId) {
    var panel = document.getElementById(panelId);
    if (!panel) return;
    var cards = panel.querySelectorAll(':scope > .draggable-card[data-card-id]');
    if (cards.length < 2) return;

    var draggedCard = null;

    panel.addEventListener('mousedown', function(e) {
        if (e.target.closest('.card-drag-handle')) {
            _cardDragFromHandle = true;
        }
    });
    document.addEventListener('mouseup', function() {
        _cardDragFromHandle = false;
    });

    cards.forEach(function(card) {
        card.setAttribute('draggable', 'true');

        card.addEventListener('dragstart', function(e) {
            if (!_cardDragFromHandle) {
                e.preventDefault();
                return;
            }
            draggedCard = card;
            card.classList.add('card-dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', card.dataset.cardId);
        });

        card.addEventListener('dragend', function() {
            card.classList.remove('card-dragging');
            draggedCard = null;
            _cardDragFromHandle = false;
            panel.querySelectorAll('.draggable-card').forEach(function(c) {
                c.classList.remove('card-drag-over');
            });
        });

        card.addEventListener('dragover', function(e) {
            if (!draggedCard || draggedCard === card) return;
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            panel.querySelectorAll('.draggable-card').forEach(function(c) {
                c.classList.remove('card-drag-over');
            });
            card.classList.add('card-drag-over');
        });

        card.addEventListener('dragleave', function(e) {
            if (!card.contains(e.relatedTarget)) {
                card.classList.remove('card-drag-over');
            }
        });

        card.addEventListener('drop', function(e) {
            e.preventDefault();
            card.classList.remove('card-drag-over');
            if (!draggedCard || draggedCard === card) return;
            var allCards = Array.from(panel.querySelectorAll(':scope > .draggable-card[data-card-id]'));
            var fromIdx = allCards.indexOf(draggedCard);
            var toIdx = allCards.indexOf(card);
            if (fromIdx < toIdx) {
                panel.insertBefore(draggedCard, card.nextSibling);
            } else {
                panel.insertBefore(draggedCard, card);
            }
            _saveCardOrder(panelId);
        });
    });
}

function _saveCardOrder(panelId) {
    var panel = document.getElementById(panelId);
    if (!panel) return;
    var order = [];
    panel.querySelectorAll(':scope > .draggable-card[data-card-id]').forEach(function(card) {
        order.push(card.dataset.cardId);
    });
    try {
        localStorage.setItem(CARD_ORDER_KEY_PREFIX + panelId, JSON.stringify(order));
    } catch(e) {}
}

function _applyCardOrder(panelId) {
    try {
        var order = JSON.parse(localStorage.getItem(CARD_ORDER_KEY_PREFIX + panelId) || '[]');
        if (!order.length) return;
        var panel = document.getElementById(panelId);
        if (!panel) return;
        var cardMap = {};
        panel.querySelectorAll(':scope > .draggable-card[data-card-id]').forEach(function(card) {
            cardMap[card.dataset.cardId] = card;
        });
        var inserted = {};
        order.forEach(function(id) {
            if (cardMap[id]) {
                panel.appendChild(cardMap[id]);
                inserted[id] = true;
            }
        });
        // Append any new cards not in saved order
        Object.keys(cardMap).forEach(function(id) {
            if (!inserted[id]) {
                panel.appendChild(cardMap[id]);
            }
        });
    } catch(e) {}
}

// Initialize card drag for panels that have draggable cards
function _initAllCardDrag() {
    // Find all tab panels whose direct children are draggable cards
    document.querySelectorAll('.tab-panel').forEach(function(panel) {
        var cards = panel.querySelectorAll(':scope > .draggable-card[data-card-id]');
        if (cards.length >= 2) {
            _applyCardOrder(panel.id);
            _initCardDrag(panel.id);
        }
    });
    // Also handle today-grid (cards are nested inside the grid, not the tab-panel)
    var todayGrid = document.getElementById('today-grid');
    if (todayGrid) {
        var todayCards = todayGrid.querySelectorAll(':scope > .draggable-card[data-card-id]');
        if (todayCards.length >= 2) {
            _applyCardOrder('today-grid');
            _initCardDrag('today-grid');
        }
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _initAllCardDrag);
} else {
    _initAllCardDrag();
}
