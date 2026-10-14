<#
  hyperframes-video - environment setup (Windows)

  What it does, in order:
    1. locate Node + npm  (uses the Node bundled with WorkBuddy if not on PATH)
    2. locate Python 3    (same idea)
    3. resolve the data root (see hyperframes.env / default)
    4. create data folders
    5. install the toolchain: hyperframes CLI + ffmpeg + ffprobe
    6. point CLI cache/state folders at the data root (directory junctions)
    7. run "doctor" self-check and print the result

  Safe to re-run: every step is idempotent.

  Usage:
    powershell -ExecutionPolicy Bypass -File scripts\setup-env.ps1
    powershell -ExecutionPolicy Bypass -File scripts\setup-env.ps1 -DataRoot "E:\hf"
    powershell -ExecutionPolicy Bypass -File scripts\setup-env.ps1 -DryRun

  NOTE: this file must stay pure ASCII. Windows PowerShell parses .ps1 with the
  system code page; non-ASCII characters get mis-decoded and silently break the
  script (it echoes its own source as commands instead of failing loudly).
#>
[CmdletBinding()]
param(
  [string]$DataRoot = "",
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

function Info($m) { Write-Host "[setup] $m" }
function Ok($m)   { Write-Host "[setup] OK  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[setup] !   $m" -ForegroundColor Yellow }
function Bad($m)  { Write-Host "[setup] X   $m" -ForegroundColor Red }

$SkillDir = Split-Path -Parent $PSScriptRoot

# ---------------------------------------------------------------- 1. data root
$cfgPath = Join-Path $HOME ".workbuddy\hyperframes.env"
if (-not $DataRoot -and (Test-Path $cfgPath)) {
  # -Encoding UTF8 is mandatory: Windows PowerShell 5.1 reads files with the
  # system code page by default, and a UTF-8 config with non-ASCII path (very
  # common on Chinese Windows) gets mis-decoded badly enough to merge lines,
  # so the key/value regex silently never matches.
  foreach ($line in (Get-Content -Path $cfgPath -Encoding UTF8)) {
    if ($line -match '^\s*HF_DATA_ROOT\s*=\s*"?([^"#]+?)"?\s*$') {
      $DataRoot = $Matches[1].Trim()
    }
  }
  if ($DataRoot) { Info "data root from hyperframes.env" }
}
if (-not $DataRoot) { $DataRoot = Join-Path $HOME ".workbuddy\hyperframes" }
$DataRoot = $DataRoot.TrimEnd('\', '/')  -replace '/', '\'

$Toolchain = Join-Path $DataRoot "toolchain"
$Projects  = Join-Path $DataRoot "projects"
$Output    = Join-Path $DataRoot "output"
$Temp      = Join-Path $DataRoot "temp"

Info "skill dir  : $SkillDir"
Info "data root  : $DataRoot"

# ------------------------------------------------------------ 2. node and npm
function Find-Exe([string[]]$Candidates) {
  foreach ($c in $Candidates) {
    if ($c -and (Test-Path $c)) { return (Resolve-Path $c).Path }
  }
  return $null
}

$nodeCandidates = @()
$onPath = Get-Command node -ErrorAction SilentlyContinue
if ($onPath) { $nodeCandidates += $onPath.Source }
$bundledRoot = Join-Path $HOME ".workbuddy\binaries\node\versions"
$nodeCandidates += (Join-Path $bundledRoot "current\node.exe")
$nodeCandidates += (Get-ChildItem $bundledRoot -Directory -ErrorAction SilentlyContinue |
                    Sort-Object Name -Descending |
                    ForEach-Object { Join-Path $_.FullName "node.exe" })
$NodeExe = Find-Exe $nodeCandidates
if (-not $NodeExe) {
  Bad "Node.js not found. Install Node 18+ from https://nodejs.org and re-run."
  exit 1
}
$nodeVer = (& $NodeExe -v) -replace '^v', ''
$major = [int]($nodeVer.Split('.')[0])
if ($major -lt 18) {
  Bad "Node $nodeVer is too old. Node 18 or newer is required."
  exit 1
}
Ok "node $nodeVer  ($NodeExe)"

$NpmCmd = Join-Path (Split-Path $NodeExe) "npm.cmd"
if (-not (Test-Path $NpmCmd)) {
  $onPath = Get-Command npm -ErrorAction SilentlyContinue
  if ($onPath) { $NpmCmd = $onPath.Source } else { $NpmCmd = $null }
}
if (-not $NpmCmd) {
  Bad "npm not found next to node and not on PATH. Reinstall Node.js with npm included."
  exit 1
}
Ok "npm          ($NpmCmd)"

# ----------------------------------------------------------------- 3. python 3
# Candidate order matters: the WorkBuddy-bundled interpreter first, PATH last.
# Anything under WindowsApps is skipped outright - those entries are App
# Execution Alias stubs that resolve to a Store redirector, not a real Python.
function Test-Python([string]$exe) {
  if (-not $exe) { return $false }
  if ($exe -like "*\WindowsApps\*") { return $false }
  try {
    $out = & $exe -c "print('ok')" 2>$null
    return ($LASTEXITCODE -eq 0 -and $out -eq "ok")
  } catch { return $false }
}

$pyCandidates = @()
$pyRoot = Join-Path $HOME ".workbuddy\binaries\python\versions"
$pyCandidates += (Join-Path $pyRoot "current\python.exe")
$pyCandidates += (Get-ChildItem $pyRoot -Directory -ErrorAction SilentlyContinue |
                   Sort-Object Name -Descending |
                   ForEach-Object { Join-Path $_.FullName "python.exe" })
$onPath = Get-Command python -ErrorAction SilentlyContinue
if ($onPath) { $pyCandidates += $onPath.Source }

$PythonExe = $null
foreach ($c in $pyCandidates) {
  if (Test-Python $c) { $PythonExe = (Resolve-Path $c).Path; break }
}
if ($PythonExe) { Ok "python       ($PythonExe)"
} else { Warn "python not found - the analysis scripts (bpm grid / motion audit) need Python 3.8+" }

# --------------------------------------------------------------- 4. make dirs
if ($DryRun) {
  Info "dry run: would create folders under $DataRoot"
} else {
  foreach ($d in @($DataRoot, $Toolchain, $Projects, $Output, $Temp, (Join-Path $Temp "extract"))) {
    New-Item -ItemType Directory -Force -Path $d | Out-Null
  }
  Ok "data folders ready"
}

# ------------------------------------------------------------- 5. toolchain
# Two npm gotchas, both measured on a real machine:
#   * --ignore-scripts is MANDATORY: esbuild's postinstall calls spawnSync and
#     fails with EBUSY on some Windows setups, aborting the whole install.
#   * the CLI locates ffmpeg/ffprobe through "node_modules in the CURRENT
#     directory", so it must be installed into (and run from) the toolchain dir.
$arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "win32-arm64" } else { "win32-x64" }
$ffmpegPkg  = "@ffmpeg-installer/$arch"
$ffprobePkg = "@ffprobe-installer/$arch"

if ($DryRun) {
  Info "dry run: would npm install hyperframes + $ffmpegPkg + $ffprobePkg into $Toolchain"
} else {
  $pkgJson = Join-Path $Toolchain "package.json"
  if (-not (Test-Path $pkgJson)) {
    '{"name":"hyperframes-toolchain","private":true}' | Set-Content -Path $pkgJson -Encoding ASCII
  }
  Info "installing toolchain (about 250 MB, first run may take a few minutes)..."
  Push-Location $Toolchain
  try {
    & $NpmCmd install hyperframes --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw "npm install hyperframes failed (exit $LASTEXITCODE)" }
    & $NpmCmd install $ffmpegPkg $ffprobePkg --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) {
      Warn "install of $ffmpegPkg failed, retrying with win32-x64"
      & $NpmCmd install "@ffmpeg-installer/win32-x64" "@ffprobe-installer/win32-x64" --ignore-scripts --no-audit --no-fund
      if ($LASTEXITCODE -ne 0) { throw "npm install ffmpeg/ffprobe failed (exit $LASTEXITCODE)" }
    }
  } finally {
    Pop-Location
  }
  Ok "toolchain installed"
}

