import path from 'path';
import { fileURLToPath } from 'url';
import fs from 'fs';
import dns from 'dns';
import os from 'os';
import { execSync } from 'child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Force Puppeteer to use the local project cache folder only on Linux (e.g. Render/Debian)
if (process.platform === 'linux') {
    process.env.PUPPETEER_CACHE_DIR = path.join(__dirname, '.puppeteer_cache');
}

import dotenv from 'dotenv';
dotenv.config({ path: path.join(__dirname, '../.env') });

// Dynamic imports to prevent ESM hoisting from importing puppeteer before process.env is set
const { default: express } = await import('express');
const { default: cors } = await import('cors');
const { default: pkg } = await import('whatsapp-web.js');
const { Client, LocalAuth, MessageMedia } = pkg;
const { default: qrcode } = await import('qrcode-terminal');
const { default: puppeteer } = await import('puppeteer-extra');
const { default: cleanPuppeteer } = await import('puppeteer');
const { default: StealthPlugin } = await import('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());



const { default: QRCode } = await import('qrcode');

const app  = express();
const PORT = process.env.PORT || 3333; // Default port
const HOST = process.env.HOST || '0.0.0.0';

app.use(cors({ origin: '*' }));
app.use(express.json({ limit: '50mb' }));

// ═══════════════════════════════════════════════════════════
// WhatsApp CONFIG & Client Setup
// ═══════════════════════════════════════════════════════════
let siteBase = process.env.SITE_BASE_URL || 'http://localhost/Office%20Accounts/public';
if (siteBase.includes('accounts.shreeshubhtravel.com') && !siteBase.includes('/public')) {
    siteBase = siteBase.replace(/\/+$/, '') + '/public';
}

const WA_CONFIG = {
    SECRET_TOKEN : 'YTSK_WA_Secret_2024',
    PDF_TOKEN    : 'YTSK_PDF_Token_2024_$ecure',
    SITE_BASE_URL: siteBase,
    RECEIPT_PATH : '/print-debtor-bill.php',
    AGENT_API_URL: process.env.AGENT_API_URL || 'http://127.0.0.1:8000/api/chat'
};
const isLinux = process.platform === 'linux';
let CHROME_PATH = process.env.PUPPETEER_EXECUTABLE_PATH || null;

if (!CHROME_PATH && isLinux) {
    const fs = await import('fs');
    const commonPaths = [
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chrome',
        '/usr/bin/google-chrome-unstable',
        path.join(process.env.PUPPETEER_CACHE_DIR || './.puppeteer_cache', 'chrome', 'linux-146.0.7680.31', 'chrome-linux64', 'chrome')
    ];
    for (const p of commonPaths) {
        if (fs.existsSync(p)) {
            CHROME_PATH = p;
            break;
        }
    }
}
const puppeteerConfig = {
    launcher: puppeteer,
    headless: true,
    timeout: 120000,
    args: [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-dev-shm-usage',
        '--disable-accelerated-2d-canvas',
        '--disable-gpu',
        '--window-size=800,600',
        '--disable-extensions',
        '--disable-component-update',
        '--disable-default-apps',
        '--disable-speech-api',
        '--disable-background-networking',
        '--disable-sync',
        '--mute-audio',
        '--no-default-browser-check',
        '--no-first-run',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding',
        '--disable-ipc-flooding-protection',
        '--disable-features=AudioServiceOutOfProcess,IsolateOrigins,site-per-process',
        '--ignore-certificate-errors', // Ignore SSL verification errors
        '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
    ]
};

if (CHROME_PATH) {
    puppeteerConfig.executablePath = CHROME_PATH;
}

let waClient = null;
let isWaReady = false;
let currentQrDataUrl = null;

// Concurrency Queue Settings
const activeSessions = new Map(); // key: cleanMobile, value: lastActiveTimestamp
const waitingQueue = [];         // FIFO Queue of objects: { msg, cleanMobile, userMessage }
const SESSION_TIMEOUT = 2 * 60 * 1000; // 2 minutes session timeout limit

// Helper to promote the next customer from the FIFO queue
async function promoteNextCustomer() {
    if (waitingQueue.length === 0) return;
    if (activeSessions.size >= 4) return;
    
    const nextItem = waitingQueue.shift();
    const { msg, cleanMobile, userMessage } = nextItem;
    
    console.log(`[Queue Manager] Promoting customer ${cleanMobile} from queue to active slot.`);
    activeSessions.set(cleanMobile, Date.now());
    
    try {
        await msg.reply("Thank you for waiting. We are now processing your request...");
        // Process the message through the AI Agent
        await processAgentQuery(msg, cleanMobile, userMessage);
    } catch (err) {
        console.error(`[Queue Manager Error] Failed to process promoted customer ${cleanMobile}:`, err.message);
    }
}

// Background cleanup loop for inactive sessions (runs every 10 seconds)
setInterval(async () => {
    const now = Date.now();
    let slotOpened = false;
    
    for (const [mobile, lastActive] of activeSessions.entries()) {
        if (now - lastActive > SESSION_TIMEOUT) {
            activeSessions.delete(mobile);
            console.log(`[Queue Manager] Active session for ${mobile} expired due to 2-minute inactivity.`);
            slotOpened = true;
        }
    }
    
    if (slotOpened) {
        await promoteNextCustomer();
    }
}, 10000); // 10 seconds check cycle

// Helper to process user query using the Python AI agent Beck
async function processAgentQuery(msg, cleanMobile, userMessage) {
    try {
        // Forward query to the Python Agent API
        const response = await fetch(WA_CONFIG.AGENT_API_URL, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                session_id: cleanMobile,
                message: userMessage,
                customer_id: cleanMobile // Mobile acts as customer_id for direct database lookups
            })
        });

        if (!response.ok) {
            let errText = '';
            try {
                const errJson = await response.json();
                errText = JSON.stringify(errJson, null, 2);
            } catch (e) {
                try {
                    errText = await response.text();
                } catch (tErr) {
                    errText = 'Could not read error payload';
                }
            }
            throw new Error(`Agent API returned status ${response.status}. Details: ${errText}`);
        }

        const data = await response.json();
        
        if (data.status === 'success' && data.data && data.data.response) {
            const agentReply = data.data.response;
            
            // Show typing state to the user before sending
            try {
                const chat = await msg.getChat();
                await chat.sendStateTyping();
                
                // Determine typing duration based on response length (20ms per char, capped between 1s and 3s for human feel)
                let delayMs = Math.min(Math.max(agentReply.length * 20, 1000), 3000);
                
                console.log(`[Agent Beck] Response length: ${agentReply.length} chars. Showing typing status for ${delayMs / 1000}s...`);
                await new Promise(resolve => setTimeout(resolve, delayMs));
            } catch (stateErr) {
                console.error('[Agent Beck Warning] Failed to send typing state:', stateErr.message);
            }

            console.log(`[Agent Beck] Replying to ${cleanMobile}: "${agentReply}"`);
            const modelUsed = data.data.model || 'Unknown Model';
            console.log(`\n==========================================================`);
            console.log(`Sent From ${modelUsed}`);
            console.log(`==========================================================\n`);
            await msg.reply(agentReply);

            // If the agent returned a synthesized voice audio note, send it as a WhatsApp voice message
            if (data.data.audio_url) {
                const audioUrl = data.data.audio_url;
                console.log(`[Agent Beck] Voice mode active. Delivering audio note from: ${audioUrl}`);
                try {
                    const media = await MessageMedia.fromUrl(audioUrl);
                    await waClient.sendMessage(msg.from, media, { sendAudioAsVoice: true });
                } catch (audioErr) {
                    console.error('[Agent Beck Error] Failed to send voice audio note:', audioErr.message);
                }
            }
        }
    } catch (err) {
        console.error(`[Agent Beck Error] Failed to process message for ${cleanMobile}:`, err.message);
        
        // Remove from active sessions so the slot is freed up instantly
        activeSessions.delete(cleanMobile);
        promoteNextCustomer(); // Promote the next customer if waiting
        
        // Send a polite bilingual apology to the WhatsApp user
        try {
            // Detect if user message has Devanagari characters
            const hasDevanagari = /[\u0900-\u097F]/.test(userMessage);
            if (hasDevanagari) {
                await msg.reply("क्षमा करें, वर्तमान में कुछ तकनीकी समस्याओं के कारण हम आपके संदेश का उत्तर नहीं दे पा रहे हैं। कृपया कुछ समय बाद पुनः प्रयास करें।");
            } else {
                await msg.reply("Sorry, hum abhi technical issue ki wajah se reply nahi kar pa rahe hain. Please thodi der baad dobara check karein.");
            }
        } catch (replyErr) {
            console.error('[Agent Beck Error] Failed to send apology reply:', replyErr.message);
        }
    }
}

