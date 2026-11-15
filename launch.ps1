param([switch]$NoBrowser)
# ASCII-named bridge invoked by launch.bat; forwards to the real startup script.
& (Join-Path $PSScriptRoot '启动项目.ps1') -NoBrowser:$NoBrowser
