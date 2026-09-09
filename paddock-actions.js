/* ============================================================
   PADDOCKMAP — paddock-actions.js
   Pulsanti Salva evento / Segui circuito sulle card eventi.
   Richiede auth.js già caricato (usa pmSupabase, pmOpenAuthModal, pmShowToast).
   ============================================================ */
(function () {
  'use strict';

  const style = document.createElement('style');
  style.textContent = `
    .pm-quick-actions { display:flex; gap:0.4rem; margin-bottom:0.5rem; }
    .pm-icon-btn {
      background:var(--surface, #fff); border:1.5px solid var(--line, #e0e0e0);
      border-radius:var(--radius-sm, 6px); width:34px; height:34px; cursor:pointer;
      display:flex; align-items:center; justify-content:center; color:var(--ink-soft, #666);
      transition:all 0.15s var(--ease, ease);
    }
    .pm-icon-btn svg.icon { width:17px; height:17px; }
    .pm-icon-btn:hover { border-color:var(--accent); color:var(--accent); }
    .pm-icon-btn.active { border-color:var(--accent); background:rgba(255,75,36,0.08); color:var(--accent); fill:var(--accent); }
    .pm-icon-btn.active svg.icon { fill:var(--accent); }
  `;
  document.head.appendChild(style);

  let savedEventIds = new Set();
  let followedCircuitIds = new Set();

  function pmEventId(ev) {
    return (ev.titolo + '_' + ev.dataInizio)
      .toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '');
  }
  window.pmEventId = pmEventId;

  async function getSession() {
    const { data } = await window.pmSupabase.auth.getSession();
    return data.session;
  }

  async function pmLoadUserSets() {
    const session = await getSession();
    if (!session) { savedEventIds = new Set(); followedCircuitIds = new Set(); refreshButtonStates(); return; }
    const { data: saved } = await window.pmSupabase.from('saved_events').select('event_id').eq('user_id', session.user.id);
    savedEventIds = new Set((saved || []).map(r => r.event_id));
    const { data: followed } = await window.pmSupabase.from('followed_circuits').select('circuit_id').eq('user_id', session.user.id);
    followedCircuitIds = new Set((followed || []).map(r => r.circuit_id));
    refreshButtonStates();
  }

  function refreshButtonStates() {
    document.querySelectorAll('.pm-save-btn').forEach(btn => btn.classList.toggle('active', savedEventIds.has(btn.dataset.eventId)));
    document.querySelectorAll('.pm-follow-btn').forEach(btn => btn.classList.toggle('active', followedCircuitIds.has(btn.dataset.circuitId)));
  }
  window.pmRefreshButtonStates = refreshButtonStates; 

  window.pmHandleSaveClick = async function (btn) {
    const session = await getSession();
    if (!session) { window.pmOpenAuthModal({ message: 'Per salvare questo evento crea gratuitamente il tuo account.' }); return; }
    const eventId = btn.dataset.eventId;
    if (savedEventIds.has(eventId)) {
      await window.pmSupabase.from('saved_events').delete().eq('user_id', session.user.id).eq('event_id', eventId);
      savedEventIds.delete(eventId);
    } else {
      const { error } = await window.pmSupabase.from('saved_events').insert({ user_id: session.user.id, event_id: eventId });
      if (error) {
        if (error.message.includes('Limite piano Free')) window.pmShowToast('Hai raggiunto il limite di eventi salvati del piano Free. Con Premium sono illimitati. <a href="premium.html">Scopri Premium</a>');
        return;
      }
      savedEventIds.add(eventId);
    }
    refreshButtonStates();
  };

  window.pmHandleFollowClick = async function (btn) {
    const session = await getSession();
    if (!session) { window.pmOpenAuthModal({ message: 'Per seguire questo circuito crea gratuitamente il tuo account.' }); return; }
    const circuitId = btn.dataset.circuitId;
    if (!circuitId) return;
    if (followedCircuitIds.has(circuitId)) {
      await window.pmSupabase.from('followed_circuits').delete().eq('user_id', session.user.id).eq('circuit_id', circuitId);
      followedCircuitIds.delete(circuitId);
    } else {
      const { error } = await window.pmSupabase.from('followed_circuits').insert({ user_id: session.user.id, circuit_id: circuitId });
      if (error) {
        if (error.message.includes('Limite piano Free')) window.pmShowToast('Hai raggiunto il limite di circuiti seguiti del piano Free. <a href="premium.html">Scopri Premium</a>');
        return;
      }
      followedCircuitIds.add(circuitId);
    }
    refreshButtonStates();
  };

  const container = document.getElementById('eventsContainer');
  if (container) new MutationObserver(() => refreshButtonStates()).observe(container, { childList: true });

  document.addEventListener('DOMContentLoaded', pmLoadUserSets);
  const waitAuth = setInterval(() => {
    if (window.pmSupabase) { clearInterval(waitAuth); window.pmSupabase.auth.onAuthStateChange(() => pmLoadUserSets()); }
  }, 100);
})();
