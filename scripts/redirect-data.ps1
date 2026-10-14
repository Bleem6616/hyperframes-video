# hyperframes-video: redirect the CLI's runtime data from C: to D: (idempotent, safe to re-run)
#
#   powershell -ExecutionPolicy Bypass -File .\redirect-data.ps1            # migrate / verify
#   powershell -ExecutionPolicy Bypass -File .\redirect-data.ps1 -DryRun    # show the plan only
#
# The CLI builds every cache/state path from os.homedir() and exposes no env var for them
# (source-verified): CACHE_DIR = join(homedir(), ".cache", "hyperframes"),
# CONFIG_DIR = join(homedir(), ".hyperframes"), state = join(homedir(), ".local", "state",
# "hyperframes", "previews"). So the only lever is a filesystem-level junction.
#
# Data root: taken from -DataRoot, else from the HF_DATA_ROOT environment variable
# (set by scripts/hf-env.sh). Kept out of this file on purpose - see the note at the bottom.
#
# Safety: if a target already holds data, it is copied to D: first, file count and byte count are
# compared, and only then is the C: original removed. Any mismatch aborts before touching data.

param(
  [string]$DataRoot = $env:HF_DATA_ROOT,
  [switch]$DryRun
)

$ErrorActionPreference = "Stop"

if (-not $DataRoot) {
  Write-Error "No data root. Pass -DataRoot 'X:\path\to\hyperframes' or set HF_DATA_ROOT (see scripts/hf-env.sh)."
  exit 1
}
if (Test-Path $DataRoot) { $DataRoot = (Resolve-Path $DataRoot).Path }

$Home2 = $env:USERPROFILE
$Map = @(
  @{ Link = "$Home2\.cache\hyperframes";       Target = "$DataRoot\home\.cache\hyperframes" },
  @{ Link = "$Home2\.hyperframes";             Target = "$DataRoot\home\.hyperframes" },
  @{ Link = "$Home2\.local\state\hyperframes"; Target = "$DataRoot\home\.local\state\hyperframes" }
)

function Get-DirStat([string]$p) {
  if (-not (Test-Path $p)) { return $null }
  $items = @(Get-ChildItem $p -Recurse -File -Force -ErrorAction SilentlyContinue)
  [pscustomobject]@{
    Files = $items.Count
    Bytes = ($items | Measure-Object -Property Length -Sum).Sum
  }
}

Write-Host "data root: $DataRoot"
foreach ($m in $Map) {
  $i = Get-Item $m.Link -Force -ErrorAction SilentlyContinue
  $isLink = $i -and ($i.Attributes -band [IO.FileAttributes]::ReparsePoint)

  if ($isLink) {
    $cur = ($i.Target -join '')
    $mark = if ($cur -eq $m.Target) { "OK  " } else { "WARN" }
    Write-Host "$mark $($m.Link) -> $cur"
    if ($cur -ne $m.Target) { Write-Host "     expected: $($m.Target)" }
    continue
  }

  if (-not $i) {
    if ($DryRun) { Write-Host "PLAN $($m.Link) - missing, would create junction -> $($m.Target)"; continue }
    New-Item -ItemType Directory -Path (Split-Path $m.Target -Parent) -Force | Out-Null
    New-Item -ItemType Directory -Path $m.Target -Force | Out-Null
    New-Item -ItemType Junction -Path $m.Link -Target $m.Target | Out-Null
    Write-Host "DONE $($m.Link) - junction created -> $($m.Target)"
    continue
  }

  if ($DryRun) { Write-Host "PLAN $($m.Link) - real folder, would copy to D: then replace with junction"; continue }

  New-Item -ItemType Directory -Path (Split-Path $m.Target -Parent) -Force | Out-Null
  Copy-Item -Path $m.Link -Destination $m.Target -Recurse -Force
  $c = Get-DirStat $m.Link
  $d = Get-DirStat $m.Target
  if ($null -eq $d -or $c.Files -ne $d.Files -or $c.Bytes -ne $d.Bytes) {
    throw "verify failed, C: original kept: $($m.Link)  C=$($c.Files)f/$($c.Bytes)b  D=$(if ($d) { "$($d.Files)f/$($d.Bytes)b" } else { 'missing' })"
  }
  Write-Host "verify ok  $($m.Link)  $($c.Files) files / $($c.Bytes) bytes"

  Remove-Item $m.Link -Recurse -Force
  New-Item -ItemType Junction -Path $m.Link -Target $m.Target | Out-Null
  $after = Get-Item $m.Link -Force
  if (-not ($after.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "junction creation failed: $($m.Link)" }
  Write-Host "DONE $($m.Link) -> $($m.Target)"
}

Write-Host "finished. runtime data now lives under $DataRoot; C: keeps junctions only."

# NOTE: keep this file ASCII-only. A .ps1 containing non-ASCII text gets parsed with the wrong
# codepage on this machine (observed: the script's own lines were echoed instead of executed).
# That is also why the D: path is not hardcoded here but read from HF_DATA_ROOT.
