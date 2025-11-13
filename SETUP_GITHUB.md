# Setting up GitHub Repository

The repository has been initialized locally. To push to GitHub:

## Option 1: Using GitHub CLI (if installed)

```bash
cd lighter-trend-trader
gh repo create lighter-trend-trader --public --source=. --remote=origin --push
```

## Option 2: Manual Setup

1. Create a new repository on GitHub:
   - Go to https://github.com/new
   - Repository name: `lighter-trend-trader`
   - Choose Public or Private
   - **Do NOT** initialize with README, .gitignore, or license (we already have these)

2. Add the remote and push:
   ```bash
   cd lighter-trend-trader
   git remote add origin https://github.com/YOUR_USERNAME/lighter-trend-trader.git
   git branch -M main
   git push -u origin main
   ```

Replace `YOUR_USERNAME` with your GitHub username.

## Option 3: Using SSH

If you prefer SSH:

```bash
cd lighter-trend-trader
git remote add origin git@github.com:YOUR_USERNAME/lighter-trend-trader.git
git branch -M main
git push -u origin main
```

