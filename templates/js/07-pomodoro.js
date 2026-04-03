/* ── Pomodoro Timer Widget ── */

(function() {
    'use strict';

    var WORK_MINS = 25;
    var SHORT_BREAK_MINS = 5;
    var LONG_BREAK_MINS = 15;
    var SESSIONS_BEFORE_LONG = 4;

    // Circumference of the SVG ring (r=12, C=2*PI*12 ≈ 75.4)
    var RING_CIRCUMFERENCE = 2 * Math.PI * 12;

    // State
    var PHASES = { IDLE: 'idle', WORK: 'work', SHORT_BREAK: 'short', LONG_BREAK: 'long' };
    var phase = PHASES.IDLE;
    var timeRemaining = WORK_MINS * 60;  // seconds
    var totalTime = WORK_MINS * 60;
    var sessionsCompleted = 0;
    var isRunning = false;
    var isPaused = false;
    var intervalId = null;

    // Storage key
    var STORAGE_KEY = 'dashboard-pomodoro';

    // DOM refs (set on init)
    var widget, ringProgress, timeDisplay, phaseDisplay, dots, playIcon;

    function init() {
        widget = document.getElementById('pomoWidget');
        if (!widget) return;

        ringProgress = widget.querySelector('.pomo-ring-progress');
        timeDisplay = widget.querySelector('.pomo-time');
        phaseDisplay = widget.querySelector('.pomo-phase');
        playIcon = widget.querySelector('.pomo-play-icon');
        dots = widget.querySelectorAll('.pomo-dot');

        // Restore state
        restoreState();

        // Main click = start/pause
        widget.addEventListener('click', function(e) {
            // Don't trigger on control buttons
            if (e.target.closest('.pomo-btn')) return;
            toggleTimer();
        });

        // Reset button
        var resetBtn = widget.querySelector('.pomo-reset-btn');
        if (resetBtn) {
            resetBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                resetTimer();
            });
        }

        // Skip button
        var skipBtn = widget.querySelector('.pomo-skip-btn');
        if (skipBtn) {
            skipBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                skipPhase();
            });
        }

        updateDisplay();
    }

    function toggleTimer() {
        if (phase === PHASES.IDLE) {
            startPhase(PHASES.WORK);
        } else if (isRunning) {
            pause();
        } else {
            resume();
        }
    }

    function startPhase(newPhase) {
        phase = newPhase;
        isRunning = true;
        isPaused = false;

        switch (newPhase) {
            case PHASES.WORK:
                totalTime = WORK_MINS * 60;
                break;
            case PHASES.SHORT_BREAK:
                totalTime = SHORT_BREAK_MINS * 60;
                break;
            case PHASES.LONG_BREAK:
                totalTime = LONG_BREAK_MINS * 60;
                break;
        }
        timeRemaining = totalTime;

        clearInterval(intervalId);
        intervalId = setInterval(tick, 1000);

        updateWidgetClass();
        updateDisplay();
        saveState();
    }

    function pause() {
        isRunning = false;
        isPaused = true;
        clearInterval(intervalId);
        widget.classList.add('pomo-paused');
        saveState();
    }

    function resume() {
        isRunning = true;
        isPaused = false;
        widget.classList.remove('pomo-paused');
        clearInterval(intervalId);
        intervalId = setInterval(tick, 1000);
        saveState();
    }

    function resetTimer() {
        clearInterval(intervalId);
        phase = PHASES.IDLE;
        isRunning = false;
        isPaused = false;
        sessionsCompleted = 0;
        timeRemaining = WORK_MINS * 60;
        totalTime = WORK_MINS * 60;

        updateWidgetClass();
        updateDisplay();
        saveState();
    }

    function skipPhase() {
        clearInterval(intervalId);
        phaseComplete();
    }

    function tick() {
        timeRemaining--;
        if (timeRemaining <= 0) {
            timeRemaining = 0;
            clearInterval(intervalId);
            phaseComplete();
        }
        updateDisplay();

        // Save state every 15 seconds (not every tick, for performance)
        if (timeRemaining % 15 === 0) saveState();
    }

    function phaseComplete() {
        playNotification();

        if (phase === PHASES.WORK) {
            sessionsCompleted++;
            // Every Nth session → long break, otherwise short break
            if (sessionsCompleted % SESSIONS_BEFORE_LONG === 0) {
                startPhase(PHASES.LONG_BREAK);
            } else {
                startPhase(PHASES.SHORT_BREAK);
            }
        } else {
            // Break is over → start next work session
            startPhase(PHASES.WORK);
        }
    }

    function updateDisplay() {
        if (!timeDisplay || !ringProgress) return;

        // Time text
        var mins = Math.floor(timeRemaining / 60);
        var secs = timeRemaining % 60;
        timeDisplay.textContent = (mins < 10 ? '0' : '') + mins + ':' + (secs < 10 ? '0' : '') + secs;

        // Phase label
        if (phaseDisplay) {
            switch (phase) {
                case PHASES.WORK: phaseDisplay.textContent = 'Focus'; break;
                case PHASES.SHORT_BREAK: phaseDisplay.textContent = 'Break'; break;
                case PHASES.LONG_BREAK: phaseDisplay.textContent = 'Long Break'; break;
                default: phaseDisplay.textContent = ''; break;
            }
        }

        // SVG ring progress
        var progress = totalTime > 0 ? (totalTime - timeRemaining) / totalTime : 0;
        var offset = RING_CIRCUMFERENCE * (1 - progress);
        ringProgress.style.strokeDasharray = RING_CIRCUMFERENCE;
        ringProgress.style.strokeDashoffset = offset;

        // Session dots
        if (dots && dots.length) {
            for (var i = 0; i < dots.length; i++) {
                dots[i].classList.toggle('filled', i < (sessionsCompleted % SESSIONS_BEFORE_LONG));
            }
        }

        // Play icon visibility
        if (playIcon) {
            playIcon.style.display = (phase === PHASES.IDLE) ? '' : 'none';
        }

        // Title — update with time if running
        updateWidgetTitle();
    }

    function updateWidgetClass() {
        if (!widget) return;
        widget.classList.remove('pomo-working', 'pomo-break', 'pomo-long-break', 'pomo-paused');
        switch (phase) {
            case PHASES.WORK: widget.classList.add('pomo-working'); break;
            case PHASES.SHORT_BREAK: widget.classList.add('pomo-break'); break;
            case PHASES.LONG_BREAK: widget.classList.add('pomo-long-break'); break;
        }
    }

    function updateWidgetTitle() {
        if (!widget) return;
        if (phase === PHASES.IDLE) {
            widget.title = 'Start Pomodoro (25 min focus)';
        } else {
            var phaseNames = { work: 'Focus', short: 'Short Break', long: 'Long Break' };
            widget.title = (phaseNames[phase] || '') + ' — ' + timeDisplay.textContent
                + ' (' + sessionsCompleted + '/' + SESSIONS_BEFORE_LONG + ' sessions)';
        }
    }

    // ── Audio notification ──
    function playNotification() {
        try {
            var ctx = new (window.AudioContext || window.webkitAudioContext)();
            // Play a pleasant two-tone chime
            var freqs = [587.33, 880]; // D5, A5
            freqs.forEach(function(freq, i) {
                var osc = ctx.createOscillator();
                var gain = ctx.createGain();
                osc.connect(gain);
                gain.connect(ctx.destination);
                osc.frequency.value = freq;
                osc.type = 'sine';
                var start = ctx.currentTime + (i * 0.2);
                gain.gain.setValueAtTime(0.3, start);
                gain.gain.exponentialRampToValueAtTime(0.01, start + 0.4);
                osc.start(start);
                osc.stop(start + 0.4);
            });
        } catch(e) {
            // Audio not available — silent fail
        }
    }

    // ── Persistence ──
    function saveState() {
        try {
            localStorage.setItem(STORAGE_KEY, JSON.stringify({
                phase: phase,
                timeRemaining: timeRemaining,
                totalTime: totalTime,
                sessionsCompleted: sessionsCompleted,
                isRunning: isRunning,
                isPaused: isPaused,
                savedAt: Date.now(),
            }));
        } catch(e) {}
    }

    function restoreState() {
        try {
            var data = JSON.parse(localStorage.getItem(STORAGE_KEY));
            if (!data || data.phase === PHASES.IDLE) return;

            phase = data.phase;
            totalTime = data.totalTime || WORK_MINS * 60;
            sessionsCompleted = data.sessionsCompleted || 0;

            if (data.isRunning && !data.isPaused) {
                // Account for time elapsed while page was closed
                var elapsed = Math.floor((Date.now() - data.savedAt) / 1000);
                timeRemaining = Math.max(0, (data.timeRemaining || 0) - elapsed);

                if (timeRemaining <= 0) {
                    // Phase finished while we were away — advance
                    phaseComplete();
                    return;
                }

                isRunning = true;
                isPaused = false;
                intervalId = setInterval(tick, 1000);
            } else {
                // Was paused
                timeRemaining = data.timeRemaining || 0;
                isRunning = false;
                isPaused = true;
            }

            updateWidgetClass();
            updateDisplay();
        } catch(e) {}
    }

    // ── Keyboard shortcut (P) ──
    // Registered externally in 13-keyboard-widgets.js

    // Expose for external use
    window.togglePomodoro = toggleTimer;
    window.resetPomodoro = resetTimer;
    window.initPomodoro = init;

    // Auto-init when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
