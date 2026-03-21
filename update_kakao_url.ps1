$url = (Invoke-RestMethod http://localhost:4040/api/tunnels).tunnels[0].public_url
Write-Host "ngrok: $url"

$body = @{ url = $url; token = "bsbot-kakao-token" } | ConvertTo-Json
try {
    Invoke-RestMethod -Uri "http://168.107.17.244:8765" -Method POST -Body $body -ContentType "application/json"
    Write-Host "update ok"
} catch {
    Write-Host "update fail: $($_.Exception.Message)"
}
