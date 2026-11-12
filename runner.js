const { spawn, spawnSync, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

console.log('==========================================================');
console.log('   Starting WhatsApp Bot & Python AI Agent Concurrently   ');
console.log('==========================================================');

// Robust function to forcefully free a port on Debian/Linux and Windows
function clearPort(port) {
    if (process.platform === 'win32') {
        try {
            const out = execSync(`netstat -ano | findstr :${port}`, { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'ignore'] });
            for (const line of out.split('\n')) {
                const parts = line.trim().split(/\s+/);
                const pid = parts[parts.length - 1];
                if (pid && pid !== '0' && !isNaN(pid)) {
                    execSync(`taskkill /F /PID ${pid}`, { stdio: 'ignore' });
                }
            }
        } catch (e) {}
        return;
    }

    console.log(`[Port Cleaner] Clearing port ${port}...`);
    try {
        // 1. Process specific kills
        if (port === 8000) {
            execSync('pkill -9 -f "uvicorn.*8000" 2>/dev/null || sudo pkill -9 -f "uvicorn.*8000" 2>/dev/null || true', { shell: '/bin/bash', stdio: 'ignore' });
            execSync('pkill -9 -f "src.server:app" 2>/dev/null || sudo pkill -9 -f "src.server:app" 2>/dev/null || true', { shell: '/bin/bash', stdio: 'ignore' });
        } else if (port === 3333) {
            execSync('pkill -9 -f "whatsapp.*server.js" 2>/dev/null || sudo pkill -9 -f "whatsapp.*server.js" 2>/dev/null || true', { shell: '/bin/bash', stdio: 'ignore' });
        }

        // 2. Clear via ss (works natively on Debian without requiring fuser or lsof)
        execSync(`for pid in $(ss -lptn "sport = :${port}" 2>/dev/null | grep -oP "pid=\\K[0-9]+" | sort -u); do kill -9 $pid 2>/dev/null || sudo kill -9 $pid 2>/dev/null || true; done`, { shell: '/bin/bash', stdio: 'ignore' });

        // 3. Clear via fuser (checks standard /usr/sbin path if not in regular PATH)
        execSync(`fuser -k -9 ${port}/tcp 2>/dev/null || /usr/sbin/fuser -k -9 ${port}/tcp 2>/dev/null || sudo fuser -k -9 ${port}/tcp 2>/dev/null || true`, { shell: '/bin/bash', stdio: 'ignore' });

        // 4. Clear via lsof
        execSync(`lsof -ti :${port} 2>/dev/null | xargs -r kill -9 2>/dev/null || sudo lsof -ti :${port} 2>/dev/null | sudo xargs -r kill -9 2>/dev/null || true`, { shell: '/bin/bash', stdio: 'ignore' });

        // Settle time for OS TCP socket release
        execSync('sleep 0.5 2>/dev/null || true', { shell: '/bin/bash', stdio: 'ignore' });
    } catch (cleanErr) {
        // Silent catch
    }
    console.log(`[Port Cleaner] Port ${port} is cleared and ready.`);
}

// Pre-cleanup ports 3333 and 8000 to resolve Port Error on Debian/Linux
console.log('[Runner] Performing pre-startup port cleanup (ports 8000 and 3333)...');
clearPort(8000);
clearPort(3333);
console.log('[Runner] Ports 8000 and 3333 are fully cleared and ready.');

// 1. Auto-detect directories
let rootDir = __dirname;
let waDir = path.join(__dirname, 'whatsapp');
let agentDir = path.join(__dirname, 'agent');

if (!fs.existsSync(waDir) || !fs.existsSync(agentDir)) {
    // If running from nested folders, check if they are siblings
    if (fs.existsSync(path.join(__dirname, '..', 'whatsapp')) && fs.existsSync(path.join(__dirname, '..', 'agent'))) {
        rootDir = path.join(__dirname, '..');
        waDir = path.join(rootDir, 'whatsapp');
        agentDir = path.join(rootDir, 'agent');
    }
}

console.log(`[Runner] Root: ${rootDir}`);
console.log(`[Runner] WhatsApp Bot: ${waDir}`);
console.log(`[Runner] AI Agent: ${agentDir}`);

// 2. Verify critical source files & Auto-create .env from .env.example if missing
const requiredFiles = [
    { path: path.join(rootDir, '.env'), template: path.join(rootDir, '.env.example'), isRequired: true, canAutoCreate: true },
    { path: path.join(waDir, 'server.js'), isRequired: true },
    { path: path.join(agentDir, 'src', 'server.py'), isRequired: true },
    { path: path.join(agentDir, 'src', 'config.py'), isRequired: true },
    { path: path.join(agentDir, 'src', 'agent', 'core.py'), isRequired: true },
    { path: path.join(agentDir, 'src', 'agent', 'validator.py'), isRequired: true }
];

