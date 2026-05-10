# API Keys — fill in before running collectors
FMP_API_KEY = ""
REDDIT_CLIENT_ID = ""
REDDIT_CLIENT_SECRET = ""
REDDIT_USER_AGENT = "behavioural-business-signals/1.0"

# Paths
DATA_DIR = "data"
FINANCIAL_DIR = "data/financial"
BEHAVIOURAL_DIR = "data/behavioural"
SCORES_DIR = "data/scores"

# Scoring weights — Financial (must sum to 1.0)
FINANCIAL_WEIGHTS = {
    "revenue_growth": 0.15,
    "gross_margin": 0.12,
    "operating_margin": 0.12,
    "net_profit_margin": 0.10,
    "fcf_margin": 0.12,
    "debt_to_equity": 0.10,
    "current_ratio": 0.06,
    "roe": 0.10,
    "roa": 0.06,
    "interest_coverage": 0.07,
}

# Scoring weights — Behavioural (must sum to 1.0)
BEHAVIOURAL_WEIGHTS = {
    "google_trends_score": 0.20,
    "trustpilot_rating": 0.15,
    "trustpilot_review_count": 0.05,
    "app_rating": 0.10,
    "reddit_sentiment": 0.15,
    "glassdoor_overall": 0.15,
    "glassdoor_ceo_approval": 0.10,
    "glassdoor_recommend": 0.10,
}

# Google Trends settings
TRENDS_TIMEFRAME = "today 12-m"
TRENDS_GEO = "US"

# UI settings
UI_HOST = "127.0.0.1"
UI_PORT = 5000
UI_DEBUG = True
