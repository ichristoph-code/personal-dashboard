// ── Area Section Collapse/Expand ──
var AREA_COLLAPSED_KEY = 'dashboard-area-collapsed';
function toggleAreaSection(areaId) {
    var body = document.getElementById('area-body-' + areaId);
    var chevron = document.getElementById('area-chevron-' + areaId);
    if (!body) return;
    var isCollapsed = body.classList.contains('area-collapsed');
    if (isCollapsed) {
        body.classList.remove('area-collapsed');
        body.style.maxHeight = '';        // clear inline constraint first
        var h = body.scrollHeight;        // now reads true content height
        body.style.maxHeight = '0';       // reset for animation start
        body.offsetHeight;               // force reflow (commit the 0 state)
        body.style.maxHeight = h + 'px'; // CSS transition fires: 0 → h
        if (chevron) chevron.classList.remove('collapsed');
    } else {
        body.style.maxHeight = body.scrollHeight + 'px';
        body.offsetHeight; // force reflow
        body.classList.add('area-collapsed');
        body.style.maxHeight = '0';
        if (chevron) chevron.classList.add('collapsed');
    }
    try {
        var state = JSON.parse(localStorage.getItem(AREA_COLLAPSED_KEY) || '{}');
        if (isCollapsed) { delete state[areaId]; } else { state[areaId] = true; }
        localStorage.setItem(AREA_COLLAPSED_KEY, JSON.stringify(state));
    } catch(e) {}
}
function initAreaSections() {
    try {
        var state = JSON.parse(localStorage.getItem(AREA_COLLAPSED_KEY) || '{}');
        Object.keys(state).forEach(function(areaId) {
            var body = document.getElementById('area-body-' + areaId);
            var chevron = document.getElementById('area-chevron-' + areaId);
            if (body) { body.classList.add('area-collapsed'); body.style.maxHeight = '0'; }
            if (chevron) chevron.classList.add('collapsed');
        });
    } catch(e) {}
    document.querySelectorAll('.area-body:not(.area-collapsed)').forEach(function(body) {
        body.style.maxHeight = body.scrollHeight + 'px';
    });
}
// ── Area Group Drag-to-Reorder ──
var AREA_ORDER_KEY = 'dashboard-area-order';
function initAreaDrag() {
    // Find all containers that hold area-groups (direct parents)
    var containers = [];
    document.querySelectorAll('.area-group').forEach(function(grp) {
        var parent = grp.parentElement;
        if (parent && containers.indexOf(parent) === -1) containers.push(parent);
    });
    containers.forEach(function(container) {
        var draggedGroup = null;
        container.querySelectorAll('.area-group').forEach(function(group) {
            var handle = group.querySelector('.area-drag-handle');
            if (!handle) return;

            // Set draggable via JS so the HTML attribute doesn't interfere with single-click
            handle.draggable = true;

            handle.addEventListener('dragstart', function(e) {
                draggedGroup = group;
                group.classList.add('area-dragging');
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/area', group.dataset.areaId);
                e.stopPropagation();
            });
            handle.addEventListener('dragend', function() {
                group.classList.remove('area-dragging');
                container.querySelectorAll('.area-group').forEach(function(g) { g.classList.remove('area-drag-over'); });
                draggedGroup = null;
            });
            group.addEventListener('dragover', function(e) {
                if (!draggedGroup) return;
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                if (group !== draggedGroup) {
                    container.querySelectorAll('.area-group').forEach(function(g) { g.classList.remove('area-drag-over'); });
                    group.classList.add('area-drag-over');
                }
            });
            group.addEventListener('dragleave', function() {
                group.classList.remove('area-drag-over');
            });
            group.addEventListener('drop', function(e) {
                if (!draggedGroup || draggedGroup === group) return;
                // Only handle drops from area drags, not task drags
                if (!e.dataTransfer.types || e.dataTransfer.types.indexOf('text/area') === -1) return;
                e.preventDefault();
                e.stopPropagation();
                group.classList.remove('area-drag-over');
                var allGroups = Array.from(container.querySelectorAll('.area-group'));
                var fromIdx = allGroups.indexOf(draggedGroup);
                var toIdx = allGroups.indexOf(group);
                if (fromIdx < toIdx) {
                    container.insertBefore(draggedGroup, group.nextSibling);
                } else {
                    container.insertBefore(draggedGroup, group);
                }
                saveAreaOrder();
            });
        });
    });
}
function saveAreaOrder() {
    var order = [];
    document.querySelectorAll('.area-group').forEach(function(g) {
        if (g.dataset.areaId) order.push(g.dataset.areaId);
    });
    try { localStorage.setItem(AREA_ORDER_KEY, JSON.stringify(order)); } catch(e) {}
}
function applyAreaOrder() {
    try {
        var saved = localStorage.getItem(AREA_ORDER_KEY);
        if (!saved) return;
        var order = JSON.parse(saved);
        // Group area-groups by their parent container
        var containers = [];
        document.querySelectorAll('.area-group').forEach(function(grp) {
            var parent = grp.parentElement;
            if (parent && containers.indexOf(parent) === -1) containers.push(parent);
        });
        containers.forEach(function(container) {
            var groupMap = {};
            container.querySelectorAll('.area-group').forEach(function(g) {
                if (g.dataset.areaId) groupMap[g.dataset.areaId] = g;
            });
            order.forEach(function(areaId) {
                if (groupMap[areaId]) container.appendChild(groupMap[areaId]);
            });
        });
    } catch(e) {}
}
// Apply saved order first, THEN init sections so maxHeight is set on final DOM positions
applyAreaOrder();
initAreaSections();
initAreaDrag();
