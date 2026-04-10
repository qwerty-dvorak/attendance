const state = {
  overview: null,
  health: null,
  activeSessionId: "",
  selectedSessionId: "",
  captures: {
    student: null,
    esp32: null,
  },
  streams: {},
};

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || payload.message || "Request failed");
  }
  return payload;
}

function formatJson(data) {
  return JSON.stringify(data, null, 2);
}

function setText(id, value) {
  document.getElementById(id).textContent = value;
}

function setCodePanel(id, value) {
  document.getElementById(id).textContent =
    typeof value === "string" ? value : formatJson(value);
}

function setActionFeedback(message) {
  setText("action-feedback", message);
}

function updateSessionTargets(sessionId) {
  state.activeSessionId = sessionId || "";
  setText("active-session-pill", state.activeSessionId || "none");
  document.getElementById("esp32-session-id").value = state.activeSessionId;
  document.getElementById("stop-session-id").value = state.activeSessionId;
}

function renderHealth() {
  if (!state.health) return;
  setText("health-status", state.health.status || "--");
  setText("embedder-name", state.health.default_embedder || "--");
  const frameSize = state.health.esp32_frame_size || {};
  setText(
    "esp32-size",
    frameSize.width && frameSize.height
      ? `${frameSize.width} x ${frameSize.height}`
      : "--"
  );
}

function renderSummary() {
  const overview = state.overview;
  if (!overview) return;
  setText("seed-teacher-name", overview.seed_teacher.name || "--");
  setText("seed-teacher-email", overview.seed_teacher.email || "--");
  setText("seed-teacher-rfid", overview.seed_teacher.rfid_uid || "--");
  setText("summary-teachers", overview.summary.teachers ?? 0);
  setText("summary-students", overview.summary.students ?? 0);
  setText("summary-active-sessions", overview.summary.active_sessions ?? 0);
  setText("summary-records", overview.summary.attendance_records ?? 0);
  setText("summary-sample-folders", overview.sample_data.student_folders ?? 0);
  setText("summary-test-photos", overview.test_photos.image_count ?? 0);
  const latestActiveId = overview.latest_active_session?.session_id || "";
  updateSessionTargets(latestActiveId);
  document.getElementById("rfid-input").value =
    overview.seed_teacher.rfid_uid || "";
}

function renderTeachers() {
  const container = document.getElementById("teacher-list");
  const teachers = state.overview?.teachers || [];
  if (!teachers.length) {
    container.innerHTML = '<div class="empty-state">No teachers registered yet.</div>';
    return;
  }
  container.innerHTML = teachers
    .map(
      (teacher) => `
        <div class="list-row">
          <strong>${teacher.name}</strong>
          <div class="muted-line">${teacher.email}</div>
          <div class="tag-line">
            <span class="tag">RFID ${teacher.rfid_uid}</span>
            <span class="tag">Teacher #${teacher.id}</span>
          </div>
        </div>
      `
    )
    .join("");
}

function renderStudents() {
  const container = document.getElementById("student-cards");
  const students = state.overview?.students || [];
  if (!students.length) {
    container.innerHTML = '<div class="empty-state">No students registered yet.</div>';
    return;
  }
  container.innerHTML = students
    .map(
      (student) => `
        <article class="student-card">
          ${
            student.face_image_url
              ? `<img src="${student.face_image_url}" alt="${student.name}">`
              : '<div class="empty-state">No photo</div>'
          }
          <div class="student-card-body">
            <strong>${student.name}</strong>
            <div class="muted-line">${student.roll_no}</div>
            <div class="muted-line">${student.email || "No email"}</div>
            <div class="tag-line">
              <span class="tag">${student.face_registered ? "Face ready" : "No embedding"}</span>
              <span class="tag">${student.embedding_model || "pending"}</span>
            </div>
          </div>
        </article>
      `
    )
    .join("");
}

