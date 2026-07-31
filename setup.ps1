# 새 PC에 이 도구를 설치합니다.
#   PowerShell에서:  .\setup.ps1
#
# 하는 일: 환경 점검 -> 가상환경 생성 -> 패키지 설치 -> 자체 테스트 실행.
# 서버 실행은 run.ps1, 부팅 시 자동 시작은 install-autostart.ps1 을 쓰세요.

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

function Head($t) { Write-Host "`n=== $t ===" -ForegroundColor Cyan }
function Ok($t)   { Write-Host "  [OK]   $t" -ForegroundColor Green }
function Warn($t) { Write-Host "  [주의] $t" -ForegroundColor Yellow }
function Bad($t)  { Write-Host "  [문제] $t" -ForegroundColor Red }

Head "1. 환경 점검"

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) {
    Bad "Python이 없습니다."
    Write-Host "     https://www.python.org/downloads/ 에서 설치하세요."
    Write-Host "     설치 화면에서 'Add python.exe to PATH'를 반드시 체크하세요."
    exit 1
}
$pyver = (& python --version 2>&1)
Ok "$pyver  ($($py.Source))"

# Inventor 유무에 따라 지원 형식이 달라집니다
$inv = $false
foreach ($k in @("HKLM:\SOFTWARE\Autodesk\Inventor", "Registry::HKEY_CLASSES_ROOT\Inventor.Application")) {
    if (Test-Path $k) { $inv = $true; break }
}
if ($inv) {
    Ok "Autodesk Inventor 감지됨 -> .ipt / .idw / .iam / .dwg / .dxf 전부 분석 가능"
} else {
    Warn "Inventor가 없습니다 -> .dwg / .dxf 만 분석됩니다."
    Write-Host "       .ipt/.idw/.iam 의 치수·공차·스케치 정보는 Inventor를 통해서만"
    Write-Host "       읽을 수 있어, 다른 방법으로 대체할 수 없습니다."
}

$dwg = Join-Path $here "vendor\libredwg\dwg2dxf.exe"
if (Test-Path $dwg) { Ok "DWG 변환기(LibreDWG) 포함됨" }
else { Warn "vendor\libredwg 폴더가 없습니다. DWG는 안 되고 DXF만 됩니다." }

Head "2. 가상환경"
if (Test-Path ".venv\Scripts\python.exe") {
    Ok "이미 있음 - 재사용"
} else {
    & python -m venv .venv
    if ($LASTEXITCODE -ne 0) { Bad "가상환경 생성 실패"; exit 1 }
    Ok "생성 완료"
}
$vpy = Join-Path $here ".venv\Scripts\python.exe"

Head "3. 패키지 설치"
& $vpy -m pip install --upgrade pip --quiet
$pkgs = @("pywin32", "ezdxf", "fastapi", "uvicorn[standard]", "python-multipart", "pillow")
& $vpy -m pip install --quiet @pkgs
if ($LASTEXITCODE -ne 0) { Bad "패키지 설치 실패"; exit 1 }
Ok ($pkgs -join ", ")

Head "4. 자체 테스트"
& $vpy test_rules.py
if ($LASTEXITCODE -ne 0) { Bad "검사 규칙 테스트 실패 - 설치가 온전하지 않습니다"; exit 1 }

Head "설치 완료"
Write-Host ""
Write-Host "  서버 실행        : .\run.ps1"
Write-Host "  공개 주소까지     : .\run.ps1 -Tunnel"
Write-Host "  부팅 시 자동 시작 : .\install-autostart.ps1"
Write-Host ""
if (-not $inv) {
    Write-Host "  ! 이 PC는 DWG/DXF 전용으로 동작합니다." -ForegroundColor Yellow
    Write-Host ""
}
