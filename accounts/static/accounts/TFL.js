// ═══════════════════════════════════════════════════
// RULES GATE
// Shows once per browser tab/session: either the first time someone lands
// on the site, or on the first home-page load right after logging in.
// Once acknowledged, it's remembered in sessionStorage, so it stays hidden
// on refreshes and on later trips back to the home page in the same tab -
// it only reappears if the tab/window is fully closed and reopened (a
// genuinely new visit).
// ═══════════════════════════════════════════════════
(function () {
  var checkbox = document.getElementById('rules-checkbox');
  var proceedBtn = document.getElementById('rules-proceed');
  var gate = document.getElementById('rules-gate');
  if (!checkbox || !proceedBtn || !gate) return;

  var SEEN_KEY = 'tfl_rules_acknowledged';

  function hideGate() {
    gate.classList.remove('active');
    document.body.style.overflow = '';
  }

  var alreadySeen = false;
  try {
    alreadySeen = sessionStorage.getItem(SEEN_KEY) === '1';
  } catch (e) {
    // sessionStorage can be unavailable (some private-browsing modes) -
    // fail open and just show the gate rather than break the page.
  }

  if (alreadySeen) {
    hideGate();
  } else {
    // block page scroll while the gate is up
    document.body.style.overflow = 'hidden';

    checkbox.addEventListener('change', function () {
      proceedBtn.disabled = !checkbox.checked;
      proceedBtn.classList.toggle('enabled', checkbox.checked);
    });

    proceedBtn.addEventListener('click', function () {
      if (!checkbox.checked) return;
      try {
        sessionStorage.setItem(SEEN_KEY, '1');
      } catch (e) {
        // ignore - worst case the gate shows again next load
      }
      hideGate();
    });
  }
})();

// ═══════════════════════════════════════════════════
// PAGE SWITCHER + LIGHTBOX
// (Note: the old mockup PROFILE tab and its client-side-only photo
// preview / status toggle / nav-logo sync logic have been removed - the
// real profile now lives at /profile/, a proper Django page, with its own
// photo preview script inline on that template.)
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
  Media base path: home.html sets `window.TFL_MEDIA_BASE` (via Django's
  {% static %} tag) before this script loads, since a plain static .js
  file can't use template tags itself. Falls back to '' (same-folder
  relative paths) if that variable somehow isn't set, so this still works
  if TFL.js is ever used standalone again.
*/
const MEDIA_BASE = (typeof TFL_MEDIA_BASE !== 'undefined') ? TFL_MEDIA_BASE : '';

const mediaItems = [
  { src: MEDIA_BASE + 'Animate.mp4', type: 'video', caption: 'SLOT 01 — VIDEO' },
  { src: MEDIA_BASE + 'Player effects.mp4', type: 'video', caption: 'SLOT 02 — VIDEO' },
  { src: MEDIA_BASE + 'Player pov.mp4', type: 'video', caption: 'SLOT 03 — VIDEO' },
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
