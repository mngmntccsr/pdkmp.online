/* PaddockMap — consent.js
   Include in OGNI pagina, come PRIMO script nel <head>, e RIMUOVI gli snippet
   Google tag (gtag.js) da index.html e mappa.html: li carica questo file,
   ma solo dopo il consenso.                                               */
(function () {
  'use strict';
  var GA_ID = 'G-F54J4RR4YY';
  var KEY = 'pm_consent';
  var MONTHS6 = 1000 * 60 * 60 * 24 * 182;
  var MAIL = 'managementcesar37@gmail.com';

  // Prima del consenso gtag() non fa nulla e non invia nulla.
  window.dataLayer = window.dataLayer || [];
  window.gtag = function () {};

  function read() {
    try {
      var c = JSON.parse(localStorage.getItem(KEY));
      if (c && Date.now() - c.t < MONTHS6) return c;
    } catch (e) {}
    return null;
  }
  function save(analytics) {
    try { localStorage.setItem(KEY, JSON.stringify({ a: analytics, t: Date.now() })); } catch (e) {}
  }

  function enableAnalytics() {
    if (document.getElementById('pm-ga')) return;
    window.gtag = function () { window.dataLayer.push(arguments); };
    var s = document.createElement('script');
    s.id = 'pm-ga'; s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + GA_ID;
    document.head.appendChild(s);
    gtag('js', new Date());
    gtag('config', GA_ID, { anonymize_ip: true });
  }

  function disableAnalytics() {
    window.gtag = function () {};
    document.cookie.split(';').forEach(function (c) {
      var n = c.split('=')[0].trim();
      if (n.indexOf('_ga') === 0) {
        document.cookie = n + '=; Max-Age=0; path=/';
        document.cookie = n + '=; Max-Age=0; path=/; domain=' + location.hostname;
      }
    });
  }

  function apply(c) { if (c && c.a) enableAnalytics(); else disableAnalytics(); }

  var css = document.createElement('style');
  css.textContent =
    '.pm-cb{position:fixed;left:50%;bottom:16px;transform:translateX(-50%);z-index:100001;width:min(560px,calc(100% - 24px));' +
    'background:#fff;color:var(--ink,#12151B);border:1px solid var(--line-strong,rgba(18,21,27,.14));border-radius:var(--radius-lg,20px);' +
    'box-shadow:var(--shadow-pop,0 24px 60px -16px rgba(18,21,27,.32));padding:1.1rem 1.25rem;font:0.85rem/1.5 var(--font,system-ui)}' +
    '.pm-cb p{margin:0 0 .8rem}.pm-cb a{color:var(--accent-dark,#E23D14);font-weight:600}' +
    '.pm-cb-row{display:flex;gap:.5rem}' +
    '.pm-cb button{flex:1;padding:.7rem 1rem;border-radius:999px;border:0;background:var(--ink,#12151B);color:#fff;font:600 .85rem var(--font,system-ui);cursor:pointer}' +
    '.pm-cb button:focus-visible,.pm-legal a:focus-visible,.pm-legal button:focus-visible{outline:3px solid #12151B;outline-offset:2px}' +
    '.pm-legal{font-size:.78rem;display:flex;flex-wrap:wrap;gap:.3rem .9rem;justify-content:center;margin-top:.6rem}' +
    '.pm-legal a,.pm-legal button{color:inherit;background:none;border:0;font:inherit;text-decoration:underline;cursor:pointer;padding:0}' +
    '.pm-legal.pm-fixed{position:fixed;left:8px;bottom:6px;z-index:900;background:rgba(255,255,255,.92);color:#12151B;padding:.3rem .6rem;border-radius:999px;margin:0}';
  document.head.appendChild(css);

  function banner() {
    var b = document.createElement('div');
    b.className = 'pm-cb'; b.setAttribute('role', 'dialog'); b.setAttribute('aria-label', 'Cookie e privacy');
    b.innerHTML =
      '<p>Usiamo strumenti tecnici necessari al funzionamento del sito. Con il tuo consenso usiamo anche Google Analytics ' +
      'per capire come viene usato PaddockMap. Puoi cambiare idea in ogni momento. ' +
      '<a href="legale.html#cookie">Cookie policy</a> · <a href="legale.html#privacy">Privacy</a></p>' +
      '<div class="pm-cb-row"><button type="button" id="pmNo">Rifiuta</button><button type="button" id="pmYes">Accetta</button></div>';
    document.body.appendChild(b);
    function done(v) { save(v); apply({ a: v }); b.remove(); }
    b.querySelector('#pmNo').onclick = function () { done(false); };
    b.querySelector('#pmYes').onclick = function () { done(true); };
    b.querySelector('#pmNo').focus();
  }

  function legalLinks() {
    var d = document.createElement('div');
    d.className = 'pm-legal';
    d.innerHTML =
      '<a href="legale.html#privacy">Privacy</a><a href="legale.html#cookie">Cookie</a><a href="legale.html#termini">Termini</a>' +
      '<button type="button" id="pmPrefs">Preferenze cookie</button>' +
      '<a href="mailto:' + MAIL + '?subject=Richiesta%20cancellazione%20dati%20PaddockMap&body=Chiedo%20la%20cancellazione%20dei%20dati%20associati%20all%27email%20del%20mio%20account.">Cancella i miei dati</a>';
    var f = document.querySelector('footer');
    if (f && getComputedStyle(f).display !== 'none') f.appendChild(d);
    else { d.classList.add('pm-fixed'); document.body.appendChild(d); }
    d.querySelector('#pmPrefs').onclick = function () {
      try { localStorage.removeItem(KEY); } catch (e) {}
      disableAnalytics();
      if (!document.querySelector('.pm-cb')) banner();
    };
  }

  function init() {
    var c = read();
    apply(c);
    if (!c) banner();
    legalLinks();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
