param([Parameter(Mandatory=$true)][string[]]$Paths,[Parameter(Mandatory=$true)][string]$Publisher)
$ErrorActionPreference = 'Stop'
if ([string]::IsNullOrWhiteSpace($Publisher)) { throw 'Expected publisher is required' }
$files = @($Paths | ForEach-Object {
    if (Test-Path -LiteralPath $_ -PathType Container) { Get-ChildItem -LiteralPath $_ -Recurse -File | Where-Object Extension -in '.exe','.dll','.pyd' }
    else { Get-Item -LiteralPath $_ -ErrorAction Stop }
})
if ($files.Count -eq 0) { throw 'No binaries found for signature verification' }
foreach ($file in $files) {
    $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
    if ($signature.Status -ne 'Valid' -or -not $signature.SignerCertificate) { throw "Invalid or missing signature: $($file.Name)" }
    if ($signature.SignerCertificate.Subject -ne $Publisher) { throw "Unexpected publisher: $($file.Name)" }
    if (-not $signature.TimeStamperCertificate) { throw "Missing trusted timestamp: $($file.Name)" }
    Write-Output "Verified publisher, signature and timestamp: $($file.Name)"
}
