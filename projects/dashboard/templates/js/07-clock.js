/* ── Analog Clock — Jony Ive ── */
(function () {
  var hourHand, minuteHand, secondHand, dateLabel;
  var running = false;
  var rafId = null;

  function initClock() {
    hourHand = document.getElementById('iveHourHand');
    minuteHand = document.getElementById('iveMinuteHand');
    secondHand = document.getElementById('iveSecondHand');
    dateLabel = document.getElementById('iveClockDate');
    if (!hourHand || !minuteHand || !secondHand) return;
    if (running) return;
    running = true;
    tick();
  }

  function tick() {
    var now = new Date();
    var h = now.getHours() % 12;
    var m = now.getMinutes();
    var s = now.getSeconds();
    var ms = now.getMilliseconds();

    // Smooth continuous rotation
    var secAngle = (s + ms / 1000) * 6;          // 6° per second
    var minAngle = (m + s / 60) * 6;              // 6° per minute
    var hourAngle = (h + m / 60 + s / 3600) * 30; // 30° per hour

    if (hourHand) hourHand.style.transform = 'rotate(' + hourAngle + 'deg)';
    if (minuteHand) minuteHand.style.transform = 'rotate(' + minAngle + 'deg)';
    if (secondHand) secondHand.style.transform = 'rotate(' + secAngle + 'deg)';

    // Update date label
    if (dateLabel) {
      var days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      var months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
      dateLabel.textContent = days[now.getDay()] + ', ' + months[now.getMonth()] + ' ' + now.getDate();
    }

    rafId = requestAnimationFrame(tick);
  }

  // Start on DOMContentLoaded or immediately if already loaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initClock);
  } else {
    initClock();
  }

  // Re-init after AJAX tab refresh
  document.addEventListener('calendarRefreshed', initClock);
})();
