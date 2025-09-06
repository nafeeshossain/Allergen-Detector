const ALLERGENS = window.ALLERGENS || {};
const PROFILE_KEY = "allergen_profile";

function loadProfile() {
  try {
    const raw = localStorage.getItem(PROFILE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) { return []; }
}

function saveProfile(list) {
  localStorage.setItem(PROFILE_KEY, JSON.stringify(list));
}

function renderAllergenTags() {
  const container = document.getElementById("allergen-tags");
  const profile = new Set(loadProfile());

  container.innerHTML = "";
  Object.keys(ALLERGENS).forEach(key => {
    const el = document.createElement("button");
    el.className = "tag" + (profile.has(key) ? " active" : "");
    el.textContent = key.replaceAll("_"," ");
    el.onclick = () => {
      if (profile.has(key)) profile.delete(key);
      else profile.add(key);
      saveProfile(Array.from(profile));
      renderAllergenTags();
    }
    container.appendChild(el);
  });
}

async function scanImage(evt) {
  evt.preventDefault();
  const file = document.getElementById("image").files[0];
  if (!file) return;
  const progress = document.getElementById("progress");
  progress.textContent = "Uploading & scanning...";

  const fd = new FormData();
  fd.append("image", file);

  const res = await fetch("/api/scan", { method: "POST", body: fd });
  const data = await res.json();
  progress.textContent = "";

  const raw = document.getElementById("raw-text");
  const detected = document.getElementById("detected");
  const personal = document.getElementById("personal-warnings");
  raw.textContent = data.ok ? data.ingredients_raw : (data.error || "Error");

  if (!data.ok) {
    detected.innerHTML = "";
    personal.innerHTML = "";
    return;
  }

  // Detected allergens
  if (data.matches.length === 0) {
    detected.innerHTML = "<p>No allergen hits found (remember OCR can miss text). Verify manually.</p>";
  } else {
    const list = data.matches.map(m => {
      const terms = m.hits.map(h => `${h.term} (${h.score})`).join(", ");
      return `<li><strong>${m.allergen}</strong> — ${terms}</li>`;
    }).join("");
    detected.innerHTML = `<h3>Detected Allergens</h3><ul>${list}</ul>`;
  }

  // Personalized warnings
  const profile = new Set(loadProfile());
  const myHits = (data.matches || []).filter(m => profile.has(m.allergen));
  if (myHits.length) {
    const items = myHits.map(m => `<li><strong>${m.allergen}</strong> (max score: ${m.max_score})</li>`).join("");
    personal.innerHTML = `<h3 style="color: red;">⚠ Personalized Warnings</h3><ul>${items}</ul>`;
  } else {
    personal.innerHTML = "<p class='muted'>No personal allergen matches based on your profile.</p>";
  }
}

document.getElementById("scan-form").addEventListener("submit", scanImage);
renderAllergenTags();
