// State Variables
let currentSessionId = "";
let currentCustomer = { id: null, name: "Mock Customer", mobile: "9999999999" };
let customersList = [];

// Initialize Page
document.addEventListener("DOMContentLoaded", () => {
    // Generate initial session ID
    createNewSession();
    
    // Fetch customers list
    fetchCustomers();
    
    // Fetch active sessions list
    fetchSessions();

    // Event Listeners
    document.getElementById("chat-form").addEventListener("submit", handleChatSubmit);
    document.getElementById("new-chat-btn").addEventListener("new-chat", () => createNewSession(true));
    document.getElementById("new-chat-btn").addEventListener("click", () => createNewSession(true));
    document.getElementById("clear-chat-btn").addEventListener("click", clearCurrentChatHistory);
    document.getElementById("refresh-customers-btn").addEventListener("click", fetchCustomers);
    document.getElementById("customer-select").addEventListener("change", handleCustomerChange);
    document.getElementById("clear-error-btn").addEventListener("click", hideErrorPanel);
});

// Generate a random Session ID
function generateSessionId() {
    return "TEST-SESSION-" + Math.random().toString(36).substring(2, 9).toUpperCase();
}

// Create New Session
function createNewSession(clearUI = true) {
    currentSessionId = generateSessionId();
    document.getElementById("meta-session-id").textContent = currentSessionId;
    
    if (clearUI) {
        const chatMessages = document.getElementById("chat-messages");
        chatMessages.innerHTML = `
            <div class="message system-msg">
                <div class="message-content">
                    🔒 Secure testing environment initialized. All actions are simulated and strictly read-only.
                </div>
            </div>
        `;
        clearMetadataPanel();
        hideErrorPanel();
    }
    
    // Refresh sessions list
    fetchSessions();
}

// Fetch Customers List from Local MySQL Database
async function fetchCustomers() {
    try {
        const res = await fetch("/api/customers");
        const data = await res.json();
        
        if (res.status === 500 || data.status === "error") {
            showError(data);
            return;
        }
        
        customersList = data.customers || [];
        populateCustomerSelect();
    } catch (err) {
        showError({
            error_class: "FetchError",
            error_message: "Failed to connect to backend customers API",
            traceback: err.stack || err.toString()
        });
    }
}

// Populate the customer dropdown list
function populateCustomerSelect() {
    const select = document.getElementById("customer-select");
    
    // Keep Mock Customer at the top
    select.innerHTML = `<option value="MOCK">👤 Mock Customer (Rahul Test - 9999999999)</option>`;
    
    customersList.forEach(cust => {
        const option = document.createElement("option");
        option.value = cust.id;
        option.textContent = `💼 ${cust.name} (${cust.mobile}) [${cust.origin_sector || 'Travel'}]`;
        select.appendChild(option);
    });
}

// Handle Customer Change from Selector
function handleCustomerChange(e) {
    const val = e.target.value;
    
    if (val === "MOCK") {
        currentCustomer = { id: null, name: "Mock Customer", mobile: "9999999999" };
    } else {
        const selected = customersList.find(c => c.id == val);
        if (selected) {
            currentCustomer = {
                id: selected.id,
                name: selected.name,
                mobile: selected.mobile
            };
        }
    }
    
    // Update Chat Header
    document.getElementById("current-customer-name").textContent = currentCustomer.name;
    document.getElementById("current-customer-phone").textContent = "+91 " + currentCustomer.mobile;
    
    // Append context-change message in chat
    appendSystemMessage(`Target customer switched to: ${currentCustomer.name} (${currentCustomer.mobile})`);
    
    // Clear last metadata stats
    clearMetadataPanel();
}

// Fetch active sessions list
async function fetchSessions() {
    try {
        const res = await fetch("/api/sessions");
        const data = await res.json();
        if (data.status === "success") {
            renderSessionsList(data.sessions);
        }
    } catch (err) {
        console.error("Failed to load sessions", err);
    }
}

