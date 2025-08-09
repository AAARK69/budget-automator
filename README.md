# Budget Automator

Parses bank CSVs, auto-categorizes spend, and outputs monthly reports with savings rate & trends.

## Features
- Keyword-based auto-categorization (configurable via `categories.yml`)
- Handles credits (income) and debits (expenses)
- Monthly rollups: income, expenses, savings, savings rate
- Category breakdown CSVs + Markdown report
- Optional PNG bar chart (matplotlib)

## Quick Start

```bash
# 1) Create venv (recommended)
python -m venv .venv && . .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2) Install requirements
pip install -r requirements.txt

# 3) Run on sample data (2025-07)
python budget_automator.py sample/transactions.csv --month 2025-07

# 4) See outputs
open outputs/monthly_report_2025-07.md   # Windows: type outputs\monthly_report_2025-07.md
```

## CSV Format
Expected columns (header case-insensitive):
- `date` — transaction date (e.g., 2025-07-12)
- `description` — merchant / memo
- `amount` — negative for expense, positive for income (auto-detectable via `--invert`)

If your bank exports expenses as positive values, run with `--invert` to flip signs.

## Configuration
- `categories.yml` maps **keywords** to **categories**. First match wins.
- `config.yml` lets you set currency and optional income keywords.

## CLI
```bash
python budget_automator.py <csv_path> [--month YYYY-MM] [--categories categories.yml] [--config config.yml] [--invert]
```

## License
MIT
