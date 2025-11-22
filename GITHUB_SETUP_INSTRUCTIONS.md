# GitHub Setup Instructions for Solberus

## Step 1: Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `solberus` (or your preferred name)
3. Description: "Professional Solana trading bot for pump.fun and LetsBonk platforms"
4. Visibility: Choose Public or Private
5. **DO NOT** initialize with README, .gitignore, or license (we already have these)
6. Click "Create repository"

## Step 2: Push Your Code

### Option A: Using the PowerShell Script (Recommended)

After creating the repository, run:

```powershell
cd C:\Projects\Solberus
.\PUSH_TO_GITHUB.ps1 -RepositoryUrl "https://github.com/yourusername/solberus.git"
```

Replace `yourusername` with your GitHub username.

### Option B: Manual Commands

```powershell
cd C:\Projects\Solberus

# Add remote (replace with your repository URL)
git remote add origin https://github.com/yourusername/solberus.git

# Verify remote
git remote -v

# Push to GitHub
git push -u origin main
```

## Step 3: Authentication

If you're prompted for credentials:

### Option 1: GitHub CLI (Recommended)
```powershell
# Install GitHub CLI if not installed
winget install GitHub.cli

# Authenticate
gh auth login

# Then push
git push -u origin main
```

### Option 2: Personal Access Token
1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token with `repo` scope
3. Use token as password when prompted
4. Username: your GitHub username
5. Password: your personal access token

### Option 3: SSH Key
If you have SSH keys set up:
```powershell
git remote set-url origin git@github.com:yourusername/solberus.git
git push -u origin main
```

## Step 4: Verify Upload

1. Go to your repository on GitHub
2. Verify all files are present
3. Check that README.md displays correctly
4. Verify .env.example files are present (not actual .env files)

## Step 5: Repository Settings (Optional)

1. Add topics: `solana`, `trading-bot`, `pump-fun`, `defi`, `crypto`, `python`, `nextjs`
2. Add description: "Professional Solana trading bot for pump.fun and LetsBonk platforms"
3. Enable Issues and Discussions if desired
4. Add LICENSE file if needed

## Troubleshooting

### "Repository not found"
- Verify the repository exists on GitHub
- Check the URL is correct
- Ensure you have push access

### "Authentication failed"
- Use GitHub CLI: `gh auth login`
- Or use Personal Access Token
- Or set up SSH keys

### "Branch name mismatch"
- Ensure you're on `main` branch: `git branch -M main`
- Or push to the correct branch name

### "Permission denied"
- Check your GitHub account has access
- Verify SSH keys or tokens are valid
- Try using HTTPS instead of SSH (or vice versa)

