/* Rotating Unsplash background photos — disabled, using CSS gradient instead */
(function () {
    'use strict';
    return; // gradient background active

    const KEY = (typeof UNSPLASH_ACCESS_KEY !== 'undefined') ? UNSPLASH_ACCESS_KEY : '';
    if (!KEY) return;

    const CACHE_KEY    = 'unsplash_photos_v2';
    const CACHE_TS_KEY = 'unsplash_ts_v2';
    const CACHE_TTL    = 12 * 60 * 60 * 1000;   // 12h
    const ROTATE_MS    = 10 * 60 * 1000;         // rotate every 10 min
    const QUERIES      = ['golden hour landscape', 'coast ocean waves', 'forest mountains nature', 'aerial nature landscape', 'california nature'];

    let photos = [];
    let idx    = 0;
    let layerA, layerB, creditEl;
    let active = 'A';   // which layer is currently on top
    let enabled = localStorage.getItem('bg_photo_enabled') !== 'false';

    /* ── DOM setup ── */
    function createLayers() {
        layerA = document.createElement('div');
        layerA.id = 'bgPhotoA';
        layerB = document.createElement('div');
        layerB.id = 'bgPhotoB';
        creditEl = document.createElement('a');
        creditEl.id = 'bgCredit';
        creditEl.target = '_blank';
        creditEl.rel = 'noopener noreferrer';
        document.body.prepend(layerB);
        document.body.prepend(layerA);
        document.body.appendChild(creditEl);
    }

    /* ── Cross-fade to a photo ── */
    function showPhoto(photo) {
        if (!photo || !enabled) return;

        const top    = active === 'A' ? layerA : layerB;
        const bottom = active === 'A' ? layerB : layerA;

        // Load new image on the hidden bottom layer
        bottom.style.backgroundImage = `url('${photo.url}')`;
        bottom.style.zIndex = '-2';
        bottom.style.opacity = '0';

        // Brief tick so the browser registers the new bg before fading
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                // Promote bottom → top
                bottom.style.zIndex = '-1';
                bottom.style.opacity = '1';
                // Demote old top → bottom
                top.style.zIndex = '-2';
                top.style.opacity = '0';
                active = (active === 'A') ? 'B' : 'A';
            });
        });

        // Update credit link
        if (photo.photographer) {
            creditEl.textContent = `📷 ${photo.photographer} / Unsplash`;
            creditEl.href = photo.profileUrl || '#';
        }
    }

    function nextPhoto() {
        if (!photos.length || !enabled) return;
        idx = (idx + 1) % photos.length;
        showPhoto(photos[idx]);
    }

    /* ── Fetch from Unsplash (with localStorage cache) ── */
    async function fetchPhotos() {
        const cached   = localStorage.getItem(CACHE_KEY);
        const cachedTs = parseInt(localStorage.getItem(CACHE_TS_KEY) || '0', 10);
        if (cached && Date.now() - cachedTs < CACHE_TTL) {
            try { photos = JSON.parse(cached); return; } catch (_) {}
        }

        const query = QUERIES[Math.floor(Math.random() * QUERIES.length)];
        const url   = `https://api.unsplash.com/photos/random?count=20&query=${encodeURIComponent(query)}&orientation=landscape&client_id=${KEY}`;
        try {
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            photos = data.map(p => ({
                url:        p.urls.regular,
                photographer: p.user.name,
                profileUrl: `${p.user.links.html}?utm_source=personal_dashboard&utm_medium=referral`,
            }));
            localStorage.setItem(CACHE_KEY,    JSON.stringify(photos));
            localStorage.setItem(CACHE_TS_KEY, Date.now().toString());
        } catch (e) {
            console.warn('[bg] Unsplash fetch failed:', e);
        }
    }

    /* ── Enable / disable ── */
    function applyEnabled() {
        if (enabled) {
            document.body.classList.add('has-bg-photo');
            layerA.style.display = '';
            layerB.style.display = '';
            creditEl.style.display = '';
            if (photos.length) showPhoto(photos[idx]);
        } else {
            document.body.classList.remove('has-bg-photo');
            layerA.style.opacity = '0';
            layerB.style.opacity = '0';
            creditEl.style.display = 'none';
        }
    }

    window.toggleBgPhoto = function () {
        enabled = !enabled;
        localStorage.setItem('bg_photo_enabled', enabled ? 'true' : 'false');
        applyEnabled();
    };

    /* ── Init ── */
    async function init() {
        createLayers();
        await fetchPhotos();
        if (!photos.length) return;

        // Shuffle so each session starts at a random photo
        photos.sort(() => Math.random() - 0.5);

        applyEnabled();
        setInterval(nextPhoto, ROTATE_MS);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
