// static/scan.js
document.addEventListener('DOMContentLoaded', function(){
  const input = document.getElementById('imageInput');
  const btn = document.getElementById('scanBtn');
  const resultDiv = document.getElementById('result');
  const rawPre = document.getElementById('raw');

  btn.addEventListener('click', async () => {
    if (!input.files || !input.files[0]) {
      resultDiv.innerHTML = '<p class="error">Please choose an image first.</p>';
      return;
    }
    const form = new FormData();
    form.append('image', input.files[0]);

    resultDiv.innerHTML = 'Scanning...';
    rawPre.textContent = '';

    try {
      const res = await fetch('/scan', {
        method: 'POST',
        body: form
      });
      const data = await res.json();
      if (!res.ok) {
        resultDiv.innerHTML = `<p class="error">${data.error || 'Scan failed'}</p>`;
        return;
      }
      resultDiv.innerHTML = `<strong>${data.message}</strong>`;
      rawPre.textContent = 'OCR output:\n\n' + (data.raw_text || '(no text found)');
      // also show detected & user allergies
      const extra = document.createElement('div');
      extra.style.marginTop = '8px';
      extra.innerHTML = `<small>Detected labels: ${data.detected_allergens_in_label.join(', ') || 'none' }<br>User allergies: ${data.user_allergies.join(', ') || 'none'}</small>`;
      resultDiv.appendChild(extra);
    } catch (err) {
      console.error(err);
      resultDiv.innerHTML = '<p class="error">Network error.</p>';
    }
  });
});
