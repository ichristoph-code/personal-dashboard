// ── Websites Launcher ──
var WEBSITES_KEY = 'dashboard-websites';

function getWebsites() {
    var seeds = (typeof SEED_LINKS !== 'undefined' ? SEED_LINKS : []);
    var sites = [];
    try {
        var stored = localStorage.getItem(WEBSITES_KEY);
        if (stored) sites = JSON.parse(stored);
    } catch(e) {}
    // Initialize from seeds if empty
    if (!sites.length && seeds.length) {
        sites = seeds.map(function(item, i) {
            return { name: item.name, url: item.url, id: 'web_' + Date.now() + '_' + i };
        });
        saveWebsites(sites);
        return sites;
    }
    // Merge: add any new seed URLs not already stored
    var existingUrls = {};
    sites.forEach(function(s) { existingUrls[s.url] = true; });
    var added = false;
    seeds.forEach(function(seed, i) {
        if (!existingUrls[seed.url]) {
            sites.push({ name: seed.name, url: seed.url, id: 'web_' + Date.now() + '_s' + i });
            added = true;
        }
    });
    if (added) saveWebsites(sites);
    return sites;
}

function saveWebsites(sites) {
    try { localStorage.setItem(WEBSITES_KEY, JSON.stringify(sites)); } catch(e) {}
}