// Clean up stale lock files in the session directory to prevent "browser is already running" startup errors
function clearSessionLocks() {
    const sessionDir = path.join(__dirname, 'session');
    
    // Kill any orphaned/zombie chrome processes on Linux to release active locks
    if (process.platform === 'linux') {
        try {
            console.log('[Startup Cleanup] Killing any orphaned headless chrome/chromium processes...');
            execSync('pkill -f -9 chrome || true');
            execSync('pkill -f -9 chromium || true');
        } catch (e) {
            // Ignore if pkill fails or is not available
        }
    }
    
    const lockFiles = ['SingletonLock', 'lockfile', 'DevToolsActivePort'];
    
    const deleteLocksRecursively = (dir) => {
        if (!fs.existsSync(dir)) return;
        try {
            const files = fs.readdirSync(dir);
            for (const file of files) {
                const fullPath = path.join(dir, file);
                const stat = fs.lstatSync(fullPath);
                if (stat.isDirectory()) {
                    deleteLocksRecursively(fullPath);
                } else if (lockFiles.includes(file) || file.includes('SingletonLock')) {
                    try {
                        fs.unlinkSync(fullPath);
                        console.log(`[Startup Cleanup] Removed stale lock file: ${fullPath}`);
                    } catch (e) {
                        // Ignore lock deletion failures if actually locked by active processes
                    }
                }
            }
        } catch (err) {}
    };
    
    deleteLocksRecursively(sessionDir);
}