// Render sessions in left sidebar list
function renderSessionsList(sessions) {
    const container = document.getElementById("sessions-list");
    container.innerHTML = "";
    
    if (!sessions || sessions.length === 0) {
        container.innerHTML = `<div style="color: var(--color-text-muted); text-align: center; padding: 12px; font-size: 12px;">No active sessions</div>`;
        return;
    }
    
    sessions.forEach(sid => {
        const div = document.createElement("div");
        div.className = `session-item ${sid === currentSessionId ? 'active' : ''}`;
        
        // Shorten name of session for display
        const displayId = sid.replace("TEST-SESSION-", "#");
        
        div.innerHTML = `
            <span><i class="fa-solid fa-comment-dots"></i> ${displayId}</span>
            <button class="session-delete-btn" title="Delete Session"><i class="fa-solid fa-times"></i></button>
        `;
        
        // Click item to switch session
        div.addEventListener("click", (e) => {
            if (e.target.closest(".session-delete-btn")) return; // Don't trigger switch on delete click
            switchSession(sid);
        });
        
        // Delete button click
        div.querySelector(".session-delete-btn").addEventListener("click", () => {
            deleteSession(sid);
        });
        
        container.appendChild(div);
    });
}

// Switch Session
function switchSession(sid) {
    currentSessionId = sid;
    document.getElementById("meta-session-id").textContent = currentSessionId;
    
    // Clean chat logs but reload history would be better. We'll simply alert session switched
    // In our simplified in-memory tool, switching clears visual panel and alerts developer
    const chatMessages = document.getElementById("chat-messages");
    chatMessages.innerHTML = `
        <div class="message system-msg">
            <div class="message-content">
                🔄 Switched to session: ${currentSessionId}. Previous messages stored in AgentCore memory.
            </div>
        </div>
    `;
    clearMetadataPanel();
    hideErrorPanel();
    fetchSessions();
}

// Delete / Clear session from backend
async function deleteSession(sid) {
    try {
        const res = await fetch("/api/sessions/clear", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ session_id: sid })
        });
        const data = await res.json();
        if (data.status === "success") {
            if (sid === currentSessionId) {
                createNewSession(true);
            } else {
                fetchSessions();
            }
        }
    } catch (err) {
        console.error("Failed to delete session", err);
    }
}

// Clear current session memory & UI chat history
async function clearCurrentChatHistory() {
    if (confirm("Are you sure you want to clear this conversation history?")) {
        await deleteSession(currentSessionId);
    }
}

