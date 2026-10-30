$ErrorActionPreference = 'Stop'
$kitRoot = $PSScriptRoot
python (Join-Path $kitRoot 'skills/code-review-kit/scripts/setup.py')
exit $LASTEXITCODE
