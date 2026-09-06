// HWS by Danni — shared light/dark theme toggle. Loaded on every page.
(function () {
  var root = document.documentElement;
  var stored = localStorage.getItem('hws-theme');
  var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  var initial = stored || (prefersDark ? 'dark' : 'light');
  root.setAttribute('data-theme', initial);

  var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function applyTheme(next) {
    root.setAttribute('data-theme', next);
    localStorage.setItem('hws-theme', next);
  }

  function setTheme(next) {
    // Prefer a true cross-fade via the View Transitions API where available;
    // fall back to the CSS color transitions in motion.css / styles.css.
    if (document.startViewTransition && !reduceMotion) {
      document.startViewTransition(function () { applyTheme(next); });
    } else {
      applyTheme(next);
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    var toggle = document.getElementById('themeToggle');
    if (!toggle) return;
    toggle.addEventListener('click', function () {
      var current = root.getAttribute('data-theme');
      setTheme(current === 'light' ? 'dark' : 'light');
    });
  });
})();
