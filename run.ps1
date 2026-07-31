# 서버를 실행합니다.
#   .\run.ps1            로컬만  (http://127.0.0.1:8000)
#   .\run.ps1 -Tunnel    공개 주소까지 (Cloudflare 임시 터널)
#
# 창을 닫으면 서버도 함께 종료됩니다. 계속 띄워두려면 install-autostart.ps1.

param([switch]$Tunnel, [int]$Port = 8000)

$ErrorActionPreference = "Continue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

$vpy = Join-Path $here ".venv\Scripts\python.exe"
if (-not (Test-Path $vpy)) {
    Write-Host "가상환경이 없습니다. 먼저 .\setup.ps1 을 실행하세요." -ForegroundColor Red
    exit 1
}

# 이미 떠 있는 서버 정리
Get-CimInstance Win32_Process -Filter "Name='python.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -like "*main.py*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

$env:CADCHECK_PORT = $Port
$server = Start-Process -FilePath $vpy -ArgumentList "main.py" -PassThru -WindowStyle Hidden

Write-Host "서버 시작 중..." -NoNewline
$up = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 500
    try {
        $h = Invoke-RestMethod "http://127.0.0.1:$Port/api/health" -TimeoutSec 3
        $up = $true; break
    } catch {}
}
if (-not $up) {
    Write-Host " 실패" -ForegroundColor Red
    Write-Host "서버가 응답하지 않습니다. 아래로 직접 실행해 오류를 확인하세요:"
    Write-Host "  $vpy main.py"
    exit 1
}
Write-Host " 완료" -ForegroundColor Green
Write-Host ""
Write-Host "  로컬 주소 : http://127.0.0.1:$Port" -ForegroundColor Cyan
$fmts = if ($h.inventor) { "ipt / idw / iam / dwg / dxf 전부" } else { "dwg / dxf 만 (Inventor 없음)" }
Write-Host "  분석 가능 : $fmts"

if ($Tunnel) {
    $cf = @("C:\Program Files (x86)\cloudflared\cloudflared.exe",
            "C:\Program Files\cloudflared\cloudflared.exe") |
          Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $cf) { $cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source }
    if (-not $cf) {
        Write-Host ""
        Write-Host "  cloudflared가 없습니다. 설치:" -ForegroundColor Yellow
        Write-Host "     winget install --id Cloudflare.cloudflared"
    } else {
        Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
        $log = Join-Path $env:LOCALAPPDATA "cad-checker\tunnel.log"
        New-Item -ItemType Directory -Force (Split-Path $log) | Out-Null
        Remove-Item $log -ErrorAction SilentlyContinue
        Start-Process -FilePath $cf `
            -ArgumentList "tunnel","--url","http://127.0.0.1:$Port","--no-autoupdate" `
            -WindowStyle Hidden -RedirectStandardError $log -RedirectStandardOutput "$log.out"
        Write-Host "  터널 연결 중..." -NoNewline
        $url = $null
        for ($i = 0; $i -lt 40; $i++) {
            Start-Sleep -Seconds 1
            if (Test-Path $log) {
                $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" `
                        -AllMatches -ErrorAction SilentlyContinue
                if ($m) { $url = $m.Matches[0].Value; break }
            }
        }
        if ($url) {
            Write-Host " 완료" -ForegroundColor Green
            Write-Host ""
            Write-Host "  공개 주소 : $url" -ForegroundColor Yellow
            Write-Host "              (cloudflared를 다시 켜면 주소가 바뀝니다)"
        } else {
            Write-Host " 실패" -ForegroundColor Red
            Get-Content $log -Tail 15 -ErrorAction SilentlyContinue
        }
    }
}

Write-Host ""
Write-Host "  종료하려면 이 창에서 Ctrl+C" -ForegroundColor DarkGray
try {
    Wait-Process -Id $server.Id
} finally {
    Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
    Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force
}
