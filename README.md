# Dynamic Thermo-Elastic Mesh Simulation for Parallel Systems

**CMU 15-418 / 15-618 · Spring 2026 · Allison & Alan**

## Project website

- **Local files:** [`docs/index.html`](docs/index.html) (home), [`docs/proposal.html`](docs/proposal.html) (proposal).
- **Published site (set after GitHub Pages is enabled):** replace this line with your live URL, e.g. `https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/`

### First-time Git push (step 2)

If this folder is not yet a Git repository, run from the project root:

```bash
git init
git branch -M main
git add docs README.md project-proposal.md "Final Project Proposal.pdf" project-proposal-requirements.pdf .gitignore
git commit -m "Add GitHub Pages site and proposal materials"
```

Create a **new public** repository on [github.com/new](https://github.com/new) (empty: no README, no .gitignore, no license—avoids merge conflicts). Then connect and push (use HTTPS or SSH as you prefer):

```bash
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git push -u origin main
```

Log in when Git prompts (browser or token). After the first push, continue with **Enable GitHub Pages** below.

### Step 3 — Put the live URL in the proposal

After Pages finishes building, Settings → Pages will show the site address (usually `https://YOUR_USERNAME.github.io/YOUR_REPO/`). Then:

1. Edit [`docs/proposal.html`](docs/proposal.html) in the **URL** section: set **Project web page** to a real `<a href="...">` link to that address.
2. Replace the published-site line at the top of this README with the same URL.
3. `git add docs/proposal.html README.md && git commit -m "Set published site URL" && git push`

### Enable GitHub Pages

1. Push this repository to GitHub (public).
2. In the repo: **Settings → Pages**.
3. Under **Build and deployment**, set **Source** to **Deploy from a branch**.
4. Choose branch **`main`** (or your default branch) and folder **`/docs`**, then save.
5. Wait for the workflow to finish; note the site URL (often shown at the top of the Pages settings).
6. Update **`docs/proposal.html`**: in the **URL** section, set the project web page link to that URL (and update this README).
7. For **Gradescope**, submit a **PDF** of the full proposal that includes the same URL (export/print the proposal page after the URL is final).

## Proposal requirements checklist (15-418 §5)

Use this list before submitting.

| Requirement | Where satisfied |
|---------------|-----------------|
| Project web page hosted (GitHub or UserWeb OK) | GitHub Pages from `/docs` |
| **Proposal is a link on the site**, not the only page | [`docs/index.html`](docs/index.html) links to [`docs/proposal.html`](docs/proposal.html) |
| **TITLE** + all team members (two students) | `proposal.html` § Title |
| **URL** of project web page | `proposal.html` § URL — **you must fill after publish** |
| **SUMMARY** (≤ 2–3 sentences) + parallel systems | `proposal.html` § Summary |
| **BACKGROUND** (few paragraphs; parallelism benefit) | `proposal.html` § Background |
| **THE CHALLENGE** (workload, dependencies, constraints) | `proposal.html` § The challenge |
| **RESOURCES** (machines, code start, citations) | `proposal.html` § Resources + References |
| **GOALS** — plan to achieve / hope to achieve / if behind | `proposal.html` § Goals and deliverables |
| **PLATFORM CHOICE** | `proposal.html` § Platform choice |
| **SCHEDULE** — ≥ one item per week through poster; milestone noted | `proposal.html` § Schedule |
| Optional: poster live demo described | `proposal.html` § Goals → Optional poster demo |
| Gradescope: PDF of full proposal + URL in writeup | Your submission (not automated here) |

## Repository layout

```
docs/
  index.html      # Project home (future updates/results)
  proposal.html   # Proposal writeup (linked from home)
  style.css
```

Source materials in the repo root: `project-proposal.md`, `Final Project Proposal.pdf`, `project-proposal-requirements.pdf`.