function createWhatsAppClient() {
    // Clear stale locks before initializing client
    clearSessionLocks();
    console.log('[WhatsApp] Instantiating fresh client...');
    
    waClient = new Client({
        authStrategy: new LocalAuth({ dataPath: './session' }),
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        authTimeoutMs: 120000,
        qrTimeoutMs: 120000,
        webVersionCache: {
            type: 'remote',
            remotePath: 'https://raw.githubusercontent.com/wppconnect-team/wa-version/main/html/2.2412.54.html'
        },
        puppeteer: puppeteerConfig
    });

    waClient.on('qr', async (qr) => {
        try {
            currentQrDataUrl = await QRCode.toDataURL(qr);
            console.log('[WhatsApp] New QR Code generated (Scan it on the UI dashboard).');
            
            // Print the QR code directly to the server terminal for easy scanning
            console.log('\n==========================================================');
            console.log('Scan this QR code with your phone to link WhatsApp:');
            console.log('==========================================================\n');
            qrcode.generate(qr, { small: true });
            console.log('\n');
        } catch (err) {
            console.error('[WhatsApp] Failed to generate QR data URL:', err.message);
        }
    });

    waClient.on('loading_screen', (percent, message) => {
        console.log(`[WhatsApp Loading] ${percent}% - ${message}`);
    });

    waClient.on('auth_failure', (msg) => {
        console.error('[WhatsApp Auth Failure]', msg);
    });

    waClient.on('authenticated', () => {
        console.log('[WhatsApp] Authenticated! Session saved.');
        currentQrDataUrl = null;
    });

    waClient.on('ready', async () => {
        isWaReady = true;
        currentQrDataUrl = null;
        console.log('[WhatsApp] READY! Ready to send messages.');

        // Wait 5 seconds for WhatsApp Web internal chat list sync to complete
        await new Promise(resolve => setTimeout(resolve, 5000));

        // Catch up on unread messages received while the server was offline
        console.log('[Offline Catchup] Checking for unread messages...');
        try {
            const chats = await waClient.getChats();
            const unreadChats = chats.filter(chat => chat.unreadCount > 0 && !chat.isGroup);
            
            if (unreadChats.length > 0) {
                console.log(`[Offline Catchup] Found ${unreadChats.length} unread chats. Processing...`);
                for (const chat of unreadChats) {
                    try {
                        const messages = await chat.fetchMessages({ limit: chat.unreadCount });
                        for (const msg of messages) {
                            if (!msg.fromMe) {
                                const userMessage = msg.body;
                                if (!userMessage) continue;
                                
                                let cleanMobile = msg.from.replace('@c.us', '');
                                if (msg.from.includes('@lid')) {
                                    try {
                                        const contact = await msg.getContact();
                                        if (contact && contact.number) {
                                            cleanMobile = contact.number;
                                        }
                                    } catch (err) {
                                        console.error('[LID Resolution Error] Failed to fetch contact number during catchup:', err.message);
                                    }
                                }
                                console.log(`[Offline Catchup] Found unread message from ${cleanMobile}: "${userMessage}"`);
                                
                                // Send apology reply
                                await msg.reply("We apologize for the delay. Our server was temporarily offline. We are now processing your request...");
                                
                                // Process or queue the message
                                if (activeSessions.has(cleanMobile)) {
                                    activeSessions.set(cleanMobile, Date.now());
                                    await processAgentQuery(msg, cleanMobile, userMessage);
                                } else if (activeSessions.size < 4) {
                                    activeSessions.set(cleanMobile, Date.now());
                                    await processAgentQuery(msg, cleanMobile, userMessage);
                                } else {
                                    waitingQueue.push({ msg, cleanMobile, userMessage });
                                }
                            }
                        }
                        // Mark the chat as seen
                        await chat.sendSeen();
                    } catch (chatErr) {
                        console.error(`[Offline Catchup Error] Failed to process chat ${chat.id._serialized}:`, chatErr.message);
                    }
                }
            } else {
                console.log('[Offline Catchup] No unread messages found.');
            }
        } catch (catchupErr) {
            console.error('[Offline Catchup Error] Failed to retrieve chats:', catchupErr.message);
        }
    });

    // Incoming Message Listener with Concurrency Queuing (Integrates Python AI Agent Beck)
    waClient.on('message', async (msg) => {
        // Skip group messages and status broadcasts
        if (msg.from.endsWith('@g.us') || msg.from === 'status@broadcast') {
            return;
        }

        const userMessage = msg.body;
        if (!userMessage) return;

        let cleanMobile = msg.from.replace('@c.us', '');
        if (msg.from.includes('@lid')) {
            try {
                const contact = await msg.getContact();
                if (contact && contact.number) {
                    cleanMobile = contact.number;
                }
            } catch (err) {
                console.error('[LID Resolution Error] Failed to fetch contact number:', err.message);
            }
        }
        console.log(`[Queue Manager] Incoming message from ${cleanMobile}: "${userMessage}"`);

        // Check if customer is already in active sessions
        if (activeSessions.has(cleanMobile)) {
            // Update last activity timestamp and process message
            activeSessions.set(cleanMobile, Date.now());
            await processAgentQuery(msg, cleanMobile, userMessage);
            return;
        }

        // Clean up any expired sessions before checking capacity
        const now = Date.now();
        for (const [mobile, lastActive] of activeSessions.entries()) {
            if (now - lastActive > SESSION_TIMEOUT) {
                activeSessions.delete(mobile);
                console.log(`[Queue Manager] Active session for ${mobile} expired due to 2-minute inactivity.`);
            }
        }

        // Check active slots capacity
        if (activeSessions.size < 4) {
            console.log(`[Queue Manager] Accepting customer ${cleanMobile} to active session slots (${activeSessions.size + 1}/4).`);
            activeSessions.set(cleanMobile, Date.now());
            await processAgentQuery(msg, cleanMobile, userMessage);
        } else {
            // Check if already in waiting queue to prevent duplicates
            const isAlreadyWaiting = waitingQueue.some(item => item.cleanMobile === cleanMobile);
            if (!isAlreadyWaiting) {
                console.log(`[Queue Manager] Max active sessions reached. Queueing customer ${cleanMobile} (FIFO).`);
                waitingQueue.push({ msg, cleanMobile, userMessage });
                await msg.reply("We are currently assisting other customers. You have been placed in our queue and will be replied to shortly.");
            } else {
                console.log(`[Queue Manager] Customer ${cleanMobile} is already in the waiting queue. Ignoring duplicate queue entry.`);
            }
        }
    });

    waClient.on('disconnected', async (reason) => {
        isWaReady = false;
        console.log('[WhatsApp] Disconnected:', reason, '— Reconnecting...');
        
        try {
            await waClient.destroy();
        } catch (e) {
            console.log('[WhatsApp] Client destroy failed:', e.message);
        }

        if (reason === 'LOGOUT' || reason === 'NAVIGATION') {
            try {
                const fs = await import('fs');
                const localSessionPath = './session';
                if (fs.existsSync(localSessionPath)) {
                    fs.rmSync(localSessionPath, { recursive: true, force: true });
                    console.log('[WhatsApp] Wiped session folder after LOGOUT/NAVIGATION.');
                }
            } catch (err) {
                console.error('[WhatsApp] Failed to wipe session folder:', err.message);
            }
        }
        
        setTimeout(() => {
            console.log('[WhatsApp] Attempting re-initialization with fresh instance...');
            createWhatsAppClient();
        }, 5000);
    });

    console.log('[WhatsApp] Client starting...');
    waClient.initialize().catch(err => {
        console.error('[WhatsApp Initialization Error] Failed to initialize client:', err.message);
        isWaReady = false;
        
        console.log('[WhatsApp Startup Retry] Retrying WhatsApp client initialization in 5 seconds...');
        setTimeout(() => {
            createWhatsAppClient();
        }, 5000);
    });
}