// Append a message to the Chat View Panel
function appendMessage(sender, text, timeStr, audioUrl = null, voiceMode = false) {
    const chatMessages = document.getElementById("chat-messages");
    const msgDiv = document.createElement("div");
    msgDiv.className = `message ${sender} ${(audioUrl || voiceMode) ? 'voice-note' : ''}`;
    
    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";
    
    if (audioUrl || voiceMode) {
        const randId = Math.random().toString(36).substring(2, 9);
        const fillId = `fill_${randId}`;
        
        contentDiv.innerHTML = `
            <div class="voice-player">
                <button class="voice-play-btn" onclick="toggleVoicePlayback(this, '${audioUrl || ''}', '${fillId}')">
                    <i class="fa-solid fa-play"></i>
                </button>
                <div class="voice-waveform-container">
                    <div class="voice-progress-bar">
                        <div class="voice-progress-fill" id="${fillId}" style="width: 0%;"></div>
                    </div>
                </div>
                <span class="voice-duration">0:00</span>
            </div>
            <details style="margin-top: 6px; font-size: 11px; color: var(--color-text-muted);">
                <summary style="cursor: pointer; outline: none; user-select: none;">Show Transcript</summary>
                <p style="margin-top: 4px; line-height: 1.4; white-space: pre-wrap;">${text}</p>
            </details>
            <div class="message-meta">
                ${timeStr} <i class="fa-solid fa-microphone" style="color: #53bdeb; margin-left: 4px;"></i>
            </div>
        `;
    } else {
        contentDiv.textContent = text;
        
        const metaDiv = document.createElement("div");
        metaDiv.className = "message-meta";
        metaDiv.innerHTML = `${timeStr} ${sender === 'user' ? '<i class="fa-solid fa-check-double"></i>' : ''}`;
        
        let voiceBtn = null;
        if (sender === "ai") {
            voiceBtn = document.createElement("button");
            voiceBtn.className = "play-voice-btn";
            voiceBtn.innerHTML = `<i class="fa-solid fa-volume-low"></i> Listen`;
            voiceBtn.onclick = () => playVoiceMessage(text, voiceBtn);
            contentDiv.appendChild(voiceBtn);
        }
        
        contentDiv.appendChild(metaDiv);
    }
    
    msgDiv.appendChild(contentDiv);
    chatMessages.appendChild(msgDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Text to speech playback handler
async function playVoiceMessage(text, buttonElement) {
    if (buttonElement.classList.contains("loading")) return;
    
    buttonElement.classList.add("loading");
    buttonElement.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Synthesizing...`;
    
    try {
        const res = await fetch("/api/tts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                text: text,
                session_id: currentSessionId
            })
        });
        
        const data = await res.json();
        
        if (res.status === 500 || data.status === "error") {
            // If Azure is not configured, fallback to client-side native browser TTS
            if (data.error_message && data.error_message.includes("AZURE_SPEECH_KEY")) {
                console.warn("Azure Speech credentials not configured. Falling back to native SpeechSynthesis.");
                
                const baseText = data.processed_text || text;
                const cleanText = baseText.replace(/[*_`~]/g, "");
                // Split 5-10 digit numbers (train numbers, PNRs, mobile numbers) with commas and spaces so they are read digit-by-digit
                const spokenText = cleanText.replace(/(\d{5,10})/g, (match) => {
                    return match.split("").join(", ");
                });
                const utterance = new SpeechSynthesisUtterance(spokenText);
                
                // Try to find a realistic female Hindi voice in browser fallback
                const voices = window.speechSynthesis.getVoices();
                let hiVoice = voices.find(v => v.lang.startsWith("hi") && 
                    (v.name.toLowerCase().includes("female") || 
                     v.name.toLowerCase().includes("kalpana") || 
                     v.name.toLowerCase().includes("google") || 
                     v.name.toLowerCase().includes("natural")));
                
                if (!hiVoice) {
                    hiVoice = voices.find(v => v.lang.startsWith("hi"));
                }
                
                if (hiVoice) {
                    utterance.voice = hiVoice;
                }
                utterance.lang = "hi-IN";
                utterance.rate = 1.0; // Default speech rate (10% slower than the previous 1.10 setting)
                
                buttonElement.innerHTML = `<i class="fa-solid fa-volume-high"></i> Playing (Browser)`;
                buttonElement.classList.remove("loading");
                
                window.speechSynthesis.speak(utterance);
                
                utterance.onend = () => {
                    buttonElement.innerHTML = `<i class="fa-solid fa-volume-low"></i> Listen`;
                };
                
                // Print a friendly notice to the developer timeline log
                const container = document.getElementById("timeline-log");
                const div = document.createElement("div");
                div.className = "timeline-item";
                div.innerHTML = `
                    <span class="timeline-time" style="color: var(--color-warning)">[TTS]</span>
                    <span class="timeline-event" style="color: var(--color-warning)">Azure credentials missing. Using native SpeechSynthesis fallback.</span>
                `;
                container.appendChild(div);
                container.scrollTop = container.scrollHeight;
                return;
            }
            
            buttonElement.classList.remove("loading");
            buttonElement.innerHTML = `<i class="fa-solid fa-triangle-exclamation"></i> Error`;
            showError(data);
            return;
        }
        
        const audioUrl = data.audio_url;
        
        // Play Audio in browser
        const audio = new Audio(audioUrl);
        audio.play();
        
        buttonElement.classList.remove("loading");
        buttonElement.innerHTML = `<i class="fa-solid fa-volume-high"></i> Playing`;
        
        audio.onended = () => {
            buttonElement.innerHTML = `<i class="fa-solid fa-volume-low"></i> Listen`;
        };
    } catch (err) {
        buttonElement.classList.remove("loading");
        buttonElement.innerHTML = `<i class="fa-solid fa-circle-exclamation"></i> Failed`;
        showError({
            error_class: "AudioPlaybackError",
            error_message: "Could not generate or stream TTS audio from Azure Speech services.",
            traceback: err.stack || err.toString()
        });
    }
}

