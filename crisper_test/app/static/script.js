(() => {
  "use strict";

  const MAX_FILE_SIZE = 25 * 1024 * 1024;
  const ALLOWED_EXTENSIONS = new Set(["mp3", "wav", "m4a", "ogg", "flac", "webm"]);
  const FILLER_LABELS = {
    "hesitation pause": "Hesitation pause",
    "prolonged word": "Prolonged word",
  };

  const elements = {
    uploadCard: document.querySelector("#upload-card"),
    dropZone: document.querySelector("#drop-zone"),
    fileInput: document.querySelector("#audio-file"),
    browseButton: document.querySelector("#browse-button"),
    selectedFile: document.querySelector("#selected-file"),
    fileName: document.querySelector("#file-name"),
    fileSize: document.querySelector("#file-size"),
    removeFile: document.querySelector("#remove-file"),
    recordButton: document.querySelector("#record-button"),
    recordLabel: document.querySelector("#record-label"),
    recordTimer: document.querySelector("#record-timer"),
    analyzeButton: document.querySelector("#analyze-button"),
    errorAlert: document.querySelector("#error-alert"),
    loadingState: document.querySelector("#loading-state"),
    results: document.querySelector("#results"),
    transcript: document.querySelector("#transcript-text"),
  };

  let selectedFile = null;
  let recorder = null;
  let recordingParts = [];
  let recordingStartedAt = 0;
  let recordingTimer = null;
  let lastReport = null;

  function formatClock(seconds) {
    const safeSeconds = Math.max(0, Math.floor(Number(seconds) || 0));
    const minutes = Math.floor(safeSeconds / 60);
    return `${String(minutes).padStart(2, "0")}:${String(safeSeconds % 60).padStart(2, "0")}`;
  }

  function formatFileSize(bytes) {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function setError(message = "") {
    elements.errorAlert.textContent = message;
    elements.errorAlert.hidden = !message;
  }

  function clearSelection() {
    selectedFile = null;
    elements.fileInput.value = "";
    elements.selectedFile.hidden = true;
    elements.fileName.textContent = "";
    elements.fileSize.textContent = "";
    elements.analyzeButton.disabled = true;
  }

  function acceptFile(file) {
    if (!file) return;
    const extension = file.name.split(".").pop()?.toLowerCase() || "";
    if (!ALLOWED_EXTENSIONS.has(extension)) {
      clearSelection();
      setError("That file type isn’t supported. Choose an MP3, WAV, M4A, OGG, or FLAC recording.");
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      clearSelection();
      setError("That recording is over 25 MB. Choose a shorter clip and try again.");
      return;
    }
    if (file.size === 0) {
      clearSelection();
      setError("That file appears to be empty. Choose a recording with audio and try again.");
      return;
    }

    setError();
    selectedFile = file;
    elements.fileName.textContent = file.name;
    elements.fileSize.textContent = formatFileSize(file.size);
    elements.selectedFile.hidden = false;
    elements.analyzeButton.disabled = false;
  }

  function normalizeCounts(value) {
    if (Array.isArray(value)) {
      return value.map((entry) => [String(entry.text ?? "Unknown"), Number(entry.count) || 0]);
    }
    if (value && typeof value === "object") {
      return Object.entries(value).map(([label, count]) => [label, Number(count) || 0]);
    }
    return [];
  }

  function normalizeReport(data) {
    const duration = Number(data.duration_seconds) || 0;
    const pauses = Array.isArray(data.long_pauses) ? data.long_pauses : [];
    const feedback = Array.isArray(data.feedback)
      ? data.feedback.filter(Boolean).join("\n\n")
      : String(data.feedback || "Keep practicing—each time you speak is a chance to grow.");
    return {
      duration,
      durationText: data.duration_text || data.duration_display || formatClock(duration),
      totalWords: Number(data.total_words) || 0,
      wpm: Number(data.wpm ?? data.words_per_minute) || 0,
      fillerCount: Number(data.filler_count) || 0,
      fillers: normalizeCounts(data.fillers),
      repetitions: normalizeCounts(data.repetitions),
      pauses,
      feedback,
      transcript: String(data.transcript || ""),
    };
  }

  function createEmptyState(message) {
    const wrapper = document.createElement("p");
    wrapper.className = "empty-state";
    const icon = document.createElement("span");
    icon.setAttribute("aria-hidden", "true");
    icon.textContent = "✳";
    wrapper.append(icon, document.createTextNode(message));
    return wrapper;
  }

  function renderFillers(report) {
    const chart = document.querySelector("#filler-chart");
    chart.replaceChildren();
    const entries = report.fillers
      .filter(([, count]) => count > 0)
      .sort((left, right) => right[1] - left[1]);

    if (!entries.length) {
      chart.append(createEmptyState("No filler words detected. That’s a lovely clear start."));
      return;
    }

    const maxCount = Math.max(...entries.map(([, count]) => count), 1);
    for (const [label, count] of entries) {
      const row = document.createElement("div");
      row.className = "chart-row";
      const name = document.createElement("span");
      name.className = "chart-label";
      name.textContent = FILLER_LABELS[label.toLowerCase()] || label;
      const track = document.createElement("span");
      track.className = "chart-track";
      const fill = document.createElement("span");
      fill.className = "chart-fill";
      fill.style.width = `${Math.max(4, (count / maxCount) * 100)}%`;
      track.append(fill);
      const value = document.createElement("span");
      value.className = "chart-count";
      value.textContent = String(count);
      row.append(name, track, value);
      chart.append(row);
    }
  }

  function renderRepetitions(report) {
    const list = document.querySelector("#repetitions-list");
    list.replaceChildren();
    const entries = report.repetitions.filter(([, count]) => count > 0);
    if (!entries.length) {
      list.append(createEmptyState("No repeated words or phrases found. Keep that natural flow."));
      return;
    }

    for (const [phrase, count] of entries) {
      const chip = document.createElement("span");
      chip.className = "repetition-chip";
      chip.append(document.createTextNode(`“${phrase}”`));
      const amount = document.createElement("b");
      amount.textContent = `× ${count}`;
      chip.append(amount);
      list.append(chip);
    }
  }

  function renderPauses(report) {
    const track = document.querySelector("#timeline-track");
    const list = document.querySelector("#pause-list");
    const validPauses = report.pauses.filter((pause) => Number.isFinite(Number(pause.start)) && Number.isFinite(Number(pause.end)));
    const totalDuration = Math.max(report.duration, ...validPauses.map((pause) => Number(pause.end)), 1);

    document.querySelector("#timeline-end").textContent = report.durationText;
    track.replaceChildren();
    list.replaceChildren();
    track.setAttribute(
      "aria-label",
      validPauses.length
        ? `${validPauses.length} long ${validPauses.length === 1 ? "pause" : "pauses"} in a ${report.durationText} recording`
        : "No long pauses detected",
    );

    for (const pause of validPauses) {
      const start = Math.max(0, Math.min(totalDuration, Number(pause.start)));
      const end = Math.max(start, Math.min(totalDuration, Number(pause.end)));
      const marker = document.createElement("span");
      marker.className = "pause-marker";
      marker.style.left = `${(start / totalDuration) * 100}%`;
      marker.style.width = `${Math.max(.65, ((end - start) / totalDuration) * 100)}%`;
      track.append(marker);

      const chip = document.createElement("span");
      chip.className = "pause-chip";
      chip.textContent = `${formatClock(start)} – ${formatClock(end)}`;
      list.append(chip);
    }
    if (!validPauses.length) {
      list.append(createEmptyState("No long pauses this time. Your ideas kept moving."));
    }
  }

  function renderPace(wpm) {
    const badge = document.querySelector("#pace-badge");
    badge.classList.remove("slow", "fast");
    if (wpm < 110) {
      badge.textContent = "A little slow";
      badge.classList.add("slow");
    } else if (wpm > 160) {
      badge.textContent = "A little fast";
      badge.classList.add("fast");
    } else {
      badge.textContent = "Comfortable pace";
    }
  }

  function renderResults(rawData) {
    const report = normalizeReport(rawData);
    lastReport = rawData;
    document.querySelector("#stat-duration").textContent = report.durationText;
    document.querySelector("#stat-words").textContent = String(report.totalWords);
    document.querySelector("#stat-wpm").textContent = String(report.wpm);
    document.querySelector("#stat-fillers").textContent = String(report.fillerCount);
    renderPace(report.wpm);
    renderFillers(report);
    renderRepetitions(report);
    renderPauses(report);
    document.querySelector("#feedback-text").textContent = report.feedback;
    elements.transcript.textContent = report.transcript || "A transcript wasn’t included with this report.";
    elements.results.hidden = false;
    elements.results.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function analyzeSpeech() {
    if (!selectedFile) return;
    setError();
    elements.analyzeButton.disabled = true;
    elements.recordButton.disabled = true;
    elements.browseButton.disabled = true;
    elements.loadingState.hidden = false;
    elements.results.hidden = true;

    const formData = new FormData();
    formData.append("file", selectedFile);
    try {
      const response = await fetch("/analyze", { method: "POST", body: formData });
      let result;
      try {
        result = await response.json();
      } catch {
        throw new Error("The server sent an unreadable response. Please try again.");
      }
      if (!response.ok || result.error || result.detail) {
        throw new Error(result.error || result.detail || "We couldn’t analyze that recording. Please try another file.");
      }
      renderResults(result);
    } catch (error) {
      const message = error instanceof TypeError
        ? "Couldn’t reach the speech evaluator. Check that the local server is running, then try again."
        : error.message;
      setError(message || "Something went wrong while analyzing your recording. Please try again.");
      elements.uploadCard.scrollIntoView({ behavior: "smooth", block: "center" });
    } finally {
      elements.loadingState.hidden = true;
      elements.analyzeButton.disabled = !selectedFile;
      elements.recordButton.disabled = false;
      elements.browseButton.disabled = false;
    }
  }

  function setRecordingUi(isRecording) {
    elements.recordButton.classList.toggle("recording", isRecording);
    elements.recordButton.setAttribute("aria-pressed", String(isRecording));
    elements.recordLabel.textContent = isRecording ? "Stop recording" : "Record a practice";
    elements.recordTimer.hidden = !isRecording;
  }

  function startTimer() {
    const update = () => {
      elements.recordTimer.textContent = formatClock((Date.now() - recordingStartedAt) / 1000);
    };
    update();
    recordingTimer = window.setInterval(update, 500);
  }

  async function startRecording() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError("Recording isn’t supported in this browser. Please choose an audio file instead.");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"]
        .find((type) => MediaRecorder.isTypeSupported(type));
      recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recordingParts = [];
      recorder.addEventListener("dataavailable", (event) => {
        if (event.data.size) recordingParts.push(event.data);
      });
      recorder.addEventListener("stop", () => {
        stream.getTracks().forEach((track) => track.stop());
        window.clearInterval(recordingTimer);
        setRecordingUi(false);
        elements.recordButton.disabled = false;
        elements.recordTimer.hidden = true;
        if (!recordingParts.length) {
          setError("No audio was captured. Please try recording again.");
          return;
        }
        const blob = new Blob(recordingParts, { type: recorder.mimeType || "audio/webm" });
        const extension = blob.type.includes("mp4") ? "m4a" : blob.type.includes("ogg") ? "ogg" : "webm";
        acceptFile(new File([blob], `speech-practice.${extension}`, { type: blob.type }));
      }, { once: true });
      recorder.start();
      recordingStartedAt = Date.now();
      startTimer();
      setError();
      setRecordingUi(true);
    } catch (error) {
      setError(error.name === "NotAllowedError"
        ? "Microphone access was blocked. Allow access in your browser settings or upload a recording."
        : "We couldn’t access your microphone. Check your audio settings and try again.");
    }
  }

  function stopRecording() {
    if (recorder?.state === "recording") recorder.stop();
  }

  function resetForAnotherSpeech() {
    setError();
    elements.results.hidden = true;
    elements.loadingState.hidden = true;
    elements.uploadCard.hidden = false;
    elements.transcript.textContent = "";
    document.querySelector(".transcript-card").open = false;
    lastReport = null;
    clearSelection();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function downloadReport() {
    if (!lastReport) return;
    const blob = new Blob([JSON.stringify(lastReport, null, 2)], { type: "application/json" });
    const objectUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = "speakwell-speech-report.json";
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(objectUrl);
  }

  elements.browseButton.addEventListener("click", () => elements.fileInput.click());
  elements.fileInput.addEventListener("change", () => {
    acceptFile(elements.fileInput.files?.[0]);
    elements.fileInput.value = "";
  });
  elements.dropZone.addEventListener("dragover", (event) => {
    event.preventDefault();
    elements.dropZone.classList.add("drag-active");
  });
  elements.dropZone.addEventListener("dragleave", (event) => {
    if (!elements.dropZone.contains(event.relatedTarget)) elements.dropZone.classList.remove("drag-active");
  });
  elements.dropZone.addEventListener("drop", (event) => {
    event.preventDefault();
    elements.dropZone.classList.remove("drag-active");
    acceptFile(event.dataTransfer?.files?.[0]);
  });
  elements.removeFile.addEventListener("click", clearSelection);
  elements.analyzeButton.addEventListener("click", analyzeSpeech);
  elements.recordButton.addEventListener("click", () => {
    if (recorder?.state === "recording") stopRecording();
    else startRecording();
  });
  document.querySelector("#another-button").addEventListener("click", resetForAnotherSpeech);
  document.querySelector("#download-button").addEventListener("click", downloadReport);
})();
