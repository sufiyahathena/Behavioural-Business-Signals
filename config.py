import os

# API Keys — set these as environment variables, never hardcode
FMP_API_KEY = os.environ.get("FMP_API_KEY", "")
REDDIT_CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_USER_AGENT = "behavioural-business-signals/1.0"
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# Paths
DATA_DIR = "data"
FINANCIAL_DIR = "data/financial"
BEHAVIOURAL_DIR = "data/behavioural"
SCORES_DIR = "data/scores"

# Scoring weights — Financial (must sum to 1.0)
FINANCIAL_WEIGHTS = {
    "revenue_growth":    0.15,
    "gross_margin":      0.10,
    "operating_margin":  0.12,
    "net_profit_margin": 0.06,
    "fcf_margin":        0.11,
    "debt_to_equity":    0.08,
    "current_ratio":     0.07,
    "roe":               0.10,
    "roa":               0.15,
    "interest_coverage": 0.06,
}

# Behavioural scoring — bucket base weights (computed dynamically per company)

# Consumer Experience and Trust bucket (total = 42%)
CONSUMER_WEIGHTS_HIGH_CONFIDENCE = {
    "trustpilot_rating": 0.20,
    "app_rating":        0.22,
}
CONSUMER_WEIGHTS_LOW_CONFIDENCE = {
    "trustpilot_rating": 0.12,
    "app_rating":        0.30,
}
TRUSTPILOT_CONFIDENCE_THRESHOLD = 100  # reviews

# Employee Culture and Leadership bucket (total = 30%)
EMPLOYEE_WEIGHTS = {
    "glassdoor_overall":      0.10,
    "glassdoor_ceo_approval": 0.08,
    "glassdoor_recommend":    0.12,
}

# Brand Momentum bucket (total = 28%)
MOMENTUM_WEIGHTS_US = {
    "google_trends_score_us":     0.15,
    "google_trends_score_global": 0.00,
    "youtube_subscribers":        0.13,
}
MOMENTUM_WEIGHTS_GLOBAL = {
    "google_trends_score_us":     0.00,
    "google_trends_score_global": 0.15,
    "youtube_subscribers":        0.13,
}
MOMENTUM_WEIGHTS_MIXED = {
    "google_trends_score_us":     0.075,
    "google_trends_score_global": 0.075,
    "youtube_subscribers":        0.13,
}

# Company geography classification for Google Trends weighting
COMPANY_GEOGRAPHY = {
    # Primarily US-focused
    "ULTA": "us", "SBH": "us", "AEO": "us", "ANF": "us",
    "GAP":  "us", "RVLV": "us", "ELF": "us",
    # Primarily global
    "LRLCY": "global", "BIRK": "global", "ONON": "global",
    "OLPX":  "global", "COTY": "global",
    # Mixed
    "EL": "mixed", "LULU": "mixed", "RL": "mixed", "LEVI": "mixed",
    "ODD": "mixed", "URBN": "mixed", "COLM": "mixed",
}

# YouTube proxy companies — channel represents a subsidiary brand, not the full company
# These receive a modest confidence discount on their YouTube weight
YOUTUBE_PROXY_TICKERS = {"COTY", "ODD"}
YOUTUBE_PROXY_DISCOUNT = 0.85  # 85% of normal YouTube weight

# Google Trends settings
TRENDS_TIMEFRAME = "today 12-m"
TRENDS_GEO_US = "US"
TRENDS_GEO_GLOBAL = ""

# UI settings
UI_HOST = "127.0.0.1"
UI_PORT = 5000
UI_DEBUG = True
