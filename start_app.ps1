param([string]$Address = '127.0.0.1', [string]$CertFile = '', [string]$KeyFile = '')
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path -LiteralPath '.local/access.json')) {
    throw 'Önce .\venv\Scripts\python.exe setup_access.py çalıştırın.'
}
$tlsArgs = @()
if ($Address -notin @('127.0.0.1','::1','localhost')) {
    if (-not (Test-Path -LiteralPath $CertFile -PathType Leaf) -or -not (Test-Path -LiteralPath $KeyFile -PathType Leaf)) {
        throw 'Kurum ağına açmak için güvenilir TLS sertifikası ve anahtarı gerekli: -CertFile ve -KeyFile.'
    }
    $tlsArgs = @('--server.sslCertFile', $CertFile, '--server.sslKeyFile', $KeyFile)
}
& .\venv\Scripts\python.exe -m streamlit run app.py --server.address $Address --server.port 8501 --browser.gatherUsageStats false --server.enableCORS true --server.enableXsrfProtection true @tlsArgs