let criticalFileMissing = false;
for (const file of requiredFiles) {
    if (!fs.existsSync(file.path)) {
        if (file.canAutoCreate && file.template && fs.existsSync(file.template)) {
            console.log(`[Runner Warning] ${path.basename(file.path)} was missing. Copying from ${path.basename(file.template)}...`);
            try {
                fs.copyFileSync(file.template, file.path);
                if (file.path.endsWith('.env')) {
                    console.log('[Runner Info] Generated .env file from template successfully. Continuing startup...');
                }
            } catch (copyErr) {
                console.error(`[Runner Error] Failed to auto-generate ${path.basename(file.path)}: ${copyErr.message}`);
                criticalFileMissing = true;
            }
        } else if (file.isRequired) {
            console.error(`[CRITICAL ERROR] Required file is missing: ${file.path}`);
            criticalFileMissing = true;
        }
    }
}

if (criticalFileMissing) {
    console.error('[Runner Error] Cannot start due to missing critical source files. Process aborted.');
    process.exit(1);
}

// 3. Auto-install Node.js dependencies if missing or incomplete
const requiredNodeDeps = ['express', 'whatsapp-web.js', 'qrcode', 'dotenv', 'body-parser', 'cors', 'puppeteer'];
let nodeDepsMissing = false;
const nodeModulesPath = path.join(waDir, 'node_modules');

try {
    for (const dep of requiredNodeDeps) {
        require.resolve(dep, { paths: [waDir] });
    }
} catch (e) {
    nodeDepsMissing = true;
}

if (nodeDepsMissing || !fs.existsSync(nodeModulesPath)) {
    console.log('[Runner] Node.js dependencies are missing or incomplete. Running npm install inside whatsapp folder...');
    try {
        execSync('npm install', { cwd: waDir, stdio: 'inherit' });
        console.log('[Runner] Node.js dependencies verified and installed successfully.');
    } catch (err) {
        console.error('[Runner Error] Failed to install Node.js dependencies:', err.message);
        process.exit(1);
    }
} else {
    console.log('[Runner] All Node.js dependencies are present and verified.');
}

// 4. Auto-install Python dependencies if missing
const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';
console.log('[Runner] Checking Python dependencies...');

const requiredModules = [
    { name: 'fastapi', check: 'fastapi' },
    { name: 'uvicorn', check: 'uvicorn' },
    { name: 'httpx', check: 'httpx' },
    { name: 'requests', check: 'requests' },
    { name: 'python-dotenv', check: 'dotenv' },
    { name: 'pydantic', check: 'pydantic' },
    { name: 'jinja2', check: 'jinja2' },
    { name: 'google-generativeai', check: 'google.generativeai' },
    { name: 'azure-cognitiveservices-speech', check: 'azure.cognitiveservices.speech' },
    { name: 'mysql-connector-python', check: 'mysql.connector' }
];

let pythonDepsMissing = false;
for (const mod of requiredModules) {
    try {
        execSync(`${pythonCmd} -c "import ${mod.check}"`, { stdio: 'ignore' });
    } catch (err) {
        console.log(`[Runner] Missing Python library: ${mod.name}`);
        pythonDepsMissing = true;
        break;
    }
}

if (pythonDepsMissing) {
    console.log('[Runner] Python dependencies are missing. Triggering self-healing requirements installer...');
    const selfHealerPath = path.join(rootDir, 'install_requirements.py');
    if (fs.existsSync(selfHealerPath)) {
        try {
            execSync(`${pythonCmd} "${selfHealerPath}"`, { stdio: 'inherit' });
            console.log('[Runner] Python requirements self-healed and installed successfully.');
        } catch (err) {
            console.error('[Runner Warning] Python self-healer failed, trying fallback:', err.message);
            pythonDepsMissing = true; // Let pip fallback try
        }
    }
    
    // Check again, if still missing try pip directly
    let checkAgain = false;
    for (const mod of requiredModules) {
        try {
            execSync(`${pythonCmd} -c "import ${mod.check}"`, { stdio: 'ignore' });
        } catch (err) {
            checkAgain = true;
            break;
        }
    }
    
    if (checkAgain) {
        const reqPath = path.join(agentDir, 'requirements.txt');
        if (fs.existsSync(reqPath)) {
            console.log('[Runner] Running direct pip installation fallback...');
            const installCmds = [
                `${pythonCmd} -m pip install -r "${reqPath}" --break-system-packages --user`,
                `${pythonCmd} -m pip install -r "${reqPath}" --user`,
                `${pythonCmd} -m pip install -r "${reqPath}" --break-system-packages`,
                `${pythonCmd} -m pip install -r "${reqPath}"`
            ];
            let success = false;
            for (const cmd of installCmds) {
                try {
                    console.log(`[Runner] Running: ${cmd}`);
                    execSync(cmd, { stdio: 'inherit' });
                    success = true;
                    break;
                } catch (e) {}
            }
            if (!success) {
                console.error('[CRITICAL ERROR] Python pip installation fallback failed.');
                process.exit(1);
            }
        } else {
            console.error('[CRITICAL ERROR] requirements.txt not found. Cannot proceed.');
            process.exit(1);
        }
    }
}