createWhatsAppClient();

// Helper to delay
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// Format mobile helper
function formatMobile(mobile) {
    let num = String(mobile).replace(/\D/g, '');
    if (num.startsWith('0')) num = num.substring(1);
    if (!num.startsWith('91')) num = '91' + num;
    return num + '@c.us';
}

// Puppeteer helper to print PDF from URL (Launches dedicated clean browser instance for 100% reliability)
async function generateReceiptPdf(debtorId) {
    const url = WA_CONFIG.SITE_BASE_URL + WA_CONFIG.RECEIPT_PATH
              + '?id=' + debtorId
              + '&pdf_token=' + encodeURIComponent(WA_CONFIG.PDF_TOKEN)
              + '&print=1'
              + '&cb=' + Date.now();

    console.log(`[WhatsApp PDF] Generating from URL: ${url}`);

    let tempBrowser = null;
    let page = null;
    try {
        const pdfLaunchOptions = { ...puppeteerConfig, headless: true };
        delete pdfLaunchOptions.launcher; // Safeguard against recursion loop in puppeteer-extra

        tempBrowser = await cleanPuppeteer.launch(pdfLaunchOptions);

        page = await tempBrowser.newPage();

        // Override window.print inside the Puppeteer browser so it does nothing (prevents call stack crashes)
        await page.evaluateOnNewDocument(() => {
            window.print = () => { console.log('[Puppeteer] window.print() bypassed.'); };
        });

        await page.goto(url, {
            waitUntil: 'load', // Wait for basic page load instead of networkidle0
            timeout: 20000     // Lower timeout to 20 seconds
        });

        await page.emulateMediaType('print');

        const pdfBuffer = await page.pdf({
            format: 'A4',
            printBackground: true,
            margin: { top: '5mm', right: '5mm', bottom: '5mm', left: '5mm' }
        });

        await tempBrowser.close();
        return Buffer.from(pdfBuffer).toString('base64');
    } catch (err) {
        if (tempBrowser) {
            try { await tempBrowser.close(); } catch (e) {}
        }
        console.error('[WhatsApp PDF] Failed to generate PDF:', err.message);
        throw err;
    }
}

