// ── Drag-to-Reorder Tabs ──
var TAB_ORDER_KEY = 'dashboard-tab-order';

function initTabDrag() {
    var tabBar = document.querySelector('.tab-bar');
    if (!tabBar) return;
    var draggedBtn = null;

    tabBar.querySelectorAll('.tab-btn').forEach(function(btn) {
        btn.addEventListener('dragstart', function(e) {
            draggedBtn = btn;
            btn.classList.add('dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', btn.dataset.tab);
        });
        btn.addEventListener('dragend', function() {
            btn.classList.remove('dragging');
            tabBar.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('drag-over'); });
            draggedBtn = null;
        });
        btn.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            if (btn !== draggedBtn) {
                tabBar.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.remove('drag-over'); });
                btn.classList.add('drag-over');
            }
        });
        btn.addEventListener('dragleave', function() {
            btn.classList.remove('drag-over');
        });
        btn.addEventListener('drop', function(e) {
            e.preventDefault();
            btn.classList.remove('drag-over');
            if (!draggedBtn || draggedBtn === btn) return;
            // Determine position
            var allBtns = Array.from(tabBar.querySelectorAll('.tab-btn'));
            var fromIdx = allBtns.indexOf(draggedBtn);
            var toIdx = allBtns.indexOf(btn);
            if (fromIdx < toIdx) {
                tabBar.insertBefore(draggedBtn, btn.nextSibling);
            } else {
                tabBar.insertBefore(draggedBtn, btn);
            }
            saveTabOrder();
        });
    });
}

function saveTabOrder() {
    var order = [];
    document.querySelectorAll('.tab-bar .tab-btn').forEach(function(btn) {
        order.push(btn.dataset.tab);
    });
    try { localStorage.setItem(TAB_ORDER_KEY, JSON.stringify(order)); } catch(e) {}
    // Update TAB_NAMES for keyboard shortcuts
    TAB_NAMES = order;
}

function applyTabOrder() {
    try {
        var saved = localStorage.getItem(TAB_ORDER_KEY);
        if (!saved) return;
        var order = JSON.parse(saved);
        var tabBar = document.querySelector('.tab-bar');
        if (!tabBar) return;
        var btnMap = {};
        tabBar.querySelectorAll('.tab-btn').forEach(function(btn) {
            btnMap[btn.dataset.tab] = btn;
        });
        order.forEach(function(tabName) {
            if (btnMap[tabName]) tabBar.appendChild(btnMap[tabName]);
        });
        TAB_NAMES = order;
    } catch(e) {}
}

applyTabOrder();
initTabDrag();

// ── Drag-to-Reorder Tasks ──
var TASK_ORDER_KEY = 'dashboard-task-order';

function initTaskDrag() {
    document.querySelectorAll('.task-list').forEach(function(list) {
        var draggedItem = null;

        list.querySelectorAll('.task-item').forEach(function(item) {
            item.addEventListener('dragstart', function(e) {
                // Only start drag from handle
                if (!e.target.classList.contains('task-drag-handle') &&
                    !e.target.closest('.task-drag-handle')) {
                    e.preventDefault();
                    return;
                }
                draggedItem = item;
                item.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', item.dataset.uuid);
            });
            item.addEventListener('dragend', function() {
                item.classList.remove('dragging');
                list.querySelectorAll('.task-item').forEach(function(i) { i.classList.remove('drag-over'); });
                draggedItem = null;
            });
            item.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                if (item !== draggedItem && draggedItem) {
                    list.querySelectorAll('.task-item').forEach(function(i) { i.classList.remove('drag-over'); });
                    item.classList.add('drag-over');
                }
            });
            item.addEventListener('dragleave', function() {
                item.classList.remove('drag-over');
            });
            item.addEventListener('drop', function(e) {
                e.preventDefault();
                item.classList.remove('drag-over');
                if (!draggedItem || draggedItem === item) return;
                var allItems = Array.from(list.querySelectorAll('.task-item'));
                var fromIdx = allItems.indexOf(draggedItem);
                var toIdx = allItems.indexOf(item);
                if (fromIdx < toIdx) {
                    list.insertBefore(draggedItem, item.nextSibling);
                } else {
                    list.insertBefore(draggedItem, item);
                }
                saveTaskOrder();
            });
        });
    });
}

