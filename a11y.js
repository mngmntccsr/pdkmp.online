/* PaddockMap — a11y.js
   Aggiunge tastiera, ruoli ed etichette agli elementi esistenti senza cambiare l'HTML.
   Includere con <script src="a11y.js" defer></script>. */
(function () {
  'use strict';
  var CLICKABLE = '.multi-select-display,.multi-select-option,.chip,.itinerant-badge';
  var uid = 0;

  function enhance() {
    document.querySelectorAll(CLICKABLE).forEach(function (el) {
      if (el.dataset.a11y) return;
      el.dataset.a11y = '1';
      el.tabIndex = 0;
      el.setAttribute('role', el.matches('.multi-select-option') ? 'option' : 'button');
      if (el.matches('.chip')) el.setAttribute('aria-pressed', el.classList.contains('selected'));
    });

    var labels = { '.disc-arrow.left': 'Disciplina precedente', '.disc-arrow.right': 'Disciplina successiva',
      '.popup-prev': 'Evento precedente', '.popup-next': 'Evento successivo' };
    Object.keys(labels).forEach(function (s) {
      document.querySelectorAll(s).forEach(function (b) { b.setAttribute('aria-label', labels[s]); });
    });
    document.querySelectorAll('.date-picker-nav').forEach(function (b, i) {
      b.setAttribute('aria-label', b.textContent.trim() === '‹' ? 'Mese precedente' : 'Mese successivo');
    });
    document.querySelectorAll('.panel-toggle').forEach(function (b) {
      b.setAttribute('aria-label', b.getAttribute('title') || 'Mostra o nascondi pannello');
    });
    document.querySelectorAll('.date-picker-day').forEach(function (b) {
      var m = /'(\d{4}-\d{2}-\d{2})'/.exec(b.getAttribute('onclick') || '');
      if (m) b.setAttribute('aria-label', new Date(m[1] + 'T12:00').toLocaleDateString('it-IT',
        { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }));
    });
    // Collega ogni <label> senza "for" al relativo controllo
    document.querySelectorAll('.filter-group').forEach(function (g) {
      var l = g.querySelector('label:not([for])');
      var c = g.querySelector('.multi-select-display,.date-picker-trigger');
      if (!l || !c || c.hasAttribute('aria-labelledby')) return;
      if (!l.id) l.id = 'pm-lbl-' + (++uid);
      c.setAttribute('aria-labelledby', l.id);
    });
    if (!document.querySelector('h1')) {
      var h = document.createElement('h1');
      h.className = 'pm-sr';
      h.textContent = 'PaddockMap: calendario degli eventi motorsport in Italia';
      document.body.insertBefore(h, document.body.firstChild);
    }
  }

  document.addEventListener('keydown', function (e) {
    var t = e.target;
    if ((e.key === 'Enter' || e.key === ' ') && t.matches && t.matches(CLICKABLE) && !t.matches('input')) {
      e.preventDefault();
      t.click();
      if (t.matches('.chip')) t.setAttribute('aria-pressed', t.classList.contains('selected'));
    }
    if (e.key === 'Escape') document.body.click();   // chiude menu e calendario
  });

  var timer;
  new MutationObserver(function () { clearTimeout(timer); timer = setTimeout(enhance, 80); })
    .observe(document.documentElement, { childList: true, subtree: true });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', enhance); else enhance();
})();
