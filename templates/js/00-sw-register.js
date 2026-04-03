// 00-sw-register.js -- Register service worker for offline PWA support
if ('serviceWorker' in navigator) {
    window.addEventListener('load', function() {
        navigator.serviceWorker.register('/sw.js').then(function(reg) {
            console.log('SW registered, scope:', reg.scope);
            // Check for updates hourly
            setInterval(function() { reg.update(); }, 60 * 60 * 1000);
        }).catch(function(err) {
            console.log('SW registration failed:', err);
        });
    });
}
