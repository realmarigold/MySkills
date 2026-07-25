# PowerShell installation script for Antigravity plugin 'myskills' on Windows

param (
    [switch]$Uninstall
)

$PluginName = "myskills"
$UserHome = [System.Environment]::GetFolderPath('UserProfile')
$PluginsDir = Join-Path $UserHome ".gemini\config\plugins"
$TargetDir = Join-Path $PluginsDir $PluginName
$ScriptDir = $PSScriptRoot

if ($Uninstall) {
    Write-Host "[INFO] Uninstalling Antigravity plugin '$PluginName'..." -ForegroundColor Cyan
    if (Test-Path $TargetDir) {
        $item = Get-Item $TargetDir
        if ($item.Attributes -match "ReparsePoint") {
            Remove-Item $TargetDir -Force
            Write-Host "[SUCCESS] Symlink removed from $TargetDir." -ForegroundColor Green
        } else {
            Write-Host "[WARNING] $TargetDir is a normal directory. Please manually inspect and remove it." -ForegroundColor Yellow
        }
    } else {
        Write-Host "[INFO] Plugin is not installed at $TargetDir." -ForegroundColor Cyan
    }
    Write-Host "[SUCCESS] Uninstallation completed!" -ForegroundColor Green
    exit 0
}

Write-Host "[INFO] Installing '$PluginName' as an Antigravity plugin..." -ForegroundColor Cyan

if (-not (Test-Path $PluginsDir)) {
    Write-Host "[INFO] Creating plugins directory at $PluginsDir..." -ForegroundColor Cyan
    New-Item -Path $PluginsDir -ItemType Directory -Force | Out-Null
}

if (Test-Path $TargetDir) {
    $item = Get-Item $TargetDir
    if ($item.Attributes -match "ReparsePoint") {
        $currentLink = $item.Target
        if ($currentLink -eq $ScriptDir) {
            Write-Host "[SUCCESS] Plugin '$PluginName' is already linked to $ScriptDir." -ForegroundColor Green
            exit 0
        } else {
            Write-Host "[WARNING] Updating existing symlink to $ScriptDir..." -ForegroundColor Yellow
            Remove-Item $TargetDir -Force
        }
    } else {
        Write-Host "[ERROR] Target location $TargetDir exists as a regular directory. Cannot overwrite." -ForegroundColor Red
        exit 1
    }
}

try {
    New-Item -ItemType SymbolicLink -Path $TargetDir -Target $ScriptDir -ErrorAction Stop | Out-Null
    Write-Host "[SUCCESS] Successfully installed '$PluginName' plugin!" -ForegroundColor Green
    Write-Host "[INFO] Symlink created: $TargetDir -> $ScriptDir" -ForegroundColor Cyan
    Write-Host "[INFO] Antigravity will now automatically discover skills in this plugin." -ForegroundColor Cyan
} catch {
    Write-Host "[ERROR] Failed to create symlink: $_" -ForegroundColor Red
    Write-Host "[TIP] Creating symlinks on Windows may require Administrator privileges or enabling Developer Mode." -ForegroundColor Yellow
}
