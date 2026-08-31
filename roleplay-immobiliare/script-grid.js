(() => {
  let gridMode = false;

  function addStyles() {
    if (document.getElementById('scriptGridStyles')) return;
    const style = document.createElement('style');
    style.id = 'scriptGridStyles';
    style.textContent = `
      .script-grid{display:grid;grid-template-columns:repeat(10,minmax(0,1fr));gap:7px;margin-top:12px}
      .script-cell{min-height:44px;padding:6px 2px;border-radius:10px;background:#222d47;color:var(--text);border:1px solid var(--line);font-weight:800;cursor:pointer}
      .script-cell.active{background:var(--accent);color:#081126;outline:2px solid #fff;outline-offset:1px}
      .script-cell:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
      @media(max-width:540px){.script-grid{grid-template-columns:repeat(6,minmax(0,1fr));gap:6px}.script-cell{min-height:46px}}
    `;
    document.head.appendChild(style);
  }

  function setActive(id) {
    document.querySelectorAll('.script-cell').forEach(btn => {
      btn.classList.toggle('active', String(btn.dataset.id) === String(id));
    });
  }

  function sortedAll() {
    return [...DRILLS].sort((a,b)=>(+a.id||0)-(+b.id||0));
  }

  function startFrom(index) {
    stopAudio(false);
    audioList = sortedAll();
    if (!audioList.length) return;
    audioPos = Math.max(0, Math.min(audioList.length - 1, index));
    const loop = document.getElementById('loopAudio');
    if (loop) loop.checked = true;
    gridMode = true;
    audioActive = true;
    audioPaused = false;
    keepAwake();
    const d = audioList[audioPos];
    setActive(d.id);
    document.getElementById('audioStatus').textContent = `Parto dallo script ${d.id}. Poi proseguo fino al 122, riparto dall’1 e continuo in loop infinito.`;
    playAudioCurrent();
  }

  function buildGrid() {
    if (!Array.isArray(DRILLS) || !DRILLS.length || document.getElementById('scriptGridPanel')) return;
    addStyles();
    const studio = document.getElementById('audioStudio');
    if (!studio) return;

    const panel = document.createElement('section');
    panel.className = 'panel';
    panel.id = 'scriptGridPanel';
    panel.innerHTML = `
      <div class="small">SELEZIONA IL PUNTO DI PARTENZA</div>
      <h2 style="font-size:1.08rem;margin:7px 0 0">🔢 ${DRILLS.length} script</h2>
      <div class="small" style="margin-top:6px">Tocca una casella: parte da quello script, continua fino al 122, riparte dall’1 e non si ferma finché non premi Stop.</div>
      <div class="script-grid" id="scriptGrid" aria-label="Selezione script 1-122"></div>`;
    studio.insertAdjacentElement('afterend', panel);

    const grid = panel.querySelector('#scriptGrid');
    sortedAll().forEach((d, index) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'script-cell';
      btn.textContent = d.id;
      btn.dataset.id = d.id;
      btn.setAttribute('aria-label', `Ascolta dal copione ${d.id}`);
      btn.addEventListener('click', () => startFrom(index));
      grid.appendChild(btn);
    });

    const baseRender = renderAudioDrill;
    renderAudioDrill = function(d) {
      baseRender(d);
      setActive(d.id);
    };

    const loop = document.getElementById('loopAudio');
    if (loop) {
      loop.addEventListener('change', () => {
        if (gridMode && !loop.checked) {
          loop.checked = true;
          document.getElementById('audioStatus').textContent = 'Loop infinito attivo per la modalità a caselle.';
        }
      });
    }

    document.getElementById('listenAll')?.addEventListener('click', () => { gridMode = false; });
    document.getElementById('listenCategory')?.addEventListener('click', () => { gridMode = false; });
    document.getElementById('stopAudio')?.addEventListener('click', () => { gridMode = false; setActive(null); });
  }

  function waitForDrills(tries = 0) {
    if (typeof DRILLS !== 'undefined' && Array.isArray(DRILLS) && DRILLS.length) {
      buildGrid();
      return;
    }
    if (tries < 100) setTimeout(() => waitForDrills(tries + 1), 100);
  }

  waitForDrills();
})();
