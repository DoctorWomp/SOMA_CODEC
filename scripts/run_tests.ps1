param([switch]$RequireGodot)
$ErrorActionPreference = 'Stop'
$check = Join-Path $PSScriptRoot 'check.py'
if ($RequireGodot) { python $check --require-godot } else { python $check }
exit $LASTEXITCODE
