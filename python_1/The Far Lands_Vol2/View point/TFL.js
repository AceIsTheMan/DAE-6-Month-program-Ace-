// ═══════════════════════════════════════════════════
// RULES GATE
// ═══════════════════════════════════════════════════
(function () {
  var checkbox = document.getElementById('rules-checkbox');
  var proceedBtn = document.getElementById('rules-proceed');
  var gate = document.getElementById('rules-gate');

  checkbox.addEventListener('change', function () {
    proceedBtn.disabled = !checkbox.checked;
    proceedBtn.classList.toggle('enabled', checkbox.checked);
  });

  proceedBtn.addEventListener('click', function () {
    if (checkbox.checked) {
      gate.classList.remove('active');
      document.body.style.overflow = '';
    }
  });

  // block page scroll while the gate is up
  document.body.style.overflow = 'hidden';
})();

// ═══════════════════════════════════════════════════
// PROFILE PAGE
// ═══════════════════════════════════════════════════

// ─── Profile photo import (client-side preview only) ───
(function () {
  const input = document.getElementById('photo-input');
  const img = document.getElementById('dossier-img');
  if (!input || !img) return;
  input.addEventListener('change', function (e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = function (ev) {
      img.src = ev.target.result;
      img.style.display = 'block';
    };
    reader.readAsDataURL(file);
  });
})();

// ─── Status: active / deactivated toggle ───
(function () {
  const btn = document.getElementById('status-toggle');
  if (!btn) return;
  btn.addEventListener('click', function () {
    const active = btn.dataset.state === 'active';
    btn.dataset.state = active ? 'deactivated' : 'active';
    btn.textContent = active ? 'DEACTIVATED' : 'ACTIVE';
  });
})();

// ─── Nav logo <-> profile name sync ───
(function () {
  const nameInput = document.getElementById('dossier-name');
  const navLogo = document.getElementById('nav-logo');
  if (!nameInput || !navLogo) return;

  function syncNavName() {
    const name = nameInput.value.trim();
    navLogo.textContent = '// ' + (name || 'UnknownUser');
  }

  nameInput.addEventListener('input', syncNavName);
  syncNavName(); // run once on load in case a value was preset
})();

// ═══════════════════════════════════════════════════
// PAGE SWITCHER + LIGHTBOX
// ═══════════════════════════════════════════════════

function showPage(name, link) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-links a').forEach(a => a.classList.remove('active'));
  document.getElementById('page-' + name).classList.add('active');
  if (link) link.classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
  return false;
}

/*
  To wire up real media, replace the gif-placeholder elements with actual
  <img src="your.gif"> or <video src="your.mp4"> tags, and update the
  `mediaItems` array below with the correct src values and captions.
*/
const mediaItems = [
  { src: 'Animate.mp4', type: 'video', caption: 'SLOT 01 — VIDEO' },
  { src: 'Player effects.mp4', type: 'video', caption: 'SLOT 02 — VIDEO' },
  { src: 'Player pov.mp4', type: 'video', caption: 'SLOT 03 — VIDEO' },
];

function openLightbox(index) {
  const item = mediaItems[index];
  const content = document.getElementById('lightbox-content');
  const caption = document.getElementById('lightbox-caption');
  caption.textContent = item.caption;

  if (!item.src) {
    content.outerHTML = `<div class="lightbox-placeholder" id="lightbox-content">${item.caption}</div>`;
  } else if (item.type === 'video') {
    content.outerHTML = `<video id="lightbox-content" src="${item.src}" controls autoplay loop style="width:100%;max-height:80vh;"></video>`;
  } else {
    content.outerHTML = `<img id="lightbox-content" src="${item.src}" alt="${item.caption}">`;
  }

  document.getElementById('lightbox').classList.add('active');
  document.body.style.overflow = 'hidden';
}

function closeLightbox() {
  document.getElementById('lightbox').classList.remove('active');
  document.body.style.overflow = '';
}

function closeLightboxOutside(e) {
  if (e.target === document.getElementById('lightbox')) closeLightbox();
}

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });