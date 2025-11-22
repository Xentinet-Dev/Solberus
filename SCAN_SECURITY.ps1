# Quick Security Scan for Solberus
# Run this from C:\Projects\Solberus

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Security Scan for Sensitive Data" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$issues = @()

# Check 1: Look for actual .env files (not .env.example)
Write-Host "Checking for .env files..." -ForegroundColor Yellow
$envFiles = Get-ChildItem -Recurse -File -Filter ".env*" -ErrorAction SilentlyContinue | 
    Where-Object { $_.Name -ne ".env.example" -and $_.Name -notmatch "\.example$" }

if ($envFiles.Count -gt 0) {
    Write-Host "  [CRITICAL] Found actual .env files:" -ForegroundColor Red
    foreach ($file in $envFiles) {
        $relative = $file.FullName.Replace((Get-Location).Path + "\", "")
        Write-Host "    - $relative" -ForegroundColor Red
        $issues += "CRITICAL: Actual .env file found: $relative"
    }
} else {
    Write-Host "  [OK] No .env files found (only .env.example exists)" -ForegroundColor Green
}

# Check 2: Look for hardcoded private keys (base58 or array format)
Write-Host ""
Write-Host "Checking for hardcoded private keys..." -ForegroundColor Yellow
$keyPatterns = @(
    '\[[0-9]+(,[0-9]+){31,}\]',      # Array format private key
    "SOLANA_PRIVATE_KEY\s*=\s*[^#\s\n]+[A-Za-z0-9]{20,}"  # Actual key value (not in .example)
)

# Known Solana program addresses (safe to commit - these are public)
$knownProgramAddresses = @(
    "ComputeBudget111111111111111111111111111111",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL",
    "SysvarRent111111111111111111111111111111111",
    "So11111111111111111111111111111111111111112",
    "11111111111111111111111111111111"  # System Program
)

$foundKeys = @()
foreach ($pattern in $keyPatterns) {
    $matches = Select-String -Path (Get-ChildItem -Recurse -File -Include *.py,*.ts,*.tsx,*.js,*.yaml,*.yml -Exclude *.example -ErrorAction SilentlyContinue) -Pattern $pattern -ErrorAction SilentlyContinue
    foreach ($match in $matches) {
        # Skip if it's a known program address or example/placeholder
        $isKnownAddress = $false
        foreach ($knownAddr in $knownProgramAddresses) {
            if ($match.Line -match [regex]::Escape($knownAddr)) {
                $isKnownAddress = $true
                break
            }
        }
        
        if (-not $isKnownAddress -and $match.Line -notmatch "(example|placeholder|your_|TODO|FIXME|#|//|Pubkey\.from_string)") {
            $foundKeys += $match
        }
    }
}

if ($foundKeys.Count -gt 0) {
    Write-Host "  [CRITICAL] Found potential hardcoded private keys:" -ForegroundColor Red
    foreach ($key in $foundKeys | Select-Object -First 5) {
        $relative = $key.Path.Replace((Get-Location).Path + "\", "")
        Write-Host "    - $relative : Line $($key.LineNumber)" -ForegroundColor Red
        $linePreview = $key.Line.Trim()
        if ($linePreview.Length -gt 80) { $linePreview = $linePreview.Substring(0, 80) + "..." }
        Write-Host "      $linePreview" -ForegroundColor Gray
        $issues += "CRITICAL: Potential private key in $relative : Line $($key.LineNumber)"
    }
} else {
    Write-Host "  [OK] No hardcoded private keys found" -ForegroundColor Green
}

# Check 3: Look for API keys/tokens
Write-Host ""
Write-Host "Checking for hardcoded API keys..." -ForegroundColor Yellow
$apiPatterns = @(
    "api[_-]?key\s*[:=]\s*['\`"]?[A-Za-z0-9_-]{25,}['\`"]?",
    "GEYSER_API_TOKEN\s*=\s*[A-Za-z0-9_-]{20,}",
    "API_KEY\s*=\s*[A-Za-z0-9_-]{20,}"
)

$foundApiKeys = @()
foreach ($pattern in $apiPatterns) {
    $matches = Select-String -Path (Get-ChildItem -Recurse -File -Include *.py,*.ts,*.tsx,*.js,*.yaml,*.yml -Exclude *.example -ErrorAction SilentlyContinue) -Pattern $pattern -ErrorAction SilentlyContinue
    foreach ($match in $matches) {
        if ($match.Line -notmatch "(example|placeholder|your_|TODO|FIXME|#|//)") {
            $foundApiKeys += $match
        }
    }
}

if ($foundApiKeys.Count -gt 0) {
    Write-Host "  [CRITICAL] Found potential hardcoded API keys:" -ForegroundColor Red
    foreach ($key in $foundApiKeys | Select-Object -First 5) {
        $relative = $key.Path.Replace((Get-Location).Path + "\", "")
        Write-Host "    - $relative : Line $($key.LineNumber)" -ForegroundColor Red
        $issues += "CRITICAL: Potential API key in $relative : Line $($key.LineNumber)"
    }
} else {
    Write-Host "  [OK] No hardcoded API keys found" -ForegroundColor Green
}

# Check 4: Check .env.example files exist and are templates
Write-Host ""
Write-Host "Checking .env.example files..." -ForegroundColor Yellow
$exampleFiles = Get-ChildItem -Recurse -File -Filter ".env.example" -ErrorAction SilentlyContinue
if ($exampleFiles.Count -gt 0) {
    foreach ($file in $exampleFiles) {
        $content = Get-Content $file.FullName -Raw
        if ($content -match "your_|placeholder|example|TODO") {
            Write-Host "  [OK] $($file.FullName.Replace((Get-Location).Path + '\', '')) is a template" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] $($file.FullName.Replace((Get-Location).Path + '\', '')) may contain actual values" -ForegroundColor Yellow
        }
    }
}

# Summary
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
if ($issues.Count -eq 0) {
    Write-Host "SCAN RESULT: PASSED" -ForegroundColor Green
    Write-Host ""
    Write-Host "No critical security issues found." -ForegroundColor Green
    Write-Host "Your repository appears safe to push to GitHub." -ForegroundColor Green
} else {
    Write-Host "SCAN RESULT: FAILED" -ForegroundColor Red
    Write-Host ""
    Write-Host "CRITICAL ISSUES FOUND: $($issues.Count)" -ForegroundColor Red
    Write-Host ""
    Write-Host "DO NOT push to GitHub until these are resolved:" -ForegroundColor Red
    foreach ($issue in $issues) {
        Write-Host "  - $issue" -ForegroundColor Yellow
    }
}
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

