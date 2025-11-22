# Push Solberus to GitHub
# Run this after creating your GitHub repository

param(
    [Parameter(Mandatory=$true)]
    [string]$RepositoryUrl
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Pushing Solberus to GitHub" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Validate repository URL
if ($RepositoryUrl -notmatch "^https://github\.com/|^git@github\.com:") {
    Write-Host "ERROR: Invalid GitHub repository URL format." -ForegroundColor Red
    Write-Host "Expected format: https://github.com/username/repo.git" -ForegroundColor Yellow
    Write-Host "Or: git@github.com:username/repo.git" -ForegroundColor Yellow
    exit 1
}

Push-Location (Split-Path -Parent $MyInvocation.MyCommand.Path)

try {
    # Check if remote already exists
    $existingRemote = git remote get-url origin 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Remote 'origin' already exists: $existingRemote" -ForegroundColor Yellow
        $confirm = Read-Host "Replace with new URL? (y/n)"
        if ($confirm -eq "y") {
            git remote set-url origin $RepositoryUrl
            Write-Host "Remote updated." -ForegroundColor Green
        } else {
            Write-Host "Using existing remote." -ForegroundColor Gray
            $RepositoryUrl = $existingRemote
        }
    } else {
        Write-Host "Adding remote 'origin'..." -ForegroundColor Yellow
        git remote add origin $RepositoryUrl
    }
    
    Write-Host ""
    Write-Host "Verifying remote..." -ForegroundColor Yellow
    git remote -v
    
    Write-Host ""
    Write-Host "Pushing to GitHub..." -ForegroundColor Yellow
    Write-Host "Branch: main" -ForegroundColor Gray
    Write-Host "Remote: origin" -ForegroundColor Gray
    Write-Host ""
    
    git push -u origin main
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Green
        Write-Host "SUCCESS: Code pushed to GitHub!" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
        Write-Host ""
        Write-Host "Repository URL: $RepositoryUrl" -ForegroundColor Cyan
        Write-Host ""
    } else {
        Write-Host ""
        Write-Host "ERROR: Push failed. Check the error messages above." -ForegroundColor Red
        Write-Host ""
        Write-Host "Common issues:" -ForegroundColor Yellow
        Write-Host "  - Repository doesn't exist on GitHub (create it first)" -ForegroundColor White
        Write-Host "  - Authentication required (use GitHub CLI or Personal Access Token)" -ForegroundColor White
        Write-Host "  - Branch name mismatch" -ForegroundColor White
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    Pop-Location
}

