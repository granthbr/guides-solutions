# Auto-Activate Python venv with direnv

This guide explains how to automatically activate your `.venv` when entering a project directory, and automatically deactivate it when leaving.

---

## 1. Install direnv

```bash
sudo apt install direnv
```

Add the following line to the end of your `~/.bashrc` (or `~/.zshrc` if you use zsh):

```bash
eval "$(direnv hook bash)"
```

Reload your shell:

```bash
source ~/.bashrc
```

---

## 2. Create `.envrc` in Your Project

Inside your project root (where `.venv/` exists), run:

```bash
echo 'source .venv/bin/activate' > .envrc
```

---

## 3. Allow direnv

```bash
direnv allow
```

Now, whenever you `cd` into this folder, `.venv` will auto-activate.  
Leaving the folder will auto-deactivate it.

---

## 4. (Optional) Ignore `.envrc` in Git

To avoid committing `.envrc` accidentally, add it to your `.gitignore`:

```bash
echo '.envrc' >> .gitignore
```

---

✅ After setup:
- `cd ~/your-project` → `.venv` activates automatically  
- `cd ~` (or elsewhere) → `.venv` deactivates automatically
