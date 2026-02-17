param(
    [string]$BaseUrl = "http://127.0.0.1:5000"
)

$ErrorActionPreference = "Stop"

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Path
    )

    $url = "$BaseUrl$Path"
    try {
        $resp = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 15
        if ($resp.StatusCode -ne 200) {
            Write-Host "[FAIL] $Name -> $url (status $($resp.StatusCode))"
            return $false
        }
        Write-Host "[OK]   $Name -> $url"
        return $true
    } catch {
        Write-Host "[FAIL] $Name -> $url ($($_.Exception.Message))"
        return $false
    }
}

$results = @()

$results += Test-Endpoint -Name "hello" -Path "/api/hello"
$results += Test-Endpoint -Name "health" -Path "/health"
$results += Test-Endpoint -Name "bikes" -Path "/bikes?location=dublin"
$results += Test-Endpoint -Name "traffic" -Path "/traffic?location=dublin&radius_km=2"
$results += Test-Endpoint -Name "airquality" -Path "/airquality?location=dublin&lat=53.3498&lon=-6.2603"
$results += Test-Endpoint -Name "tours" -Path "/tours?location=dublin&radius_km=2"
$results += Test-Endpoint -Name "snapshot" -Path "/snapshot?location=dublin&lat=53.3498&lon=-6.2603"

if ($Env:ENABLE_FIRESTORE -and $Env:ENABLE_FIRESTORE.ToLower() -in @("1", "true", "yes")) {
    $results += Test-Endpoint -Name "test-firestore" -Path "/test-firestore"
} else {
    Write-Host "[SKIP] test-firestore (ENABLE_FIRESTORE not set)"
}

if ($results -contains $false) {
    Write-Host "Smoke test failed."
    exit 1
}

Write-Host "Smoke test passed."