function saveTaskOrder() {
    var order = {};
    document.querySelectorAll('.task-list').forEach(function(list, listIdx) {
        var uuids = [];
        list.querySelectorAll('.task-item').forEach(function(item) {
            if (item.dataset.uuid) uuids.push(item.dataset.uuid);
        });
        order['list_' + listIdx] = uuids;
    });
    try { localStorage.setItem(TASK_ORDER_KEY, JSON.stringify(order)); } catch(e) {}
}

function applyTaskOrder() {
    try {
        var saved = localStorage.getItem(TASK_ORDER_KEY);
        if (!saved) return;
        var order = JSON.parse(saved);
        document.querySelectorAll('.task-list').forEach(function(list, listIdx) {
            var key = 'list_' + listIdx;
            if (!order[key]) return;
            var savedUuids = order[key];
            var itemMap = {};
            list.querySelectorAll('.task-item').forEach(function(item) {
                if (item.dataset.uuid) itemMap[item.dataset.uuid] = item;
            });
            savedUuids.forEach(function(uuid) {
                if (itemMap[uuid]) list.appendChild(itemMap[uuid]);
            });
        });
    } catch(e) {}
}

applyTaskOrder();
initTaskDrag();

// Area group drag-to-reorder is defined in 11-area-sections.js

// ── Drag-to-Reorder Project Area Groups ──
var PROJ_AREA_ORDER_KEY = 'dashboard-proj-area-order';

function initProjectAreaDrag() {
    var panel = document.getElementById('subpanel-projects');
    if (!panel) return;
    var draggedArea = null;

    function bindProjArea(area) {
        var handle = area.querySelector(':scope > .project-area-header > .area-drag-handle');
        if (!handle) return;

        area.setAttribute('draggable', 'true');

        area.addEventListener('dragstart', function(e) {
            if (!e.target.classList.contains('area-drag-handle') &&
                !e.target.closest('.area-drag-handle')) {
                e.preventDefault(); return;
            }
            draggedArea = area;
            area.classList.add('area-dragging');
            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', area.id || '');
        });
        area.addEventListener('dragend', function() {
            area.classList.remove('area-dragging');
            panel.querySelectorAll('.project-area-group').forEach(function(a) { a.classList.remove('area-drag-over'); });
            draggedArea = null;
        });
        area.addEventListener('dragover', function(e) {
            e.preventDefault();
            e.dataTransfer.dropEffect = 'move';
            if (area !== draggedArea && draggedArea) {
                panel.querySelectorAll('.project-area-group').forEach(function(a) { a.classList.remove('area-drag-over'); });
                area.classList.add('area-drag-over');
            }
        });
        area.addEventListener('dragleave', function(e) {
            if (!area.contains(e.relatedTarget)) area.classList.remove('area-drag-over');
        });
        area.addEventListener('drop', function(e) {
            e.preventDefault();
            area.classList.remove('area-drag-over');
            if (!draggedArea || draggedArea === area) return;
            var all = Array.from(panel.querySelectorAll(':scope > .project-area-group'));
            var fromIdx = all.indexOf(draggedArea);
            var toIdx = all.indexOf(area);
            if (fromIdx < toIdx) {
                panel.insertBefore(draggedArea, area.nextSibling);
            } else {
                panel.insertBefore(draggedArea, area);
            }
            saveProjAreaOrder();
        });
    }

    panel.querySelectorAll(':scope > .project-area-group').forEach(bindProjArea);
}

