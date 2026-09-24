(function () {
  'use strict';

  function normalizeText(t) {
    return (t || '')
      .toLowerCase()
      .replace(/\s+/g, '');
  }

  function autoClickMoreTime() {
    const keywords = [
      // English
      "more time",

      // French
      "plus de temps",

      // Spanish
      "más tiempo",

      // Portuguese
      "mais tempo",

      // Russian
      "больше времени",

      // Ukrainian
      "більше часу",

      // Arabic
      "المزيد من الوقت",

      // Persian (Farsi)
      "زمان بیشتر",

      // Urdu
      "زیادہ وقت",

      // Hindi
      "अधिक समय",

      // Bengali
      "আরও সময়",

      // Vietnamese
      "thêm thời gian",

      // Indonesian
      "lebih banyak waktu",

      // Tagalog (Filipino)
      "mas maraming oras"
    ];

    const elements = document.querySelectorAll("button, a, div, span");

    elements.forEach(el => {
      const text = normalizeText(el.innerText || el.value || el.getAttribute("title") || el.getAttribute("aria-label") || "");
      for (const key of keywords) {
        if (text.includes(normalizeText(key))) {
          console.log("⏳ Auto Clicking:", el);
          el.click();
          return;
        }
      }
    });
  }

  // Run every 2 seconds
  setInterval(autoClickMoreTime, 2000);
})();
(function () {
  'use strict';

  function autoResume() {
    // Look for div with class "play"
    const playBtn = document.querySelector("div.play");

    if (playBtn) {
      console.log("▶️ Play/Resume button detected → Clicking...");
      playBtn.click();
    }
  }

  // Check every 2 seconds
  setInterval(autoResume, 2000);
})();
(function () {
  'use strict';

  function autoFillCaptchaAndLogin() {
    // 1️⃣ Detect the captcha/code
    const codeBox = document.querySelector(
      '#codigooo, .captcha-code, .captcha_value, div.captcha, span.captcha, strong.captcha'
    );

    // 2️⃣ Detect the input field (text or number)
    const inputBox = document.querySelector(
      '#captcha_text, input[name="captcha"], input.captcha, input#captcha, input[type="text"].captcha, input[type="number"]'
    );

    if (codeBox && inputBox) {
      const codeText = (codeBox.innerText || codeBox.textContent || "").trim();

      if (codeText.length > 0) {
        // 3️⃣ Fill the captcha/code into the input box
        inputBox.value = codeText;
        console.log("✅ Captcha/code filled with:", codeText);

        // 4️⃣ Detect the login button
        const loginBtn = document.querySelector(
          'button.g-recaptcha.button_generic[data-sitekey]'
        );

        if (loginBtn) {
          // 5️⃣ Auto-click the login button after 5 seconds using MouseEvent
          setTimeout(() => {
            loginBtn.dispatchEvent(new MouseEvent('mousedown', {bubbles:true}));
            loginBtn.dispatchEvent(new MouseEvent('mouseup', {bubbles:true}));
            loginBtn.dispatchEvent(new MouseEvent('click', {bubbles:true}));
            console.log("🚀 Login button clicked automatically after 5 seconds!");
          }, 5000); // 5000 ms = 5 seconds
        }
      }
    }
  }

  setInterval(autoFillCaptchaAndLogin, 100);
})();
// content.js - multilingual "Correct" auto-clicker with 5-second delay
(() => {
  // ---------------- Config ----------------
  const SELECTOR = "#contentbox > div.side-main > div.theme-white.main-content > div:nth-child(2) > div > div > div.work-area-wrap > div > div > div > div.moderation-buttons > button:nth-child(1)";
  const VARIANTS = [
    'correct',       // English
    'tama',          // Tagalog (Filipino)
    'benar',         // Indonesian
    'সঠিক',          // Bengali
    'sothik',        // romanized Bengali
    'đúng',          // Vietnamese
    'dung',          // romanized Vietnamese
    'सही',           // Hindi
    'sahi',          // romanized Hindi
    'صحیح',          // Urdu
    'sahih',         // romanized Urdu
    'درست',          // Persian / Farsi
    'dorost',        // romanized Persian
    'صحيح',          // Arabic
    'sahih_ar',      // optional placeholder
    'правильно',      // Ukrainian/Russian
    'pravylno',      // romanized Ukrainian
    'верно',         // Russian
    'правильно',     // Russian duplicate
    'correto',       // Portuguese
    'correta',       // Portuguese
    'correcto',      // Spanish
    'correcta',      // Spanish
    'valider',       // French
  ].map(s => s.toLowerCase());

  // ---------------- Utilities ----------------
  function normalize(s='') {
    return (s || '').trim().toLowerCase();
  }

  function shouldClick(button) {
    if (!button) return false;
    const text = normalize(button.textContent || button.innerText || '');
    return VARIANTS.includes(text);
  }

  function clickButton(button) {
    if (!button) return;
    console.log('[content.js] Clicking button in 5 seconds:', button, button.textContent);
    setTimeout(() => {
      try {
        button.click();
        console.log('[content.js] Button clicked:', button.textContent);
      } catch (e) {
        console.error('[content.js] click failed', e);
      }
    }, 5000); // 5000ms = 5 seconds delay
  }

  function scanAndClick() {
    const button = document.querySelector(SELECTOR);
    if (button && shouldClick(button)) {
      clickButton(button);
    }
  }

  // ---------------- Initial scan ----------------
  if (document.readyState === 'loading') {
    window.addEventListener('DOMContentLoaded', scanAndClick);
  } else {
    scanAndClick();
  }

  // ---------------- Observe DOM changes ----------------
  const observer = new MutationObserver((mutations) => {
    mutations.forEach(m => {
      if (m.addedNodes && m.addedNodes.length) {
        scanAndClick();
      }
    });
  });

  try {
    observer.observe(document.body, { childList: true, subtree: true });
  } catch(e) { console.warn('[content.js] observer failed', e); }

  console.log('[content.js] Multilingual Correct-button auto-clicker (5s delay) loaded');
})();