# Tier 2 ambient watcher wrapper (scheduled daily via Task Scheduler).
# Dumb messenger by design: runs one watch-once cycle and shows the result as
# a balloon notification. All logic and safety lives in the Python CLI; this
# script never runs a mutating command.
#
# Register:  schtasks /Create /SC DAILY /ST 09:00 /TN agent-config-sync-sense /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\Projects\agent-config-sync\scripts\sense-watcher.ps1" /F
# Remove:    schtasks /Delete /TN agent-config-sync-sense /F

$out = & agent-config-sync watch-once 2>&1
$code = $LASTEXITCODE
$lines = @($out | ForEach-Object { "$_" } | Where-Object { $_ -ne "" })

if ($code -ge 2 -or $lines.Count -lt 2) {
    $title = "agent-config-sync: watcher error"
    $body = if ($lines) { ($lines -join " ") } else { "watch-once failed (exit $code)" }
} else {
    $title = $lines[0]
    $body = ($lines[1..($lines.Count - 1)] -join " ")
}
if ($body.Length -gt 250) { $body = $body.Substring(0, 247) + "..." }

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
$icon = New-Object System.Windows.Forms.NotifyIcon
$icon.Icon = [System.Drawing.SystemIcons]::Information
$icon.Visible = $true
$icon.BalloonTipTitle = $title
$icon.BalloonTipText = $body
$icon.ShowBalloonTip(10000)
Start-Sleep -Seconds 12
$icon.Dispose()
