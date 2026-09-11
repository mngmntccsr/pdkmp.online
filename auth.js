/* ============================================================
   PADDOCKMAP — auth.js
   Gestisce: connessione Supabase, login/signup/logout,
   aggiornamento dinamico dell'header.
   Richiede: style.css e icons.js già caricati nella pagina.

   Da includere in ogni pagina HTML, in <head>, DOPO:
     <link rel="stylesheet" href="style.css">
     <script src="icons.js"></script>
     <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2" defer></script>
   ============================================================ */

(function () {
  'use strict';

  // ------------------------------------------------------------
  // 1. CLIENT SUPABASE
  // ------------------------------------------------------------
  const SUPABASE_URL = 'https://iwmiokxyrxdbkwicajse.supabase.co';
  const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml3bWlva3h5cnhkYmt3aWNhanNlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg2MjM0OTEsImV4cCI6MjEwNDE5OTQ5MX0.Qra9VsDogDp2CIITzPDyC0LRONJs9LfpTT1Om3pSiew';

  const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  window.pmSupabase = supabase;

  // ------------------------------------------------------------
  // 2. STILE — solo le regole che il design system non copre già
  //    (il resto riusa .modal, .form-card, .btn, .btn-primary,
  //    .btn-secondary e le variabili CSS di style.css)
  // ------------------------------------------------------------
  const style = document.createElement('style');
  style.textContent = `
    .pm-auth-widget { display:flex; align-items:center; gap:0.5rem; }
    .pm-header-btn {
      color: rgba(255,255,255,0.62);
      text-decoration:none; font-weight:500; font-size:0.86rem;
      padding:0.42rem 0.95rem; border-radius:var(--radius-pill);
      transition:color 0.2s var(--ease), background 0.2s var(--ease);
      border:none; background:none; cursor:pointer; font-family:inherit;
    }
    .pm-header-btn:hover { color:#fff; background:rgba(255,255,255,0.06); }
    .pm-header-btn.pm-btn-primary { color:#fff; background:var(--accent); }
    .pm-header-btn.pm-btn-primary:hover { background:var(--accent-dark); }
    .pm-user-chip {
      display:flex; align-items:center; gap:0.4rem; color:#fff; font-size:0.86rem;
      text-decoration:none; padding:0.42rem 0.95rem; border-radius:var(--radius-pill);
      background:rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.08);
      transition:background 0.2s var(--ease);
    }
    .pm-user-chip:hover { background:rgba(255,255,255,0.12); }
    .pm-user-chip svg.icon { color:var(--accent); }

    .pm-auth-card { position:relative; max-width:400px; }
    .pm-modal-close {
      position:absolute; top:1.1rem; right:1.1rem; background:none; border:none;
      cursor:pointer; color:var(--muted); width:28px; height:28px;
      display:flex; align-items:center; justify-content:center; border-radius:50%;
      transition:background 0.2s;
    }
    .pm-modal-close:hover { background:rgba(18,21,27,0.06); color:var(--ink); }
    .pm-auth-card h1 { display:flex; align-items:center; gap:0.5rem; }
    .pm-auth-card h1 svg.icon { color:var(--accent); }
    .pm-modal-switch { font-size:0.83rem; text-align:center; color:var(--ink-soft); margin-top:0.3rem; }
    .pm-modal-switch a { color:var(--accent); font-weight:600; cursor:pointer; }
    .pm-modal-error { color:#c1272d; font-size:0.82rem; margin:-0.5rem 0 0.7rem; min-height:1em; }
    #pmGoogleBtn { margin-bottom: 1.1rem; display:flex; align-items:center; justify-content:center; gap:0.5rem; }

    .pm-toast {
      position:fixed; bottom:24px; left:50%; transform:translateX(-50%);
      background:var(--ink); color:#fff; padding:0.85rem 1.2rem; border-radius:var(--radius-md);
      font-size:0.85rem; max-width:340px; text-align:center; z-index:100000;
      box-shadow:var(--shadow-pop); display:flex; align-items:center; gap:0.5rem; justify-content:center;
    }
    .pm-toast a { color:var(--accent); font-weight:700; text-decoration:none; }
  `;
  document.head.appendChild(style);

  // ------------------------------------------------------------
  // 3. TOAST condiviso (usato anche da paddock-actions.js)
  // ------------------------------------------------------------
  function pmShowToast(html) {
    const toast = document.createElement('div');
    toast.className = 'pm-toast';
    toast.innerHTML = html;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
  }
  window.pmShowToast = pmShowToast;

  // ------------------------------------------------------------
  // 4. MODALE LOGIN / SIGNUP
  // ------------------------------------------------------------
  let modalMode = 'signup'; // 'signup' | 'login'

  const overlay = document.createElement('div');
  overlay.className = 'modal hidden';
  overlay.id = 'pmAuthModal';
  overlay.innerHTML = `
    <div class="form-card pm-auth-card">
      <button class="pm-modal-close" id="pmModalClose" aria-label="Chiudi">${PMIcons.close}</button>
      <h1 id="pmModalTitle">${PMIcons.user} Crea il tuo account</h1>
      <p id="pmModalMsg">Crea gratuitamente il tuo Paddock su PaddockMap.</p>

      <button type="button" class="btn btn-secondary" id="pmGoogleBtn">Continua con Google</button>

      <form id="pmAuthForm">
        <label for="pmName" id="pmNameLabel" style="display:none;">Nome</label>
        <input type="text" id="pmName" placeholder="Il tuo nome" style="display:none;">

        <label for="pmEmail">Email</label>
        <input type="email" id="pmEmail" placeholder="nome@esempio.com" required>

        <label for="pmPassword">Password</label>
        <input type="password" id="pmPassword" placeholder="Almeno 6 caratteri" required minlength="6">

        <div class="pm-modal-error" id="pmModalError"></div>
        <button type="submit" class="btn btn-primary" id="pmSubmitBtn">Crea account</button>
      </form>

      <p class="pm-modal-switch" id="pmModalSwitch">
        Hai già un account? <a id="pmSwitchLink">Accedi</a>
      </p>
    </div>
  `;
  document.body.appendChild(overlay);

  const els = {
    title: overlay.querySelector('#pmModalTitle'),
    msg: overlay.querySelector('#pmModalMsg'),
    nameLabel: overlay.querySelector('#pmNameLabel'),
    nameInput: overlay.querySelector('#pmName'),
    emailInput: overlay.querySelector('#pmEmail'),
    passInput: overlay.querySelector('#pmPassword'),
    error: overlay.querySelector('#pmModalError'),
    submitBtn: overlay.querySelector('#pmSubmitBtn'),
    switchText: overlay.querySelector('#pmModalSwitch'),
    form: overlay.querySelector('#pmAuthForm'),
    closeBtn: overlay.querySelector('#pmModalClose'),
    googleBtn: overlay.querySelector('#pmGoogleBtn')
  };

  function attachSwitchLink() {
    const link = overlay.querySelector('#pmSwitchLink');
    link.addEventListener('click', () => setModalMode(modalMode === 'signup' ? 'login' : 'signup'));
  }

  function setModalMode(mode) {
    modalMode = mode;
    els.error.textContent = '';
    if (mode === 'signup') {
      els.title.innerHTML = `${PMIcons.user} Crea il tuo account`;
      els.nameLabel.style.display = 'block';
      els.nameInput.style.display = 'block';
      els.submitBtn.textContent = 'Crea account';
      els.switchText.innerHTML = 'Hai già un account? <a id="pmSwitchLink">Accedi</a>';
    } else {
      els.title.innerHTML = `${PMIcons.user} Accedi`;
      els.nameLabel.style.display = 'none';
      els.nameInput.style.display = 'none';
      els.submitBtn.textContent = 'Accedi';
      els.switchText.innerHTML = 'Non hai un account? <a id="pmSwitchLink">Crea account</a>';
    }
    attachSwitchLink();
  }
  attachSwitchLink();

  els.closeBtn.addEventListener('click', closeAuthModal);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeAuthModal(); });

  function openAuthModal(options) {
    options = options || {};
    const mode = options.mode || 'signup';
    setModalMode(mode);
    els.msg.textContent = options.message || 'Crea gratuitamente il tuo Paddock su PaddockMap.';
    els.error.textContent = '';
    els.form.reset();
    overlay.classList.remove('hidden');
    if (mode === 'signup') {
      gtagSafe('signup_started');
    }
  }

  function closeAuthModal() {
    overlay.classList.add('hidden');
  }

  window.pmOpenAuthModal = openAuthModal;
  window.pmCloseAuthModal = closeAuthModal;

  els.form.addEventListener('submit', async (e) => {
    e.preventDefault();
    els.error.textContent = '';
    els.submitBtn.disabled = true;

    const email = els.emailInput.value.trim();
    const password = els.passInput.value;
    const fullName = els.nameInput.value.trim();

    try {
      if (modalMode === 'signup') {
        const { error } = await supabase.auth.signUp({
          email, password,
          options: { data: { full_name: fullName } }
        });
        if (error) throw error;
        gtagSafe('signup_completed');
        closeAuthModal();
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;

        gtagSafe('login', {
          method: 'email'
        });

        closeAuthModal();
      }
    } catch (err) {
      els.error.textContent = translateAuthError(err.message);
    } finally {
      els.submitBtn.disabled = false;
    }
  });

  els.googleBtn.addEventListener('click', async () => {
    gtagSafe('login_start', {
      method: 'google'
    });

    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: window.location.href }
    });
  });

  function translateAuthError(msg) {
    if (!msg) return 'Si è verificato un errore. Riprova.';
    if (msg.includes('already registered')) return 'Esiste già un account con questa email. Prova ad accedere.';
    if (msg.includes('Invalid login credentials')) return 'Email o password non corrette.';
    if (msg.includes('Password should be at least')) return 'La password deve avere almeno 6 caratteri.';
    return msg;
  }

  function gtagSafe(eventName, params) {
    if (typeof gtag === 'function') gtag('event', eventName, params || {});
  }
  window.pmGtagSafe = gtagSafe;

  // ------------------------------------------------------------
  // 5. LOGOUT
  // ------------------------------------------------------------
  async function pmSignOut() {
    await supabase.auth.signOut();
  }
  window.pmSignOut = pmSignOut;

  // ------------------------------------------------------------
  // 6. HEADER DINAMICO
  // ------------------------------------------------------------
  function renderAuthWidget(session) {
    const headerContent = document.querySelector('.header-content');
    if (!headerContent) return;

    let widget = headerContent.querySelector('.pm-auth-widget');
    if (!widget) {
      widget = document.createElement('div');
      widget.className = 'pm-auth-widget';
      headerContent.appendChild(widget);
    }

    if (session && session.user) {
      const name = session.user.user_metadata?.full_name || session.user.email.split('@')[0];
      widget.innerHTML = `
        <a href="il-mio-paddock.html" class="pm-user-chip">${PMIcons.user} ${escapeHtml(name)}</a>
      `;
    } else {
      widget.innerHTML = `
        <a href="#" class="pm-header-btn" id="pmHeaderLogin">Accedi</a>
        <a href="#" class="pm-header-btn pm-btn-primary" id="pmHeaderSignup">Crea account</a>
      `;
      widget.querySelector('#pmHeaderLogin').addEventListener('click', (e) => {
        e.preventDefault();
        openAuthModal({ mode: 'login' });
      });
      widget.querySelector('#pmHeaderSignup').addEventListener('click', (e) => {
        e.preventDefault();
        openAuthModal({ mode: 'signup' });
      });
    }
  }

  function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
  }

  // ------------------------------------------------------------
  // 7. STATO INIZIALE + LISTENER
  // ------------------------------------------------------------
  function initWidget() {
    supabase.auth.getSession().then(({ data }) => renderAuthWidget(data.session));
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initWidget);
  } else {
    initWidget();
  }

  supabase.auth.onAuthStateChange((_event, session) => {
    renderAuthWidget(session);
  });

})();
