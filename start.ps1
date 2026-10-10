$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    Write-Error 'Install dependencies following README.md before starting the application.'
    exit 1
}
& $pythonPath -m streamlit run (Join-Path $projectRoot 'app.py')
