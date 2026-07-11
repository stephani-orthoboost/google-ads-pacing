# Google Ads Pacing Dashboard

An at-a-glance budget-pacing dashboard for your **Live** Google Ads clients.
Self-contained and safe to publish (it holds no credentials and no client
reports) — it reads spend data produced by `build_dashboard_data.py`.

## What it shows
- Every client marked **`Live? = Yes`** in the master sheet that has a Google
  Ads Account ID (24 today). Meta-only Live clients are excluded — this view is
  Google Ads only.
- **Month-to-date spend** vs. where it should be today, per client.
- **Projected end-of-month** spend at the current run-rate, over/under budget.
- **Budgets from the master sheet** — the `Monthly Budget (Google Ads)` column in
  `../supabase/reports/ad_account_mapping.xlsx`. That sheet is the single source
  of truth for the roster *and* budgets, shared with the larger reporting project.

## Where budgets live
Edit the **`Monthly Budget (Google Ads)`** column in
`ad_account_mapping.xlsx` (the same sheet that lists each client's Google/Meta
account IDs and `Live?` flag). Save the sheet, then rerun the build script — the
dashboard picks up the new budgets.

The dashboard also lets you type a **what-if** budget inline to test a pacing
scenario. That override is this-browser-only and does **not** change the sheet;
click **Reset to sheet** to clear it.

## Refresh the data (on your machine)
The script reads the roster + budgets from the master sheet and pulls live spend
using the Google Ads credentials in your `google-ads` repo (sibling folder).

```
cd "C:\Users\steph\repos\google ads pacing"
python build_dashboard_data.py
```

This overwrites `data/dashboard.json` and regenerates `data/budgets.json`. Then
open `index.html` (double-click, or serve the folder) to see live numbers.

- Master sheet path override: `set MASTER_SHEET=C:\path\to\ad_account_mapping.xlsx`
- Credentials repo override: `set GADS_REPO=C:\path\to\google-ads`
- Credentials are read from `<GADS_REPO>/.env`; nothing sensitive is copied here.

## Files
| Path | What it is |
|------|------------|
| `index.html` | The dashboard (static; reads `data/dashboard.json` + `data/budgets.json`). |
| `data/dashboard.json` | Live client list + MTD spend/KPIs + budgets. Overwritten by the script. |
| `data/budgets.json` | **Generated cache** of budgets from the master sheet — do not hand-edit. |
| `build_dashboard_data.py` | Reads roster + budgets from the master sheet, pulls live spend, writes both JSON files. |

The master sheet itself (`../supabase/reports/ad_account_mapping.xlsx`) is **not**
part of this folder and is never published with the dashboard.

## Hosting on GitHub Pages (optional)
Because this folder is separate from the `google-ads` repo, publishing it
exposes only the dashboard — no reports, no credentials.

```
cd "C:\Users\steph\repos\google ads pacing"
git init && git add . && git commit -m "Pacing dashboard"
git branch -M main
git remote add origin https://github.com/<you>/google-ads-pacing.git
git push -u origin main
```

Then Settings → Pages → Deploy from branch → `main` / root.
(GitHub repo names can't contain spaces — use `google-ads-pacing`.)

## Notes
- **Budgets are managed in the master sheet**, so the pacing dashboard and the
  larger `supabase/reports` dashboard stay in agreement on who's Live and what
  each client's budget is — a step toward folding these projects together.
- To auto-refresh daily, a GitHub Action can run the script; that requires
  adding your Google Ads secrets to this repo's Actions secrets, and making the
  master sheet reachable from the Action.
