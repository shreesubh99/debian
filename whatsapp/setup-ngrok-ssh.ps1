# Windows PowerShell script to automate installation and setup of Ngrok CLI and OpenSSH on Windows

Write-Host "====================================================" -ForegroundColor Blue
Write-Host "  Automated Setup: Ngrok CLI & OpenSSH on Windows   " -ForegroundColor Blue
Write-Host "====================================================" -ForegroundColor Blue

# 1. Run as Administrator check
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Error "Error: Please run this PowerShell terminal as Administrator."
    Exit
}

# 2. Verify and Install OpenSSH Server on Windows
Write-Host "[1/3] Checking and enabling OpenSSH Server on Windows..." -ForegroundColor Yellow
$sshService = Get-Service -Name sshd -ErrorAction SilentlyContinue

if ($null -eq $sshService) {
    Write-Host "Installing OpenSSH Server..." -ForegroundColor Blue
    Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
} else {
    Write-Host "OpenSSH Server is already installed." -ForegroundColor Green
}

# Start and enable SSH Service
Start-Service sshd
Set-Service -Name sshd -StartupType 'Automatic'
Write-Host "OpenSSH Service is running automatically on boot." -ForegroundColor Green

# 3. Download and Install Ngrok CLI on Windows
Write-Host "[2/3] Checking and installing Ngrok CLI..." -ForegroundColor Yellow
$ngrokPath = Get-Command ngrok -ErrorAction SilentlyContinue

if ($null -eq $ngrokPath) {
    Write-Host "Installing Ngrok via winget (Windows Package Manager)..." -ForegroundColor Blue
    winget install --id ngrok.ngrok --silent --accept-package-agreements --accept-source-agreements
    # Refresh PATH variables
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
} else {
    Write-Host "Ngrok CLI is already installed." -ForegroundColor Green
}

# 4. Configure Authtoken
Write-Host "[3/3] Configuring Ngrok Authtoken..." -ForegroundColor Yellow
$NGROK_TOKEN = "31yGVbAOlk0V2i0vjxJLHGkLclx_6XXNTqL8u39utRass2MB8"
& ngrok config add-authtoken $NGROK_TOKEN

Write-Host "====================================================" -ForegroundColor Green
Write-Host "           SETUP COMPLETED SUCCESSFULLY!            " -ForegroundColor Green
Write-Host "====================================================" -ForegroundColor Green
Write-Host "`nTo start the remote SSH tunnel on Windows, run this command in Administrator PowerShell:"
Write-Host "ngrok tcp 22" -ForegroundColor Yellow
