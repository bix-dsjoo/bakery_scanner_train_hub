$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$frontendRoot = Join-Path $repoRoot "frontend"
$logRoot = Join-Path $env:TEMP "bakery-scanner-train-hub"
$apiProcess = $null
$frontendProcess = $null

function Stop-ManagedProcessTree {
    param([int]$ProcessId)

    $children = @(
        Get-CimInstance Win32_Process -Filter "ParentProcessId = $ProcessId" `
            -ErrorAction SilentlyContinue
    )
    foreach ($child in $children) {
        Stop-ManagedProcessTree -ProcessId $child.ProcessId
    }
    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Assert-LastExitCode {
    param(
        [string]$FailureMessage
    )

    if ($LASTEXITCODE -ne 0) {
        throw $FailureMessage
    }
}

$uvCommand = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uvCommand) {
    throw "uv를 찾을 수 없어요. uv를 설치한 뒤 uv가 있는 폴더를 PATH에 추가하고 새 PowerShell에서 다시 실행해 주세요: https://docs.astral.sh/uv/getting-started/installation/"
}

$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
if (-not $nodeCommand) {
    throw "Node.js를 찾을 수 없어요. Node.js 24 LTS를 설치한 뒤 새 PowerShell에서 다시 실행해 주세요: https://nodejs.org/"
}
$nodeVersion = (& $nodeCommand.Source --version).Trim()
Assert-LastExitCode "Node.js 버전을 확인하지 못했어요. Node.js 24 LTS 설치 상태를 확인해 주세요."
if ($nodeVersion -notmatch '^v24\.') {
    throw "Node.js 24 LTS가 필요하지만 현재 버전은 $nodeVersion 이에요. Node.js 24 LTS를 설치해 주세요."
}

$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCommand) {
    throw "npm.cmd를 찾을 수 없어요. Node.js 24 LTS를 다시 설치하고 설치 폴더가 PATH에 있는지 확인해 주세요."
}

& $uvCommand.Source --directory $repoRoot python find 3.13 *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Python 3.13을 찾을 수 없어요. Python 3.13을 설치하고 PATH 또는 Python Launcher에 등록한 뒤 다시 실행해 주세요: https://www.python.org/downloads/"
}

New-Item -ItemType Directory -Force -Path $logRoot | Out-Null
$apiOutputLog = Join-Path $logRoot "api-$PID.out.log"
$apiErrorLog = Join-Path $logRoot "api-$PID.err.log"
$frontendOutputLog = Join-Path $logRoot "frontend-$PID.out.log"
$frontendErrorLog = Join-Path $logRoot "frontend-$PID.err.log"

Push-Location $repoRoot
try {
    Write-Host "Python 의존성을 준비합니다..."
    & $uvCommand.Source sync
    Assert-LastExitCode "Python 의존성을 설치하지 못했어요. 네트워크 연결과 uv 오류 메시지를 확인해 주세요."

    Write-Host "프런트엔드 의존성을 준비합니다..."
    & $npmCommand.Source --prefix $frontendRoot install
    Assert-LastExitCode "프런트엔드 의존성을 설치하지 못했어요. 네트워크 연결과 npm 오류 메시지를 확인해 주세요."

    Write-Host "데이터베이스를 최신 구조로 준비합니다..."
    & $uvCommand.Source run alembic upgrade head
    Assert-LastExitCode "데이터베이스를 준비하지 못했어요. Alembic 오류 메시지에서 원인을 확인하고 수정한 뒤 다시 실행해 주세요."

    $apiProcess = Start-Process `
        -FilePath $uvCommand.Source `
        -ArgumentList @(
            "run", "uvicorn", "backend.app.main:create_app", "--factory",
            "--reload", "--host", "127.0.0.1", "--port", "8000"
        ) `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $apiOutputLog `
        -RedirectStandardError $apiErrorLog `
        -PassThru

    $frontendProcess = Start-Process `
        -FilePath $npmCommand.Source `
        -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
        -WorkingDirectory $frontendRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $frontendOutputLog `
        -RedirectStandardError $frontendErrorLog `
        -PassThru

    Write-Host "개발 서버를 시작했어요."
    Write-Host "UI:  http://127.0.0.1:5173"
    Write-Host "API: http://127.0.0.1:8000/api/v1/health"
    Write-Host "종료하려면 Ctrl+C를 누르세요."
    Write-Host "API 로그: $apiOutputLog / $apiErrorLog"
    Write-Host "UI 로그:  $frontendOutputLog / $frontendErrorLog"

    while (-not $apiProcess.HasExited -and -not $frontendProcess.HasExited) {
        Start-Sleep -Milliseconds 500
        $apiProcess.Refresh()
        $frontendProcess.Refresh()
    }

    if ($apiProcess.HasExited) {
        throw "FastAPI 개발 서버가 종료됐어요. API 오류 로그를 확인해 주세요: $apiErrorLog"
    }
    throw "Vite 개발 서버가 종료됐어요. UI 오류 로그를 확인해 주세요: $frontendErrorLog"
}
finally {
    if ($frontendProcess) {
        Stop-ManagedProcessTree -ProcessId $frontendProcess.Id
    }
    if ($apiProcess) {
        Stop-ManagedProcessTree -ProcessId $apiProcess.Id
    }
    Pop-Location
}