function renderWebList() {
    var list = document.getElementById('webLauncherList');
    if (!list) return;
    var sites = getWebsites();
    var html = '';
    sites.forEach(function(site) {
        var urlEsc = site.url.replace(/"/g, '&quot;');
        var nameEsc = site.name.replace(/</g, '&lt;');
        // Favicon via Google's service
        var domain = '';
        try { domain = new URL(site.url).hostname; } catch(e) {}
        var faviconUrl = domain ? 'https://www.google.com/s2/favicons?domain=' + domain + '&sz=32' : '';
        var iconHtml = faviconUrl
            ? '<span class="app-launcher-icon web-launcher-icon"><img src="' + faviconUrl + '" width="16" height="16" onerror="this.parentNode.innerHTML=\'🌐\'" style="border-radius:3px;display:block"></span>'
            : '<span class="app-launcher-icon web-launcher-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg></span>';
        html += '<a class="app-launcher-item" href="' + urlEsc + '" target="_blank" onclick="closeWebLauncher()">'
            + iconHtml
            + '<span>' + nameEsc + '</span>'
            + '</a>';
    });
    if (!sites.length) html = '<div style="padding:10px 14px;font-size:0.82em;color:var(--text-muted)">No websites. Click ✎ to add.</div>';
    list.innerHTML = html;
}

function toggleWebLauncher(e) {
    e.stopPropagation();
    e.preventDefault();
    var dd = document.getElementById('webLauncherDropdown');
    if (!dd) return;
    var isOpen = dd.classList.contains('open');
    // Close app launcher if open
    closeAppLauncher();
    if (isOpen) {
        closeWebLauncher();
    } else {
        renderWebList();
        dd.classList.add('open');
    }
}

function closeWebLauncher() {
    var dd = document.getElementById('webLauncherDropdown');
    if (dd) dd.classList.remove('open');
    var ed = document.getElementById('webLauncherEditor');
    if (ed) ed.style.display = 'none';
    var list = document.getElementById('webLauncherList');
    if (list) list.style.display = '';
}

function toggleWebEdit() {
    var editor = document.getElementById('webLauncherEditor');
    var list = document.getElementById('webLauncherList');
    if (!editor || !list) return;
    var editing = editor.style.display !== 'none';
    if (editing) {
        editor.style.display = 'none';
        list.style.display = '';
        renderWebList();
    } else {
        list.style.display = 'none';
        editor.style.display = '';
        renderWebEditor();
    }
}

function renderWebEditor() {
    var editor = document.getElementById('webLauncherEditor');
    if (!editor) return;
    var sites = getWebsites();
    var html = '<div class="app-launcher-editor-inner">';
    sites.forEach(function(site, i) {
        html += '<div class="app-launcher-edit-row" data-idx="' + i + '">'
            + '<input class="app-launcher-edit-input" type="text" value="' + site.name.replace(/"/g,'&quot;') + '" placeholder="Name">'
            + '<input class="app-launcher-edit-input" type="url" value="' + site.url.replace(/"/g,'&quot;') + '" placeholder="https://">'
            + '<button class="habit-remove-btn" style="flex-shrink:0" onclick="removeWebsite(' + i + ')" title="Remove">&times;</button>'
            + '</div>';
    });
    html += '<div class="app-launcher-edit-row">'
        + '<input class="app-launcher-edit-input" type="text" id="newWebName" placeholder="Name" onkeydown="if(event.key===\'Enter\')addWebsite()">'
        + '<input class="app-launcher-edit-input" type="url" id="newWebUrl" placeholder="https://" onkeydown="if(event.key===\'Enter\')addWebsite()">'
        + '<button class="habit-add-btn" style="flex-shrink:0" onclick="addWebsite()">+</button>'
        + '</div>';
    html += '<div class="app-launcher-edit-actions">'
        + '<button class="app-launcher-save-btn" onclick="saveWebEdits()">Save</button>'
        + '<button class="app-launcher-cancel-btn" onclick="toggleWebEdit()">Cancel</button>'
        + '</div></div>';
    editor.innerHTML = html;
    // Focus first new input
    var firstInput = editor.querySelector('#newWebName');
    if (firstInput) setTimeout(function(){ firstInput.focus(); }, 50);
}

function addWebsite() {
    var name = document.getElementById('newWebName').value.trim();
    var url  = document.getElementById('newWebUrl').value.trim();
    if (!name || !url) return;
    if (url.indexOf('://') === -1) url = 'https://' + url;
    var sites = getWebsites();
    sites.push({ name: name, url: url, id: 'web_' + Date.now() });
    saveWebsites(sites);
    renderWebEditor();
}

function removeWebsite(idx) {
    var sites = getWebsites();
    sites.splice(idx, 1);
    saveWebsites(sites);
    renderWebEditor();
}

function saveWebEdits() {
    var sites = getWebsites();
    var rows = document.querySelectorAll('#webLauncherEditor .app-launcher-edit-row[data-idx]');
    rows.forEach(function(row, i) {
        if (i < sites.length) {
            var inputs = row.querySelectorAll('.app-launcher-edit-input');
            var n = inputs[0].value.trim();
            var u = inputs[1].value.trim();
            if (n) sites[i].name = n;
            if (u) {
                if (u.indexOf('://') === -1) u = 'https://' + u;
                sites[i].url = u;
            }
        }
    });
    saveWebsites(sites);
    toggleWebEdit();
}

// Pre-render so dropdown shows immediately on hover
renderWebList();

// Close when clicking outside
document.addEventListener('mousedown', function(e) {
    if (!e.target.closest('#webLauncherWrap')) closeWebLauncher();
});


// ── App Launcher ──
var APPS_KEY = 'dashboard-apps';
var SEED_APPS = [
    { name: 'ChatGPT', url: 'chatgpt://', id: 'app_chatgpt' },
    { name: 'Claude',  url: 'claude://',  id: 'app_claude'  },
];

function getApps() {
    var apps = [];
    try {
        var stored = localStorage.getItem(APPS_KEY);
        if (stored) apps = JSON.parse(stored);
    } catch(e) {}
    if (!apps.length) {
        apps = SEED_APPS.map(function(a) { return { name: a.name, url: a.url, id: a.id }; });
        saveApps(apps);
    }
    return apps;
}

function saveApps(apps) {
    try { localStorage.setItem(APPS_KEY, JSON.stringify(apps)); } catch(e) {}
}

function renderAppList() {
    var list = document.getElementById('appLauncherList');
    if (!list) return;
    var apps = getApps();
    var html = '';
    apps.forEach(function(app) {
        var urlEsc = app.url.replace(/"/g, '&quot;');
        var nameEsc = app.name.replace(/</g, '&lt;');
        html += '<a class="app-launcher-item" href="' + urlEsc + '" onclick="closeAppLauncher()">'
            + '<span class="app-launcher-icon"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></span>'
            + '<span>' + nameEsc + '</span>'
            + '</a>';
    });
    if (!apps.length) html = '<div style="padding:10px 14px;font-size:0.82em;color:var(--text-muted)">No apps. Click ✎ to add.</div>';
    list.innerHTML = html;
}

function toggleAppLauncher(e) {
    e.stopPropagation();
    e.preventDefault();
    var dd = document.getElementById('appLauncherDropdown');
    if (!dd) return;
    var isOpen = dd.classList.contains('open');
    // Close web launcher if open
    closeWebLauncher();
    if (isOpen) {
        closeAppLauncher();
    } else {
        renderAppList();
        dd.classList.add('open');
    }
}

function closeAppLauncher() {
    var dd = document.getElementById('appLauncherDropdown');
    if (dd) { dd.classList.remove('open'); }
    var ed = document.getElementById('appLauncherEditor');
    if (ed) ed.style.display = 'none';
    var list = document.getElementById('appLauncherList');
    if (list) list.style.display = '';
}

function toggleAppEdit() {
    var editor = document.getElementById('appLauncherEditor');
    var list = document.getElementById('appLauncherList');
    if (!editor || !list) return;
    var editing = editor.style.display !== 'none';
    if (editing) {
        editor.style.display = 'none';
        list.style.display = '';
        renderAppList();
    } else {
        list.style.display = 'none';
        editor.style.display = '';
        renderAppEditor();
    }
}

function renderAppEditor() {
    var editor = document.getElementById('appLauncherEditor');
    if (!editor) return;
    var apps = getApps();
    var html = '<div class="app-launcher-editor-inner">';
    apps.forEach(function(app, i) {
        html += '<div class="app-launcher-edit-row" data-idx="' + i + '">'
            + '<input class="app-launcher-edit-input" type="text" value="' + app.name.replace(/"/g,'&quot;') + '" placeholder="Name">'
            + '<input class="app-launcher-edit-input" type="text" value="' + app.url.replace(/"/g,'&quot;') + '" placeholder="app://">'
            + '<button class="habit-remove-btn" style="flex-shrink:0" onclick="removeApp(' + i + ')" title="Remove">&times;</button>'
            + '</div>';
    });
    html += '<div class="app-launcher-edit-row">'
        + '<input class="app-launcher-edit-input" type="text" id="newAppName" placeholder="Name">'
        + '<input class="app-launcher-edit-input" type="text" id="newAppUrl" placeholder="app://">'
        + '<button class="habit-add-btn" style="flex-shrink:0" onclick="addApp()">+</button>'
        + '</div>';
    html += '<div class="app-launcher-edit-actions">'
        + '<button class="app-launcher-save-btn" onclick="saveAppEdits()">Save</button>'
        + '<button class="app-launcher-cancel-btn" onclick="toggleAppEdit()">Cancel</button>'
        + '</div></div>';
    editor.innerHTML = html;
}

function addApp() {
    var name = document.getElementById('newAppName').value.trim();
    var url  = document.getElementById('newAppUrl').value.trim();
    if (!name || !url) return;
    var apps = getApps();
    apps.push({ name: name, url: url, id: 'app_' + Date.now() });
    saveApps(apps);
    renderAppEditor();
}

function removeApp(idx) {
    var apps = getApps();
    apps.splice(idx, 1);
    saveApps(apps);
    renderAppEditor();
}

function saveAppEdits() {
    var apps = getApps();
    var rows = document.querySelectorAll('#appLauncherEditor .app-launcher-edit-row[data-idx]');
    rows.forEach(function(row, i) {
        if (i < apps.length) {
            var inputs = row.querySelectorAll('.app-launcher-edit-input');
            var n = inputs[0].value.trim();
            var u = inputs[1].value.trim();
            if (n) apps[i].name = n;
            if (u) apps[i].url  = u;
        }
    });
    saveApps(apps);
    toggleAppEdit();
}

// Pre-render the app list so the CSS hover fallback shows content immediately
renderAppList();

// Close dropdown when clicking outside (use mousedown so it fires before toggleAppLauncher's click)
document.addEventListener('mousedown', function(e) {
    if (!e.target.closest('#appLauncherWrap')) closeAppLauncher();
});