// ── WhatsApp Auth Middleware ──────────────────────────────────────────────────
function waAuth(req, res, next) {
    const token = req.headers['x-api-token'] || req.body?.token;
    if (token !== WA_CONFIG.SECRET_TOKEN) {
        return res.status(401).json({ ok: false, error: 'Unauthorized' });
    }
    next();
}

// ── GET /status ───────────────────────────────────────────────────────────────
app.get('/status', (req, res) => {
    res.json({ ok: true, ready: isWaReady, qr: currentQrDataUrl, server: 'YTSK WhatsApp Bot Server v1.0' });
});

// ═══════════════════════════════════════════════════════════
// Message Queue Manager
// ═══════════════════════════════════════════════════════════
const LOG_FILE_PATH = path.join(__dirname, 'sent_log.json');

// Helper to check if a mobile number has already received a message today
async function hasBeenSentToday(mobile) {
    const fs = await import('fs');
    const todayStr = new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD in local time
    
    try {
        if (fs.existsSync(LOG_FILE_PATH)) {
            const raw = fs.readFileSync(LOG_FILE_PATH, 'utf8');
            const logData = JSON.parse(raw);
            if (logData && logData.date === todayStr && logData.sent && logData.sent[mobile]) {
                return logData.sent[mobile];
            }
        }
    } catch (e) {
        // Safe fallback
    }
    return null;
}

// Helper to save a sent message timestamp for today
async function markAsSentToday(mobile) {
    const fs = await import('fs');
    const todayStr = new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD in local time
    let logData = { date: todayStr, sent: {} };
    
    try {
        if (fs.existsSync(LOG_FILE_PATH)) {
            const raw = fs.readFileSync(LOG_FILE_PATH, 'utf8');
            const parsed = JSON.parse(raw);
            if (parsed && parsed.date === todayStr && parsed.sent) {
                logData = parsed;
            }
        }
    } catch (e) {
        // Safe to ignore, we will write a fresh file
    }
    
    logData.sent[mobile] = new Date().toISOString();
    try {
        fs.writeFileSync(LOG_FILE_PATH, JSON.stringify(logData, null, 4));
        console.log(`[Sent Log] Marked ${mobile} as sent for today (${todayStr})`);
    } catch (e) {
        console.error('[Sent Log Error] Failed to write sent_log.json:', e.message);
    }
}

const messageQueue = [];
let isProcessingQueue = false;
let lastSentMobile = null;
let lastSentTimestamp = 0;

