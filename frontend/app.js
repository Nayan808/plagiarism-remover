const API_BASE = (typeof CONFIG !== "undefined" ? CONFIG.API_BASE : "http://127.0.0.1:8000");

// ── Elements ──────────────────────────────────
const dropZone      = document.getElementById("drop-zone");
const fileInput     = document.getElementById("file-input");
const filePreview   = document.getElementById("file-preview");
const fileIcon      = document.getElementById("file-icon");
const fileName      = document.getElementById("file-name");
const fileSize      = document.getElementById("file-size");
const clearFileBtn  = document.getElementById("clear-file");
const modelSelect   = document.getElementById("model-select");
const processBtn    = document.getElementById("process-btn");
const healthBanner  = document.getElementById("health-banner");

const progressCard  = document.getElementById("progress-card");
const progressLabel = document.getElementById("progress-label");

const resultCard    = document.getElementById("result-card");
const resultInfo    = document.getElementById("result-info");
const downloadLink  = document.getElementById("download-link");
const processAnother= document.getElementById("process-another");

const errorCard     = document.getElementById("error-card");
const errorMsg      = document.getElementById("error-msg");
const retryBtn      = document.getElementById("retry-btn");

let selectedFile = null;

// ── Health Check ──────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`);
    const data = await res.json();
    if (data.groq === "configured") {
      healthBanner.className = "banner banner-ok";
      healthBanner.textContent = "Groq AI connected and ready.";
    } else {
      throw new Error(data.error || "GROQ_API_KEY not configured on server");
    }
  } catch (e) {
    healthBanner.className = "banner banner-error";
    healthBanner.textContent = `API not reachable: ${e.message}`;
  }
}

// ── File Handling ─────────────────────────────
const EXT_LABELS = { docx: "DOCX", pdf: "PDF", txt: "TXT" };
const EXT_COLORS = { docx: "#2563eb", pdf: "#dc2626", txt: "#16a34a" };

function setFile(file) {
  if (!file) return;
  const ext = file.name.split(".").pop().toLowerCase();
  if (!["docx", "pdf", "txt"].includes(ext)) {
    showError("Unsupported file type. Please upload .docx, .pdf, or .txt");
    return;
  }
  selectedFile = file;
  fileIcon.textContent = EXT_LABELS[ext] || ext.toUpperCase();
  fileIcon.style.background = EXT_COLORS[ext] || "#6366f1";
  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);
  filePreview.classList.remove("hidden");
  dropZone.classList.add("hidden");
  processBtn.disabled = false;
  hideCards();
}

function clearFile() {
  selectedFile = null;
  fileInput.value = "";
  filePreview.classList.add("hidden");
  dropZone.classList.remove("hidden");
  processBtn.disabled = true;
  hideCards();
}

function formatBytes(bytes) {
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

// ── Drag & Drop ───────────────────────────────
dropZone.addEventListener("dragover", e => { e.preventDefault(); dropZone.classList.add("dragover"); });
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("dragover"));
dropZone.addEventListener("drop", e => {
  e.preventDefault();
  dropZone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file) setFile(file);
});
dropZone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => { if (fileInput.files[0]) setFile(fileInput.files[0]); });
clearFileBtn.addEventListener("click", clearFile);

// ── Process ───────────────────────────────────
processBtn.addEventListener("click", processFile);

async function processFile() {
  if (!selectedFile) return;

  hideCards();
  progressCard.classList.remove("hidden");
  processBtn.disabled = true;
  progressLabel.textContent = "Sending file to AI...";

  const formData = new FormData();
  formData.append("file", selectedFile);
  formData.append("model", modelSelect.value);

  try {
    progressLabel.textContent = "Paraphrasing content... (this may take a while)";

    const res = await fetch(`${API_BASE}/process`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: res.statusText }));
      throw new Error(err.detail || "Server error");
    }

    const blob = await res.blob();
    const outFilename = res.headers.get("X-Output-Filename") ||
      selectedFile.name.replace(/(\.[^.]+)$/, "_paraphrased$1");
    const aiBefore = res.headers.get("X-AI-Before");
    const aiAfter  = res.headers.get("X-AI-After");

    const url = URL.createObjectURL(blob);
    downloadLink.href = url;
    downloadLink.download = outFilename;
    resultInfo.textContent = `Output file: ${outFilename}`;

    updateAiDetection(aiBefore, aiAfter);

    progressCard.classList.add("hidden");
    resultCard.classList.remove("hidden");

  } catch (e) {
    progressCard.classList.add("hidden");
    showError(e.message);
  } finally {
    processBtn.disabled = false;
  }
}

// ── Result / Error Helpers ─────────────────────
function showError(msg) {
  errorMsg.textContent = msg;
  errorCard.classList.remove("hidden");
}

function hideCards() {
  progressCard.classList.add("hidden");
  resultCard.classList.add("hidden");
  errorCard.classList.add("hidden");
}

processAnother.addEventListener("click", () => {
  clearFile();
  hideCards();
  URL.revokeObjectURL(downloadLink.href);
});

retryBtn.addEventListener("click", () => {
  hideCards();
  if (selectedFile) processBtn.disabled = false;
});

// ── AI Detection Display ───────────────────────
function updateAiDetection(before, after) {
  const section  = document.getElementById("ai-detection");
  const b = parseInt(before, 10);
  const a = parseInt(after,  10);

  if (isNaN(b) || b < 0 || isNaN(a) || a < 0) {
    section.classList.add("hidden");
    return;
  }

  document.getElementById("ai-pct-before").textContent = b + "%";
  document.getElementById("ai-pct-after").textContent  = a + "%";

  const barBefore = document.getElementById("ai-bar-before");
  const barAfter  = document.getElementById("ai-bar-after");
  barBefore.style.width      = b + "%";
  barAfter.style.width       = a + "%";
  barBefore.style.background = aiColor(b);
  barAfter.style.background  = aiColor(a);

  section.classList.remove("hidden");
}

function aiColor(pct) {
  if (pct >= 70) return "#ef4444";   // red   — high AI
  if (pct >= 40) return "#f97316";   // orange — medium
  return "#22c55e";                  // green  — mostly human
}

// ── Init ──────────────────────────────────────
checkHealth();