function renderSessions() {
  const container = document.getElementById("session-cards");
  const sessions = state.overview?.recent_sessions || [];
  if (!sessions.length) {
    container.innerHTML = '<div class="empty-state">No sessions recorded yet.</div>';
    return;
  }
  container.innerHTML = sessions
    .map(
      (session) => `
        <div class="list-row">
          <strong>${session.session_id}</strong>
          <div class="muted-line">${session.teacher_name || "Unknown teacher"}</div>
          <div class="tag-line">
            <span class="tag">${session.status}</span>
            <span class="tag">${session.attendance_count} attendance marks</span>
            <span class="tag">${session.frame_count || 0} frames</span>
          </div>
          <div class="session-actions">
            <button type="button" class="ghost mini-btn" data-action="view-frames" data-session-id="${session.session_id}">Frames</button>
            <button type="button" class="ghost mini-btn" data-action="send-report" data-session-id="${session.session_id}">Send mail</button>
            <button type="button" class="ghost mini-btn" data-action="deactivate-session" data-session-id="${session.session_id}">Deactivate</button>
            <button type="button" class="danger mini-btn" data-action="delete-session" data-session-id="${session.session_id}">Delete</button>
          </div>
        </div>
      `
    )
    .join("");
}

function renderFrameHistory(frames = [], sessionId = "") {
  const container = document.getElementById("frame-history-list");
  if (!sessionId) {
    container.innerHTML =
      '<div class="empty-state">No session selected. Use the Frames button on a session card.</div>';
    return;
  }
  if (!frames.length) {
    container.innerHTML = `<div class="empty-state">No processed frames stored for ${sessionId} yet.</div>`;
    return;
  }
  container.innerHTML = frames
    .map(
      (frame) => `
        <div class="list-row frame-row">
          <img class="frame-thumb" src="/media/uploads/${frame.image_path.split('/uploads/').pop()}" alt="Session frame ${frame.id}">
          <div class="result-grid">
            <strong>Frame #${frame.id}</strong>
            <div class="muted-line">${frame.processed_at || ""}</div>
            <div class="tag-line">
              <span class="tag">${frame.source}</span>
              <span class="tag">${frame.faces_detected} detections</span>
              <span class="tag">${frame.recognized_count} recognized</span>
              <span class="tag">${frame.new_records_count} new</span>
              <span class="tag">${frame.duplicate_count} duplicate</span>
            </div>
            <pre class="code-panel">${formatJson({
              matched_students: frame.matched_students,
              new_records: frame.new_records,
              duplicate_matches: frame.duplicate_matches,
              all_detections: frame.all_detections,
            })}</pre>
          </div>
        </div>
      `
    )
    .join("");
}

function renderSampleData() {
  const sample = state.overview?.sample_data || {};
  document.getElementById("sample-data-path").textContent = sample.path || "--";
  const container = document.getElementById("sample-data-list");
  const students = sample.students || [];
  if (!students.length) {
    container.innerHTML = '<div class="empty-state">No sample student folders found.</div>';
    return;
  }
  container.innerHTML = students
    .map(
      (student) => `
        <div class="list-row">
          <strong>${student.name}</strong>
          <div class="muted-line">${student.folder}</div>
          <div class="tag-line">
            <span class="tag">${student.roll_no}</span>
            <span class="tag">${student.images.length} images</span>
            <span class="tag">seed ${student.seed_image || "none"}</span>
          </div>
        </div>
      `
    )
    .join("");
}

function renderTestPhotos() {
  const testPhotos = state.overview?.test_photos || {};
  document.getElementById("test-photos-path").textContent =
    testPhotos.path || "--";
  const container = document.getElementById("test-photo-list");
  const files = testPhotos.files || [];
  if (!files.length) {
    container.innerHTML =
      '<div class="empty-state">No dummy sensor photos found in the test folder.</div>';
    return;
  }
  container.innerHTML = files
    .map(
      (file) => `
        <div class="list-row">
          <strong>${file}</strong>
        </div>
      `
    )
    .join("");
}

async function loadDashboard() {
  const [health, overview] = await Promise.all([
    api("/health"),
    api("/api/dashboard/overview"),
  ]);
  state.health = health;
  state.overview = overview;
  renderHealth();
  renderSummary();
  renderTeachers();
  renderStudents();
  renderSessions();
  if (state.selectedSessionId) {
    await handleViewFrames(state.selectedSessionId, { silent: true });
  } else {
    renderFrameHistory([], "");
  }
  renderSampleData();
  renderTestPhotos();
}