async function processQueue() {
    if (isProcessingQueue) return;
    isProcessingQueue = true;

    while (messageQueue.length > 0) {
        const item = messageQueue.shift();
        const { type, mobile, payload, resolve, reject } = item;

        // If WhatsApp connection is not active, wait 5 seconds and retry (preventing infinite command execution crash)
        if (!isWaReady) {
            console.warn('[Queue] WhatsApp client is not ready. Delaying message processing...');
            messageQueue.unshift(item); // Put it back at the front of the queue
            await delay(5000);
            continue;
        }

        try {
            // Duplicate Checkpoint: Skip if already sent to this customer today
            const alreadySentAt = await hasBeenSentToday(mobile);
            if (alreadySentAt) {
                console.log(`[Queue Skip] Duplicate message for ${mobile} ignored. Already sent today at ${alreadySentAt}.`);
                resolve({ ok: true, status: 'skipped', reason: 'already_sent_today', mobile });
                continue;
            }

            // Delay check: If mobile is different, enforce 8 second gap
            if (lastSentMobile && lastSentMobile !== mobile) {
                const elapsed = Date.now() - lastSentTimestamp;
                const requiredDelay = 8000; // 8 seconds gap
                if (elapsed < requiredDelay) {
                    const waitTime = requiredDelay - elapsed;
                    console.log(`[Queue] Target changed to ${mobile}. Waiting ${waitTime}ms to enforce 8-sec gap...`);
                    await delay(waitTime);
                }
            } else if (lastSentMobile && lastSentMobile === mobile) {
                console.log(`[Queue] Same target mobile (${mobile}) detected. Sending immediately without gap!`);
            }

            console.log(`[Queue] Processing message of type '${type}' for: ${mobile}`);
            let result;

            if (type === 'receipt') {
                const { debtor_id, debtor_name, message, skip_pdf } = payload;
                const chatId = formatMobile(mobile);

                // 1. Try to generate PDF first
                const shouldSkipPdf = skip_pdf === true || skip_pdf === 'true' ||
                                      WA_CONFIG.SITE_BASE_URL.includes('localhost') ||
                                      WA_CONFIG.SITE_BASE_URL.includes('127.0.0.1');

                let pdfBase64 = null;
                if (!shouldSkipPdf) {
                    try {
                        pdfBase64 = await generateReceiptPdf(parseInt(debtor_id));
                    } catch (pdfErr) {
                        console.error(`[Queue Warning] PDF generation failed for ${mobile}, falling back to text-only:`, pdfErr.message);
                    }
                }

                // 2. Send Text Message
                if (message) {
                    await waClient.sendMessage(chatId, message);
                    console.log('  [WhatsApp] Text message sent successfully.');
                }

                // 3. Send PDF if generated successfully
                if (pdfBase64) {
                    await delay(1000); // 1 sec separation between text & PDF
                    const media = new MessageMedia(
                        'application/pdf',
                        pdfBase64,
                        `Receipt_${debtor_name || debtor_id}.pdf`
                    );
                    await waClient.sendMessage(chatId, media);
                    console.log('  [WhatsApp] Receipt PDF sent successfully.');
                }
                result = { ok: true, mobile, debtor_id, status: 'sent' };
            } else if (type === 'text') {
                const { message } = payload;
                const chatId = formatMobile(mobile);
                await waClient.sendMessage(chatId, message);
                console.log('  [WhatsApp] Text message sent successfully.');
                result = { ok: true, mobile, status: 'sent' };
            } else if (type === 'document') {
                const { file_content_base64, filename, mime_type } = payload;
                const chatId = formatMobile(mobile);
                const media = new MessageMedia(
                    mime_type || 'text/plain',
                    file_content_base64,
                    filename || 'report.txt'
                );
                await waClient.sendMessage(chatId, media);
                console.log('  [WhatsApp] Document sent successfully.');
                result = { ok: true, mobile, status: 'sent' };
            }

            // Mark as sent today in the log file
            await markAsSentToday(mobile);

            lastSentMobile = mobile;
            lastSentTimestamp = Date.now();
            resolve(result);
        } catch (err) {
            console.error(`[Queue Error] Failed to process message for ${mobile}:`, err.message);
            
            // Queue retry logic (retries up to 3 times with 5s delay)
            const attempts = (item.attempts || 0) + 1;
            if (attempts < 3) {
                item.attempts = attempts;
                console.log(`[Queue Retry] Re-queueing message for ${mobile} in 5 seconds (Attempt ${attempts}/3) due to error...`);
                setTimeout(() => {
                    messageQueue.push(item);
                    processQueue();
                }, 5000);
            } else {
                console.error(`[Queue Error] Maximum retry limit (3 attempts) reached for ${mobile}. Discarding message.`);
                reject(err);
            }
        }
    }

    isProcessingQueue = false;
}

// ── POST /send-receipt ────────────────────────────────────────────────────────
app.post('/send-receipt', waAuth, (req, res) => {
    if (!isWaReady) {
        return res.status(503).json({
            ok: false,
            error: 'WhatsApp is not connected. Please scan the QR code first.'
        });
    }

    const { debtor_id, mobile, debtor_name, message, skip_pdf } = req.body;

    if (!debtor_id || !mobile) {
        return res.status(400).json({ ok: false, error: 'debtor_id and mobile are required' });
    }

    const chatId = formatMobile(mobile);
    if (!chatId) {
        return res.status(400).json({ ok: false, error: `Invalid mobile number: ${mobile}` });
    }

    console.log(`[Queue Push] Receipt queued for: ${debtor_name || 'Unknown'} (${mobile})`);

    // Add to queue in background
    messageQueue.push({
        type: 'receipt',
        mobile,
        payload: { debtor_id, debtor_name, message, skip_pdf },
        resolve: (result) => console.log(`[Queue Success] Receipt sent for ${mobile}`),
        reject: (err) => console.error(`[Queue Failure] Failed for ${mobile}: ${err.message}`)
    });
    processQueue();

    // Respond immediately to PHP to prevent network timeouts
    return res.json({
        ok: true,
        status: 'queued',
        message: 'Message queued successfully'
    });
});

// ── POST /send-text ───────────────────────────────────────────────────────────
app.post('/send-text', waAuth, (req, res) => {
    if (!isWaReady) {
        return res.status(503).json({ ok: false, error: 'WhatsApp is not connected.' });
    }

    const { mobile, message } = req.body;
    const chatId = formatMobile(mobile);

    if (!chatId) {
        return res.status(400).json({ ok: false, error: `Invalid mobile number: ${mobile}` });
    }

    console.log(`[Queue Push] Text message queued for: ${mobile}`);

    // Add to queue in background
    messageQueue.push({
        type: 'text',
        mobile,
        payload: { message },
        resolve: (result) => console.log(`[Queue Success] Text message sent to ${mobile}`),
        reject: (err) => console.error(`[Queue Failure] Failed for ${mobile}: ${err.message}`)
    });
    processQueue();

    // Respond immediately to PHP to prevent network timeouts
    return res.json({
        ok: true,
        status: 'queued',
        message: 'Message queued successfully'
    });
});

