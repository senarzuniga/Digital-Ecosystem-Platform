param(
    [string]$RepoPath = "C:\Users\Inaki Senar\Documents\GitHub\Digital-Ecosystem-Platform",
    [string]$Subdomain = "ing-sync-dep",
    [int]$BackendPort = 8000,
    [int]$PanelPort = 8502
)

$pythonExe = Join-Path $RepoPath ".venv\Scripts\python.exe"
if (-not (Test-Path $pythonExe)) {
    Write-Error "Python venv not found at $pythonExe"
    exit 1
}

Set-Location $RepoPath

function Test-PortListening {
    param([int]$Port)
    return $null -ne (Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue)
}

function Ensure-Process {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$Args,
        [int]$Port,
        [string]$WorkingDir
    )

    if (Test-PortListening -Port $Port) {
        Write-Host "[$Name] already listening on port $Port"
        return
    }

    Write-Host "[$Name] starting on port $Port"
    Start-Process -FilePath $FilePath -ArgumentList $Args -WorkingDirectory $WorkingDir -WindowStyle Minimized | Out-Null
    Start-Sleep -Seconds 3

    if (Test-PortListening -Port $Port) {
        Write-Host "[$Name] started successfully"
    } else {
        Write-Warning "[$Name] did not bind port $Port yet"
    }
}

# Ensure backend and panel are up
Ensure-Process -Name "backend" -FilePath $pythonExe -Args @("-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "$BackendPort") -Port $BackendPort -WorkingDir $RepoPath
Ensure-Process -Name "public_panel" -FilePath $pythonExe -Args @("-m", "streamlit", "run", "public_machine_connectivity.py", "--server.port", "$PanelPort", "--server.headless", "true") -Port $PanelPort -WorkingDir $RepoPath

Write-Host "Starting persistent localtunnel loop on https://$Subdomain.loca.lt"
Write-Host "Press Ctrl+C to stop"

while ($true) {
    npx localtunnel --port $PanelPort --subdomain $Subdomain
    Write-Warning "localtunnel exited. Reconnecting in 5s..."
    Start-Sleep -Seconds 5
}
