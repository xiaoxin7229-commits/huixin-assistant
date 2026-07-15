const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const chatMessages = document.querySelector("#chatMessages");
const chatSection = document.querySelector("#chat");
const sendButton = document.querySelector("#sendButton");
const quickButtons = document.querySelectorAll(".quick-question");
const tabButtons = document.querySelectorAll(".tab");
const questionPanels = document.querySelectorAll(".question-list");
const stopReadButton = document.querySelector("#stopReadButton");
const voiceReadToggle = document.querySelector("#voiceReadToggle");
const voiceOptionButtons = document.querySelectorAll(".voice-option");
const voiceStatus = document.querySelector("#voiceStatus");
const imageInput = document.querySelector("#imageInput");
const mascotUrl = document.querySelector(".app-shell")?.dataset.aiAvatarUrl
  || document.querySelector(".message-avatar")?.src
  || "";

let autoRead = false;
let selectedVoiceLang = "zh-CN";
let availableVoices = [];
let currentAudio = null;
let currentAudioUrl = "";
let currentTtsController = null;
let speechSequence = 0;

function scrollToBottom() {
  window.requestAnimationFrame(() => {
    chatMessages.scrollTop = chatMessages.scrollHeight;
  });
}

function scrollChatIntoView() {
  scrollToBottom();
  window.requestAnimationFrame(() => {
    chatSection?.scrollIntoView({ behavior: "smooth", block: "start" });
  });
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
  updateVoiceButtons();
}

function chooseVoice(lang) {
  if (!availableVoices.length) {
    return null;
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

function hasVoiceFor(lang) {
  return Boolean(chooseVoice(lang));
}

function updateVoiceButtons() {
  voiceOptionButtons.forEach((button) => {
    const lang = button.dataset.lang || "zh-CN";
    const browserFallbackAvailable = canSpeak() && hasVoiceFor(lang);
    button.classList.remove("unavailable");
    button.title = browserFallbackAvailable
      ? "使用云端语音，失败时可使用设备同语言语音"
      : "使用云端语音；设备备用语音可能使用默认声音";
  });
}

function setVoiceStatus(message) {
  if (voiceStatus) {
    voiceStatus.textContent = message;
  }
}

function speakWithBrowser(text) {
  if (!canSpeak() || !text) {
    setVoiceStatus("云端语音不可用，当前设备也不支持备用朗读");
    return false;
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
  setVoiceStatus("正在使用设备备用语音朗读");
  return true;
}

function stopSpeaking() {
  speechSequence += 1;
  currentTtsController?.abort();
  currentTtsController = null;

  if (currentAudio) {
    currentAudio.pause();
    currentAudio.src = "";
    currentAudio = null;
  }
  if (currentAudioUrl) {
    URL.revokeObjectURL(currentAudioUrl);
    currentAudioUrl = "";
  }
  if (canSpeak()) {
    window.speechSynthesis.cancel();
  }
  setVoiceStatus("朗读已停止，可重新选择语言或点击朗读");
}

async function speakText(text, button = null) {
  if (!text) {
    return;
  }

  stopSpeaking();
  const requestId = ++speechSequence;
  const controller = new AbortController();
  currentTtsController = controller;
  const originalLabel = button?.textContent || "朗读";
  if (button) {
    button.disabled = true;
    button.textContent = "生成语音中…";
  }
  setVoiceStatus("正在准备云端语音…");

  try {
    const response = await fetch("/api/tts", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, language: selectedVoiceLang }),
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error("cloud tts unavailable");
    }

    const audioBlob = await response.blob();
    if (!audioBlob.size || requestId !== speechSequence) {
      return;
    }

    currentAudioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(currentAudioUrl);
    currentAudio = audio;
    audio.addEventListener("ended", () => {
      if (currentAudio === audio) {
        currentAudio = null;
        URL.revokeObjectURL(currentAudioUrl);
        currentAudioUrl = "";
        setVoiceStatus("云端语音朗读完成");
      }
    }, { once: true });
    audio.addEventListener("error", () => {
      if (currentAudio === audio) {
        currentAudio = null;
        if (currentAudioUrl) {
          URL.revokeObjectURL(currentAudioUrl);
          currentAudioUrl = "";
        }
        speakWithBrowser(text);
      }
    }, { once: true });
    await audio.play();
    setVoiceStatus("正在使用云端语音朗读");
  } catch (error) {
    if (error.name !== "AbortError" && requestId === speechSequence) {
      if (currentAudio) {
        currentAudio.pause();
        currentAudio = null;
      }
      if (currentAudioUrl) {
        URL.revokeObjectURL(currentAudioUrl);
        currentAudioUrl = "";
      }
      speakWithBrowser(text);
    }
  } finally {
    if (currentTtsController === controller) {
      currentTtsController = null;
    }
    if (button) {
      button.disabled = false;
      button.textContent = originalLabel;
    }
  }
}

function createReadButton(text) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "read-button";
  button.textContent = "朗读";
  button.addEventListener("click", () => speakText(text, button));
  return button;
}