async function handleTeacherSubmit(event) {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.target).entries());
  const result = await api("/api/teacher/register", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  setActionFeedback(`Teacher saved: ${result.teacher.name}`);
  event.target.reset();
  await loadDashboard();
}

async function handleSeed() {
  const result = await api("/api/admin/seed-sample", { method: "POST" });
  setActionFeedback(
    `Created ${result.seeded_count} and refreshed ${result.updated_count} sample students for ${result.teacher.name}.`
  );
  setCodePanel("session-output", result);
  await loadDashboard();
}

async function handleClear() {
  const confirmed = window.confirm(
    "Clear the full database and uploaded images?"
  );
  if (!confirmed) return;
  const result = await api("/api/admin/clear-db", { method: "POST" });
  updateSessionTargets("");
  setCodePanel("session-output", "Database cleared.");
  setCodePanel("esp32-output", "Database cleared.");
  setActionFeedback(result.message || "Database cleared.");
  await loadDashboard();
}

async function handleStartSession(event, payloadOverride = null) {
  if (event) event.preventDefault();
  const payload =
    payloadOverride ||
    Object.fromEntries(new FormData(document.getElementById("rfid-session-form")).entries());
  payload.duration_minutes = Number(payload.duration_minutes || 15);
  const result = await api("/api/rfid/start-session", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  state.selectedSessionId = result.session_id;
  updateSessionTargets(result.session_id);
  setCodePanel("session-output", result);
  await loadDashboard();
}

async function handleStopSession(event) {
  event.preventDefault();
  const payload = Object.fromEntries(new FormData(event.target).entries());
  const result = await api("/api/session/stop", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  state.selectedSessionId = payload.session_id || "";
  setCodePanel("session-output", result);
  await loadDashboard();
}

async function handleStudentSubmit(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const fileInput = document.getElementById("student-file-input");
  if (!fileInput.files.length && state.captures.student) {
    form.set("face_image", state.captures.student, "student-camera.jpg");
  }
  const result = await api("/api/students/register", {
    method: "POST",
    body: form,
  });
  setActionFeedback(`Student registered: ${result.student.name}`);
  event.target.reset();
  clearPreview("student");
  await loadDashboard();
}

async function handleEsp32Submit(event) {
  event.preventDefault();
  const form = new FormData(event.target);
  const fileInput = document.getElementById("esp32-file-input");
  if (!fileInput.files.length && state.captures.esp32) {
    form.set("frame", state.captures.esp32, "esp32-camera.jpg");
  }
  const result = await api("/api/esp32/frame", {
    method: "POST",
    body: form,
  });
  state.selectedSessionId = form.get("session_id") || state.selectedSessionId;
  setCodePanel("esp32-output", result);
  if (state.selectedSessionId) {
    await handleViewFrames(state.selectedSessionId, { silent: true });
  }
  await loadDashboard();
}

async function handleViewFrames(sessionId, options = {}) {
  const result = await api(`/api/attendance/${sessionId}/frames`);
  state.selectedSessionId = sessionId;
  renderFrameHistory(result.frames, sessionId);
  if (!options.silent) {
    setCodePanel("session-output", result);
  }
}

async function handleDeactivateSession(sessionId) {
  const result = await api("/api/session/deactivate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  setCodePanel("session-output", result);
  await loadDashboard();
}

async function handleDeleteSession(sessionId) {
  const confirmed = window.confirm(`Delete session ${sessionId}?`);
  if (!confirmed) return;
  const result = await api(`/api/session/${sessionId}`, { method: "DELETE" });
  if (state.selectedSessionId === sessionId) {
    state.selectedSessionId = "";
    renderFrameHistory([], "");
  }
  setCodePanel("session-output", result);
  await loadDashboard();
}

async function handleSendReport(sessionId) {
  const result = await api("/api/session/send-report", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });
  setCodePanel("session-output", result);
}

async function startCamera(role, videoId) {
  stopCamera(role);
  const stream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: "user" },
    audio: false,
  });
  state.streams[role] = stream;
  document.getElementById(videoId).srcObject = stream;
}

