param(
  [switch]$SummaryOnly
)

$ErrorActionPreference = "Stop"
$repo = Resolve-Path (Join-Path $PSScriptRoot "..")
$logDir = Join-Path $repo "docs\data"
$logFile = Join-Path $logDir "local-automation.log"
$lockFile = Join-Path $logDir ".local-signal-paper.lock"

New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Write-TaskLog {
  param([string]$Message)
  $line = "[{0}] {1}" -f (Get-Date -Format o), $Message
  Add-Content -Path $logFile -Value $line -Encoding utf8
  Write-Host $line
}

function Invoke-Step {
  param(
    [string]$Name,
    [scriptblock]$Block
  )
  Write-TaskLog "START $Name"
  & $Block
  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE"
  }
  Write-TaskLog "DONE  $Name"
}

function Has-GitChanges {
  param([string[]]$Paths)
  $status = git status --short -- @Paths
  return -not [string]::IsNullOrWhiteSpace(($status -join "`n"))
}

function Commit-IfChanged {
  param(
    [string]$Message,
    [string[]]$Paths
  )
  if (Has-GitChanges -Paths $Paths) {
    git add -- @Paths
    git commit -m $Message
    return $true
  }
  Write-TaskLog "No changes for commit: $Message"
  return $false
}

if (Test-Path $lockFile) {
  $ageMinutes = ((Get-Date) - (Get-Item $lockFile).LastWriteTime).TotalMinutes
  if ($ageMinutes -lt 90) {
    Write-TaskLog "Another local signal task appears to be running. Lock age: $([math]::Round($ageMinutes, 1)) minutes."
    exit 0
  }
  Write-TaskLog "Removing stale lock. Lock age: $([math]::Round($ageMinutes, 1)) minutes."
  Remove-Item -Force -Path $lockFile
}

try {
  Set-Content -Path $lockFile -Value (Get-Date -Format o) -Encoding utf8
  Set-Location $repo
  Write-TaskLog "Local Onchain OS automation started. SummaryOnly=$SummaryOnly"

  Invoke-Step "sync main" {
    git pull --rebase origin main
  }

  if (-not $SummaryOnly) {
    Invoke-Step "scan signal paper" {
      npm run scan:signal
    }
  }

  Invoke-Step "write daily summary" {
    npm run summarize:daily
  }

  $mainPaths = @(
    "docs/data/signal-paper.json",
    "docs/data/operation-log.json",
    "docs/data/daily-strategy-summary.json",
    "docs/reports"
  )

  $mainCommitted = Commit-IfChanged -Message ($(if ($SummaryOnly) { "Update local strategy summary" } else { "Update local signal paper ledger" })) -Paths $mainPaths
  if ($mainCommitted) {
    Invoke-Step "push main" {
      git push origin main
    }
  }

  $pagesRoot = Join-Path $repo ".worktrees\gh-pages"
  if (-not (Test-Path $pagesRoot)) {
    Invoke-Step "create gh-pages worktree" {
      git worktree add ".worktrees\gh-pages" origin/gh-pages
    }
  }

  New-Item -ItemType Directory -Force -Path (Join-Path $pagesRoot "data") | Out-Null
  New-Item -ItemType Directory -Force -Path (Join-Path $pagesRoot "reports") | Out-Null
  Copy-Item -Force "docs\index.html" (Join-Path $pagesRoot "index.html")
  Copy-Item -Force "docs\data\signal-paper.json" (Join-Path $pagesRoot "data\signal-paper.json")
  Copy-Item -Force "docs\data\operation-log.json" (Join-Path $pagesRoot "data\operation-log.json")
  Copy-Item -Force "docs\data\daily-strategy-summary.json" (Join-Path $pagesRoot "data\daily-strategy-summary.json")
  Copy-Item -Force "docs\reports\*.md" (Join-Path $pagesRoot "reports")

  Push-Location $pagesRoot
  try {
    $pagePaths = @(
      "index.html",
      "data/signal-paper.json",
      "data/operation-log.json",
      "data/daily-strategy-summary.json",
      "reports"
    )
    $pagesCommitted = Commit-IfChanged -Message ($(if ($SummaryOnly) { "Publish local strategy summary" } else { "Publish local signal paper ledger" })) -Paths $pagePaths
    if ($pagesCommitted) {
      Invoke-Step "push gh-pages" {
        git push origin HEAD:gh-pages
      }
    }
  } finally {
    Pop-Location
  }

  Write-TaskLog "Local Onchain OS automation finished successfully."
} catch {
  Write-TaskLog "ERROR $($_.Exception.Message)"
  throw
} finally {
  if (Test-Path $lockFile) {
    Remove-Item -Force -Path $lockFile
  }
}
