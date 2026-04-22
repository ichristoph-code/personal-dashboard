/* ── Contacts Tab — list interaction + detail rendering ── */

var _DEFAULT_AVATAR = "data:image/svg+xml,"
    + "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 40 40'%3E"
    + "%3Ccircle cx='20' cy='20' r='20' fill='%23a0aec0'/%3E"
    + "%3Ccircle cx='20' cy='15' r='7' fill='%23fff'/%3E"
    + "%3Cpath d='M6 36a14 14 0 0 1 28 0' fill='%23fff'/%3E"
    + "%3C/svg%3E";


function selectContact(cid) {
    // Highlight in sidebar
    document.querySelectorAll('.contacts-item').forEach(function(el) {
        el.classList.toggle('active', parseInt(el.dataset.cid) === cid);
    });

    var detail = document.getElementById('contactsDetail');
    if (!detail) return;

    // Find contact scalar data
    var contacts = window.CONTACTS_INDEX || [];
    var c = null;
    for (var i = 0; i < contacts.length; i++) {
        if (contacts[i].id === cid) { c = contacts[i]; break; }
    }
    if (!c) {
        detail.innerHTML = '<div class="contacts-detail-empty"><p>Contact not found</p></div>';
        return;
    }

    // Show loading state while fetching multi-value detail
    detail.innerHTML = '<div class="contacts-detail-empty"><p style="color:var(--text-muted)">Loading\u2026</p></div>';

    var contactId = c.contact_id;
    if (!contactId) {
        // No UUID (SQLite fallback contact) — render with scalar data only
        _renderContactDetail(detail, c, {});
        return;
    }

    fetch('/api/contact?id=' + encodeURIComponent(contactId))
        .then(function(r) { return r.json(); })
        .then(function(detailData) { _renderContactDetail(detail, c, detailData); })
        .catch(function() { _renderContactDetail(detail, c, {}); });
}


