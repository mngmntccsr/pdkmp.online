/* ============================================================
   PADDOCKMAP — auth.js
   Gestisce: connessione Supabase, login/signup/logout,
   aggiornamento dinamico dell'header ("Accedi" ↔ "👤 Nome utente").

   Da includere in ogni pagina HTML, in <head>, DOPO:
     <script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2"></script>
   ============================================================ */

(function () {
  'use strict';

  // ------------------------------------------------------------
  // 1. CLIENT SUPABASE
  // ------------------------------------------------------------
  const SUPABASE_URL = 'https://iwmiokxyrxdbkwicajse.supabase.co';
  const SUPABASE_ANON_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Iml3bWlva3h5cnhkYmt3aWNhanNlIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODg2MjM0OTEsImV4cCI6MjEwNDE5OTQ5MX0.Qra9VsDogDp2CIITzPDyC0LRONJs9LfpTT1Om3pSiew';

  const supabase = window.supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY);
  // Esposto per poter essere usato in futuro da altri script (es. salva evento)
  window.pmSupabase = supabase;

  // ------------------------------------------------------------
  // 2. STILE DEL WIDGET (iniettato via JS, così funziona su tutte
  //    le pagine anche se non condividono lo stesso CSS)
  // ------------------------------------------------------------
  const style = document.createElement('style');
  style.textContent = `
    .pm-auth-widget { display:flex; align-items:center; gap:0.75rem; margin-left:1.25rem; }
    .pm-auth-btn {
      background:none; border:1.5px solid #FF4B24; color:#FF4B24;
      padding:0.4rem 0.9rem; border-radius:6px; font-weight:600; font-size:0.85rem;
      cursor:pointer; font-family:inherit; text-decoration:none; white-space:nowrap;
      transition:all .2s;
    }
    .pm-auth-btn:hover { background:#FF4B24; color:#fff; }
    .pm-auth-btn.pm-btn-primary { background:#FF4B24; color:#fff; }
    .pm-auth-btn.pm-btn-primary:hover { background:#c62828; }
    .pm-user-chip {
      display:flex; align-items:center; gap:0.5rem; color:#fff; font-size:0.85rem;
      text-decoration:none; cursor:pointer; white-space:nowrap;
    }
    .pm-user-chip:hover { opacity:0.85; }

    .pm-modal-overlay {
      position:fixed; inset:0; background:rgba(0,0,0,0.6);
      display:flex; align-items:center; justify-content:center; z-index:99999;
    }
    .pm-modal-overlay.pm-hidden { display:none; }
    .pm-modal-box {
      background:#fff; border-radius:12px; padding:1.75rem; width:100%;
      max-width:360px; box-shadow:0 10px 30px rgba(0,0,0,0.25); font-family:inherit;
      color:#212121;
    }
    .pm-modal-box h2 { font-size:1.25rem; margin-bottom:0.3rem; }
    .pm-modal-box p.pm-modal-msg { font-size:0.85rem; color:#555; margin-bottom:1.1rem; }
    .pm-modal-box input {
      width:100%; padding:0.65rem 0.8rem; margin-bottom:0.7rem; border-radius:6px;
      border:1.5px solid #e0e0e0; font-size:0.9rem; font-family:inherit;
    }
    .pm-modal-box input:focus { outline:none; border-color:#FF4B24; }
    .pm-modal-submit {
      width:100%; padding:0.7rem; border:none; border-radius:6px; background:#FF4B24;
      color:#fff; font-weight:600; cursor:pointer; font-size:0.9rem; margin-bottom:0.6rem;
    }
    .pm-modal-submit:hover { background:#c62828; }
    .pm-google-btn {
      width:100%; padding:0.65rem; border:1.5px solid #ddd; border-radius:6px;
      background:#fff; cursor:pointer; font-weight:600; font-size:0.9rem; margin-bottom:0.9rem;
    }
    .pm-google-btn:hover { background:#f5f5f5; }
    .pm-modal-switch { font-size:0.82rem; text-align:center; color:#555; }
    .pm-modal-switch a { color:#FF4B24; cursor:pointer; font-weight:600; }
    .pm-modal-close {
      position:absolute; top:10px; right:14px; cursor:pointer; font-size:1.2rem; color:#999;
      background:none; border:none;
    }
    .pm-modal-error { color:#c62828; font-size:0.82rem; margin:-0.3rem 0 0.7rem; min-height:1em; }
  `;
  document.head.appendChild(style);

  // ------------------------------------------------------------
  // 3. MODALE LOGIN / SIGNUP
  // ------------------------------------------------------------
  let modalMode = 'signup'; // 'signup' | 'login'

  const overlay = document.createElement('div');
  overlay.className = 'pm-modal-overlay pm-hidden';
  overlay.innerHTML = `
    <div class="pm-modal-box" style="position:relative;">
      <button class="pm-modal-close" id="pmModalClose">&times;</button>
      <h2 id="pmModalTitle">Crea il tuo account</h2>
      <p class="pm-modal-msg" id="pmModalMsg">Crea gratuitamente il tuo Paddock su PaddockMap.</p>

      <button class="pm-google-btn" id="pmGoogleBtn">Continua con Google</button>

      <form id="pmAuthForm">
        <input type="text" id="pmName" placeholder="Nome" style="display:none;">
        <input type="email" id="pmEmail" placeholder="Email" required>
        <input type="password" id="pmPassword" placeholder="Password" required minlength="6">
        <div class="pm-modal-error" id="pmModalError"></div>
        <button type="submit" class="pm-modal-submit" id="pmSubmitBtn">Crea account</button>
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
    nameInput: overlay.querySelector('#pmName'),
    emailInput: overlay.querySelector('#pmEmail'),
    passInput: overlay.querySelector('#pmPassword'),
    error: overlay.querySelector('#pmModalError'),
    submitBtn: overlay.querySelector('#pmSubmitBtn'),
    switchText: overlay.querySelector('#pmModalSwitch'),
    switchLink: overlay.querySelector('#pmSwitchLink'),
    form: overlay.querySelector('#pmAuthForm'),
    closeBtn: overlay.querySelector('#pmModalClose'),
    googleBtn: overlay.querySelector('#pmGoogleBtn')
  };

  function setModalMode(mode) {
    modalMode = mode;
    els.error.textContent = '';
    if (mode === 'signup') {
      els.title.textContent = 'Crea il tuo account';
      els.nameInput.style.display = 'block';
      els.submitBtn.textContent = 'Crea account';
      els.switchText.innerHTML = 'Hai già un account? <a id="pmSwitchLink">Accedi</a>';
    } else {
      els.title.textContent = 'Accedi';
      els.nameInput.style.display = 'none';
      els.submitBtn.textContent = 'Accedi';
      els.switchText.innerHTML = 'Non hai un account? <a id="pmSwitchLink">Crea account</a>';
    }
    // il link viene ricreato ogni volta: riattacco il listener
    overlay.querySelector('#pmSwitchLink').addEventListener('click', () => {
      setModalMode(modalMode === 'signup' ? 'login' : 'signup');
    });
  }

  els.switchLink.addEventListener('click', () => {
    setModalMode(modalMode === 'signup' ? 'login' : 'signup');
  });

  els.closeBtn.addEventListener('click', closeAuthModal);
  overlay.addEventListener('click', (e) => { if (e.target === overlay) closeAuthModal(); });

  function openAuthModal(options) {
    options = options || {};
    setModalMode(options.mode || 'signup');
    els.msg.textContent = options.message || 'Crea gratuitamente il tuo Paddock su PaddockMap.';
    els.error.textContent = '';
    els.form.reset();
    overlay.classList.remove('pm-hidden');
  }

  function closeAuthModal() {
    overlay.classList.add('pm-hidden');
  }

  // Esposte globalmente per essere richiamate da altri script (es. click su "Salva evento")
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
          email,
          password,
          options: { data: { full_name: fullName } }
        });
        if (error) throw error;
        gtagSafe('signup_completed');
        closeAuthModal();
      } else {
        const { error } = await supabase.auth.signInWithPassword({ email, password });
        if (error) throw error;
        closeAuthModal();
      }
    } catch (err) {
      els.error.textContent = translateAuthError(err.message);
    } finally {
      els.submitBtn.disabled = false;
    }
  });

  els.googleBtn.addEventListener('click', async () => {
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

  // ------------------------------------------------------------
  // 4. LOGOUT
  // ------------------------------------------------------------
  async function pmSignOut() {
    await supabase.auth.signOut();
  }
  window.pmSignOut = pmSignOut;

  // ------------------------------------------------------------
  // 5. HEADER DINAMICO
  //    Cerca ".header-content" (presente in tutte le pagine attuali)
  //    e inserisce/aggiorna il widget account.
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
        <a href="il-mio-paddock.html" class="pm-user-chip">👤 ${escapeHtml(name)}</a>
      `;
    } else {
      widget.innerHTML = `
        <a href="#" class="pm-auth-btn" id="pmHeaderLogin">Accedi</a>
        <a href="#" class="pm-auth-btn pm-btn-primary" id="pmHeaderSignup">Crea account</a>
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
  // 6. STATO INIZIALE + LISTENER
  // ------------------------------------------------------------
  supabase.auth.getSession().then(({ data }) => {
    renderAuthWidget(data.session);
  });

  supabase.auth.onAuthStateChange((_event, session) => {
    renderAuthWidget(session);
  });

})();