# ------------------------------------------- 6. CLI cache folders -> data root
# The CLI derives its cache/state paths from os.homedir() with no env override
# (measured in source): ~/.cache/hyperframes, ~/.hyperframes,
# ~/.local/state/hyperframes. When the data root is somewhere else we redirect
# them with directory junctions. A junction is fine here (plain file IO), unlike
# the skill folder itself, which must never be a link.
$defaultRoot = Join-Path $HOME ".workbuddy\hyperframes"
if ($DataRoot -ne $defaultRoot) {
  $links = @(
    @{ Link = Join-Path $HOME ".cache\hyperframes";       Target = Join-Path $DataRoot "home\.cache\hyperframes" },
    @{ Link = Join-Path $HOME ".hyperframes";             Target = Join-Path $DataRoot "home\.hyperframes" },
    @{ Link = Join-Path $HOME ".local\state\hyperframes"; Target = Join-Path $DataRoot "home\.local\state\hyperframes" }
  )
  foreach ($l in $links) {
    if (Test-Path $l.Link) {
      $item = Get-Item $l.Link -Force
      if ($item.LinkType) { Ok "junction already in place: $($l.Link)" }
      else { Warn "SKIPPED $($l.Link) - it is a real folder with data. Run scripts\redirect-data.ps1 to migrate it safely." }
      continue
    }
    if ($DryRun) { Info "dry run: would link $($l.Link) -> $($l.Target)"; continue }
    New-Item -ItemType Directory -Force -Path $l.Target | Out-Null
    cmd /c mklink /J "$($l.Link)" "$($l.Target)" | Out-Null
    if (Test-Path $l.Link) { Ok "linked $($l.Link)" } else { Warn "could not link $($l.Link)" }
  }
} else {
  Info "data root is the default location - no junctions needed"
}