function _renderContactDetail(detail, c, d) {
    // Merge scalar data (c) with lazy-loaded multi-value data (d)
    var phones    = d.phones    || [];
    var emails    = d.emails    || [];
    var addresses = d.addresses || [];
    var urls      = d.urls      || [];
    var ims       = d.ims       || [];
    var related   = d.related   || [];

    var thumb = d.thumb || c.thumb || _DEFAULT_AVATAR;
    var parts = [];

    // Header
    parts.push('<div class="contact-detail-card">');
    parts.push('<div class="contact-detail-header">');
    parts.push('<img class="contact-detail-avatar" src="' + _escHtml(thumb) + '" alt="" />');
    parts.push('<div>');
    parts.push('<h2 class="contact-detail-name">' + _escHtml(c.name) + '</h2>');
    if (c.nickname) {
        parts.push('<p class="contact-detail-nickname">&ldquo;' + _escHtml(c.nickname) + '&rdquo;</p>');
    }
    if (c.jobtitle || c.department) {
        var jobLine = [c.jobtitle, c.department].filter(Boolean).join(' \u00b7 ');
        parts.push('<p class="contact-detail-job">' + _escHtml(jobLine) + '</p>');
    }
    if (c.org && c.org !== c.name) {
        parts.push('<p class="contact-detail-org">' + _escHtml(c.org) + '</p>');
    }
    parts.push('</div></div>');

    // Birthday
    if (c.birthday) {
        var months = ['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
        var bdParts = c.birthday.split('-');
        var bm = parseInt(bdParts[0]);
        var bd = parseInt(bdParts[1]);
        var bdayStr = months[bm] + ' ' + bd;

        var ageHtml = '';
        if (c.birthday_year) {
            var now = new Date();
            var age = now.getFullYear() - c.birthday_year;
            var bdThisYear = new Date(now.getFullYear(), bm - 1, bd);
            if (bdThisYear > now) age--;
            ageHtml = '<span class="contact-birthday-age">Age ' + age + '</span>';
        }

        parts.push('<div class="contact-section">');
        parts.push('<div class="contact-section-title">Birthday</div>');
        parts.push('<div class="contact-birthday-display">');
        parts.push('<span class="bday-icon">\uD83C\uDF82</span>');
        parts.push('<span>' + _escHtml(bdayStr) + (c.birthday_year ? ', ' + c.birthday_year : '') + '</span>');
        parts.push(ageHtml);
        parts.push('</div></div>');
    }

    // Phones
    if (phones.length > 0) {
        parts.push('<div class="contact-section">');
        parts.push('<div class="contact-section-title">Phone</div>');
        for (var i = 0; i < phones.length; i++) {
            var p = phones[i];
            parts.push('<div class="contact-info-row">');
            parts.push('<span class="contact-info-label">' + _escHtml(p.label) + '</span>');
            parts.push('<span class="contact-info-value"><a href="tel:' + _escHtml(p.number) + '">' + _escHtml(p.number) + '</a></span>');
            parts.push('</div>');
        }
        parts.push('</div>');
    }

    // Emails
    if (emails.length > 0) {
        parts.push('<div class="contact-section">');
        parts.push('<div class="contact-section-title">Email</div>');
        for (var i = 0; i < emails.length; i++) {
            var e = emails[i];
            parts.push('<div class="contact-info-row">');
            parts.push('<span class="contact-info-label">' + _escHtml(e.label) + '</span>');
            parts.push('<span class="contact-info-value"><a href="mailto:' + _escHtml(e.address) + '">' + _escHtml(e.address) + '</a></span>');
            parts.push('</div>');
        }
        parts.push('</div>');
    }

    // Addresses
    if (addresses.length > 0) {
        parts.push('<div class="contact-section">');
        parts.push('<div class="contact-section-title">Address</div>');
        for (var i = 0; i < addresses.length; i++) {
            var a = addresses[i];
            var lines = [];
            if (a.street) lines.push(a.street);
            var cityLine = [a.city, a.state, a.zip].filter(Boolean).join(' ');
            if (cityLine) lines.push(cityLine);
            if (a.country) lines.push(a.country);
            if (!lines.length) continue;
            var mapsUrl = 'https://maps.apple.com/?q=' + encodeURIComponent(lines.join(', '));
            parts.push('<div class="contact-info-row contact-info-row--block">');
            parts.push('<span class="contact-info-label">' + _escHtml(a.label) + '</span>');
            parts.push('<span class="contact-info-value"><a href="' + mapsUrl + '" target="_blank">'
                + _escHtml(lines.join('\n')).replace(/\n/g, '<br>') + '</a></span>');
            parts.push('</div>');
        }
        parts.push('</div>');
    }

    // URLs
    if (urls.length > 0) {
        parts.push('<div class="contact-section">');
        parts.push('<div class="contact-section-title">URL</div>');
        for (var i = 0; i < urls.length; i++) {
            var u = urls[i];
            var href = u.url.match(/^https?:\/\//) ? u.url : 'https://' + u.url;
            parts.push('<div class="contact-info-row">');
            parts.push('<span class="contact-info-label">' + _escHtml(u.label) + '</span>');
            parts.push('<span class="contact-info-value"><a href="' + _escHtml(href) + '" target="_blank">'
                + _escHtml(u.url) + '</a></span>');
            parts.push('</div>');
        }
        parts.push('</div>');
    }

    // IM / Social
    if (ims.length > 0) {
        parts.push('<div class="contact-section">');
        parts.push('<div class="contact-section-title">Messaging</div>');
        for (var i = 0; i < ims.length; i++) {
            var im = ims[i];
            parts.push('<div class="contact-info-row">');
            parts.push('<span class="contact-info-label">' + _escHtml(im.label) + '</span>');
            parts.push('<span class="contact-info-value">' + _escHtml(im.username) + '</span>');
            parts.push('</div>');
        }
        parts.push('</div>');
    }

    // Related names
    if (related.length > 0) {
        parts.push('<div class="contact-section">');
        parts.push('<div class="contact-section-title">Related</div>');
        for (var i = 0; i < related.length; i++) {
            var r = related[i];
            parts.push('<div class="contact-info-row">');
            parts.push('<span class="contact-info-label">' + _escHtml(r.label) + '</span>');
            parts.push('<span class="contact-info-value">' + _escHtml(r.name) + '</span>');
            parts.push('</div>');
        }
        parts.push('</div>');
    }

    // Notes
    if (c.note) {
        parts.push('<div class="contact-section">');
        parts.push('<div class="contact-section-title">Notes</div>');
        parts.push('<div class="contact-note">' + _escHtml(c.note) + '</div>');
        parts.push('</div>');
    }

    parts.push('</div>'); // contact-detail-card

    detail.innerHTML = parts.join('');
}


function filterContacts(query) {
    query = (query || '').toLowerCase().trim();
    var items = document.querySelectorAll('.contacts-item');
    var groups = document.querySelectorAll('.contacts-letter-group');

    // Track which letter groups have visible items
    var visibleLetters = {};

    items.forEach(function(item) {
        var name = (item.querySelector('.contacts-item-name') || {}).textContent || '';
        var org = (item.querySelector('.contacts-item-org') || {}).textContent || '';
        var match = !query || name.toLowerCase().indexOf(query) !== -1
                           || org.toLowerCase().indexOf(query) !== -1;
        item.style.display = match ? '' : 'none';
        if (match) {
            var group = item.closest('.contacts-letter-group');
            if (group) visibleLetters[group.dataset.letter] = true;
        }
    });

    // Hide letter groups with no visible items
    groups.forEach(function(g) {
        g.style.display = visibleLetters[g.dataset.letter] ? '' : 'none';
    });
}


function initContactsList() {
    // Select first contact if none selected
    var first = document.querySelector('.contacts-item');
    if (first && first.dataset.cid) {
        selectContact(parseInt(first.dataset.cid));
    }

    // Keyboard navigation: ↑/↓ to move, / to focus search
    document.addEventListener('keydown', function(e) {
        // Only when Contacts tab is active
        var panel = document.getElementById('tab-contacts');
        if (!panel || panel.style.display === 'none') return;
        // Don't intercept when typing in an input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
            e.preventDefault();
            var items = Array.from(document.querySelectorAll(
                '.contacts-item:not([style*="display: none"])'
            ));
            var current = document.querySelector('.contacts-item.active');
            var idx = current ? items.indexOf(current) : -1;
            var next = e.key === 'ArrowDown' ? items[idx + 1] : items[idx - 1];
            if (next) {
                next.click();
                next.scrollIntoView({ block: 'nearest' });
            }
        } else if (e.key === '/') {
            e.preventDefault();
            var search = document.querySelector('.contacts-search');
            if (search) search.focus();
        }
    });
}


// Simple HTML escaper
function _escHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}
