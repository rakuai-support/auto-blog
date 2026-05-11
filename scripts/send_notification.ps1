param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("success", "failure")]
    [string]$Status,

    [string]$Message = "",
    [string]$LogPath = "logs\daily.log"
)

function Import-DotEnv {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content $Path -Encoding UTF8 | ForEach-Object {
        $line = $_.Trim()
        if ($line -eq "" -or $line.StartsWith("#") -or $line -notmatch "=") {
            return
        }

        $parts = $line.Split("=", 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()

        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }

        if ($name -and -not [Environment]::GetEnvironmentVariable($name, "Process")) {
            [Environment]::SetEnvironmentVariable($name, $value, "Process")
        }
    }
}

function Get-EnvOrDefault {
    param([string]$Name, [string]$Default = "")
    $value = [Environment]::GetEnvironmentVariable($Name, "Process")
    if ($value) {
        return $value
    }
    return $Default
}

Import-DotEnv ".env"

$to = Get-EnvOrDefault "NOTIFY_EMAIL_TO"
$from = Get-EnvOrDefault "NOTIFY_EMAIL_FROM" $to
$smtpHost = Get-EnvOrDefault "SMTP_HOST"
$smtpUser = Get-EnvOrDefault "SMTP_USER"
$smtpPass = Get-EnvOrDefault "SMTP_PASS"
$smtpPort = [int](Get-EnvOrDefault "SMTP_PORT" "587")
$enableSsl = (Get-EnvOrDefault "SMTP_ENABLE_SSL" "true") -notmatch "^(0|false|no)$"

if (-not $to -or -not $from -or -not $smtpHost) {
    Write-Output "Notification skipped: set NOTIFY_EMAIL_TO, NOTIFY_EMAIL_FROM, and SMTP_HOST in .env"
    exit 0
}

if ($smtpUser -and -not $smtpPass) {
    Write-Output "Notification skipped: SMTP_USER is set but SMTP_PASS is missing in .env"
    exit 0
}

$branch = (& git rev-parse --abbrev-ref HEAD 2>$null)
$commit = (& git rev-parse --short HEAD 2>$null)
$logTail = ""

if (Test-Path $LogPath) {
    $logTail = (Get-Content $LogPath -Tail 80 -Encoding UTF8 -ErrorAction SilentlyContinue) -join "`r`n"
}

$statusLabel = if ($Status -eq "success") { "SUCCESS" } else { "FAILURE" }
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$subject = "[auto-blog] $statusLabel daily run $timestamp"
$body = @"
auto-blog daily run result.

Status: $statusLabel
Message: $Message
Time: $timestamp
Repository: $(Get-Location)
Branch: $branch
Commit: $commit

Log tail:
$logTail
"@

try {
    $mail = New-Object System.Net.Mail.MailMessage
    $mail.From = $from
    foreach ($address in ($to -split "[,;]" | ForEach-Object { $_.Trim() } | Where-Object { $_ })) {
        $mail.To.Add($address)
    }
    $mail.Subject = $subject
    $mail.Body = $body
    $mail.SubjectEncoding = [System.Text.Encoding]::UTF8
    $mail.BodyEncoding = [System.Text.Encoding]::UTF8

    $client = New-Object System.Net.Mail.SmtpClient($smtpHost, $smtpPort)
    $client.EnableSsl = $enableSsl
    if ($smtpUser -and $smtpPass) {
        $client.Credentials = New-Object System.Net.NetworkCredential($smtpUser, $smtpPass)
    }

    $client.Send($mail)
    Write-Output "Notification sent by SMTP: $statusLabel"
} catch {
    Write-Output "Notification failed by SMTP: $($_.Exception.Message)"
}

exit 0