function addMessage(role, text, extraClass = "") {
  const row = document.createElement("div");
  row.className = `message-row ${role} ${extraClass}`.trim();

  if (role === "ai" && mascotUrl) {
    const avatar = document.createElement("img");
    avatar.className = "message-avatar";
    avatar.src = mascotUrl;
    avatar.alt = "惠芒go头像";
    row.appendChild(avatar);
  }

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

  if (!message) {
    messageInput.focus();
    return;
  }

  addMessage("user", message);
  const loadingRow = addMessage("ai", "惠芒go正在查找政策信息", "loading");
  setLoading(true);
  scrollChatIntoView();

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
    scrollChatIntoView();

    if (autoRead) {
      speakText(answer);
    }
  } catch (error) {
    const fallback = "暂时无法连接问答服务，请稍后再试。如现场急需咨询，请联系学校老师、县级学生资助管理中心或现场工作人员。";
    loadingRow.remove();
    addMessage("ai", fallback);
    scrollChatIntoView();

    if (autoRead) {
      speakText(fallback);
    }
  } finally {
    setLoading(false);
    messageInput.focus({ preventScroll: true });
  }
}

async function analyzeImage(file) {
  const note = messageInput.value.trim();
  addMessage("user", note ? `请解析这张图片：${note}` : "请解析这张图片。");
  const loadingRow = addMessage("ai", "惠芒go正在认真查看图片", "loading");
  setLoading(true);
  scrollChatIntoView();

  const formData = new FormData();
  formData.append("image", file);
  formData.append("message", note);
  messageInput.value = "";

  try {
    const response = await fetch("/api/analyze-image", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    const answer = data.answer || "暂时没有解析结果，请稍后再试。";
    loadingRow.remove();
    addMessage("ai", answer);
    scrollChatIntoView();

    if (autoRead) {
      speakText(answer);
    }
  } catch (error) {
    const fallback = "暂时无法完成图片解析。请确认图片清晰，或改用文字描述问题。";
    loadingRow.remove();
    addMessage("ai", fallback);
    scrollChatIntoView();

    if (autoRead) {
      speakText(fallback);
    }
  } finally {
    setLoading(false);
    imageInput.value = "";
    messageInput.focus({ preventScroll: true });
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
    voiceOptionButtons.forEach((item) => {
      item.classList.remove("active");
      item.setAttribute("aria-pressed", "false");
    });
    button.classList.add("active");
    button.setAttribute("aria-pressed", "true");
    stopSpeaking();
    setVoiceStatus(`${button.textContent}已选择，云端语音优先`);
  });
});

imageInput.addEventListener("change", () => {
  const file = imageInput.files?.[0];
  if (!file) {
    return;
  }

  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
    addMessage("ai", "目前仅支持 JPG、PNG、WebP 格式图片。");
    imageInput.value = "";
    return;
  }

  if (file.size > 5 * 1024 * 1024) {
    addMessage("ai", "图片过大，请上传 5MB 以内的清晰图片。");
    imageInput.value = "";
    return;
  }

  analyzeImage(file);
});

stopReadButton.addEventListener("click", stopSpeaking);

voiceReadToggle.addEventListener("click", () => {
  autoRead = !autoRead;
  voiceReadToggle.setAttribute("aria-pressed", String(autoRead));
  const stateText = voiceReadToggle.querySelector("em");
  if (stateText) {
    stateText.textContent = autoRead ? "已开启" : "已关闭";
  }

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
  button.textContent = "朗读";
  button.addEventListener("click", () => speakText(text, button));
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
} else {
  updateVoiceButtons();
}
