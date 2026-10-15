# PowerShell installation script for Antigravity 2.0 plugin 'myskills' on Windows
# Note: Antigravity Language Server (Go os.ReadDir) requires a real directory (entry.IsDir() == true)
# and ignores symlinks/junctions (ReparsePoint). This script installs a clean real directory copy.

param (
    [switch]$Uninstall
)

$PluginName = "myskills"
$UserHome = [System.Environment]::GetFolderPath('UserProfile')
$PluginsDir = Join-Path $UserHome ".gemini\config\plugins"
$TargetDir = Join-Path $PluginsDir $PluginName
$ScriptDir = $PSScriptRoot

function Enable-PluginInAntigravity {
    if ($env:ANTIGRAVITY_CSRF_TOKEN) {
        $addr = if ($env:ANTIGRAVITY_LS_ADDRESS) { $env:ANTIGRAVITY_LS_ADDRESS } else { "localhost:5387" }
        $headers = @{ "Content-Type" = "application/json"; "x-codeium-csrf-token" = $env:ANTIGRAVITY_CSRF_TOKEN }
        $uri = "http://$addr/exa.language_server_pb.LanguageServerService/JetboxWriteState"
        try {
            Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body "{`"userConfig`":{`"plugins`":{`"$PluginName`":{`"enabled`":false}}}}" -TimeoutSec 5 | Out-Null
            Start-Sleep -Milliseconds 150
            Invoke-RestMethod -Uri $uri -Method Post -Headers $headers -Body "{`"userConfig`":{`"plugins`":{`"$PluginName`":{`"enabled`":true}}}}" -TimeoutSec 5 | Out-Null
        } catch {
            # Ignore if Language Server is not reachable in standalone terminal
        }
    }
}

function Remove-PluginTarget {
    param ([string]$PathToRemove)
    if (Test-Path $PathToRemove) {
        $item = Get-Item $PathToRemove -Force
        if ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
            [System.IO.Directory]::Delete($PathToRemove)
        } else {
            Remove-Item -Path $PathToRemove -Recurse -Force
        }
    }
}

if ($Uninstall) {
    Write-Host "[INFO] Uninstalling Antigravity plugin '$PluginName'..." -ForegroundColor Cyan
    Enable-PluginInAntigravity
    if (Test-Path $TargetDir) {
        Remove-PluginTarget -PathToRemove $TargetDir
        Write-Host "[SUCCESS] Removed plugin directory $TargetDir." -ForegroundColor Green
    } else {
        Write-Host "[INFO] Plugin is not installed at $TargetDir." -ForegroundColor Cyan
    }
    Write-Host "[SUCCESS] Uninstallation completed!" -ForegroundColor Green
    exit 0
}

Write-Host "[INFO] Installing '$PluginName' as an Antigravity 2.0 plugin..." -ForegroundColor Cyan

if (-not (Test-Path $PluginsDir)) {
    Write-Host "[INFO] Creating plugins directory at $PluginsDir..." -ForegroundColor Cyan
    New-Item -Path $PluginsDir -ItemType Directory -Force | Out-Null
}

if (Test-Path $TargetDir) {
    Write-Host "[INFO] Updating existing plugin installation at $TargetDir..." -ForegroundColor Cyan
    Remove-PluginTarget -PathToRemove $TargetDir
}

New-Item -Path $TargetDir -ItemType Directory -Force | Out-Null

# Copy plugin bundle contents (plugin.json, README.md, assets/, skills/)
Copy-Item -Path (Join-Path $ScriptDir "plugin.json") -Destination $TargetDir -Force
if (Test-Path (Join-Path $ScriptDir "README.md")) {
    Copy-Item -Path (Join-Path $ScriptDir "README.md") -Destination $TargetDir -Force
}
if (Test-Path (Join-Path $ScriptDir "assets")) {
    Copy-Item -Path (Join-Path $ScriptDir "assets") -Destination (Join-Path $TargetDir "assets") -Recurse -Force
}
if (Test-Path (Join-Path $ScriptDir "skills")) {
    Copy-Item -Path (Join-Path $ScriptDir "skills") -Destination (Join-Path $TargetDir "skills") -Recurse -Force
}

Enable-PluginInAntigravity
Write-Host "[SUCCESS] Successfully installed '$PluginName' plugin to $TargetDir!" -ForegroundColor Green
Write-Host "[INFO] Manage plugin at: customization://$PluginName" -ForegroundColor Cyan
