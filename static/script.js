const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const chatMessages = document.querySelector("#chatMessages");
const sendButton = document.querySelector("#sendButton");
const quickButtons = document.querySelectorAll(".quick-question");

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addMessage(role, text, extraClass = "") {
  const row = document.createElement("div");
  row.className = `message-row ${role} ${extraClass}`.trim();

  const avatar = document.createElement("div");
  avatar.className = "avatar";
  avatar.setAttribute("aria-hidden", "true");
  avatar.textContent = role === "user" ? "我" : "惠";

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text;

  row.appendChild(avatar);
  row.appendChild(bubble);
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
    loadingRow.remove();
    addMessage("ai", data.answer || "暂时没有收到回答，请稍后再试。");
  } catch (error) {
    loadingRow.remove();
    addMessage("ai", "暂时无法连接问答服务，请稍后再试。如现场急需咨询，请联系学校老师、县级学生资助管理中心或现场工作人员。");
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
    sendMessage(button.textContent);
  });
});