# ------------------------------------------------------------- 7. self-check
$cli = Join-Path $Toolchain "node_modules\hyperframes\bin\hyperframes.mjs"
if ($DryRun) {
  Info "dry run finished. Re-run without -DryRun to apply."
  exit 0
}
if (-not (Test-Path $cli)) {
  Bad "CLI entry not found at $cli - toolchain install looks incomplete."
  exit 1
}

$ffmpeg = Get-ChildItem (Join-Path $Toolchain "node_modules\@ffmpeg-installer") -Recurse -Filter "ffmpeg.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
$ffprobe = Get-ChildItem (Join-Path $Toolchain "node_modules\@ffprobe-installer") -Recurse -Filter "ffprobe.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if ($ffmpeg)  { Ok "ffmpeg       ($($ffmpeg.FullName))" }  else { Bad "ffmpeg.exe not found" }
if ($ffprobe) { Ok "ffprobe      ($($ffprobe.FullName))" } else { Bad "ffprobe.exe not found" }

$browser = @(
  "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
  "C:\Program Files\Microsoft\Edge\Application\msedge.exe",
  "C:\Program Files\Google\Chrome\Application\chrome.exe",
  "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($browser) { Ok "browser      ($browser)" } else { Warn "no Edge/Chrome found - set HF_BROWSER to a Chromium-based browser path" }

Info "running doctor..."
Push-Location $Toolchain
try { & $NodeExe $cli doctor } finally { Pop-Location }

Write-Host ""
Ok "setup finished."
Info "next: source scripts/hf-env.sh (Git Bash) then run:  hf doctor"
