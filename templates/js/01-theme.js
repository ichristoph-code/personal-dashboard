// ── Sunrise/Sunset (NOAA simplified algorithm) ──
function _getSunTimes(lat, lon) {
    try {
        var D2R = Math.PI / 180, R2D = 180 / Math.PI;
        var now = new Date();
        var start = new Date(now.getFullYear(), 0, 0);
        var day = Math.floor((now - start) / 86400000);
        var zenith = 90.833, lnHour = lon / 15;

        function calc(rising) {
            var t = day + ((rising ? 6 : 18) - lnHour) / 24;
            var M = 0.9856 * t - 3.289;
            var L = M + 1.916 * Math.sin(M * D2R) + 0.020 * Math.sin(2 * M * D2R) + 282.634;
            L = ((L % 360) + 360) % 360;
            var RA = R2D * Math.atan(0.91764 * Math.tan(L * D2R));
            RA = ((RA % 360) + 360) % 360;
            RA += (Math.floor(L / 90) * 90) - (Math.floor(RA / 90) * 90);
            RA /= 15;
            var sinDec = 0.39782 * Math.sin(L * D2R);
            var cosDec = Math.cos(Math.asin(sinDec));
            var cosH = (Math.cos(zenith * D2R) - sinDec * Math.sin(lat * D2R)) / (cosDec * Math.cos(lat * D2R));
            if (cosH > 1 || cosH < -1) return null;
            var H = rising ? (360 - R2D * Math.acos(cosH)) / 15 : R2D * Math.acos(cosH) / 15;
            var T = H + RA - 0.06571 * t - 6.622;
            var UT = ((T - lnHour) % 24 + 24) % 24;
            return UT - now.getTimezoneOffset() / 60;
        }

        var sr = calc(true), ss = calc(false);
        return (sr !== null && ss !== null) ? { sunrise: sr, sunset: ss } : null;
    } catch(e) { return null; }
}

function _applyAutoTheme() {
    var lat = (typeof DASHBOARD_LAT !== 'undefined') ? DASHBOARD_LAT : 37.89;
    var lon = (typeof DASHBOARD_LON !== 'undefined') ? DASHBOARD_LON : -122.54;
    var times = _getSunTimes(lat, lon);
    var hour = new Date().getHours() + new Date().getMinutes() / 60;
    var isDark = times ? (hour < times.sunrise || hour >= times.sunset)
                       : window.matchMedia('(prefers-color-scheme: dark)').matches;
    document.documentElement.classList.toggle('dark-mode', isDark);

    // Schedule flip at next transition
    if (times) {
        var next = (hour < times.sunrise) ? times.sunrise
                 : (hour < times.sunset)  ? times.sunset
                 : (times.sunrise + 24);
        var msUntil = (next - hour) * 3600000;
        setTimeout(function () {
            if (localStorage.getItem('dashboard-theme') === 'auto') _applyAutoTheme();
        }, msUntil + 60000);
    }
}

// ── Theme Management ──
function initTheme() {
    try {
        var saved = localStorage.getItem('dashboard-theme');
        if (saved === 'dark') {
            document.documentElement.classList.add('dark-mode');
        } else if (saved === 'light') {
            document.documentElement.classList.remove('dark-mode');
        } else {
            // 'auto' or unset — follow sunrise/sunset
            if (!saved) localStorage.setItem('dashboard-theme', 'auto');
            _applyAutoTheme();
        }
    } catch(e) {}
}
function toggleTheme() {
    var saved = localStorage.getItem('dashboard-theme') || 'auto';
    var next = saved === 'auto' ? 'dark' : saved === 'dark' ? 'light' : 'auto';
    try { localStorage.setItem('dashboard-theme', next); } catch(e) {}
    if (next === 'auto') {
        _applyAutoTheme();
    } else {
        document.documentElement.classList.toggle('dark-mode', next === 'dark');
    }
    if (typeof chartsInitialized !== 'undefined' && chartsInitialized) {
        updateChartTheme();
        if (typeof updateFinancialChartTheme === 'function') updateFinancialChartTheme();
    }
}
function getThemeColors() {
    var isDark = document.documentElement.classList.contains('dark-mode');
    return {
        text: isDark ? '#e2e8f0' : '#2d3748',
        textMuted: isDark ? '#a0aec0' : '#718096',
        grid: isDark ? 'rgba(255,255,255,0.06)' : 'rgba(0,0,0,0.04)',
        barBg: isDark ? 'rgba(127, 156, 245, 0.75)' : 'rgba(102, 126, 234, 0.75)',
        barBorder: isDark ? 'rgba(127, 156, 245, 1)' : 'rgba(102, 126, 234, 1)',
        barGradientStart: isDark ? 'rgba(127, 156, 245, 0.85)' : 'rgba(102, 126, 234, 0.85)',
        barGradientEnd: isDark ? 'rgba(183, 148, 244, 0.7)' : 'rgba(118, 75, 162, 0.7)',
    };
}
var pieChartInstance = null;
var barChartInstance = null;
function updateChartTheme() {
    var colors = getThemeColors();
    if (pieChartInstance) {
        pieChartInstance.options.plugins.legend.labels.color = colors.textMuted;
        pieChartInstance.update();
    }
    if (barChartInstance) {
        // Rebuild gradient for new theme
        var barCanvas = document.getElementById('categoryChart');
        if (barCanvas) {
            var barCtx = barCanvas.getContext('2d');
            var grad = barCtx.createLinearGradient(0, 0, barCanvas.width, 0);
            grad.addColorStop(0, colors.barGradientStart);
            grad.addColorStop(1, colors.barGradientEnd);
            barChartInstance.data.datasets[0].backgroundColor = grad;
        }
        barChartInstance.options.scales.x.grid.color = colors.grid;
        barChartInstance.options.scales.x.ticks.color = colors.textMuted;
        barChartInstance.options.scales.y.ticks.color = colors.textMuted;
        barChartInstance.update();
    }
}
initTheme();

// ── Privacy Toggle (financial summary blur) ──
function initPrivacy() {
    try {
        var el = document.getElementById('summaryCards');
        if (!el) return;
        // Always start hidden — never restore a previously revealed state
        el.classList.add('privacy-blur');
    } catch(e) {}
}
function togglePrivacy() {
    var el = document.getElementById('summaryCards');
    if (!el) return;
    el.classList.toggle('privacy-blur');
    // Intentionally not saved to localStorage — resets to hidden on next visit
}

// ── Privacy Toggle (Today finance card) ──
function initTodayFinancePrivacy() {
    // Always start hidden when visiting the Today tab
    document.body.classList.add('today-finance-on');
}
function toggleTodayFinancePrivacy(e) {
    if (e) e.stopPropagation();
    document.body.classList.toggle('today-finance-on');
}
