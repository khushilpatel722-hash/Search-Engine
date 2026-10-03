/* Runs before the page paints so the saved theme / animation choice has no flash. */
(function () {
  var root = document.documentElement;
  try {
    var theme = localStorage.getItem('privata-theme');
    if (!theme) theme = (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches) ? 'dark' : 'light';
    root.setAttribute('data-theme', theme);
    var anim = localStorage.getItem('privata-anim');
    var reduce = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (anim === 'off' || (anim === null && reduce)) root.classList.add('no-anim');
  } catch (e) { /* storage blocked: defaults are fine */ }
})();
