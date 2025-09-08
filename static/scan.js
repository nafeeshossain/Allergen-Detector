document.addEventListener('DOMContentLoaded', function () {
    // --- Element Declarations ---
    // For Image Upload
    const input = document.getElementById('imageInput');
    const scanBtn = document.getElementById('scanBtn');

    // For Camera Capture
    const captureBtn = document.getElementById('captureBtn');
    const scanCapturedBtn = document.getElementById('scanCapturedBtn'); // The new button
    const video = document.getElementById('camera');
    const canvas = document.getElementById('canvas');

    // For Barcode Scanner
    const startBarcodeBtn = document.getElementById("startBarcodeScan");
    const stopBarcodeBtn = document.getElementById("stopBarcodeScan");
    const barcodeResult = document.getElementById("barcodeResult");
    const barcodeContainer = document.getElementById("barcodeScanner");

    // For Results
    const resultDiv = document.getElementById('result');
    const rawPre = document.getElementById('raw');

    // --- State Variables ---
    let capturedBlob = null;
    let isBarcodeScanning = false;

    // ==========================
    // 📷 CAMERA SETUP
    // ==========================
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } })
            .then(stream => {
                video.srcObject = stream;
            })
            .catch(err => {
                console.error("Camera could not be started:", err);
                if (video.parentElement) {
                    video.parentElement.style.display = 'none';
                }
            });
    } else {
        console.error("This browser does not support camera access.");
        if (video.parentElement) {
            video.parentElement.style.display = 'none';
        }
    }

    // ==========================
    // 🖱️ EVENT LISTENERS FOR BUTTONS
    // ==========================

    // 1. When you click "Capture"
    captureBtn.addEventListener('click', () => {
        if (!video.videoWidth) {
            console.error("Video stream not ready.");
            resultDiv.innerHTML = `<p style="color: red;">Camera not ready. Please grant permission and try again.</p>`;
            return;
        }
        const context = canvas.getContext('2d');
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(blob => {
            capturedBlob = blob;
            resultDiv.innerHTML = "<p style='color: #007bff;'>✅ Image captured. Ready to scan.</p>";
            scanCapturedBtn.style.display = 'inline-block'; // Show the new button
        }, 'image/jpeg', 0.95);
    });

    // 2. When you click the NEW "Scan Captured Image" button
    scanCapturedBtn.addEventListener('click', () => {
        if (!capturedBlob) return;
        const file = new File([capturedBlob], "capture.jpg", { type: "image/jpeg" });
        performOcrScan(file);
    });

    // 3. When you click the ORIGINAL "Scan Ingredients" button for uploads
    scanBtn.addEventListener('click', () => {
        const file = input.files && input.files[0];
        if (!file) {
            resultDiv.innerHTML = '<p style="color: red;">Please upload an image file first.</p>';
            return;
        }
        performOcrScan(file);
    });

    // ==========================
    // 🔎 IMAGE OCR SCAN FUNCTION (Shared)
    // ==========================
    async function performOcrScan(fileToSend) {
        const form = new FormData();
        form.append('image', fileToSend);

        resultDiv.innerHTML = 'Scanning...';
        rawPre.textContent = '';
        scanCapturedBtn.style.display = 'none'; // Hide button after clicking

        try {
            const res = await fetch('/scan', { method: 'POST', body: form });
            const data = await res.json();
            if (!res.ok) {
                resultDiv.innerHTML = `<p style="color: red;">${data.error || 'Scan failed'}</p>`;
                return;
            }
            renderResults(data);
        } catch (err) {
            console.error("Network or fetch error:", err);
            resultDiv.innerHTML = '<p style="color: red;">A network error occurred.</p>';
        }
    }

    // ==========================
    // 📦 BARCODE SCANNING (Your existing logic)
    // ==========================
    startBarcodeBtn.addEventListener("click", () => {
        if (isBarcodeScanning) return;
        isBarcodeScanning = true;

        Quagga.init({
            inputStream: {
                type: "LiveStream",
                target: barcodeContainer,
                constraints: {
                    width: barcodeContainer.clientWidth,
                    height: barcodeContainer.clientHeight,
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
            document.getElementById("barcodeResult").textContent = code; // Update result display
            document.getElementById("barcodeResultBox").style.display = 'block';

            fetch("/scan_barcode", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ barcode: code })
            })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    alert("⚠️ " + data.error + "\nScan ingredient image instead.");
                } else {
                    renderResults(data);
                }
            })
            .catch(err => console.error("Fetch error:", err));

            Quagga.stop();
            isBarcodeScanning = false;
            startBarcodeBtn.style.display = "inline-block";
            stopBarcodeBtn.style.display = "none";
        });
    });

    stopBarcodeBtn.addEventListener("click", () => {
        if (!isBarcodeScanning) return;
        Quagga.stop();
        isBarcodeScanning = false;
        startBarcodeBtn.style.display = "inline-block";
        stopBarcodeBtn.style.display = "none";
    });

    // ==========================
    // 📊 RENDER RESULTS (Shared by all scans)
    // ==========================
    function renderResults(data) {
        let html = "";
        if (data.message) html += `<strong>${data.message}</strong><br/><br/>`;

        if (data.detections?.length)
            html += `<div><strong>Detected Allergens:</strong> ${data.detections.map(d => `${d.allergen} (${d.severity})`).join(', ')}</div>`;

        if (data.user_allergies?.length)
            html += `<div><strong>Your Allergies:</strong> ${data.user_allergies.join(', ')}</div>`;

        if (data.safe_alternatives && Object.keys(data.safe_alternatives).length) {
            html += `<div style="margin-top:10px;"><strong>Safe Alternatives:</strong><ul>`;
            for (const allergen in data.safe_alternatives) {
                html += `<li><b>${allergen}</b>: ${data.safe_alternatives[allergen].join(', ')}</li>`;
            }
            html += `</ul></div>`;
        }

        if (data.health_score !== undefined) {
            html += `<div style="margin-top:10px;"><strong>Health Score:</strong> ${data.health_score}/100</div>`;
            if (data.health_found?.length)
                html += `<div><small>Risky ingredients: ${data.health_found.map(x => x[0]).join(', ')}</small></div>`;
        }

        if (data.predictive_allergens?.length)
            html += `<div style="margin-top:10px;"><strong>Possible Hidden Allergens:</strong> ${data.predictive_allergens.join(', ')}</div>`;

        resultDiv.innerHTML = html;
        rawPre.textContent = 'Scan Output:\n\n' + (data.raw_text || data.ingredients || '(none)');
    }
});
