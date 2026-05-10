# Behavioural Business Signals

A dual-score business analytics framework that evaluates 19 publicly traded beauty and fashion companies using both financial performance metrics and behavioural signals from consumers, employees, and market attention.

## Project Overview

Behavioural Business Signals compares what the numbers say with what people actually do. For each of the 19 companies in the beauty, fashion, and apparel sectors, it produces two independent scores: a Financial Health and Performance Score derived from 10 traditional financial metrics, and a Behavioural Business Quality Score built from consumer sentiment, employee feedback, app ratings, brand search interest, and social media discussion. The primary analytical question is where the two scores agree — and more interestingly, where they diverge.

## Setup

```bash
# 1. Clone or navigate to the project directory
cd behavioural-business-signals

# 2. Install dependencies
pip install -r requirements.txt

# 3. Fill in API keys in config.py
#    FMP_API_KEY      — Financial Modeling Prep (optional, yfinance is the default)
#    REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET — Reddit API app credentials
```

## Running the Scorers

```bash
# Run both scorers
python main.py score --all

# Run only the financial scorer
python main.py score --financial

# Run only the behavioural scorer
python main.py score --behavioural
```

Scores are saved to `data/scores/financial_scores.csv` and `data/scores/behavioural_scores.csv`. A summary table is printed to the terminal after each run.

## Running the UI

```bash
python main.py ui
```

Open your browser at `http://127.0.0.1:5000`. The dashboard displays a scoreboard for all 19 companies with their financial and behavioural scores and a quadrant classification. No additional setup is required.

## Data Sources

| Source | Type | Method |
|--------|------|--------|
| yfinance | Financial statements | Free, automatic |
| Financial Modeling Prep | Financial statements | API key required (optional fallback) |
| Google Trends (pytrends) | Brand search interest | Free, automatic |
| Trustpilot | Consumer ratings | Web scraping |
| Apple App Store | App ratings | app-store-scraper |
| Google Play Store | App ratings | google-play-scraper |
| Reddit (PRAW) | Brand sentiment | API key required |
| Glassdoor | Employee feedback | **Manual collection** |

## Financial Metrics Scored

| Metric | Description |
|--------|-------------|
| `revenue_growth` | Year-over-year revenue growth rate — measures top-line momentum |
| `gross_margin` | Gross profit as a % of revenue — indicates pricing power and cost efficiency |
| `operating_margin` | Operating income as a % of revenue — reflects operational leverage |
| `net_profit_margin` | Net income as a % of revenue — overall bottom-line profitability |
| `fcf_margin` | Free cash flow as a % of revenue — quality of earnings and cash conversion |
| `debt_to_equity` | Total debt divided by shareholder equity — leverage risk (lower is better) |
| `current_ratio` | Current assets divided by current liabilities — short-term liquidity |
| `roe` | Return on equity — efficiency of shareholder capital deployment |
| `roa` | Return on assets — efficiency of total asset base |
| `interest_coverage` | EBIT divided by interest expense — debt servicing capacity |

All metrics are min-max normalised to [0, 1] before weighting. `debt_to_equity` is inverted so that lower debt scores higher.

## Behavioural Metrics Scored

| Metric | Description |
|--------|-------------|
| `google_trends_score` | Average weekly Google Trends search interest (US, last 12 months) |
| `trustpilot_rating` | Overall Trustpilot star rating (1–5 scale) |
| `trustpilot_review_count` | Total number of Trustpilot reviews — signal of consumer engagement volume |
| `app_rating` | Average App Store / Google Play rating (1–5 scale) |
| `reddit_sentiment` | Mean VADER compound sentiment score from Reddit brand mentions, mapped to [0, 1] |
| `glassdoor_overall` | Overall Glassdoor employee rating (1–5 scale) |
| `glassdoor_ceo_approval` | % of Glassdoor reviewers who approve of the CEO |
| `glassdoor_recommend` | % of Glassdoor reviewers who would recommend the company to a friend |

## Glassdoor Data

Glassdoor does not offer a public API, so employee ratings are manually collected and stored in `data/behavioural/glassdoor_manual.csv`.

**CSV schema:**

| Column | Description |
|--------|-------------|
| `ticker` | Stock ticker symbol |
| `company_name` | Company display name |
| `overall_rating` | Overall rating (1.0–5.0) |
| `recommend_to_friend_pct` | % who would recommend (0–100) |
| `ceo_approval_pct` | % who approve of CEO (0–100) |
| `culture_rating` | Culture & Values sub-rating (1.0–5.0) |
| `diversity_rating` | Diversity & Inclusion sub-rating (1.0–5.0) |
| `work_life_balance_rating` | Work-Life Balance sub-rating (1.0–5.0) |
| `senior_management_rating` | Senior Management sub-rating (1.0–5.0) |
| `compensation_rating` | Compensation & Benefits sub-rating (1.0–5.0) |
| `last_updated` | Date of manual collection (YYYY-MM-DD) |

Refresh quarterly. Zero values in the CSV are treated as missing and filled with column medians during scoring.

## Project Structure

```
behavioural-business-signals/
├── data/
│   ├── companies.json          # 19 companies with full metadata
│   ├── financial/              # Raw financial data CSVs (generated by collector)
│   ├── behavioural/
│   │   └── glassdoor_manual.csv
│   └── scores/                 # Scored output CSVs (generated by scorers)
├── collectors/
│   ├── financial_collector.py  # yfinance + FMP financial data (stubs)
│   ├── trends_collector.py     # Google Trends via pytrends (stubs)
│   ├── reddit_collector.py     # Reddit sentiment via PRAW (stubs)
│   ├── trustpilot_collector.py # Trustpilot web scraper (stubs)
│   └── appstore_collector.py   # App Store + Google Play ratings (stubs)
├── processors/
│   ├── normaliser.py           # Min-max normalisation utilities
│   ├── financial_scorer.py     # Financial scoring pipeline
│   └── behavioural_scorer.py   # Behavioural scoring pipeline
├── ui/
│   ├── app.py                  # Flask app with routes
│   ├── templates/index.html    # Dashboard HTML template
│   └── static/style.css        # Self-contained CSS
├── notebooks/
│   └── analysis.ipynb          # Exploratory analysis notebook
├── main.py                     # CLI entrypoint
├── config.py                   # API keys, paths, and scoring weights
└── requirements.txt
```

## Notes

- **L'Oréal (LRLCY)** trades as a US ADR. Some financial APIs may require the Paris ticker (`OR.PA`) for complete data. yfinance generally handles LRLCY, but verify coverage before running.
- **Oddity Tech (ODD)** and **Birkenstock (BIRK)** are recent IPOs (both 2023). Historical financial data may be limited to 2–3 years, which can affect growth metric calculations.
- **Behavioural scores will be incomplete** until the collector stubs are implemented. The scorer handles missing data gracefully by substituting column medians — scores will reflect available data only.
- **Scoring weights** can be adjusted in `config.py`. Both `FINANCIAL_WEIGHTS` and `BEHAVIOURAL_WEIGHTS` must each sum to 1.0.
