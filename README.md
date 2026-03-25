# Dynamic Thermo-Elastic Mesh Simulation for Parallel Systems

**CMU 15-418 / 15-618 · Spring 2026 · Alan Wang & Allison Chen**

## Project website

- **Live site:** [https://alanwang8.github.io/15418-final-project/](https://alanwang8.github.io/15418-final-project/)
- **Source:** single-page [`docs/index.html`](docs/index.html) with [`docs/style.css`](docs/style.css) (Bulma + custom theme).

### First-time Git push

From the project root:

```bash
git init
git branch -M main
git add docs README.md project-proposal.md "Final Project Proposal.pdf" project-proposal-requirements.pdf .gitignore
git commit -m "Add GitHub Pages site and proposal materials"
```

Create a **new public** repository on [github.com/new](https://github.com/new), then:

```bash
git remote add origin https://github.com/alanwang8/15418-final-project.git
git push -u origin main
```

### Enable GitHub Pages

1. Repo **Settings → Pages** → Deploy from branch **`main`**, folder **`/docs`**.
2. For **Gradescope**, submit a **PDF** of the full proposal that includes the project page URL above.

## Proposal requirements checklist (15-418 §5)

| Requirement | Where satisfied |
|-------------|-----------------|
| Project web page (GitHub OK) | [Live site](https://alanwang8.github.io/15418-final-project/) |
| **TITLE** + two team members | Hero title + Alan Wang, Allison Chen |
| **URL** of project web page | § URL + footer |
| **SUMMARY** (≤2–3 sentences) + parallel systems | § Summary |
| **BACKGROUND** | § Background |
| **THE CHALLENGE** | § Challenges |
| **RESOURCES** | § Resources + References |
| Split **PLAN / HOPE / behind** goals | § Goals and deliverables |
| **PLATFORM CHOICE** | § Platform choice |
| **SCHEDULE** (weekly + milestone) | § Schedule |
| Optional poster demo | § Optional poster demo |
| Gradescope PDF + URL | Your submission |

## Repository layout

```
docs/
  index.html    # Full project + proposal (single page)
  style.css
  assets/
    processor-floor-plan.png
```

Source materials in repo root: `project-proposal.md`, `Final Project Proposal.pdf`, `project-proposal-requirements.pdf`.
