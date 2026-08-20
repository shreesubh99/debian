const { spawn, spawnSync, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

console.log('==========================================================');
console.log('   Starting WhatsApp Bot & Python AI Agent Concurrently   ');
console.log('==========================================================');

// Pre-cleanup ports 3333 and 8000 to resolve Port Error on Debian/Linux
if (process.platform !== 'win32') {
    console.log('[Runner] Performing pre-startup port cleanup (killing stale processes on 3333 and 8000)...');
    try {
        // Run exact requested kill command for ports 8000 and 3333
        execSync("sudo kill -9 $(sudo lsof -t -i:8000) 2>/dev/null || true");
        execSync("sudo kill -9 $(sudo lsof -t -i:3333) 2>/dev/null || true");
        
        // Additional cleanups to make sure nothing is missed
        execSync("fuser -k 3333/tcp 2>/dev/null || true");
        execSync("fuser -k 8000/tcp 2>/dev/null || true");
        execSync("sudo fuser -k 3333/tcp 2>/dev/null || true");
        execSync("sudo fuser -k 8000/tcp 2>/dev/null || true");
        execSync("kill -9 $(lsof -t -i:3333) 2>/dev/null || true");
        execSync("kill -9 $(lsof -t -i:8000) 2>/dev/null || true");
        
        console.log('[Runner] Ports cleaned successfully.');
    } catch (cleanErr) {
        console.warn(`[Runner Warning] Failed to clean ports: ${cleanErr.message}`);
    }
}

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

// 4. Start Python Agent
console.log('[Runner] Spawning Python AI Agent...');
const agentProcess = spawn(pythonCmd, ['-m', 'uvicorn', 'src.server:app', '--host', '127.0.0.1', '--port', '8000'], {
    cwd: agentDir,
    shell: true,
    stdio: 'inherit'
});

agentProcess.on('error', (err) => {
    console.error('[Runner Error] Failed to start Python Agent process:', err.message);
});

// 5. Start Node.js WhatsApp Bot
console.log('[Runner] Spawning Node.js WhatsApp Bot...');
const botProcess = spawn('node', ['server.js'], {
    cwd: waDir,
    shell: true,
    stdio: 'inherit'
});

botProcess.on('error', (err) => {
    console.error('[Runner Error] Failed to start Node.js WhatsApp Bot process:', err.message);
});

// Exit runner if either child process closes to trigger systemd auto-restart
agentProcess.on('close', (code) => {
    console.error(`[Runner Error] Python AI Agent process closed with code ${code}. Terminating runner...`);
    try { botProcess.kill(); } catch (e) {}
    process.exit(code || 1);
});

botProcess.on('close', (code) => {
    console.error(`[Runner Error] Node.js WhatsApp Bot process closed with code ${code}. Terminating runner...`);
    try { agentProcess.kill(); } catch (e) {}
    process.exit(code || 1);
});

// Handle graceful termination
function shutdown() {
    console.log('\n[Runner] Stopping both processes...');
    try { agentProcess.kill(); } catch (e) {}
    try { botProcess.kill(); } catch (e) {}
    process.exit(0);
}

process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
