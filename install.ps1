$ErrorActionPreference = 'Stop'
$kitRoot = $PSScriptRoot
python -m pip install --target (Join-Path $kitRoot '.deps') --requirement (Join-Path $kitRoot 'requirements.txt') --disable-pip-version-check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
python (Join-Path $kitRoot 'review.py') doctor
exit $LASTEXITCODE
