# Git Large File Troubleshooting Guide

## 🚨 Problem: GitHub Push Rejected Due to Large Files

### Error Message
```
remote: error: File <filename> is XXX.XX MB; this exceeds GitHub's file size limit of 100.00 MB
remote: error: GH001: Large files detected. You may want to try Git Large File Storage - https://git-lfs.github.com.
! [remote rejected] main -> main (pre-receive hook declined)
error: failed to push some refs to 'https://github.com/username/repository.git'
```

### Root Cause
GitHub has a strict 100MB file size limit per file. When large files (like compiled binaries, archives, datasets, or Docker images) are committed to Git history, they prevent pushing to GitHub.

## 🛠️ Solution Process

### Step 1: Identify the Problem
```bash
# Check current Git status
git status

# Check recent commits
git log --oneline -5

# Find large files in repository
find . -type f -size +50M -exec ls -lh {} \;
```

### Step 2: Remove File from Git Cache (if not yet committed)
```bash
# Remove file from staging area
git rm --cached <large-filename>

# Add to .gitignore to prevent future commits
echo "<large-filename>" >> .gitignore
echo "*.tar" >> .gitignore  # For file types
echo "*.zip" >> .gitignore
echo "*.bin" >> .gitignore

# Commit the removal
git commit -m "Remove large file from repository and update .gitignore"
```

### Step 3: Remove File from Git History (if already committed)

If the file is already in Git history, you need to rewrite history:

```bash
# Method 1: Using git filter-branch (built-in but slower)
git filter-branch --force --index-filter \
  'git rm --cached --ignore-unmatch <large-filename>' \
  --prune-empty --tag-name-filter cat -- --all

# Method 2: Using git filter-repo (faster, requires installation)
# pip install git-filter-repo
git filter-repo --strip-blobs-bigger-than 100M
# OR
git filter-repo --path <large-filename> --invert-paths
```

### Step 4: Clean Up Git References
```bash
# Remove backup references created by filter-branch
rm -rf .git/refs/original/

# Expire reflog entries
git reflog expire --expire=now --all

# Garbage collect and compress
git gc --prune=now --aggressive
```

### Step 5: Force Push Cleaned History
```bash
# Use force-with-lease for safety (recommended)
git push --force-with-lease origin main

# Or regular force push (use with caution)
git push --force origin main
```

## 🔍 Verification Steps

### Verify File Removal
```bash
# Check that large file is gone from history
git log --stat --follow <large-filename>

# Verify repository size
du -sh .git/

# Check what files are tracked
git ls-files | grep -E "\.(tar|zip|bin|exe)$"
```

### Test Push
```bash
# Verify push works
git push origin main
```

## 🛡️ Prevention Strategies

### 1. Update .gitignore Proactively
```gitignore
# Build artifacts
*.tar
*.tar.gz
*.zip
*.rar
*.7z
*.bin
*.exe
*.dll
*.so
*.dylib

# Large data files
*.csv
*.json
*.xml
*.sql
*.db
*.sqlite

# Docker and container files
*.tar
docker-compose.override.yml

# IDE and OS files
.DS_Store
Thumbs.db
*.swp
*.swo
.vscode/
.idea/

# Compiled binaries
dist/
build/
target/
*.class
*.jar
*.war
```

### 2. Use Git Hooks
Create `.git/hooks/pre-commit` to check file sizes:

```bash
#!/bin/bash
# Check for large files before commit
large_files=$(find . -type f -size +50M | grep -v ".git")
if [ -n "$large_files" ]; then
    echo "❌ Large files detected (>50MB):"
    echo "$large_files"
    echo "Add them to .gitignore or use Git LFS"
    exit 1
fi
```

### 3. Use Git LFS for Legitimate Large Files
```bash
# Install Git LFS
git lfs install

# Track large file types
git lfs track "*.tar"
git lfs track "*.zip"
git lfs track "*.bin"

# Add .gitattributes
git add .gitattributes
git commit -m "Configure Git LFS for large files"
```

## 🚀 Alternative Solutions

### Option 1: Git LFS (Git Large File Storage)
For legitimate large files that need version control:
```bash
git lfs install
git lfs track "*.large-extension"
git add .gitattributes
git add large-file.ext
git commit -m "Add large file via Git LFS"
```

### Option 2: External Storage
Store large files externally and reference them:
- Cloud storage (AWS S3, Google Cloud Storage)
- Artifact repositories (Nexus, Artifactory)
- Container registries (Docker Hub, GHCR)

### Option 3: Split Repository
Separate large assets into dedicated repositories:
- Main code repository (small, fast)
- Assets repository (large files)
- CI/CD pipelines to combine when needed

## 📚 Additional Resources

- [GitHub File Size Limits](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)
- [Git LFS Documentation](https://git-lfs.github.com/)
- [Git Filter-Repo](https://github.com/newren/git-filter-repo)
- [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/)

## ⚠️ Important Warnings

1. **Force pushing rewrites history** - coordinate with team members
2. **Test the process** on a backup/clone first
3. **Backup your repository** before running history-rewriting commands
4. **Communicate with team** when rewriting shared history
5. **Check CI/CD pipelines** after force pushing

## 💡 Pro Tips

- Run `git log --oneline --graph` to visualize history changes
- Use `git filter-repo` instead of `git filter-branch` for better performance
- Consider repository size limits: GitHub recommends <1GB total
- Automate prevention with pre-commit hooks and CI checks
- Document large file policies for your team

---

*This guide helps resolve Git push failures due to GitHub's 100MB file size limit through safe history rewriting and prevention strategies.*
