# GitHub Pages setup

The site is served from the **`docs/`** folder. Enable it once in the repo:

1. On GitHub open **https://github.com/bhavink/databricksIPranges**
2. **Settings** → in the left sidebar **Pages** (under "Code and automation")
3. Under **Build and deployment** → **Source**: choose **Deploy from a branch**
4. **Branch**: `main` (or your default branch)
5. **Folder**: **`/docs`**
6. Click **Save**

The site will be available at **https://bhavink.github.io/databricksIPranges/** after a minute or two.

**Note:** Pushes from the "Update IP ranges" GitHub Action may not always trigger a new Pages build when using the default token. If the site doesn’t update after the weekly run, push a small change to `main` (e.g. an empty commit) or re-run the workflow and wait; or configure a [PAT or workflow that deploys Pages](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).
