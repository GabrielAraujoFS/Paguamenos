$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd([IO.Path]::DirectorySeparatorChar)
$stage = Join-Path $tempRoot ('paguamenos-docker-' + [guid]::NewGuid().ToString('N'))
$stage = [IO.Path]::GetFullPath($stage)

if (-not $stage.StartsWith($tempRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The temporary build directory is outside the system temporary folder.'
}

function Copy-BuildContext {
    param(
        [string] $Source,
        [string] $Destination,
        [string[]] $ExcludedDirectories,
        [string[]] $ExcludedFiles
    )

    $arguments = @($Source, $Destination, '/E', '/COPY:DAT', '/DCOPY:DAT', '/R:1', '/W:1', '/NFL', '/NDL', '/NJH', '/NJS')
    if ($ExcludedDirectories.Count -gt 0) {
        $arguments += '/XD'
        $arguments += $ExcludedDirectories
    }
    if ($ExcludedFiles.Count -gt 0) {
        $arguments += '/XF'
        $arguments += $ExcludedFiles
    }

    & robocopy @arguments | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "Could not copy Docker build context: $Source (robocopy exit code $LASTEXITCODE)."
    }
}

try {
    New-Item -ItemType Directory -Path $stage | Out-Null
    $backendStage = Join-Path $stage 'backend'
    $frontendStage = Join-Path $stage 'frontend'

    Copy-BuildContext -Source (Join-Path $projectRoot 'backend') -Destination $backendStage `
        -ExcludedDirectories @('.venv', '__pycache__', '.pytest_cache', 'tests', 'examples', 'docs') `
        -ExcludedFiles @('*.db', '*.db-*', '*.sqlite*', '.env', '.env.*')
    Copy-BuildContext -Source (Join-Path $projectRoot 'paguemenos-FRONT-END') -Destination $frontendStage `
        -ExcludedDirectories @('node_modules', 'dist', '.git') `
        -ExcludedFiles @('.env', '.env.*', '*.tsbuildinfo')

    $backendContext = $backendStage.Replace('\', '/')
    $frontendContext = $frontendStage.Replace('\', '/')
    $override = Join-Path $stage 'compose.override.yaml'
    @"
services:
  backend:
    build:
      context: '$backendContext'
  frontend:
    build:
      context: '$frontendContext'
"@ | Set-Content -LiteralPath $override -Encoding utf8

    & docker compose --project-directory $projectRoot -f (Join-Path $projectRoot 'compose.yaml') -f $override up --build -d --force-recreate
    if ($LASTEXITCODE -ne 0) {
        throw "Docker Compose failed (exit code $LASTEXITCODE)."
    }
}
finally {
    if (Test-Path -LiteralPath $stage) {
        Remove-Item -LiteralPath $stage -Recurse -Force
    }
}
