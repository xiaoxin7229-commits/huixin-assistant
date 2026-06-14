const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const chatMessages = document.querySelector("#chatMessages");
const sendButton = document.querySelector("#sendButton");
const quickButtons = document.querySelectorAll(".quick-question");
const tabButtons = document.querySelectorAll(".tab");
const questionPanels = document.querySelectorAll(".question-list");
const stopReadButton = document.querySelector("#stopReadButton");
const voiceReadToggle = document.querySelector("#voiceReadToggle");
const voiceOptionButtons = document.querySelectorAll(".voice-option");

let autoRead = false;
let selectedVoiceLang = "zh-CN";
let availableVoices = [];

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function canSpeak() {
  return "speechSynthesis" in window && "SpeechSynthesisUtterance" in window;
}

function refreshVoices() {
  if (!canSpeak()) {
    availableVoices = [];
    return;
  }
  availableVoices = window.speechSynthesis.getVoices();
}

function chooseVoice(lang) {
  if (!availableVoices.length) {
    refreshVoices();
  }

  const normalized = lang.toLowerCase();
  const exact = availableVoices.find((voice) => voice.lang.toLowerCase() === normalized);
  if (exact) {
    return exact;
  }

  const sameFamily = availableVoices.find((voice) => voice.lang.toLowerCase().startsWith(normalized.split("-")[0]));
  if (sameFamily) {
    return sameFamily;
  }

  return null;
}

function speakText(text) {
  if (!canSpeak() || !text) {
    return;
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = selectedVoiceLang;
  utterance.rate = selectedVoiceLang.startsWith("en") ? 0.9 : 0.95;
  utterance.pitch = 1;

  const voice = chooseVoice(selectedVoiceLang);
  if (voice) {
    utterance.voice = voice;
  }

  window.speechSynthesis.speak(utterance);
}

function stopSpeaking() {
  if (canSpeak()) {
    window.speechSynthesis.cancel();
  }
}

function createReadButton(text) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "read-button";
  button.textContent = canSpeak() ? "朗读" : "暂不支持朗读";
  button.disabled = !canSpeak();
  button.addEventListener("click", () => speakText(text));
  return button;
}

function addMessage(role, text, extraClass = "") {
  const row = document.createElement("div");
  row.className = `message-row ${role} ${extraClass}`.trim();

  const card = document.createElement("div");
  card.className = "bubble-card";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text;

  card.appendChild(bubble);
  if (role === "ai" && extraClass !== "loading") {
    card.appendChild(createReadButton(text));
  }

  row.appendChild(card);
  chatMessages.appendChild(row);
  scrollToBottom();
  return row;
}

function setLoading(isLoading) {
  sendButton.disabled = isLoading;
  messageInput.disabled = isLoading;
  quickButtons.forEach((button) => {
    button.disabled = isLoading;
  });
}

async function sendMessage(text) {
  const message = text.trim();

  addMessage("user", message);
  const loadingRow = addMessage("ai", "惠心小助正在思考中……", "loading");
  setLoading(true);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message }),
    });

    const data = await response.json();
    const answer = data.answer || "暂时没有收到回答，请稍后再试。";
    loadingRow.remove();
    addMessage("ai", answer);

    if (autoRead) {
      speakText(answer);
    }
  } catch (error) {
    const fallback = "暂时无法连接问答服务，请稍后再试。如现场急需咨询，请联系学校老师、县级学生资助管理中心或现场工作人员。";
    loadingRow.remove();
    addMessage("ai", fallback);

    if (autoRead) {
      speakText(fallback);
    }
  } finally {
    setLoading(false);
    messageInput.focus();
  }
}

chatForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const message = messageInput.value.trim();
  messageInput.value = "";
  sendMessage(message);
});

quickButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const question = button.dataset.question || button.textContent;
    sendMessage(question);
  });
});

tabButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const target = button.dataset.tab;

    tabButtons.forEach((tab) => tab.classList.remove("active"));
    questionPanels.forEach((panel) => {
      panel.classList.toggle("active", panel.dataset.panel === target);
    });

    button.classList.add("active");
  });
});

voiceOptionButtons.forEach((button) => {
  button.addEventListener("click", () => {
    selectedVoiceLang = button.dataset.lang || "zh-CN";
    voiceOptionButtons.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    stopSpeaking();
  });
});

stopReadButton.addEventListener("click", stopSpeaking);

voiceReadToggle.addEventListener("click", () => {
  autoRead = !autoRead;
  voiceReadToggle.setAttribute("aria-pressed", String(autoRead));

  if (!autoRead) {
    stopSpeaking();
  }
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopSpeaking();
  }
});

document.querySelectorAll(".message-row.ai .read-button").forEach((button) => {
  const bubble = button.closest(".bubble-card")?.querySelector(".message-bubble");
  const text = bubble?.textContent || "";
  button.textContent = canSpeak() ? "朗读" : "暂不支持朗读";
  button.disabled = !canSpeak();
  button.addEventListener("click", () => speakText(text));
});

const askFromUrl = new URLSearchParams(window.location.search).get("ask");
if (askFromUrl) {
  setTimeout(() => {
    document.querySelector("#chat")?.scrollIntoView({ behavior: "smooth", block: "start" });
    sendMessage(askFromUrl);
  }, 300);
}

if (canSpeak()) {
  refreshVoices();
  window.speechSynthesis.onvoiceschanged = refreshVoices;
}