// ── POST /send-document ───────────────────────────────────────────────────────
app.post('/send-document', waAuth, (req, res) => {
    if (!isWaReady) {
        return res.status(503).json({ ok: false, error: 'WhatsApp is not connected.' });
    }

    const { mobile, file_content_base64, filename, mime_type } = req.body;
    const chatId = formatMobile(mobile);

    if (!chatId) {
        return res.status(400).json({ ok: false, error: `Invalid mobile number: ${mobile}` });
    }

    console.log(`[Queue Push] Document queued for: ${mobile}, filename: ${filename}`);

    // Add to queue in background
    messageQueue.push({
        type: 'document',
        mobile,
        payload: { file_content_base64, filename, mime_type },
        resolve: (result) => console.log(`[Queue Success] Document sent to ${mobile}`),
        reject: (err) => console.error(`[Queue Failure] Failed for ${mobile}: ${err.message}`)
    });
    processQueue();

    return res.json({
        ok: true,
        status: 'queued',
        message: 'Document queued successfully'
    });
});

// ── POST /logout ─────────────────────────────────────────────────────────────
app.post('/logout', waAuth, async (req, res) => {
    try {
        console.log('[WhatsApp] Force logout/reset requested...');
        
        isWaReady = false;
        currentQrDataUrl = null;

        // Force destroy the current browser instance safely to release locks
        try {
            await Promise.race([
                waClient.destroy(),
                new Promise((_, reject) => setTimeout(() => reject(new Error('Destroy timeout')), 4000))
            ]);
        } catch (e) {
            console.log('[WhatsApp] Could not destroy client cleanly, forcing manual cleanup:', e.message);
        }

        // Give Puppeteer a brief moment to fully terminate the chrome process and free locks
        await delay(2000);

        // Clean up session folder manually to wipe corrupted login data
        const fs = await import('fs');
        const sessionPath = path.join(__dirname, '.puppeteer_cache', 'session');
        const localSessionPath = './session';
        const cachePath = './.wwebjs_cache';

        const deleteFolderSafely = (folderPath, label) => {
            try {
                if (fs.existsSync(folderPath)) {
                    fs.rmSync(folderPath, { recursive: true, force: true });
                    console.log(`[WhatsApp] Deleted ${label} directory.`);
                }
            } catch (err) {
                console.warn(`[WhatsApp Warning] Failed to delete ${label} (${folderPath}): ${err.message}`);
            }
        };

        deleteFolderSafely(localSessionPath, 'local ./session');
        deleteFolderSafely(sessionPath, 'cache session');
        deleteFolderSafely(cachePath, 'cache .wwebjs_cache');

        // Re-initialize a fresh WhatsApp client instance
        console.log('[WhatsApp] Re-initializing fresh client...');
        createWhatsAppClient();

        res.json({ ok: true, message: 'WhatsApp logged out, session cleared, and re-initialized.' });
    } catch (err) {
        console.error('[WhatsApp] Force logout/reset failed:', err.message);
        res.status(500).json({ ok: false, error: err.message });
    }
});
// ── GET /health ───────────────────────────────────────────────────────────────
app.get('/health', (req, res) => {
    res.json({ status: 'ok', service: 'YTSK WhatsApp Bot Server', port: PORT });
});

const waUrlFilePath = path.join(__dirname, '../../app/wa_url.json');

// Cleanup dynamic url file on exit
async function cleanupWaUrlFile() {
    try {
        const fs = await import('fs');
        if (fs.existsSync(waUrlFilePath)) {
            fs.unlinkSync(waUrlFilePath);
            console.log('[Ngrok] Cleared dynamic wa_url.json config.');
        }
    } catch (e) {
        // Silent error
    }
}

