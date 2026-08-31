(() => {
  const KEY = 'roleplayScriptVolume';
  const clamp = v => Math.max(0.20, Math.min(1, Number.isFinite(v) ? v : 0.90));
  const current = () => clamp(parseFloat(localStorage.getItem(KEY) || '0.90'));

  try {
    const synth = window.speechSynthesis;
    if (synth && !synth.__roleplayVolumePatched) {
      const nativeSpeak = synth.speak.bind(synth);
      synth.speak = utterance => {
        try {
          const base = Number.isFinite(utterance.volume) ? utterance.volume : 1;
          utterance.volume = Math.max(0, Math.min(1, base * current()));
        } catch (_) {}
        return nativeSpeak(utterance);
      };
      synth.__roleplayVolumePatched = true;
    }
  } catch (_) {}

  window.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('scriptVol')) return;
    const studio = document.getElementById('audioStudio');
    if (!studio) return;
    const actions = studio.querySelector('.audio-actions');
    const box = document.createElement('div');
    box.style.margin = '14px 0 10px';
    box.innerHTML = `
      <label style="display:block;margin-bottom:6px">Volume script <strong id="scriptVolVal" style="color:var(--text)">${Math.round(current()*100)}%</strong></label>
      <input id="scriptVol" type="range" min="0.20" max="1.00" step="0.05" value="${current()}" style="width:100%">
      <div class="small">Regola solo la voce del Role Play. Spotify resta separato.</div>`;
    studio.insertBefore(box, actions || null);
    const slider = document.getElementById('scriptVol');
    const value = document.getElementById('scriptVolVal');
    slider.addEventListener('input', () => {
      const v = clamp(parseFloat(slider.value));
      localStorage.setItem(KEY, String(v));
      value.textContent = Math.round(v * 100) + '%';
    });
  });
})();