let currentUtterance = null;
let playInterval = null;
let activeAudio = null;
let activePlayBtn = null;
let activeProgressFill = null;

function toggleVoicePlayback(button, audioUrl, progressFillId) {
    const playIcon = button.querySelector("i");
    
    // Check if it's the browser fallback player (no Azure audio URL)
    if (!audioUrl || audioUrl === "null" || audioUrl === "") {
        const text = button.closest('.message-content').querySelector('details p').textContent;
        const progressFill = document.getElementById(progressFillId);
        
        // If speaking, toggle pause/resume
        if (window.speechSynthesis.speaking && currentUtterance) {
            if (window.speechSynthesis.paused) {
                window.speechSynthesis.resume();
                playIcon.className = "fa-solid fa-pause";
            } else {
                window.speechSynthesis.pause();
                playIcon.className = "fa-solid fa-play";
            }
            return;
        }
        
        // Cancel previous speech
        window.speechSynthesis.cancel();
        if (playInterval) clearInterval(playInterval);
        
        const cleanText = text.replace(/[*_`~]/g, "");
        const spokenText = cleanText.replace(/(\d{5,10})/g, (match) => {
            return match.split("").join(", ");
        });
        
        const utterance = new SpeechSynthesisUtterance(spokenText);
        
        // Search Hindi female voice
        const voices = window.speechSynthesis.getVoices();
        let hiVoice = voices.find(v => v.lang.startsWith("hi") && 
            (v.name.toLowerCase().includes("female") || 
             v.name.toLowerCase().includes("kalpana") || 
             v.name.toLowerCase().includes("google") || 
             v.name.toLowerCase().includes("natural")));
        if (!hiVoice) hiVoice = voices.find(v => v.lang.startsWith("hi"));
        if (hiVoice) utterance.voice = hiVoice;
        
        utterance.lang = "hi-IN";
        utterance.rate = 1.0;
        
        currentUtterance = utterance;
        
        // Estimate duration (2.1 words per second)
        const wordCount = spokenText.split(/\s+/).length;
        const estimatedDuration = (wordCount / 2.1) * 1000;
        let startTime = Date.now();
        let elapsed = 0;
        
        window.speechSynthesis.speak(utterance);
        playIcon.className = "fa-solid fa-pause";
        
        playInterval = setInterval(() => {
            if (window.speechSynthesis.paused) {
                startTime = Date.now() - elapsed;
                return;
            }
            
            elapsed = Date.now() - startTime;
            let percent = (elapsed / estimatedDuration) * 100;
            if (percent > 99) percent = 99;
            progressFill.style.width = `${percent}%`;
            
            const durationSpan = button.closest(".voice-player").querySelector(".voice-duration");
            const sec = Math.floor((elapsed / 1000) % 60);
            const min = Math.floor(elapsed / 60000);
            durationSpan.textContent = `${min}:${sec < 10 ? '0' : ''}${sec}`;
        }, 100);
        
        const resetPlayer = () => {
            clearInterval(playInterval);
            playIcon.className = "fa-solid fa-play";
            progressFill.style.width = "0%";
            button.closest(".voice-player").querySelector(".voice-duration").textContent = "0:00";
            currentUtterance = null;
        };
        
        utterance.onend = resetPlayer;
        utterance.onerror = resetPlayer;
        return;
    }
    
    // Toggle play/pause if it is the same audio
    if (activeAudio && activeAudio.src.endsWith(audioUrl)) {
        if (activeAudio.paused) {
            activeAudio.play();
            playIcon.className = "fa-solid fa-pause";
        } else {
            activeAudio.pause();
            playIcon.className = "fa-solid fa-play";
        }
        return;
    }
    
    // Stop currently playing audio if different
    if (activeAudio) {
        activeAudio.pause();
        if (activePlayBtn) activePlayBtn.querySelector("i").className = "fa-solid fa-play";
        if (activeProgressFill) activeProgressFill.style.width = "0%";
    }
    
    const audio = new Audio(audioUrl);
    activeAudio = audio;
    activePlayBtn = button;
    
    const progressFill = document.getElementById(progressFillId);
    activeProgressFill = progressFill;
    
    audio.play();
    playIcon.className = "fa-solid fa-pause";
    
    audio.ontimeupdate = () => {
        if (audio.duration) {
            const percent = (audio.currentTime / audio.duration) * 100;
            progressFill.style.width = `${percent}%`;
            
            const bubble = button.closest(".voice-player");
            if (bubble) {
                const durationSpan = bubble.querySelector(".voice-duration");
                const currentSec = Math.floor(audio.currentTime % 60);
                const currentMin = Math.floor(audio.currentTime / 60);
                durationSpan.textContent = `${currentMin}:${currentSec < 10 ? '0' : ''}${currentSec}`;
            }
        }
    };
    
    audio.onended = () => {
        playIcon.className = "fa-solid fa-play";
        progressFill.style.width = "0%";
        activeAudio = null;
        activePlayBtn = null;
        activeProgressFill = null;
        
        const bubble = button.closest(".voice-player");
        if (bubble) {
            bubble.querySelector(".voice-duration").textContent = "0:00";
        }
    };
}

// Append System notification to chat view
function appendSystemMessage(text) {
    const chatMessages = document.getElementById("chat-messages");
    const msgDiv = document.createElement("div");
    msgDiv.className = "message system-msg";
    
    const contentDiv = document.createElement("div");
    contentDiv.className = "message-content";
    contentDiv.textContent = text;
    
    msgDiv.appendChild(contentDiv);
    chatMessages.appendChild(msgDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Form Submission - Send Chat message
async function handleChatSubmit(e) {
    e.preventDefault();
    
    const input = document.getElementById("message-input");
    const messageText = input.value.trim();
    if (!messageText) return;
    
    // Add user message to UI
    const now = new Date();
    const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    appendMessage("user", messageText, timeStr);
    
    // Clear and disable input
    input.value = "";
    input.disabled = true;
    document.getElementById("send-btn").disabled = true;
    
    // Show typing indicator
    const typingIndicator = document.getElementById("typing-indicator");
    typingIndicator.classList.remove("hidden");
    
    hideErrorPanel();
    
    try {
        // Send request to API
        const payload = {
            session_id: currentSessionId,
            message: messageText,
            customer_id: currentCustomer.id
        };
        
        // If we are using a real customer, we prepend a database mapping message in prompt context
        // Server will receive the payload and handle customer loading
        const response = await fetch("/api/chat", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        const data = await response.json();
        
        // Hide typing indicator
        typingIndicator.classList.add("hidden");
        
        if (response.status === 500 || data.status === "error") {
            // Propagate server errors directly to user UI and error logging panel
            appendSystemMessage("⚠️ An error occurred in the Agent pipeline. Check Developer Monitor.");
            showError(data);
        } else {
            // Success response
            const agentResponse = data.data.response;
            const meta = data.data;
            
            // Append AI response (pass audio_url if generated)
            appendMessage("ai", agentResponse, new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }), meta.audio_url);
            
            // If voice mode is active but no Azure audio file was generated, fall back to auto-triggering browser Speech
            if (meta.voice_mode && !meta.audio_url) {
                const msgList = document.getElementById("chat-messages").getElementsByClassName("message ai");
                if (msgList.length > 0) {
                    const lastMsg = msgList[msgList.length - 1];
                    const voiceBtn = lastMsg.querySelector(".play-voice-btn");
                    if (voiceBtn) {
                        playVoiceMessage(agentResponse, voiceBtn);
                    }
                }
            }
            
            // Populate Developer Pane Meta
            document.getElementById("res-provider").textContent = meta.provider;
            document.getElementById("res-model").textContent = meta.model;
            document.getElementById("res-time").textContent = `${meta.response_time_ms.toFixed(0)} ms`;
            document.getElementById("res-fallback").textContent = meta.fallback_used ? "Yes (⚠️)" : "No";
            
            if (meta.fallback_used) {
                document.getElementById("res-fallback").style.color = "var(--color-warning)";
            } else {
                document.getElementById("res-fallback").style.color = "var(--color-primary)";
            }
            
            // Tools formatting
            const toolsText = meta.called_tools && meta.called_tools.length > 0
                ? meta.called_tools.join(", ")
                : "None";
            document.getElementById("res-tools").textContent = toolsText;
            
            // Timeline rendering
            renderTimeline(meta.timeline);
        }
    } catch (err) {
        typingIndicator.classList.add("hidden");
        appendSystemMessage("⚠️ Connection failure. Backend server is unreachable.");
        showError({
            error_class: "NetworkConnectionError",
            error_message: "FastAPI server could not be reached. Ensure uvicorn is running.",
            traceback: err.stack || err.toString()
        });
    } finally {
        // Re-enable inputs
        input.disabled = false;
        document.getElementById("send-btn").disabled = false;
        input.focus();
    }
}

// Clear metadata panel fields
function clearMetadataPanel() {
    document.getElementById("res-provider").textContent = "-";
    document.getElementById("res-model").textContent = "-";
    document.getElementById("res-time").textContent = "-";
    document.getElementById("res-fallback").textContent = "-";
    document.getElementById("res-fallback").style.color = "inherit";
    document.getElementById("res-tools").textContent = "-";
    document.getElementById("timeline-log").innerHTML = `<div class="timeline-empty">Send a message to monitor routing activities.</div>`;
}

// Render timeline items
function renderTimeline(timeline) {
    const container = document.getElementById("timeline-log");
    container.innerHTML = "";
    
    if (!timeline || timeline.length === 0) {
        container.innerHTML = `<div class="timeline-empty">No timeline recorded.</div>`;
        return;
    }
    
    timeline.forEach(item => {
        const div = document.createElement("div");
        div.className = "timeline-item";
        div.innerHTML = `
            <span class="timeline-time">[${item.timestamp}]</span>
            <span class="timeline-event">${item.event}</span>
        `;
        container.appendChild(div);
    });
    
    // Scroll to bottom of timeline
    container.scrollTop = container.scrollHeight;
}

// Display error trace (Propagate raw errors)
function showError(errData) {
    const errSection = document.getElementById("error-section");
    errSection.classList.remove("hidden");
    
    document.getElementById("error-class").textContent = errData.error_class || "RuntimeError";
    document.getElementById("error-message").textContent = errData.error_message || "Unknown error occurred.";
    document.getElementById("error-traceback").textContent = errData.traceback || "No traceback available.";
    
    // Append error description to timeline log
    const container = document.getElementById("timeline-log");
    const div = document.createElement("div");
    div.className = "timeline-item";
    div.innerHTML = `
        <span class="timeline-time" style="color: var(--color-danger)">[ERROR]</span>
        <span class="timeline-event" style="color: var(--color-danger)">Pipeline failed with ${errData.error_class}: ${errData.error_message}</span>
    `;
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

// Hide developer error panel
function hideErrorPanel() {
    document.getElementById("error-section").classList.add("hidden");
}