app.listen(PORT, HOST, async () => {
    console.log(`\n✅ YTSK WhatsApp Bot Server running at http://${HOST}:${PORT}`);
    console.log(`[Env Debug] USE_NGROK: ${process.env.USE_NGROK}, NGROK_DOMAIN: ${process.env.NGROK_DOMAIN}`);
    
    if (process.env.USE_NGROK === 'true') {
        try {
            console.log('[Ngrok] Starting ngrok tunnel...');
            const ngrok = await import('@ngrok/ngrok');
            const listener = await ngrok.forward({
                addr: PORT,
                domain: process.env.NGROK_DOMAIN || undefined,
                authtoken: process.env.NGROK_AUTHTOKEN || undefined,
                authtoken_from_env: !process.env.NGROK_AUTHTOKEN
            });
            
            const publicUrl = listener.url();
            console.log(`\n🚀 Ngrok Ingress established at: ${publicUrl}`);
            
            // 1. Update local PHP config (if running locally on the same machine)
            const fs = await import('fs');
            try {
                fs.writeFileSync(waUrlFilePath, JSON.stringify({ url: publicUrl }, null, 4));
                console.log(`[Ngrok] Dynamic URL updated in local PHP config at: ${waUrlFilePath}`);
            } catch (err) {
                // Ignore local write failure if directories differ
            }

            // 2. Notify remote Hostinger PHP website to update its wa_url.json
            const cleanBaseUrl = WA_CONFIG.SITE_BASE_URL.replace(/\/+$/, '');
            const updateUrl = cleanBaseUrl + '/update_wa_url.php';
            console.log(`[Ngrok] Notifying remote PHP application at: ${updateUrl}`);
            try {
                const response = await fetch(updateUrl, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        token: WA_CONFIG.SECRET_TOKEN,
                        url: publicUrl
                    })
                });
                const resData = await response.json();
                if (resData.ok) {
                    console.log(`[Ngrok] Remote Hostinger PHP config updated successfully!`);
                } else {
                    console.error('[Ngrok] Remote Hostinger PHP config update failed:', resData.error);
                }
            } catch (postErr) {
                console.error('[Ngrok] Failed to notify remote PHP application:', postErr.message);
            }
        } catch (err) {
            console.error('[Ngrok] Failed to establish tunnel:', err.message);
        }
    } else {
        await cleanupWaUrlFile();
    }
});

// Heartbeat Monitor (Runs every 15 minutes to keep WebSocket alive & detect freezes)
setInterval(async () => {
    if (!isWaReady) return;
    
    console.log('[Heartbeat] Checking WhatsApp connection state...');
    try {
        // Query the state. If the browser or WebSocket is frozen, this will time out.
        const state = await Promise.race([
            waClient.getState(),
            new Promise((_, reject) => setTimeout(() => reject(new Error('State query timeout')), 10000))
        ]);
        
        console.log(`[Heartbeat] WhatsApp Connection State: ${state}`);
        if (state !== 'CONNECTED') {
            console.warn('[Heartbeat Warning] State is not CONNECTED. Re-initializing...');
            isWaReady = false;
            createWhatsAppClient();
        }
    } catch (err) {
        console.error('[Heartbeat Error] Connection is frozen or disconnected:', err.message);
        isWaReady = false;
        
        // Safety destroy & auto-recover
        try {
            await waClient.destroy();
        } catch (e) {
            console.log('[Heartbeat Error] Failed to destroy client cleanly:', e.message);
        }
        
        console.log('[Heartbeat Recovery] Re-initializing a fresh WhatsApp client session...');
        createWhatsAppClient();
    }
}, 15 * 60 * 1000); // 15 minutes interval

let consecutiveDisconnects = 0;

// Helper to check if the machine has a valid local network/router connection (LAN or Wi-Fi)
function hasLocalNetworkConnection() {
    try {
        const interfaces = os.networkInterfaces();
        for (const interfaceName in interfaces) {
            const addresses = interfaces[interfaceName];
            for (const addr of addresses) {
                // Check for a non-internal (non-loopback) IPv4 address
                if (addr.family === 'IPv4' && !addr.internal) {
                    // Ignore APIPA auto-configuration IPs (means link is up but no router/DHCP found)
                    if (!addr.address.startsWith('169.254.')) {
                        return true; 
                    }
                }
            }
        }
    } catch (e) {
        console.error('[Network Monitor Error] Failed to read network interfaces:', e.message);
    }
    return false; 
}

// Monitor Local Network Connection every 30 seconds.
// If disconnected from router/LAN for 2 continuous minutes (4 consecutive failures), terminate server.
setInterval(async () => {
    const isConnected = hasLocalNetworkConnection();
    
    if (isConnected) {
        consecutiveDisconnects = 0; // Reset counter
    } else {
        consecutiveDisconnects++;
        console.warn(`[Network Monitor] Disconnected from local network/router. Consecutive check failures: ${consecutiveDisconnects}/4`);
        
        if (consecutiveDisconnects >= 4) {
            console.error('[Network Monitor] Disconnected from local network/router for 2 continuous minutes. Terminating server for safety.');
            try {
                await cleanupWaUrlFile();
            } catch (e) {
                console.error('[Network Monitor Error] Failed to clean up url file:', e.message);
            }
            process.exit(1);
        }
    }
}, 30000); // 30 seconds check interval

// Capture exit events to clean up URL file
process.on('SIGINT', async () => {
    await cleanupWaUrlFile();
    process.exit(0);
});
process.on('SIGTERM', async () => {
    await cleanupWaUrlFile();
    process.exit(0);
});
// Global error catching to prevent the server from crashing on unhandled rejections/exceptions
process.on('unhandledRejection', (reason, promise) => {
    console.error('[Process Error] Unhandled Rejection at:', promise, 'reason:', reason);
});

process.on('uncaughtException', (err) => {
    console.error('[Process Error] Uncaught Exception thrown:', err.message, err.stack);
});