// Final assertion to ensure all Python libraries are actually importable
for (const mod of requiredModules) {
    try {
        execSync(`${pythonCmd} -c "import ${mod.check}"`, { stdio: 'ignore' });
    } catch (err) {
        console.error(`[CRITICAL ERROR] Python library ${mod.name} is still not working after installation attempts.`);
        console.error('Please install it manually or check permissions.');
        process.exit(1);
    }
}

console.log('[Runner] All Python dependencies are present and verified.');

// 4. Start Python Agent with Auto-Restart & Health Watchdog
let agentProcess = null;
let agentRestartScheduled = false;
let botProcess = null;
let botRestartScheduled = false;
let isShuttingDown = false;
let agentHealthFailures = 0;

function startAgent() {
    if (isShuttingDown) return;
    agentRestartScheduled = false;
    agentHealthFailures = 0;
    clearPort(8000);
    console.log('[Runner] Spawning Python AI Agent on port 8000...');
    agentProcess = spawn(pythonCmd, ['-m', 'uvicorn', 'src.server:app', '--host', '127.0.0.1', '--port', '8000'], {
        cwd: agentDir,
        shell: false,
        stdio: 'inherit'
    });

    agentProcess.on('error', (err) => {
        console.error('[Runner Error] Failed to start Python Agent process:', err.message);
    });

    agentProcess.on('close', (code, signal) => {
        if (isShuttingDown) return;
        console.warn(`[Runner Warning] Python AI Agent process closed (code: ${code}, signal: ${signal}). Respawning in 3 seconds...`);
        if (!agentRestartScheduled) {
            agentRestartScheduled = true;
            setTimeout(startAgent, 3000);
        }
    });
}
startAgent();

// Active Health Watchdog for Python AI Agent (checks every 30s)
const http = require('http');
setInterval(() => {
    if (isShuttingDown || agentRestartScheduled) return;
    const req = http.get('http://127.0.0.1:8000/health', { timeout: 5000 }, (res) => {
        res.resume();
        if (res.statusCode === 200) {
            agentHealthFailures = 0;
        } else {
            agentHealthFailures++;
            console.warn(`[Agent Watchdog] Unhealthy status ${res.statusCode} (${agentHealthFailures}/3)`);
        }
    });
    req.on('error', () => {
        agentHealthFailures++;
        console.warn(`[Agent Watchdog] Python AI Agent unreachable (${agentHealthFailures}/3)`);
        if (agentHealthFailures >= 3 && !agentRestartScheduled) {
            console.error('[Agent Watchdog] Python AI Agent unresponsive! Force restarting...');
            agentHealthFailures = 0;
            try { if (agentProcess) agentProcess.kill('SIGKILL'); } catch (e) {}
            agentRestartScheduled = true;
            setTimeout(startAgent, 2000);
        }
    });
    req.on('timeout', () => {
        req.destroy();
    });
}, 30000);

// 5. Start Node.js WhatsApp Bot with Auto-Restart
function startBot() {
    if (isShuttingDown) return;
    botRestartScheduled = false;
    clearPort(3333);
    console.log('[Runner] Spawning Node.js WhatsApp Bot on port 3333...');
    botProcess = spawn('node', ['server.js'], {
        cwd: waDir,
        shell: false,
        stdio: 'inherit'
    });

    botProcess.on('error', (err) => {
        console.error('[Runner Error] Failed to start Node.js WhatsApp Bot process:', err.message);
    });

    botProcess.on('close', (code, signal) => {
        if (isShuttingDown) return;
        console.log(`[Runner] Node.js WhatsApp Bot process closed (code: ${code}, signal: ${signal}). Respawning in 2 seconds...`);
        if (!botRestartScheduled) {
            botRestartScheduled = true;
            setTimeout(startBot, 2000);
        }
    });
}
startBot();

// Handle graceful termination
function shutdown() {
    isShuttingDown = true;
    console.log('\n[Runner] Stopping both processes...');
    try { if (agentProcess) agentProcess.kill('SIGTERM'); } catch (e) {}
    try { if (botProcess) botProcess.kill('SIGTERM'); } catch (e) {}
    process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
