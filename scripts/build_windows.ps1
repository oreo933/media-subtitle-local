param(
    [string]$Entry = "app/main.py",
    [string]$Name = "MediaSubtitleLocal",
    [string]$PythonExe = "",
    [switch]$SkipInstall,
    [ValidateSet("launcher", "full")]
    [string]$Mode = "launcher"
)

$workspacePython = Join-Path $env:USERPROFILE ".workbuddy/binaries/python/versions/3.11.9/python.exe"
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    if (Test-Path $workspacePython) {
        $PythonExe = $workspacePython
    }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonExe = "py -3.11"
    }
    else {
        $PythonExe = "python"
    }
}

function Invoke-PythonModule {
    param(
        [string]$Interpreter,
        [string[]]$Args
    )

    if ($Interpreter.StartsWith("py ")) {
        & py -3.11 @Args
    }
    else {
        & $Interpreter @Args
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Interpreter $($Args -join ' ')"
    }
}

Write-Host "[0/3] Python: $PythonExe"
Write-Host "[0/3] Mode: $Mode"

if (-not $SkipInstall) {
    Write-Host "[1/3] Installing dependencies..."
    Invoke-PythonModule -Interpreter $PythonExe -Args @("-m", "pip", "install", "-r", "requirements.txt")
}
else {
    Write-Host "[1/3] Skip dependency install"
}

Write-Host "[2/3] Running PyInstaller..."
if ($Mode -eq "launcher") {
    $launcherName = "${Name}Launcher"
    $launcherDist = "build/launcher_dist"
    $launcherWork = "build/pyi_launcher"
    $launcherSpec = "build/pyi_launcher_spec"

    if (Test-Path $launcherDist) { Remove-Item $launcherDist -Recurse -Force }
    if (Test-Path $launcherWork) { Remove-Item $launcherWork -Recurse -Force }
    if (Test-Path $launcherSpec) { Remove-Item $launcherSpec -Recurse -Force }

    Invoke-PythonModule -Interpreter $PythonExe -Args @(
        "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onefile", "--windowed",
        "--name", $launcherName,
        "--distpath", $launcherDist,
        "--workpath", $launcherWork,
        "--specpath", $launcherSpec,
        "launcher.py"
    )

    $rootExe = Join-Path (Get-Location) "$Name.exe"
    $launcherExe = Join-Path (Get-Location) "$launcherDist/$launcherName.exe"

    $waitSec = 0
    while (-not (Test-Path $launcherExe) -and $waitSec -lt 8) {
        Start-Sleep -Seconds 1
        $waitSec += 1
    }

    if (-not (Test-Path $launcherExe)) {
        throw "Launcher build failed. Missing file: $launcherExe"
    }

    if (Test-Path $rootExe) { Remove-Item $rootExe -Force }
    Copy-Item -Path $launcherExe -Destination $rootExe -Force


    if (-not (Test-Path $rootExe)) {
        throw "Launcher build completed but root exe not found: $rootExe"
    }

    Write-Host "[3/3] Done. Output: ./$Name.exe"
}
else {


    $iconPath = "assets/icons/app.ico"
    $fullArgs = @(
        "-m", "PyInstaller",
        "--noconfirm", "--clean", "--windowed",
        "--name", $Name
    )
    if (Test-Path $iconPath) {
        $fullArgs += @("--icon", $iconPath)
    }
    $fullArgs += $Entry
    Invoke-PythonModule -Interpreter $PythonExe -Args $fullArgs

    Write-Host "[3/3] Done. Output dir: dist/$Name"
}
