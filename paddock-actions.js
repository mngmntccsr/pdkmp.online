/* ============================================================
   PADDOCKMAP — paddock-actions.js
   Gestisce i pulsanti ❤️ Salva evento / 🏁 Segui circuito
   sulle card eventi. Richiede che auth.js sia già caricato
   (usa window.pmSupabase e window.pmOpenAuthModal).
   ============================================================ */

(function () {
  'use strict';

  const style = document.createElement('style');
  style.textContent = `
    .pm-quick-actions { display:flex; gap:0.4rem; margin-bottom:0.5rem; }
    .pm-icon-btn {
      background:#fff; border:1.5px solid #e0e0e0; border-radius:6px;
      width:34px; height:34px; font-size:1rem; cursor:pointer;
      display:flex; align-items:center; justify-content:center;
      transition:all .15s;
    }
    .pm-icon-btn:hover { border-color:#FF4B24; }
    .pm-icon-btn.active { border-color:#FF4B24; background:#fff5f3; }
    .pm-toast {
      position:fixed; bottom:24px; left:50%; transform:translateX(-50%);
      background:#212121; color:#fff; padding:0.8rem 1.2rem; border-radius:8px;
      font-size:0.85rem; max-width:340px; text-align:center; z-index:100000;
      box-shadow:0 6px 20px rgba(0,0,0,0.3);
    }
    .pm-toast a { color:#FF9F80; font-weight:700; text-decoration:none; }
  `;
  document.head.appendChild(style);

  let savedEventIds = new Set();
  let followedCircuitIds = new Set();

  // Genera un id stabile per un evento (non c'è un id univoco nel feed)
  function pmEventId(ev) {
    return (ev.titolo + '_' + ev.dataInizio)
      .toLowerCase()
      .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/(^-|-$)/g, '');
  }
  window.pmEventId = pmEventId;

  function pmShowToast(message) {
    const toast = document.createElement('div');
    toast.className = 'pm-toast';
    toast.innerHTML = message + ' <a href="#">Scopri Premium</a>';
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
  }

  async function getSession() {
    const { data } = await window.pmSupabase.auth.getSession();
    return data.session;
  }

  async function pmLoadUserSets() {
    const session = await getSession();
    if (!session) { savedEventIds = new Set(); followedCircuitIds = new Set(); refreshButtonStates(); return; }

    const { data: saved } = await window.pmSupabase
      .from('saved_events').select('event_id').eq('user_id', session.user.id);
    savedEventIds = new Set((saved || []).map(r => r.event_id));

    const { data: followed } = await window.pmSupabase
      .from('followed_circuits').select('circuit_id').eq('user_id', session.user.id);
    followedCircuitIds = new Set((followed || []).map(r => r.circuit_id));

    refreshButtonStates();
  }

  function refreshButtonStates() {
    document.querySelectorAll('.pm-save-btn').forEach(btn => {
      btn.classList.toggle('active', savedEventIds.has(btn.dataset.eventId));
    });
    document.querySelectorAll('.pm-follow-btn').forEach(btn => {
      btn.classList.toggle('active', followedCircuitIds.has(btn.dataset.circuitId));
    });
  }

  window.pmHandleSaveClick = async function (btn) {
    const session = await getSession();
    if (!session) {
      window.pmOpenAuthModal({ message: 'Per salvare questo evento crea gratuitamente il tuo account.' });
      return;
    }
    const eventId = btn.dataset.eventId;
    if (savedEventIds.has(eventId)) {
      await window.pmSupabase.from('saved_events').delete()
        .eq('user_id', session.user.id).eq('event_id', eventId);
      savedEventIds.delete(eventId);
    } else {
      const { error } = await window.pmSupabase.from('saved_events')
        .insert({ user_id: session.user.id, event_id: eventId });
      if (error) {
        if (error.message.includes('Limite piano Free')) {
          pmShowToast('Hai raggiunto il limite di eventi salvati del piano Free. Con Premium puoi salvare eventi illimitati.');
        }
        return;
      }
      savedEventIds.add(eventId);
    }
    refreshButtonStates();
  };

  window.pmHandleFollowClick = async function (btn) {
    const session = await getSession();
    if (!session) {
      window.pmOpenAuthModal({ message: 'Per seguire questo circuito crea gratuitamente il tuo account.' });
      return;
    }
    const circuitId = btn.dataset.circuitId;
    if (!circuitId) return;
    if (followedCircuitIds.has(circuitId)) {
      await window.pmSupabase.from('followed_circuits').delete()
        .eq('user_id', session.user.id).eq('circuit_id', circuitId);
      followedCircuitIds.delete(circuitId);
    } else {
      const { error } = await window.pmSupabase.from('followed_circuits')
        .insert({ user_id: session.user.id, circuit_id: circuitId });
      if (error) {
        if (error.message.includes('Limite piano Free')) {
          pmShowToast('Hai raggiunto il limite di circuiti seguiti del piano Free. Con Premium puoi seguirne illimitati.');
        }
        return;
      }
      followedCircuitIds.add(circuitId);
    }
    refreshButtonStates();
  };

  // Riapplica lo stato ogni volta che le card eventi vengono ridisegnate
  const container = document.getElementById('eventsContainer');
  if (container) {
    new MutationObserver(() => refreshButtonStates()).observe(container, { childList: true });
  }

  document.addEventListener('DOMContentLoaded', pmLoadUserSets);
  if (window.pmSupabase) {
    window.pmSupabase.auth.onAuthStateChange(() => pmLoadUserSets());
  }
})();
