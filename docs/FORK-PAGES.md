# Publish a public Pages copy without leaking private apps

Use this only when **this** repo cannot serve GitHub Pages.

As of **2026-09-22** the preferred fix is simpler: [Treyu2023/FAFO-Power-Toolbox](https://github.com/Treyu2023/FAFO-Power-Toolbox) is **public**, and [https://treyu2023.github.io/FAFO-Power-Toolbox/](https://treyu2023.github.io/FAFO-Power-Toolbox/) 404s because Pages is not enabled. Turn it on (Settings → Pages → Deploy from branch → `main` → `/ (root)`). Do not create a second repo for that.

Use the steps below when Pages still cannot run here — for example the repo is **private** on a plan that does not include private Pages, or an org policy blocks Pages on this remote.

## Do not press Fork

A GitHub **Fork** copies **all history**. These paths are gitignored now and are **not** in the current `HEAD` tree, but they **were committed** earlier:

- `Investor Portal.html`
- `Business Tax Preparedness/` (TaxForge)

Pages itself only serves the branch tip, so enabling Pages on the current `main` does not upload those files. A fork (or any push of the old history) puts them on a public commit list. Do not do that.

Also never copy `server/security_config.json`, `.env`, or anything under a `Secrets` directory. `.gitignore` already excludes them. Confirm before you publish:

```bash
git check-ignore -v -- "Investor Portal.html" "Business Tax Preparedness/" server/security_config.json .env
git ls-files -- "Investor Portal.html" "Business Tax Preparedness" server/security_config.json
git cat-file -e "HEAD:Investor Portal.html"   # must fail
```

`git ls-files` should print nothing. `git check-ignore` should list `.gitignore` rules.

## Fresh public tree (no history)

From a machine that already has the private checkout, export **only the current files**, then push to a new empty public repo.

```bash
# Shallow clone = current tip only, not old Investor Portal commits
git clone --depth 1 git@github.com:Treyu2023/FAFO-Power-Toolbox.git fafo-pages-export
cd fafo-pages-export

# Belt and suspenders — these must not be in the export
rm -rf "Investor Portal.html" "Business Tax Preparedness" \
  server/investor_ops.py server/xero_ops.py \
  server/_private_investor_routes.py server/_private_xero_routes.py \
  server/security_config.json .env

test ! -e "Investor Portal.html"
test ! -d "Business Tax Preparedness"
test ! -e server/security_config.json

rm -rf .git
git init -b main
git add -A
git status   # stop if Investor Portal, TaxForge, or security_config.json appear
git commit -m "Publish FAFO Power Toolbox static site"
# Create an EMPTY public repo first (GitHub → New → Public, no README)
git remote add origin git@github.com:Treyu2023/FAFO-Power-Toolbox-Pages.git
git push -u origin main
```

Then on **that** public repo: Settings → Pages → Deploy from branch → `main` → `/ (root)`.

The site URL will be `https://treyu2023.github.io/FAFO-Power-Toolbox-Pages/` (or whatever the new repo is named). `index.html` and `.nojekyll` are already in the tree so names with spaces keep working.

Keep the real toolbox development on `Treyu2023/FAFO-Power-Toolbox`. The Pages repo is a publish mirror, not a second place to edit.
