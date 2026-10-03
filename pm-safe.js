/* PaddockMap — pm-safe.js
   Pulisce i dati del feed PRIMA che finiscano in innerHTML o negli attributi.
   Toglie < > " ` dai testi e accetta come link solo http/https. */
(function () {
  'use strict';
  var URL_FIELDS = { immagine: 1, linkBiglietti: 1, linkInfo: 1 };
  // true = ignora le immagini del feed (copiate da siti di terzi). Metti false solo
  // quando avrai un permesso scritto o immagini tue.
  var BLOCK_IMAGES = true;

  function text(v) {
    if (typeof v === 'string') return v.replace(/[<>"`]/g, '');
    if (Array.isArray(v)) return v.map(text);
    return v;
  }
  function url(v) {
    if (!v || typeof v !== 'string') return '';
    try {
      var u = new URL(v.trim(), location.href);
      if (u.protocol !== 'http:' && u.protocol !== 'https:') return '';
      return u.href.replace(/'/g, '%27');
    } catch (e) { return ''; }
  }

  window.pmCleanEvents = function (list) {
    if (!Array.isArray(list)) return [];
    return list.map(function (ev) {
      var out = {};
      Object.keys(ev || {}).forEach(function (k) {
        if (k === 'immagine' && BLOCK_IMAGES) { out[k] = ''; return; }
        out[k] = URL_FIELDS[k] ? url(ev[k]) : text(ev[k]);
      });
      return out;
    });
  };
})();
