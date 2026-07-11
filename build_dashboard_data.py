"""Builds the pacing dashboard's data file from live Google Ads.

Roster + budgets come from the shared master sheet
`../supabase/reports/ad_account_mapping.xlsx` (the same sheet that drives the
larger reporting project). Every row flagged **Live?=Yes** that has a Google
Ads Account ID is pulled for this month's spend + KPIs, and the
"Monthly Budget (Google Ads)" column becomes each client's pacing budget.

Google Ads credentials are resolved in this order:
  1. Environment variables (GOOGLE_ADS_* ...) -- used by GitHub Actions.
  2. <GADS_REPO>/.env  -- used when you run this locally.
     GADS_REPO defaults to the sibling folder ../google-ads
     (override with the GADS_REPO env var if it lives elsewhere).

Overrides:
  MASTER_SHEET  path to ad_account_mapping.xlsx (default: ../supabase/reports/…)
  GADS_REPO     folder holding the Google Ads .env credentials

Run from this folder:  python build_dashboard_data.py
"""
import os
import json
import calendar
import datetime as dt

import openpyxl
from dotenv import dotenv_values
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUT_FILE = os.path.join(HERE, "data", "dashboard.json")
BUDGETS_FILE = os.path.join(HERE, "data", "budgets.json")

# Google Ads credentials live in the sibling google-ads repo.
GADS_REPO = os.environ.get("GADS_REPO") or os.path.join(HERE, "..", "google-ads")

# The master client roster + budgets (shared with the supabase/reports project).
MASTER_SHEET = os.environ.get("MASTER_SHEET") or os.path.join(
    HERE, "..", "supabase", "reports", "ad_account_mapping.xlsx")
MASTER_TAB = "Client Overview"

QUERY = """
    SELECT metrics.cost_micros, metrics.clicks, metrics.conversions
    FROM customer
    WHERE segments.date DURING THIS_MONTH
"""


def fmt_cid(cid):
    d = "".join(ch for ch in str(cid) if ch.isdigit())
    return f"{d[0:3]}-{d[3:6]}-{d[6:]}" if len(d) == 10 else str(cid)


def shared_credentials():
    keys = [
        "GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID",
        "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN",
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
    ]
    if all(os.environ.get(k) for k in keys):
        env = {k: os.environ[k] for k in keys}
    else:
        env = dotenv_values(os.path.join(GADS_REPO, ".env"))
    return {
        "developer_token": env.get("GOOGLE_ADS_DEVELOPER_TOKEN"),
        "client_id": env.get("GOOGLE_ADS_CLIENT_ID"),
        "client_secret": env.get("GOOGLE_ADS_CLIENT_SECRET"),
        "refresh_token": env.get("GOOGLE_ADS_REFRESH_TOKEN"),
        "login_customer_id": env.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID"),
        "use_proto_plus": True,
    }


def _num(v):
    """Coerce a spreadsheet cell to a positive float, or None."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v) if v > 0 else None
    s = str(v).replace("$", "").replace(",", "").strip()
    try:
        f = float(s)
        return f if f > 0 else None
    except ValueError:
        return None


def roster_from_sheet():
    """Read Live clients (with a Google Ads ID) + budgets from the master sheet.

    Returns a list of dicts: {name, customer_id (digits), budget|None}.
    """
    wb = openpyxl.load_workbook(MASTER_SHEET, data_only=True)
    ws = wb[MASTER_TAB]
    rows = list(ws.iter_rows(values_only=True))
    header = [str(c).strip() if c is not None else "" for c in rows[0]]

    def col(name):
        return header.index(name)

    i_name = col("Client (Supabase)")
    i_live = col("Live?")
    i_gid = col("Google Ads Account ID")
    i_budget = col("Monthly Budget (Google Ads)")

    roster = []
    for r in rows[1:]:
        if str(r[i_live]).strip().lower() != "yes":
            continue
        gid = "".join(ch for ch in str(r[i_gid] or "") if ch.isdigit())
        if len(gid) != 10:
            continue  # Meta-only Live client — not in a Google Ads pacing view
        roster.append({
            "name": str(r[i_name]).strip(),
            "customer_id": gid,
            "budget": _num(r[i_budget]),
        })
    roster.sort(key=lambda a: a["name"])
    return roster


def write_budgets_cache(accounts):
    """Regenerate data/budgets.json from the sheet (a read-only cache).

    Budgets are managed in the master sheet; this file just lets the static
    dashboard read them without parsing xlsx in the browser.
    """
    budgets = {a["customer_id_fmt"]: {"name": a["name"], "monthly": a["budget"]}
               for a in accounts}
    out = {
        "_comment": ("GENERATED FILE — do not hand-edit. Monthly Google Ads budget "
                     "per client, keyed by customer ID. Source of truth is the "
                     "'Monthly Budget (Google Ads)' column in "
                     "ad_account_mapping.xlsx; rerun build_dashboard_data.py to refresh."),
        "source": "ad_account_mapping.xlsx :: Client Overview",
        "budgets": dict(sorted(budgets.items(), key=lambda kv: kv[1]["name"])),
    }
    os.makedirs(os.path.dirname(BUDGETS_FILE), exist_ok=True)
    with open(BUDGETS_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    n_set = sum(1 for a in accounts if a["budget"])
    print(f"Wrote {BUDGETS_FILE}: {len(accounts)} clients, {n_set} with a budget set")


def main():
    config = shared_credentials()
    today = dt.date.today()
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    frac = round(today.day / days_in_month, 4)

    roster = roster_from_sheet()
    print(f"Roster: {len(roster)} Live Google Ads clients from {os.path.basename(MASTER_SHEET)}\n")

    accounts = []
    for entry in roster:
        name, customer_id, budget = entry["name"], entry["customer_id"], entry["budget"]
        client = GoogleAdsClient.load_from_dict(config)
        ga = client.get_service("GoogleAdsService")
        cost = clicks = conv = 0.0
        try:
            for row in ga.search(customer_id=customer_id, query=QUERY):
                cost += row.metrics.cost_micros / 1_000_000
                clicks += row.metrics.clicks
                conv += row.metrics.conversions
        except GoogleAdsException as e:
            print(f"  [warn] {name} ({customer_id}): {e.error.code().name}")

        accounts.append({
            "customer_id": fmt_cid(customer_id),
            "customer_id_fmt": fmt_cid(customer_id),
            "name": name,
            "budget": budget,
            "mtd_spend": round(cost, 2),
            "clicks": int(clicks),
            "conversions": round(conv, 1),
            "cost_per_conv": round(cost / conv, 2) if conv else None,
            "google_ads_url": f"https://ads.google.com/aw/overview?ocid={customer_id}",
        })
        b = f"budget ${budget:,.0f}" if budget else "no budget"
        print(f"{name}: ${cost:,.2f} MTD, {int(clicks)} clicks, {conv:g} conv ({b})")

    accounts.sort(key=lambda a: a["mtd_spend"], reverse=True)
    data = {
        "generated_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z",
        "awaiting_refresh": False,
        "budget_source": "ad_account_mapping.xlsx",
        "period": {
            "month_label": today.strftime("%B %Y"),
            "day_of_month": today.day,
            "days_in_month": days_in_month,
            "month_fraction_elapsed": frac,
        },
        "accounts": accounts,
    }
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    total = sum(a["mtd_spend"] for a in accounts)
    print(f"\nWrote {OUTPUT_FILE}: {len(accounts)} accounts, ${total:,.0f} MTD spend")
    write_budgets_cache(accounts)


if __name__ == "__main__":
    main()
