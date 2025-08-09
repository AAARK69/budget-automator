#!/usr/bin/env python3
import argparse, os, sys, re, yaml
from dateutil import parser as dparser
import pandas as pd
import matplotlib.pyplot as plt

def load_yaml(path, default_text):
    import yaml
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    else:
        return yaml.safe_load(default_text)

def normalize_columns(df):
    df = df.copy()
    cols = {c.lower().strip(): c for c in df.columns}
    need = {"date", "description", "amount"}
    # Try to map common variants
    alias = {
        "posted date": "date",
        "transaction date": "date",
        "details": "description",
        "memo": "description",
        "amount (usd)": "amount",
        "debit": "amount",
        "credit": "amount"
    }
    rev = {v:k for k,v in alias.items()}
    # Lowercase normalized
    lcols = [c.lower().strip() for c in df.columns]
    # Create new mapping
    mapping = {}
    for c_orig, c_low in zip(df.columns, lcols):
        if c_low in need:
            mapping[c_orig] = c_low
        elif c_low in alias:
            mapping[c_orig] = alias[c_low]
        else:
            mapping[c_orig] = c_low
    df.rename(columns=mapping, inplace=True)
    # Check
    if not set(["date","description","amount"]).issubset(set(df.columns)):
        raise SystemExit("CSV must include date, description, amount columns (case-insensitive).")
    return df[["date","description","amount"]]

def categorize(desc, rules):
    d = desc.lower()
    for cat, keywords in rules.items():
        for kw in keywords:
            if kw in d:
                return cat
    return "uncategorized"

def month_filter(df, month):
    if not month:
        return df
    # month format YYYY-MM
    mask = df["date"].dt.strftime("%Y-%m") == month
    return df[mask].copy()

def main():
    p = argparse.ArgumentParser(description="Budget Automator: categorize transactions and create monthly reports")
    p.add_argument("csv_path", help="Path to transactions CSV")
    p.add_argument("--month", help="YYYY-MM to filter (optional)")
    p.add_argument("--categories", default="categories.yml")
    p.add_argument("--config", default="config.yml")
    p.add_argument("--invert", action="store_true", help="Invert amounts if expenses are positive")
    args = p.parse_args()

    # Load configs (fall back to embedded defaults if files missing)
    default_categories = """# Map keywords (lowercase) to categories.
# First match wins; order matters.
groceries: [kroger, whole foods, trader joe, walmart, costco]
dining: [mcdonald, chipotle, starbucks, taco bell, pizza, panera]
transport: [uber, lyft, shell, exxon, chevron, mobil, gas]
shopping: [amazon, target, best buy, nike, adidas]
subscriptions: [netflix, spotify, apple, google storage, prime]
utilities: [verizon, xfinity, comcast, at&t, t-mobile, spectrum]
health: [cvs, walgreens, rite aid, walgreens]
education: [udemy, coursera, khan academy]
income: [payroll, paycheck, direct deposit, employer]
"""
    default_config = """currency: USD
income_keywords: [payroll, paycheck, employer, direct deposit]
"""
    cat_rules = load_yaml(args.categories, default_categories)
    cfg = load_yaml(args.config, default_config)
    currency = cfg.get("currency", "USD")

    # Load CSV
    df = pd.read_csv(args.csv_path)
    df = normalize_columns(df)
    # Parse dates
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    if df["date"].isna().any():
        raise SystemExit("Some dates could not be parsed. Please ensure 'date' column is valid.")
    # Clean description
    df["description"] = df["description"].astype(str).str.strip()
    # Amounts
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    if df["amount"].isna().any():
        raise SystemExit("Some amounts could not be parsed as numbers.")
    if args.invert:
        df["amount"] = -df["amount"]

    # Categorize
    df["category"] = df["description"].apply(lambda s: categorize(s, cat_rules))

    # Determine credits vs debits
    df["type"] = df["amount"].apply(lambda x: "income" if x > 0 else "expense" if x < 0 else "neutral")

    # Month filter
    if args.month:
        df = month_filter(df, args.month)
        if df.empty:
            raise SystemExit(f"No transactions found for {args.month}.")

    # Aggregations
    total_income = df.loc[df["type"] == "income", "amount"].sum()
    total_expense = -df.loc[df["type"] == "expense", "amount"].sum()  # positive number
    savings = total_income - total_expense
    savings_rate = (savings / total_income * 100) if total_income > 0 else 0.0

    by_cat = df.groupby("category")["amount"].sum().sort_values()
    # For expenses, make positive for charting
    expenses_by_cat = (-df[df["type"]=="expense"].groupby("category")["amount"].sum()).sort_values()

    # Outputs
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("plots", exist_ok=True)

    # CSV summaries
    month_tag = args.month or "ALL"
    df.to_csv(f"outputs/transactions_{month_tag}.csv", index=False)
    expenses_by_cat.to_csv(f"outputs/category_expenses_{month_tag}.csv", header=["amount"])

    # Markdown report
    md = [
        f"# Monthly Report — {month_tag}",
        "",
        f"- **Income:** {currency} {total_income:,.2f}",
        f"- **Expenses:** {currency} {total_expense:,.2f}",
        f"- **Savings:** {currency} {savings:,.2f}",
        f"- **Savings Rate:** {savings_rate:.1f}%",
        "",
        "## Top Expense Categories",
        "",
    ]
    for cat, amt in expenses_by_cat.sort_values(ascending=False).head(10).items():
        md.append(f"- {cat}: {currency} {amt:,.2f}")
    md.append("")
    md.append("## Notes")
    md.append("- Categorization is keyword-based; adjust `categories.yml` as needed.")
    md.append("- Use `--invert` if your bank exports expenses as positive numbers.")
    with open(f"outputs/monthly_report_{month_tag}.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    # Plot
    if len(expenses_by_cat) > 0:
        plt.figure()
        expenses_by_cat.plot(kind="barh")
        plt.title(f"Expenses by Category — {month_tag}")
        plt.xlabel(f"Amount ({currency})")
        plt.tight_layout()
        plot_path = f"plots/expenses_by_category_{month_tag}.png"
        plt.savefig(plot_path, dpi=160)
        plt.close()

    print(f"Done. Income={total_income:.2f} Expenses={total_expense:.2f} SavingsRate={savings_rate:.1f}%")
    print(f"Wrote outputs/monthly_report_{month_tag}.md and CSV/plot files.")
    
if __name__ == "__main__":
    main()
