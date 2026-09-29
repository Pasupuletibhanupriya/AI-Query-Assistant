// ===============================
// Elements
// ===============================

const sendBtn = document.getElementById("sendBtn");
const voiceBtn = document.getElementById("voiceBtn");
const questionInput = document.getElementById("question");
const chatBox = document.getElementById("chatBox");
const newChatBtn = document.getElementById("newChat");
const historyList = document.getElementById("history");
const clearAllBtn = document.getElementById("clearAllBtn");
const shareBtn = document.getElementById("shareBtn");

// Current active session
let currentSessionId = null;

// ===============================
// Marked fallback
// ===============================

function renderMarkdown(text) {
    if (typeof marked !== "undefined" && typeof marked.parse === "function") {
        return marked.parse(text);
    }
    // Simple fallback: escape HTML and preserve line breaks
    const escaped = text
        .replace(/&/g, "&amp;")
        .replace(/</g, "<")
        .replace(/>/g, ">");
    return escaped.replace(/\n/g, "<br>");
}

// ===============================
// Send Message
// ===============================

async function sendMessage() {

    const question = questionInput.value.trim();

    if (question === "") return;

    addUserMessage(question);
    questionInput.value = "";

    // If this is a brand new chat, create a session id
    if (!currentSessionId) {
        currentSessionId = "session_" + Date.now();
    }

    addThinking();

    const formData = new FormData();
    formData.append("question", question);
    formData.append("session_id", currentSessionId);

    try {

        const response = await fetch("/ask", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        removeThinking();

        addBotMessage(data.answer);

        // Refresh sidebar to reflect the new chat
        loadChats();

    } catch (error) {

        removeThinking();

        addBotMessage("❌ Something went wrong. Please try again.");

        console.error(error);
    }
}

// ===============================
// Helper functions
// ===============================

function addUserMessage(text) {
    const div = document.createElement("div");
    div.className = "user";
    div.textContent = text;
    chatBox.appendChild(div);
    scrollToBottom();
}

function addBotMessage(text) {
    const div = document.createElement("div");
    div.className = "bot";
    div.innerHTML = renderMarkdown(text);
    chatBox.appendChild(div);
    scrollToBottom();
}

function addThinking() {
    const div = document.createElement("div");
    div.className = "bot";
    div.id = "thinking";
    div.textContent = "🤖 Thinking...";
    chatBox.appendChild(div);
    scrollToBottom();
}

function removeThinking() {
    const thinking = document.getElementById("thinking");
    if (thinking) {
        thinking.remove();
    }
}

function scrollToBottom() {
    chatBox.scrollTop = chatBox.scrollHeight;
}

function truncate(text, max = 40) {
    if (!text) return "New Chat";
    const clean = text.replace(/\s+/g, " ").trim();
    return clean.length > max ? clean.slice(0, max) + "…" : clean;
}

function formatTime(ts) {
    if (!ts) return "";
    // SQLite timestamp like "2026-08-07 18:04:23" - replace space with T for reliable parsing
    const normalized = String(ts).replace(" ", "T");
    const date = new Date(normalized);
    if (isNaN(date.getTime())) return "";
    const now = new Date();
    const sameDay = date.toDateString() === now.toDateString();
    if (sameDay) {
        return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

// ===============================
// Chat History (Sidebar)
// ===============================

async function loadChats() {
    try {
        const response = await fetch("/api/chats");
        const data = await response.json();
        renderChatList(data.chats || []);
    } catch (error) {
        console.error("Error loading chats:", error);
    }
}

function renderChatList(chats) {
    historyList.innerHTML = "";

    if (!chats.length) {
        historyList.innerHTML = `
            <li class="empty-state">
                <i class="fa-regular fa-comment-dots"></i>
                No recent chats yet.
            </li>
        `;
        return;
    }

    chats.forEach(chat => {
        const li = document.createElement("li");
        li.className = "chat-item";
        li.dataset.sessionId = chat.session_id;
        if (chat.session_id === currentSessionId) {
            li.classList.add("active");
        }

        li.innerHTML = `
            <div class="chat-info">
                <div class="chat-title">${truncate(chat.title)}</div>
                <div class="chat-time">${formatTime(chat.time)}</div>
            </div>
            <button class="delete-chat" title="Delete this chat">
                <i class="fa-solid fa-trash"></i>
            </button>
        `;

        // Click chat to load conversation
        li.addEventListener("click", function (e) {
            if (e.target.closest(".delete-chat")) return;
            openChat(chat.session_id);
        });

        // Delete button
        const deleteBtn = li.querySelector(".delete-chat");
        deleteBtn.addEventListener("click", function (e) {
            e.stopPropagation();
            deleteChat(chat.session_id, li);
        });

        historyList.appendChild(li);
    });
}

async function openChat(sessionId) {
    currentSessionId = sessionId;

    // Highlight active
    document.querySelectorAll(".chat-item").forEach(item => {
        item.classList.toggle("active", item.dataset.sessionId === sessionId);
    });

    try {
        const response = await fetch(`/api/chats/${sessionId}`);
        const data = await response.json();

        chatBox.innerHTML = "";

        (data.messages || []).forEach(msg => {
            addUserMessage(msg.question);
            addBotMessage(msg.answer);
        });

        if (!data.messages || data.messages.length === 0) {
            chatBox.innerHTML = `
                <div class="bot">
                    👋 Welcome back!
                    <br><br>
                    This conversation is empty.
                </div>
            `;
        }

    } catch (error) {
        console.error("Error loading conversation:", error);
    }
}

async function deleteChat(sessionId, li) {
    if (!confirm("Delete this chat?")) return;

    try {
        const response = await fetch(`/api/chats/${sessionId}`, {
            method: "DELETE"
        });
        const data = await response.json();

        if (data.success) {
            // Remove from sidebar instantly
            li.remove();

            // If the deleted chat was active, reset to a new chat
            if (currentSessionId === sessionId) {
                currentSessionId = null;
                startNewChat();
            }

            // Update empty state
            if (historyList.children.length === 0) {
                historyList.innerHTML = `
                    <li class="empty-state">
                        <i class="fa-regular fa-comment-dots"></i>
                        No recent chats yet.
                    </li>
                `;
            }
        }
    } catch (error) {
        console.error("Error deleting chat:", error);
    }
}

async function clearAllChats() {
    if (!confirm("Are you sure you want to delete all chats?")) return;

    try {
        const response = await fetch("/api/chats", {
            method: "DELETE"
        });
        const data = await response.json();

        if (data.success) {
            currentSessionId = null;
            startNewChat();
            loadChats();
        }
    } catch (error) {
        console.error("Error clearing chats:", error);
    }
}

// ===============================
// New Chat
// ===============================

function startNewChat() {
    currentSessionId = null;
    chatBox.innerHTML = `
        <div class="bot">
            👋 Hello! Welcome to Meta AI.
            <br><br>
            How can I help you today?
        </div>
    `;
    questionInput.value = "";
    questionInput.focus();

    // Remove active highlight
    document.querySelectorAll(".chat-item").forEach(item => {
        item.classList.remove("active");
    });
}

// ===============================
// Voice Input (Web Speech API)
// ===============================

let recognition = null;
let isListening = false;

function initVoice() {
    if (!("webkitSpeechRecognition" in window) && !("SpeechRecognition" in window)) {
        voiceBtn.title = "Voice input not supported in this browser";
        voiceBtn.style.opacity = "0.5";
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.continuous = false;

    recognition.onstart = function () {
        isListening = true;
        voiceBtn.classList.add("listening");
    };

    recognition.onresult = function (event) {
        const transcript = event.results[0][0].transcript;
        questionInput.value = transcript;
    };

    recognition.onerror = function () {
        stopListening();
    };

    recognition.onend = function () {
        stopListening();
    };
}

function stopListening() {
    isListening = false;
    voiceBtn.classList.remove("listening");
}

if (voiceBtn) {
    voiceBtn.addEventListener("click", function () {
        if (!recognition) {
            initVoice();
        }
        if (!recognition) return;

        if (isListening) {
            recognition.stop();
            stopListening();
        } else {
            try {
                recognition.start();
            } catch (e) {
                // Already started
            }
        }
    });
}

// ===============================
// Share Conversation
// ===============================

function showToast(message) {
    // Remove existing toast
    const oldToast = document.getElementById("toast");
    if (oldToast) oldToast.remove();

    const toast = document.createElement("div");
    toast.id = "toast";
    toast.className = "toast";
    toast.textContent = message;
    document.body.appendChild(toast);

    // Auto-dismiss
    setTimeout(() => {
        toast.classList.add("show");
    }, 10);
    setTimeout(() => {
        toast.classList.remove("show");
        setTimeout(() => toast.remove(), 300);
    }, 2500);
}

function getConversationText() {
    // Collect user + bot messages from the DOM
    const messages = [];
    const nodes = chatBox.querySelectorAll(".user, .bot");

    nodes.forEach(node => {
        if (node.id === "thinking") return;

        const isUser = node.classList.contains("user");
        const raw = node.textContent.trim();
        if (!raw) return;

        const prefix = isUser ? "You" : "Meta AI";
        messages.push(`${prefix}: ${raw}`);
    });

    return messages.join("\n\n");
}

async function shareConversation() {
    const text = getConversationText();

    if (!text) {
        showToast("Nothing to share yet.");
        return;
    }

    const shareText = "🤖 Meta AI Conversation\n" + "=".repeat(30) + "\n\n" + text;

    try {
        if (navigator.clipboard && window.isSecureContext) {
            await navigator.clipboard.writeText(shareText);
        } else {
            // Fallback for non-secure contexts
            const textarea = document.createElement("textarea");
            textarea.value = shareText;
            textarea.style.position = "fixed";
            textarea.style.opacity = "0";
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand("copy");
            textarea.remove();
        }
        showToast("✅ Conversation copied to clipboard!");
    } catch (error) {
        console.error("Share failed:", error);
        showToast("❌ Could not copy conversation.");
    }
}

if (shareBtn) {
    shareBtn.addEventListener("click", shareConversation);
}

// ===============================
// Events
// ===============================

sendBtn.addEventListener("click", sendMessage);

questionInput.addEventListener("keypress", function (event) {
    if (event.key === "Enter") {
        sendMessage();
    }
});

if (newChatBtn) {
    newChatBtn.addEventListener("click", startNewChat);
}

if (clearAllBtn) {
    clearAllBtn.addEventListener("click", clearAllChats);
}

// ===============================
// Init
// ===============================

// Robust init: works whether script loads at end of body or head.
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadChats);
} else {
    loadChats();
}
async function loadHistory() {

    try {

        const response = await fetch("/history");

        const chats = await response.json();

        const history = document.getElementById("history");

        history.innerHTML = "";

        if (chats.length === 0) {

            history.innerHTML = `
                <li>No recent chats</li>
            `;

            return;
        }

        chats.forEach(chat => {

            const li = document.createElement("li");

            li.textContent = chat.question;

            li.onclick = function () {

                chatBox.innerHTML = `
                    <div class="user">
                        ${chat.question}
                    </div>

                    <div class="bot">
                        ${chat.answer}
                    </div>
                `;

                chatBox.scrollTop = chatBox.scrollHeight;
            };

            history.appendChild(li);

        });

    } catch (error) {

        console.error("History Error:", error);

    }
}

loadHistory();