function saveProjAreaOrder() {
    var panel = document.getElementById('subpanel-projects');
    if (!panel) return;
    var ids = [];
    panel.querySelectorAll(':scope > .project-area-group').forEach(function(area) {
        ids.push(area.id);
    });
    try { localStorage.setItem(PROJ_AREA_ORDER_KEY, JSON.stringify(ids)); } catch(e) {}
}

function applyProjAreaOrder() {
    try {
        var saved = localStorage.getItem(PROJ_AREA_ORDER_KEY);
        if (!saved) return;
        var ids = JSON.parse(saved);
        var panel = document.getElementById('subpanel-projects');
        if (!panel) return;
        ids.forEach(function(id) {
            var el = document.getElementById(id);
            if (el) panel.appendChild(el);
        });
    } catch(e) {}
}

applyProjAreaOrder();
initProjectAreaDrag();

// ── Drag-to-Reorder Projects within an area ──
var PROJ_ORDER_KEY = 'dashboard-proj-order';

function initProjectDrag() {
    document.querySelectorAll('.project-area-body').forEach(function(body) {
        var draggedProj = null;

        function bindProj(proj) {
            proj.setAttribute('draggable', 'true');

            proj.addEventListener('dragstart', function(e) {
                // Only drag from the proj-drag-handle
                if (!e.target.classList.contains('proj-drag-handle') &&
                    !e.target.closest('.proj-drag-handle')) {
                    e.preventDefault(); return;
                }
                draggedProj = proj;
                proj.classList.add('area-dragging');
                e.dataTransfer.effectAllowed = 'move';
                e.dataTransfer.setData('text/plain', proj.id || '');
            });
            proj.addEventListener('dragend', function() {
                proj.classList.remove('area-dragging');
                body.querySelectorAll('.project-group').forEach(function(p) { p.classList.remove('area-drag-over'); });
                draggedProj = null;
            });
            proj.addEventListener('dragover', function(e) {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                if (proj !== draggedProj && draggedProj) {
                    body.querySelectorAll('.project-group').forEach(function(p) { p.classList.remove('area-drag-over'); });
                    proj.classList.add('area-drag-over');
                }
            });
            proj.addEventListener('dragleave', function(e) {
                if (!proj.contains(e.relatedTarget)) proj.classList.remove('area-drag-over');
            });
            proj.addEventListener('drop', function(e) {
                e.preventDefault();
                proj.classList.remove('area-drag-over');
                if (!draggedProj || draggedProj === proj) return;
                var all = Array.from(body.querySelectorAll(':scope > .project-group'));
                var fromIdx = all.indexOf(draggedProj);
                var toIdx = all.indexOf(proj);
                if (fromIdx < toIdx) {
                    body.insertBefore(draggedProj, proj.nextSibling);
                } else {
                    body.insertBefore(draggedProj, proj);
                }
                saveProjOrder();
            });
        }

        body.querySelectorAll(':scope > .project-group').forEach(bindProj);
    });
}

function saveProjOrder() {
    var order = {};
    document.querySelectorAll('.project-area-body').forEach(function(body) {
        var bodyId = body.id;
        var ids = [];
        body.querySelectorAll(':scope > .project-group').forEach(function(proj) {
            ids.push(proj.id);
        });
        order[bodyId] = ids;
    });
    try { localStorage.setItem(PROJ_ORDER_KEY, JSON.stringify(order)); } catch(e) {}
}

function applyProjOrder() {
    try {
        var saved = localStorage.getItem(PROJ_ORDER_KEY);
        if (!saved) return;
        var order = JSON.parse(saved);
        document.querySelectorAll('.project-area-body').forEach(function(body) {
            var ids = order[body.id];
            if (!ids) return;
            var projMap = {};
            body.querySelectorAll(':scope > .project-group').forEach(function(proj) {
                projMap[proj.id] = proj;
            });
            ids.forEach(function(id) {
                if (projMap[id]) body.appendChild(projMap[id]);
            });
        });
    } catch(e) {}
}

applyProjOrder();
initProjectDrag();
