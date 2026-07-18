# OrthoBoost Keyword Generator

STAG combination research tool — builds a copy-ready keyword list to check
volume in Keyword Planner before deciding what becomes an ad group. Fully
static: open `keyword-generator.html` (or the GitHub Pages URL).

| Path | What it is |
|------|------------|
| `keyword-generator.html` | The tool. |
| `data/keyword_generator.json` | Seed lists (services, modifiers, cities). |
| `index.html` | Redirect stub to the keyword generator. |

## Where did the pacing dashboard go?

The budget pacing dashboard that used to live here was merged into the
**OrthoBoost Ads Tools** app in the `fluency` repo (2026-07-18) — it's the
"Budget Pacing" section there, refreshed from the app itself. Budgets are
still managed in the master sheet (`../supabase/reports/ad_account_mapping.xlsx`,
"Monthly Budget (Google Ads)" column). The old build script and data files
were removed from this repo; they remain in git history if ever needed.
