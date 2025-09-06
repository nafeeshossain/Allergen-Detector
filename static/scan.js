document.addEventListener('DOMContentLoaded', function () {
  const input = document.getElementById('imageInput');
  const scanBtn = document.getElementById('scanBtn');
  const captureBtn = document.getElementById('captureBtn');
  const video = document.getElementById('camera');
  const canvas = document.getElementById('canvas');
  const resultDiv = document.getElementById('result');
  const rawPre = document.getElementById('raw');

  const startBarcodeBtn = document.getElementById("startBarcodeScan");
  const stopBarcodeBtn = document.getElementById("stopBarcodeScan");
  const barcodeResult = document.getElementById("barcodeResult");
  const barcodeContainer = document.getElementById("barcodeScanner");

  let capturedBlob = null;
  let isBarcodeScanning = false;

  // ==========================
  // 📷 CAMERA FOR IMAGE CAPTURE
  // ==========================
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
      .then(stream => {
        video.srcObject = stream;
      })
      .catch(err => {
        console.error("Camera not available:", err);
        video.style.display = "none";
        captureBtn.style.display = "none";
      });
  } else {
    video.style.display = "none";
    captureBtn.style.display = "none";
  }

  captureBtn.addEventListener('click', () => {
    const context = canvas.getContext('2d');
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    canvas.toBlob(blob => {
      capturedBlob = blob;
      resultDiv.innerHTML = "<p>📷 Image captured. Now click Scan.</p>";
    }, 'image/jpeg', 0.95);
  });

  // ==========================
  // 🔎 IMAGE/PHOTO OCR SCAN
  // ==========================
  scanBtn.addEventListener('click', async () => {
    let fileToSend = capturedBlob ? new File([capturedBlob], "capture.jpg", { type: "image/jpeg" }) :
                     input.files && input.files[0] ? input.files[0] : null;

    if (!fileToSend) {
      resultDiv.innerHTML = '<p class="error">Please upload or capture an image.</p>';
      return;
    }

    const form = new FormData();
    form.append('image', fileToSend);

    resultDiv.innerHTML = 'Scanning...';
    rawPre.textContent = '';

    try {
      const res = await fetch('/scan', { method: 'POST', body: form });
      const data = await res.json();
      if (!res.ok) {
        resultDiv.innerHTML = `<p class="error">${data.error || 'Scan failed'}</p>`;
        return;
      }
      renderResults(data);
    } catch (err) {
      console.error(err);
      resultDiv.innerHTML = '<p class="error">Network error.</p>';
    }
  });

  // ==========================
  // 📦 BARCODE SCANNING
  // ==========================
  startBarcodeBtn.addEventListener("click", () => {
    if (isBarcodeScanning) return;
    isBarcodeScanning = true;

    Quagga.init({
      inputStream: {
        type: "LiveStream",
        target: barcodeContainer,
        constraints: { 
    width: barcodeContainer.clientWidth,  // fit container width
    height: barcodeContainer.clientHeight, // fit container height
    facingMode: "environment" 
    }
  },
      decoder: { readers: ["ean_reader", "code_128_reader"] }
    }, function (err) {
      if (err) { console.error("Quagga init error:", err); return; }
      Quagga.start();
      startBarcodeBtn.style.display = "none";
      stopBarcodeBtn.style.display = "inline-block";
      console.log("Quagga started ✅");
    });

    Quagga.onDetected(function (result) {
      let code = result.codeResult.code;
      barcodeResult.innerText = "Detected Barcode: " + code;

      fetch("/scan_barcode", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ barcode: code })
      })
      .then(res => res.json())
      .then(data => {
        if (data.error) alert("⚠️ " + data.error + "\nScan ingredient image instead.");
        else renderResults(data);
      })
      .catch(err => console.error("Fetch error:", err));

      Quagga.stop();
      isBarcodeScanning = false;
      startBarcodeBtn.style.display = "inline-block";
      stopBarcodeBtn.style.display = "none";
    });
  });

  stopBarcodeBtn.addEventListener("click", () => {
    Quagga.stop();
    isBarcodeScanning = false;
    startBarcodeBtn.style.display = "inline-block";
    stopBarcodeBtn.style.display = "none";
  });

  // ==========================
  // 📊 RENDER RESULTS (shared)
  // ==========================
  function renderResults(data) {
    let html = "";
    if (data.message) html += `<strong>${data.message}</strong><br/><br/>`;

    if (data.detections?.length)
      html += `<div><strong>Detected Allergens:</strong> ${data.detections.map(d => d.allergen + ' (' + d.severity + ')').join(', ')}</div>`;

    if (data.user_allergies?.length)
      html += `<div><strong>User Allergies:</strong> ${data.user_allergies.join(', ')}</div>`;

    if (data.safe_alternatives && Object.keys(data.safe_alternatives).length) {
      html += `<div><strong>Safe Alternatives:</strong><ul>`;
      for (const a of Object.keys(data.safe_alternatives))
        html += `<li><b>${a}</b>: ${data.safe_alternatives[a].join(', ')}</li>`;
      html += `</ul></div>`;
    }

    if (data.health_score !== undefined) {
      html += `<div><strong>Health Score:</strong> ${data.health_score}/100</div>`;
      if (data.health_found?.length)
        html += `<div><small>Risky ingredients: ${data.health_found.map(x => x[0]).join(', ')}</small></div>`;
    }

    if (data.predictive_allergens?.length)
      html += `<div><strong>Possible Hidden Allergens:</strong> ${data.predictive_allergens.join(', ')}</div>`;

    resultDiv.innerHTML = html;
    rawPre.textContent = 'OCR/Barcode Output:\n\n' + (data.raw_text || data.ingredients || '(none)');
  }
});
