$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$candidates = @(
    (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'),
    (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    'python'
)
foreach ($candidate in $candidates) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) {
        & $candidate -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('pydantic') and __import__('pydantic').VERSION.startswith('2.') else 1)"
        if ($LASTEXITCODE -eq 0) {
            & $candidate backend/offline_demo.py
            exit $LASTEXITCODE
        }
    }
}
throw 'Install Python 3.11+ and Pydantic 2, or use the standard setup in README.md.'
