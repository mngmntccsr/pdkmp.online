// ============================================================
// map-common.js
// Logica condivisa della mappa PaddockMap.
// Usato sia da index.html (mappa laterale) sia da mappa.html
// (pagina dedicata). Qualsiasi modifica qui si applica automaticamente
// a entrambe le pagine — non serve più duplicare il codice.
// ============================================================

// Confini stretti attorno all'Italia (limita panning/zoom della mappa)
const ITALY_BOUNDS = L.latLngBounds([36.5, 6.6], [47.1, 18.5]);

// Verrà popolato da loadCityCoordinates()
let cityCoordinates = {};

// Carica il file coordinates.json (una volta sola, all'avvio della pagina)
async function loadCityCoordinates() {
  const res = await fetch('coordinates.json');
  cityCoordinates = await res.json();
  return cityCoordinates;
}

// Distanza in km tra due punti (usata dal filtro "raggio")
function haversineKm(lat1, lon1, lat2, lon2) {
  const R = 6371;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

// Crea la mappa Leaflet di base (tono neutro chiaro, coerente col resto del sito)
function createBaseMap(containerId) {
  const map = L.map(containerId, {
    maxBounds: ITALY_BOUNDS.pad(0.05),
    maxBoundsViscosity: 1.0,
    minZoom: 5,
    maxZoom: 12,
    zoomControl: true,
    attributionControl: true
  });
  map.setView([41.5, 12.5], 5);

  L.tileLayer('https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Esri, HERE, Garmin, &copy; OpenStreetMap contributors',
    maxZoom: 16
  }).addTo(map);

  L.tileLayer('https://services.arcgisonline.com/arcgis/rest/services/Canvas/World_Light_Gray_Reference/MapServer/tile/{z}/{y}/{x}', {
    maxZoom: 16
  }).addTo(map);

  return map;
}

function formatDateShort(dateString) {
  if (!dateString) return '';
  const date = new Date(dateString);
  return `${date.getDate()} ${date.toLocaleDateString('it-IT', { month: 'short' })}`;
}

// Raggruppa una lista di eventi per località (usando le coordinate note),
// ordina ogni gruppo per data, e segnala in console le località sconosciute.
//
// - events: array di eventi
// - getCitta: funzione che, dato un evento, restituisce il nome della città/circuito
function groupEventsByLocation(events, getCitta) {
  const groups = {};
  const missing = new Map(); // citta -> primo titolo evento trovato (per riconoscerlo più facilmente)

  events.forEach(ev => {
    const citta = getCitta(ev);
    const coords = citta ? cityCoordinates[citta] : null;

    if (!coords) {
      if (citta && !missing.has(citta)) {
        missing.set(citta, ev.titolo || '(titolo sconosciuto)');
      }
      return;
    }

    if (!groups[citta]) groups[citta] = { coords, items: [] };
    groups[citta].items.push(ev);
  });

  if (missing.size > 0) {
    console.warn(
      `PaddockMap — ${missing.size} localita' senza coordinate (non compaiono sulla mappa). ` +
      `Aggiungile a coordinates.json:`
    );
    console.table(Array.from(missing, ([citta, titolo]) => ({ citta, esempio_evento: titolo })));
  }

  Object.values(groups).forEach(g => {
    g.items.sort((a, b) => new Date(a.dataInizio) - new Date(b.dataInizio));
  });

  return Object.values(groups);
}

// Colori marker coerenti con la palette del sito
const MARKER_COLOR = '#FF4B24';
const MARKER_STROKE = '#FFFFFF';

// Crea un marker (pallino) per un gruppo di eventi nella stessa località,
// con popup navigabile a frecce se ci sono più eventi.
//
// - group: { coords: [lat, lng], items: [...eventi ordinati per data] }
// - buildEventHtml: funzione che, dato un singolo evento, restituisce l'HTML da mostrare nel popup
function createGroupMarker(group, buildEventHtml) {
  const marker = L.circleMarker(group.coords, {
    radius: 7,
    weight: 2,
    color: MARKER_STROKE,
    fillColor: MARKER_COLOR,
    fillOpacity: 0.95
  });

  marker._groupEvents = group.items;
  marker._groupIndex = 0;

  function renderHtml() {
    const items = marker._groupEvents;
    const idx = marker._groupIndex;
    const ev = items[idx];
    const showPrev = idx > 0;
    const showNext = idx < items.length - 1;

    const nav = items.length > 1 ? `
      <div class="map-popup-nav">
        <button class="popup-arrow popup-prev" style="${showPrev ? '' : 'visibility:hidden;'}">‹</button>
        <span class="popup-counter">${idx + 1} / ${items.length}</span>
        <button class="popup-arrow popup-next" style="${showNext ? '' : 'visibility:hidden;'}">›</button>
      </div>` : '';

    return `<div class="map-popup">${nav}${buildEventHtml(ev)}</div>`;
  }

  function update() {
    marker.setPopupContent(renderHtml());
    requestAnimationFrame(() => {
      const popupEl = marker.getPopup().getElement();
      if (!popupEl) return;
      const prevBtn = popupEl.querySelector('.popup-prev');
      const nextBtn = popupEl.querySelector('.popup-next');
      if (prevBtn) prevBtn.onclick = (e) => { e.stopPropagation(); marker._groupIndex--; update(); };
      if (nextBtn) nextBtn.onclick = (e) => { e.stopPropagation(); marker._groupIndex++; update(); };
    });
  }

  marker.bindPopup(renderHtml());
  marker.on('popupopen', () => {
    marker._groupIndex = 0;
    update();
  });

  return marker;
}