function stopCamera(role) {
  const stream = state.streams[role];
  if (!stream) return;
  stream.getTracks().forEach((track) => track.stop());
  delete state.streams[role];
}

function clearPreview(role) {
  state.captures[role] = null;
  const preview = document.getElementById(`${role}-preview`);
  preview.removeAttribute("src");
  if (role === "student") {
    document.getElementById("student-file-input").value = "";
  }
  if (role === "esp32") {
    document.getElementById("esp32-file-input").value = "";
  }
}

function captureFromVideo(role, videoId) {
  const video = document.getElementById(videoId);
  if (!video.videoWidth || !video.videoHeight) {
    throw new Error("Camera is not ready yet");
  }
  const canvas = document.createElement("canvas");
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  canvas.getContext("2d").drawImage(video, 0, 0);
  return new Promise((resolve) => {
    canvas.toBlob((blob) => resolve(blob), "image/jpeg", 0.92);
  });
}

async function handleCapture(role, videoId) {
  const blob = await captureFromVideo(role, videoId);
  state.captures[role] = blob;
  const preview = document.getElementById(`${role}-preview`);
  preview.src = URL.createObjectURL(blob);
}

function bindEvents() {
  document.getElementById("teacher-form").addEventListener("submit", (event) => {
    handleTeacherSubmit(event).catch(showError);
  });
  document
    .getElementById("rfid-session-form")
    .addEventListener("submit", (event) => handleStartSession(event).catch(showError));
  document
    .getElementById("stop-form")
    .addEventListener("submit", (event) => handleStopSession(event).catch(showError));
  document
    .getElementById("student-form")
    .addEventListener("submit", (event) => handleStudentSubmit(event).catch(showError));
  document
    .getElementById("esp32-upload-form")
    .addEventListener("submit", (event) => handleEsp32Submit(event).catch(showError));

  document.getElementById("reload-dashboard").addEventListener("click", () => {
    loadDashboard().catch(showError);
  });
  document.getElementById("seed-sample-btn").addEventListener("click", () => {
    handleSeed().catch(showError);
  });
  document.getElementById("clear-db-btn").addEventListener("click", () => {
    handleClear().catch(showError);
  });
  document.getElementById("quick-start-seed").addEventListener("click", () => {
    const rfid = state.overview?.seed_teacher?.rfid_uid || "";
    handleStartSession(null, { rfid_uid: rfid, duration_minutes: 15 }).catch(showError);
  });

  document.getElementById("student-camera-start").addEventListener("click", () => {
    startCamera("student", "student-video").catch(showError);
  });
  document.getElementById("student-camera-capture").addEventListener("click", () => {
    handleCapture("student", "student-video").catch(showError);
  });
  document.getElementById("student-camera-clear").addEventListener("click", () => {
    clearPreview("student");
  });

  document.getElementById("esp32-camera-start").addEventListener("click", () => {
    startCamera("esp32", "esp32-video").catch(showError);
  });
  document.getElementById("esp32-camera-capture").addEventListener("click", () => {
    handleCapture("esp32", "esp32-video").catch(showError);
  });
  document.getElementById("esp32-camera-clear").addEventListener("click", () => {
    clearPreview("esp32");
  });

  document.getElementById("session-cards").addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    const sessionId = button.dataset.sessionId;
    const action = button.dataset.action;
    if (action === "view-frames") {
      handleViewFrames(sessionId).catch(showError);
    } else if (action === "send-report") {
      handleSendReport(sessionId).catch(showError);
    } else if (action === "deactivate-session") {
      handleDeactivateSession(sessionId).catch(showError);
    } else if (action === "delete-session") {
      handleDeleteSession(sessionId).catch(showError);
    }
  });
}

function showError(error) {
  window.alert(error.message || String(error));
}

window.addEventListener("beforeunload", () => {
  stopCamera("student");
  stopCamera("esp32");
});

bindEvents();
loadDashboard().catch(showError);
