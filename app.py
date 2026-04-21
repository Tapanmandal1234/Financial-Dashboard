## ============================================================
## BBS NONPROFIT FINANCIAL HEALTH DASHBOARD
## Bridge Builder Strategies — BRIDGE Project
## Author: Tapan Mandal
## Version: 3.0 — Final Prototype
## ============================================================
## WHAT'S IN THIS FILE (13 SECTIONS):
##   1. Imports
##   2. Page configuration
##   3. Custom CSS (BBS color scheme)
##   4. Config (all weights, benchmarks, thresholds)
##   5. Validation functions
##   6. Ratio calculations
##   7. Tier scoring
##   8. Composite scoring + contribution breakdown
##   9. Scenario engine + band change + breakpoint detection
##  10. Formatting helpers
##  11. Excel export (7 tabs including full AI Framework)
##  12. Streamlit UI
##  13. Methodology expander
## ============================================================


## ============================================================
## SECTION 1 — IMPORTS
## ============================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO
from datetime import date
import os


## ============================================================
## SECTION 2 — PAGE CONFIGURATION
## Must be the first Streamlit command.
## ============================================================

st.set_page_config(
    page_title="BBS Financial Health Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)


## ============================================================
## SECTION 3 — CUSTOM CSS
## BBS color scheme: dark navy background, BBS green accent,
## BBS orange secondary. Does not affect calculations.
## ============================================================

st.markdown("""
<style>
    /* ── Core backgrounds ── */
    .main { background-color: #0D1B2A; }
    .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
    section[data-testid="stSidebar"] { background-color: #0D1B2A; }

    /* ── Metric cards ── */
    [data-testid="metric-container"] {
        background: #132030;
        border-radius: 10px;
        padding: 14px;
        border: 1px solid rgba(255,255,255,0.07);
    }

    /* ── Dataframes ── */
    [data-testid="stDataFrame"] {
        border-radius: 8px;
        overflow: hidden;
    }

    /* ── Primary calculate button ── */
    [data-testid="baseButton-primary"] {
        background: #2E8B57 !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: none !important;
        letter-spacing: 0.02em !important;
    }
    [data-testid="baseButton-primary"]:hover {
        background: #26734A !important;
    }

    /* ── Secondary buttons ── */
    [data-testid="baseButton-secondary"] {
        border-radius: 8px !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
    }

    /* ── Number inputs ── */
    [data-testid="stNumberInput"] input {
        background: #132030 !important;
        border-radius: 6px !important;
        color: #E8EAF0 !important;
    }

    /* ── Selectboxes ── */
    [data-testid="stSelectbox"] > div > div {
        background: #132030 !important;
        border-radius: 6px !important;
    }

    /* ── Expander ── */
    [data-testid="stExpander"] {
        background: #132030;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.07) !important;
    }

    /* ── Divider ── */
    hr { border-color: rgba(255,255,255,0.07) !important; }

    /* ── Section headers ── */
    h2 {
        border-bottom: 2px solid #2E8B57;
        padding-bottom: 6px;
        margin-top: 6px !important;
        color: #E8EAF0 !important;
    }
    h3 { color: #E8EAF0 !important; }

    /* ── Caption text ── */
    .stCaption { color: #6B7A8E !important; }

    /* ── Warning / info / error boxes ── */
    [data-testid="stAlert"] { border-radius: 8px !important; }

    /* ── Checkboxes ── */
    [data-testid="stCheckbox"] label { color: #8A95A8 !important; }

    /* ── Radio buttons ── */
    [data-testid="stRadio"] label { color: #C0C8D4 !important; }

    /* ── Slider ── */
    [data-testid="stSlider"] { padding-top: 4px; }

    /* ── Tab-style section highlight ── */
    .bbs-section {
        background: #132030;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
        border: 1px solid rgba(255,255,255,0.07);
    }
</style>
""", unsafe_allow_html=True)


## ============================================================
## SECTION 4 — CONFIG
## Every number a supervisor might change lives here.
## Nothing hardcoded in calculation functions.
## ============================================================

## -- Dimension weights --
## Sustainability = can the org keep operating under pressure?
## Efficiency     = is spending aligned with mission?
## Solvency       = is the balance sheet structurally sound?
DIMENSION_WEIGHTS = {
    "sustainability": 0.40,
    "efficiency":     0.35,
    "solvency":       0.25
}

## -- Dimension → ratio mapping --
DIMENSIONS = {
    "sustainability": ["operating_surplus_margin", "revenue_growth_rate", "months_runway"],
    "efficiency":     ["program_efficiency", "admin_expense_pct", "fundraising_efficiency"],
    "solvency":       ["working_capital_ratio", "debt_ratio"]
}

## -- Dimension display colors (BBS palette) --
DIMENSION_COLORS = {
    "sustainability": "#2E8B57",   ## BBS green
    "efficiency":     "#7C5CBF",   ## purple
    "solvency":       "#2F6FA8"    ## blue
}

## -- Floor rule: program efficiency below this triggers warning --
FLOOR_RULE_THRESHOLD = 0.50

## -- Revenue concentration flag thresholds --
## Pending supervisor confirmation — defaults used
CONCENTRATION_ELEVATED = 0.30   ## > 30% single funder = elevated
CONCENTRATION_CRITICAL = 0.40   ## > 40% single funder = critical

## -- Fundraising proxy overstatement threshold --
## Ratio above 50:1 almost certainly reflects wrong numerator
FUNDRAISING_PROXY_WARNING = 50.0

## -- Score bands --
SCORE_BANDS = {
    "Strong":     (80, 100),
    "Stable":     (60, 79),
    "Watchlist":  (40, 59),
    "Distressed": (0,  39)
}

BAND_COLORS = {
    "Strong":     "#4CAF82",
    "Stable":     "#2E8B57",
    "Watchlist":  "#E8A020",
    "Distressed": "#E05050"
}

## -- Benchmarks per ratio --
## direction: "higher" = bigger value is better
##            "lower"  = smaller value is better (inverted)
## Thresholds grounded in Charity Navigator + NFF methodology.
BENCHMARKS = {
    "program_efficiency": {
        "label":       "Program Efficiency",
        "direction":   "higher",
        "excellent":   0.75, "strong": 0.65, "average": 0.50,
        "format":      "percent",
        "dimension":   "efficiency",
        "description": "% of total spending directed to mission programs",
        "note":        None
    },
    "admin_expense_pct": {
        "label":       "Admin Expense %",
        "direction":   "lower",
        "excellent":   0.15, "strong": 0.20, "average": 0.30,
        "format":      "percent",
        "dimension":   "efficiency",
        "description": "% of total spending on overhead and administration",
        "note":        "Benchmark reflects sector median (~15–20%). Complex multi-program organizations with infrastructure costs typically range 20–28%. Average rating does not automatically indicate inefficiency."
    },
    "fundraising_efficiency": {
        "label":       "Fundraising Efficiency",
        "direction":   "higher",
        "excellent":   5.0, "strong": 3.0, "average": 2.0,
        "format":      "dollar",
        "dimension":   "efficiency",
        "description": "Revenue generated per $1 spent on fundraising",
        "note":        None
    },
    "operating_surplus_margin": {
        "label":       "Operating Surplus Margin",
        "direction":   "higher",
        "excellent":   0.10, "strong": 0.05, "average": 0.00,
        "format":      "percent",
        "dimension":   "sustainability",
        "description": "Net surplus or deficit as % of total revenue",
        "note":        "For organizations with investment portfolios, this figure includes investment returns which are not operationally generated. Operational margin may be substantially lower than reported."
    },
    "working_capital_ratio": {
        "label":       "Working Capital Ratio",
        "direction":   "higher",
        "excellent":   0.50, "strong": 0.25, "average": 0.08,
        "format":      "months_wc",
        "dimension":   "solvency",
        "description": "Months of operating buffer from working capital",
        "note":        None
    },
    "debt_ratio": {
        "label":       "Debt Ratio",
        "direction":   "lower",
        "excellent":   0.25, "strong": 0.40, "average": 0.60,
        "format":      "percent",
        "dimension":   "solvency",
        "description": "% of total assets financed by debt",
        "note":        None
    },
    "revenue_growth_rate": {
        "label":       "Revenue Growth Rate",
        "direction":   "higher",
        "excellent":   0.10, "strong": 0.05, "average": 0.00,
        "format":      "percent",
        "dimension":   "sustainability",
        "description": "Year-over-year revenue growth",
        "note":        "Includes restricted grant revenue. For high grant-concentration organizations this may overstate sustainable growth."
    },
    "months_runway": {
        "label":       "Months of Operating Runway",
        "direction":   "higher",
        "excellent":   6.0, "strong": 3.0, "average": 1.0,
        "format":      "months",
        "dimension":   "sustainability",
        "description": "Months org could operate on current assets if revenue stopped",
        "note":        "Calculated from total current assets. For precision use liquid assets available for general use from audit Note 11."
    }
}

SCENARIO_PRESETS  = [0.10, 0.20, 0.25]
SCENARIO_CHANGES  = ["operating_surplus_margin", "revenue_growth_rate"]

DATA_SOURCE_OPTIONS = [
    "Audited Financials",
    "IRS Form 990",
    "YTD Projection",
    "Budget Estimate"
]

ORG_PROFILES = [
    "Service-Delivery Nonprofit",
    "Advocacy / Capacity-Building",
    "Community / Cultural Organization",
    "Faith-Based / Denominational",
    "Chapter / Affiliate of National Org"
]

## -- Score limitations --
SCORE_LIMITATIONS = [
    {
        "limitation":  "Operating Surplus Margin includes investment returns",
        "severity":    "High",
        "affects":     "Sustainability score",
        "description": "Investment returns are not operationally generated. If a significant portion of the surplus is investment return, the true operational margin may be substantially lower.",
        "action":      "Request investment return breakdown. Recalculate operational margin separately."
    },
    {
        "limitation":  "Revenue Growth Rate includes restricted grant revenue",
        "severity":    "Medium",
        "affects":     "Sustainability score",
        "description": "Growth driven by a single restricted funder is not the same as sustainable diversified growth. For high grant-concentration organizations, this metric may overstate sustainability.",
        "action":      "Review unrestricted revenue trend separately. Ask: what specifically drove the growth?"
    },
    {
        "limitation":  "Months of Runway calculated from total current assets",
        "severity":    "Low",
        "affects":     "Sustainability score",
        "description": "Total current assets may include restricted receivables. Audit Note 11 (Liquidity and Availability) gives a more precise figure.",
        "action":      "Cross-reference with audit Note 11 if available."
    },
    {
        "limitation":  "Fundraising Efficiency may use Total Revenue as proxy",
        "severity":    "Medium",
        "affects":     "Efficiency score",
        "description": "When Fundraising Income is not separately tracked, Total Revenue is used. For orgs with significant grant or investment revenue this can substantially overstate fundraising return.",
        "action":      "Enter Fundraising Income in the dedicated field if available in the audit."
    },
    {
        "limitation":  "Composite score reflects financial ratios only",
        "severity":    "Structural",
        "affects":     "Overall score",
        "description": "The score does not capture: revenue concentration risk, grant compliance issues, program-level cost sustainability, subsidiary obligations, or early-year performance trends.",
        "action":      "Supplement with qualitative organizational assessment. A high score means ratios are healthy — not that there are no financial risks."
    }
]


## ============================================================
## SECTION 5 — VALIDATION
## Run before any calculation.
## Hard errors block output. Warnings show alongside results.
## ============================================================

def validate_inputs(inputs, fe_value=None):
    errors   = []
    warnings = []

    rev  = inputs.get("total_revenue")
    exp  = inputs.get("total_expenses")
    prog = inputs.get("program_expenses")
    ta   = inputs.get("total_assets")
    tl   = inputs.get("total_liabilities")
    top  = inputs.get("top_funder_revenue")

    ## Hard errors
    if rev  is not None and rev  < 0: errors.append("Total Revenue cannot be negative.")
    if exp  is not None and exp  < 0: errors.append("Total Expenses cannot be negative.")
    if prog is not None and exp is not None and prog > exp:
        errors.append("Program Expenses cannot exceed Total Expenses.")

    ## Soft warnings
    if ta is not None and tl is not None and tl > ta:
        warnings.append("Total Liabilities exceed Total Assets — organization may be technically insolvent.")

    ## Fundraising proxy overstatement
    if fe_value is not None and fe_value > FUNDRAISING_PROXY_WARNING:
        warnings.append(
            f"Fundraising Efficiency of {fe_value:.1f}:1 likely reflects non-fundraising "
            f"revenue in the numerator. Enter Fundraising Income separately for an accurate result. "
            f"Treat current ratio as unverified."
        )

    ## Revenue concentration flag
    if top is not None and rev is not None and rev > 0:
        pct = top / rev
        if pct > CONCENTRATION_CRITICAL:
            warnings.append(
                f"Revenue Concentration — CRITICAL: Top funder represents {pct*100:.1f}% "
                f"of total revenue (threshold: >40%). This creates acute vulnerability "
                f"to a single funder decision."
            )
        elif pct > CONCENTRATION_ELEVATED:
            warnings.append(
                f"Revenue Concentration — ELEVATED: Top funder represents {pct*100:.1f}% "
                f"of total revenue (threshold: >30%). Active monitoring recommended."
            )

    return errors, warnings


## ============================================================
## SECTION 6 — RATIO CALCULATIONS
## None = data unavailable. Never substitute zero for None.
## Returns ratios dict + flags dict.
## ============================================================

def calculate_ratios(inputs):
    rev      = inputs.get("total_revenue")
    exp      = inputs.get("total_expenses")
    prog     = inputs.get("program_expenses")
    admin    = inputs.get("admin_expenses")
    fund_exp = inputs.get("fundraising_expenses")
    fund_inc = inputs.get("fundraising_income")
    ca       = inputs.get("current_assets")
    cl       = inputs.get("current_liabilities")
    ta       = inputs.get("total_assets")
    tl       = inputs.get("total_liabilities")
    prior    = inputs.get("prior_year_revenue")
    top      = inputs.get("top_funder_revenue")

    ratios = {}
    flags  = {}

    ## R1 — Program Efficiency
    if prog is not None and exp is not None and exp > 0:
        ratios["program_efficiency"] = prog / exp
        flags["program_efficiency"]  = "clean"
    else:
        ratios["program_efficiency"] = None
        flags["program_efficiency"]  = "unavailable"

    ## R2 — Admin Expense %
    if admin is not None and exp is not None and exp > 0:
        ratios["admin_expense_pct"] = admin / exp
        flags["admin_expense_pct"]  = "clean"
    else:
        ratios["admin_expense_pct"] = None
        flags["admin_expense_pct"]  = "unavailable"

    ## R3 — Fundraising Efficiency (three-level logic)
    ## Level 1: Fundraising Income provided → correct formula
    ## Level 2: Not provided → proxy using Total Revenue
    ## Level 3: Proxy ratio > 50:1 → validation warning fires
    if fund_exp is not None and fund_exp > 0:
        if fund_inc is not None and fund_inc > 0:
            ratios["fundraising_efficiency"] = fund_inc / fund_exp
            flags["fundraising_efficiency"]  = "clean"
        elif rev is not None:
            ratios["fundraising_efficiency"] = rev / fund_exp
            flags["fundraising_efficiency"]  = "proxy"
        else:
            ratios["fundraising_efficiency"] = None
            flags["fundraising_efficiency"]  = "unavailable"
    else:
        ratios["fundraising_efficiency"] = None
        flags["fundraising_efficiency"]  = "unavailable"

    ## R4 — Operating Surplus Margin
    if rev is not None and exp is not None and rev > 0:
        ratios["operating_surplus_margin"] = (rev - exp) / rev
        flags["operating_surplus_margin"]  = "clean"
    else:
        ratios["operating_surplus_margin"] = None
        flags["operating_surplus_margin"]  = "unavailable"

    ## R5 — Working Capital Ratio (× 12 = months for display)
    if ca is not None and cl is not None and exp is not None and exp > 0:
        ratios["working_capital_ratio"] = (ca - cl) / exp
        flags["working_capital_ratio"]  = "clean"
    else:
        ratios["working_capital_ratio"] = None
        flags["working_capital_ratio"]  = "unavailable"

    ## R6 — Debt Ratio
    if tl is not None and ta is not None and ta > 0:
        ratios["debt_ratio"] = tl / ta
        flags["debt_ratio"]  = "clean"
    else:
        ratios["debt_ratio"] = None
        flags["debt_ratio"]  = "unavailable"

    ## R7 — Revenue Growth Rate
    if rev is not None and prior is not None and prior > 0:
        ratios["revenue_growth_rate"] = (rev - prior) / prior
        flags["revenue_growth_rate"]  = "clean"
    else:
        ratios["revenue_growth_rate"] = None
        flags["revenue_growth_rate"]  = "unavailable"

    ## R8 — Months of Operating Runway
    if ca is not None and exp is not None and exp > 0:
        ratios["months_runway"] = ca / (exp / 12)
        flags["months_runway"]  = "clean"
    else:
        ratios["months_runway"] = None
        flags["months_runway"]  = "unavailable"

    ## R9 — Current Ratio (reference only — not scored)
    if ca is not None and cl is not None and cl > 0:
        ratios["current_ratio"] = ca / cl
        flags["current_ratio"]  = "reference"
    else:
        ratios["current_ratio"] = None
        flags["current_ratio"]  = "unavailable"

    ## R10 — Revenue Concentration % (display only — not scored)
    if top is not None and rev is not None and rev > 0:
        ratios["concentration_pct"] = top / rev
        flags["concentration_pct"]  = "clean"
    else:
        ratios["concentration_pct"] = None
        flags["concentration_pct"]  = "unavailable"

    return ratios, flags


## ============================================================
## SECTION 7 — TIER SCORING
## Maps ratio value to 100 / 75 / 50 / 25.
## Handles "higher is better" and "lower is better" directions.
## ============================================================

def tier_score(ratio_name, value):
    if value is None: return None
    bench = BENCHMARKS.get(ratio_name)
    if bench is None: return None

    direction = bench["direction"]
    excellent = bench["excellent"]
    strong    = bench["strong"]
    average   = bench["average"]

    if direction == "higher":
        if value >= excellent: return 100
        elif value >= strong:  return 75
        elif value >= average: return 50
        else:                  return 25
    else:
        if value <= excellent: return 100
        elif value <= strong:  return 75
        elif value <= average: return 50
        else:                  return 25

def get_tier_label(score):
    return {100: "Excellent", 75: "Strong", 50: "Average", 25: "Issues"}.get(score, "N/A")

def get_tier_color(score):
    return {100: "#4CAF82", 75: "#2E8B57", 50: "#E8A020", 25: "#E05050"}.get(score, "#6B7A8E")


## ============================================================
## SECTION 8 — COMPOSITE SCORING + CONTRIBUTION BREAKDOWN
## Three partial data cases:
##   A: One ratio missing → score remaining, include dimension
##   B: Full dimension missing → exclude, redistribute weight
##   C: Two dimensions missing → score one, show strong warning
## Contribution breakdown shows points per dimension.
## ============================================================

def calculate_composite(ratios, flags=None):
    result = {
        "composite":        None,
        "dimension_scores": {},
        "available_ratios": 0,
        "total_ratios":     8,
        "excluded_dims":    [],
        "floor_rule":       False,
        "band":             None,
        "key_finding":      "",
        "contribution":     {},   ## NEW: points each dimension contributed
        "primary_strength": None, ## NEW: highest scoring dimension
        "primary_risk":     None  ## NEW: lowest scoring dimension
    }

    ## Floor rule check
    prog_eff = ratios.get("program_efficiency")
    if prog_eff is not None and prog_eff < FLOOR_RULE_THRESHOLD:
        result["floor_rule"] = True

    ## Dimension sub-scores
    dimension_scores = {}
    for dim_name, ratio_list in DIMENSIONS.items():
        scores_in_dim = []
        for ratio_name in ratio_list:
            val   = ratios.get(ratio_name)
            score = tier_score(ratio_name, val)
            if score is not None:
                scores_in_dim.append(score)
                result["available_ratios"] += 1
        if scores_in_dim:
            dimension_scores[dim_name] = sum(scores_in_dim) / len(scores_in_dim)
        else:
            dimension_scores[dim_name] = None
            result["excluded_dims"].append(dim_name)

    result["dimension_scores"] = dimension_scores

    ## Composite with weight redistribution
    available_dims = {d: s for d, s in dimension_scores.items() if s is not None}
    if not available_dims:
        return result

    total_weight = sum(DIMENSION_WEIGHTS[d] for d in available_dims)
    composite    = 0

    ## Contribution breakdown — how many points each dimension contributed
    for dim, score in available_dims.items():
        adjusted_weight = DIMENSION_WEIGHTS[dim] / total_weight
        pts_contributed = round(score * adjusted_weight)
        max_pts         = round(DIMENSION_WEIGHTS[dim] * 100)
        composite      += score * adjusted_weight
        result["contribution"][dim] = {
            "score":       round(score),
            "contributed": pts_contributed,
            "max":         max_pts
        }

    result["composite"] = round(composite)

    ## Score band
    for band_label, (low, high) in SCORE_BANDS.items():
        if low <= result["composite"] <= high:
            result["band"] = band_label
            break

    ## Primary strength and risk (dimension level — Option A)
    scored_dims = {d: s for d, s in dimension_scores.items() if s is not None}
    if scored_dims:
        result["primary_strength"] = max(scored_dims, key=scored_dims.get)
        result["primary_risk"]     = min(scored_dims, key=scored_dims.get)

    ## Key finding sentence
    result["key_finding"] = generate_key_finding(result, ratios, flags or {})

    return result


def generate_key_finding(composite_result, ratios, flags):
    score = composite_result["composite"]
    band  = composite_result["band"]
    if score is None:
        return "Insufficient data to generate a financial health assessment."

    base_map = {
        "Strong":     "financial ratios indicate a well-capitalized organization with solid fundamentals across all three dimensions",
        "Stable":     "financial ratios indicate a generally stable organization with some areas warranting attention",
        "Watchlist":  "financial ratios indicate financial stress in one or more dimensions — active monitoring is recommended",
        "Distressed": "financial ratios indicate significant financial risk requiring immediate strategic attention"
    }
    base = base_map.get(band, "financial ratios reflect mixed performance")

    dim_scores = {k: v for k, v in composite_result["dimension_scores"].items() if v is not None}
    if dim_scores:
        strongest = max(dim_scores, key=dim_scores.get)
        weakest   = min(dim_scores, key=dim_scores.get)
        finding   = (
            f"This organization's {base}. "
            f"Strongest dimension: {strongest.capitalize()} ({dim_scores[strongest]:.0f}/100)."
        )
        if strongest != weakest:
            finding += f" Area for attention: {weakest.capitalize()} ({dim_scores[weakest]:.0f}/100)."
    else:
        finding = f"This organization's {base}."

    if flags.get("fundraising_efficiency") == "proxy":
        finding += " Note: Fundraising Efficiency uses Total Revenue as a proxy — verify against fundraising-specific income."

    return finding


## ============================================================
## SECTION 9 — SCENARIO ENGINE + INSIGHT DETECTION
## Scenario engine: only Margin and Growth Rate change.
## New: band change detection, breakpoint detection,
## most impacted dimension detection.
## ============================================================

def run_scenario(inputs, ratios, composite_result, decline_pct):
    rev   = inputs.get("total_revenue")
    exp   = inputs.get("total_expenses")
    prior = inputs.get("prior_year_revenue")

    if rev is None: return None

    scenario_revenue = rev * (1 - decline_pct)
    scenario_ratios  = ratios.copy()

    ## Only these two ratios change
    if exp is not None:
        if scenario_revenue > 0:
            scenario_ratios["operating_surplus_margin"] = (scenario_revenue - exp) / scenario_revenue
        else:
            scenario_ratios["operating_surplus_margin"] = -1.0
    else:
        scenario_ratios["operating_surplus_margin"] = None

    if prior is not None and prior > 0:
        scenario_ratios["revenue_growth_rate"] = (scenario_revenue - prior) / prior
    else:
        scenario_ratios["revenue_growth_rate"] = None

    scenario_composite = calculate_composite(scenario_ratios)

    ## Status flags per ratio
    status_flags = {}
    for ratio_name in BENCHMARKS.keys():
        bs = tier_score(ratio_name, ratios.get(ratio_name))
        ss = tier_score(ratio_name, scenario_ratios.get(ratio_name))
        if bs is None or ss is None:
            status_flags[ratio_name] = "gray"
        elif ss == bs:
            status_flags[ratio_name] = "green"
        elif bs - ss == 25:
            status_flags[ratio_name] = "yellow"
        else:
            status_flags[ratio_name] = "red"

    return {
        "scenario_revenue":   scenario_revenue,
        "decline_pct":        decline_pct,
        "scenario_ratios":    scenario_ratios,
        "scenario_composite": scenario_composite,
        "status_flags":       status_flags
    }


def find_band_change_decline(inputs, ratios, composite_result):
    """
    Iterates 1% steps to find the exact decline % where score
    crosses to the next lower band. Returns integer % or None.
    """
    baseline_band = composite_result.get("band")
    if not baseline_band: return None

    band_order = ["Strong", "Stable", "Watchlist", "Distressed"]
    if baseline_band not in band_order: return None
    baseline_idx = band_order.index(baseline_band)

    for pct in range(1, 51):
        scenario = run_scenario(inputs, ratios, composite_result, pct / 100)
        if scenario:
            scenario_band = scenario["scenario_composite"].get("band")
            if scenario_band in band_order:
                scenario_idx = band_order.index(scenario_band)
                if scenario_idx > baseline_idx:
                    return pct
    return None


def find_surplus_breakpoint(ratios):
    """
    Direct calculation: surplus goes negative at exactly
    the current Operating Surplus Margin percentage.
    Returns float % or None.
    """
    margin = ratios.get("operating_surplus_margin")
    if margin is None or margin <= 0: return None
    return round(margin * 100, 1)


def find_most_impacted_dimension(inputs, ratios, composite_result, decline_pct):
    """
    Under a given scenario decline, finds which dimension
    drops the most points from baseline.
    Returns (dimension_name, baseline_score, scenario_score) or (None, None, None).
    """
    scenario = run_scenario(inputs, ratios, composite_result, decline_pct)
    if not scenario: return None, None, None

    baseline_dims = composite_result.get("dimension_scores", {})
    scenario_dims = scenario["scenario_composite"].get("dimension_scores", {})

    max_drop    = 0
    most_impacted = None

    for dim in baseline_dims:
        bv = baseline_dims.get(dim)
        sv = scenario_dims.get(dim)
        if bv is not None and sv is not None:
            drop = bv - sv
            if drop > max_drop:
                max_drop      = drop
                most_impacted = dim

    if most_impacted:
        return (
            most_impacted,
            round(baseline_dims.get(most_impacted, 0)),
            round(scenario_dims.get(most_impacted, 0))
        )
    return None, None, None


## ============================================================
## SECTION 10 — FORMATTING HELPERS
## ============================================================

def format_ratio_value(ratio_name, value):
    if value is None: return "—"
    fmt = BENCHMARKS.get(ratio_name, {}).get("format", "decimal")
    if fmt == "percent":     return f"{value * 100:.1f}%"
    elif fmt == "dollar":    return f"${value:.2f} per $1"
    elif fmt == "months_wc": return f"{value * 12:.1f} months"
    elif fmt == "months":    return f"{value:.1f} months"
    return f"{value:.3f}"

def format_currency(value):
    if value is None: return "—"
    return f"${value:,.2f}"


## ============================================================
## SECTION 11 — EXCEL EXPORT (7 TABS)
## Tab 1: Organization Profile
## Tab 2: Raw Inputs
## Tab 3: Ratio Results (with flags, notes, contribution)
## Tab 4: Dimension Scores (with contribution breakdown)
## Tab 5: Score Limitations
## Tab 6: Scenario Results (with insight sentences)
## Tab 7: AI Analysis Framework (condensed Part 9 + instructions)
## ============================================================

def generate_excel(
    inputs, source_tags, ratios, flags, composite_result,
    scenario_results, org_name, fiscal_year, org_profile,
    data_profile, assessment_date, band_change_pct,
    breakpoint_pct, most_impacted_dim, most_impacted_baseline,
    most_impacted_scenario
):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        ## ── TAB 1: Organization Profile ──
        score = composite_result.get("composite")
        band  = composite_result.get("band")
        avail = composite_result.get("available_ratios")
        total = composite_result.get("total_ratios")
        excl  = composite_result.get("excluded_dims", [])
        ps    = composite_result.get("primary_strength")
        pr    = composite_result.get("primary_risk")

        conc_val  = ratios.get("concentration_pct")
        conc_flag = "—"
        if conc_val is not None:
            if conc_val > CONCENTRATION_CRITICAL:
                conc_flag = f"CRITICAL — {conc_val*100:.1f}%"
            elif conc_val > CONCENTRATION_ELEVATED:
                conc_flag = f"ELEVATED — {conc_val*100:.1f}%"
            else:
                conc_flag = f"Low Risk — {conc_val*100:.1f}%"

        profile_rows = [
            {"Field": "Organization Name",         "Value": org_name or "Not specified"},
            {"Field": "Fiscal Year",                "Value": str(fiscal_year)},
            {"Field": "Assessment Date",            "Value": str(assessment_date)},
            {"Field": "Organization Profile",       "Value": org_profile},
            {"Field": "Data Profile",               "Value": data_profile},
            {"Field": "Prepared By",                "Value": "Bridge Builder Strategies"},
            {"Field": "Overall Score",              "Value": f"{score}/100" if score else "N/A"},
            {"Field": "Score Band",                 "Value": band or "N/A"},
            {"Field": "Score Confidence",           "Value": f"{avail} of {total} indicators available"},
            {"Field": "Excluded Dimensions",        "Value": ", ".join(excl) if excl else "None"},
            {"Field": "Floor Rule Triggered",       "Value": str(composite_result.get("floor_rule", False))},
            {"Field": "Primary Strength",           "Value": ps.capitalize() if ps else "N/A"},
            {"Field": "Primary Risk",               "Value": pr.capitalize() if pr else "N/A"},
            {"Field": "Revenue Concentration Flag", "Value": conc_flag},
            {"Field": "Key Finding",                "Value": composite_result.get("key_finding", "")}
        ]
        pd.DataFrame(profile_rows).to_excel(
            writer, sheet_name="Organization Profile", index=False
        )

        ## ── TAB 2: Raw Inputs ──
        field_labels = {
            "total_revenue":        "Total Revenue ($)",
            "total_expenses":       "Total Expenses ($)",
            "program_expenses":     "Program Expenses ($)",
            "admin_expenses":       "Administrative Expenses ($)",
            "fundraising_expenses": "Fundraising Expenses ($)",
            "fundraising_income":   "Fundraising Income ($)",
            "top_funder_revenue":   "Top Funder Revenue ($)",
            "current_assets":       "Current Assets ($)",
            "current_liabilities":  "Current Liabilities ($)",
            "total_assets":         "Total Assets ($)",
            "total_liabilities":    "Total Liabilities ($)",
            "prior_year_revenue":   "Prior Year Revenue ($)"
        }
        inputs_rows = []
        for key, label in field_labels.items():
            value  = inputs.get(key)
            source = source_tags.get(key, "—")
            if key == "fundraising_income":
                status = ("Verified — used as Fundraising Efficiency numerator"
                          if value is not None
                          else "Not provided — Total Revenue used as proxy")
            elif key == "top_funder_revenue":
                status = ("Verified — concentration flag calculated"
                          if value is not None
                          else "Not provided — concentration analysis unavailable")
            else:
                status = "Verified" if value is not None else "Unavailable"

            inputs_rows.append({
                "Field":       label,
                "Value":       format_currency(value) if value is not None else "Unavailable",
                "Data Source": source,
                "Status":      status
            })
        pd.DataFrame(inputs_rows).to_excel(
            writer, sheet_name="Raw Inputs", index=False
        )

        ## ── TAB 3: Ratio Results ──
        ratio_rows = []
        for ratio_name, bench in BENCHMARKS.items():
            value     = ratios.get(ratio_name)
            score_val = tier_score(ratio_name, value)
            flag      = flags.get(ratio_name, "clean")

            if flag == "proxy":
                tier_label = "See Note — Proxy Used"
                data_flag  = "Proxy — Total Revenue used as numerator"
            elif flag == "unavailable":
                tier_label = "Unavailable"
                data_flag  = "Unavailable"
            else:
                tier_label = get_tier_label(score_val) if score_val else "Unavailable"
                data_flag  = "Clean"

            note = bench.get("note") or ""
            if flag == "proxy":
                note = ("Total Revenue used as proxy. May overstate result for orgs with "
                        "significant non-fundraising revenue. " + note)

            ratio_rows.append({
                "Ratio":      bench["label"],
                "Value":      format_ratio_value(ratio_name, value),
                "Tier":       tier_label,
                "Tier Score": score_val if score_val else "—",
                "Dimension":  bench["dimension"].capitalize(),
                "Data Flag":  data_flag,
                "Note":       note
            })

        ## Current ratio reference
        cr = ratios.get("current_ratio")
        ratio_rows.append({
            "Ratio":      "Current Ratio (reference — not scored)",
            "Value":      f"{cr:.2f}" if cr is not None else "—",
            "Tier":       "Reference only",
            "Tier Score": "—",
            "Dimension":  "Reference",
            "Data Flag":  "Reference",
            "Note":       "1.5–2.0 is healthy. >3.0 may indicate underinvestment of reserves."
        })

        ## Concentration reference
        conc = ratios.get("concentration_pct")
        ratio_rows.append({
            "Ratio":      "Revenue Concentration — Top Funder (signal only)",
            "Value":      f"{conc*100:.1f}%" if conc is not None else "—",
            "Tier":       conc_flag,
            "Tier Score": "—",
            "Dimension":  "Signal",
            "Data Flag":  "Signal — not scored",
            "Note":       ">30% = Elevated. >40% = Critical. (BBS Framework threshold — pending supervisor confirmation)"
        })

        ## Spacer + dimension summaries
        ratio_rows.append({k: "" for k in ratio_rows[0].keys()})
        for dim, dim_score in composite_result["dimension_scores"].items():
            contrib = composite_result["contribution"].get(dim, {})
            ratio_rows.append({
                "Ratio":      f"— {dim.capitalize()} Dimension Score",
                "Value":      f"{dim_score:.1f}/100" if dim_score else "Excluded",
                "Tier":       "",
                "Tier Score": contrib.get("contributed", "—"),
                "Dimension":  dim.capitalize(),
                "Data Flag":  "",
                "Note":       f"Weight: {DIMENSION_WEIGHTS[dim]*100:.0f}% | Contributed: {contrib.get('contributed','—')}/{contrib.get('max','—')} pts"
            })

        ratio_rows.append({
            "Ratio":      "COMPOSITE FINANCIAL HEALTH SCORE",
            "Value":      f"{composite_result['composite']}/100 — {composite_result['band']}" if composite_result['composite'] else "N/A",
            "Tier":       composite_result.get("band", ""),
            "Tier Score": composite_result.get("composite", ""),
            "Dimension":  "All",
            "Data Flag":  "",
            "Note":       composite_result.get("key_finding", "")
        })

        pd.DataFrame(ratio_rows).to_excel(
            writer, sheet_name="Ratio Results", index=False
        )

        ## ── TAB 4: Dimension Scores ──
        dim_rows = []
        for dim in ["sustainability", "efficiency", "solvency"]:
            dim_score   = composite_result["dimension_scores"].get(dim)
            ratio_names = DIMENSIONS[dim]
            available   = sum(1 for r in ratio_names if ratios.get(r) is not None)
            scored      = {r: tier_score(r, ratios.get(r)) for r in ratio_names if tier_score(r, ratios.get(r)) is not None}
            strongest   = BENCHMARKS[max(scored, key=scored.get)]["label"] if scored else "—"
            weakest     = BENCHMARKS[min(scored, key=scored.get)]["label"] if scored else "—"
            contrib     = composite_result["contribution"].get(dim, {})

            dim_rows.append({
                "Dimension":           dim.capitalize(),
                "Weight":              f"{DIMENSION_WEIGHTS[dim]*100:.0f}%",
                "Sub-Score":           f"{dim_score:.1f}" if dim_score else "Excluded",
                "Points Contributed":  f"{contrib.get('contributed','—')} of {contrib.get('max','—')} possible",
                "Ratios Available":    f"{available} of {len(ratio_names)}",
                "Strongest Ratio":     strongest,
                "Weakest Ratio":       weakest,
                "Status":              "Included" if dim_score else "Excluded — insufficient data"
            })

        pd.DataFrame(dim_rows).to_excel(
            writer, sheet_name="Dimension Scores", index=False
        )

        ## ── TAB 5: Score Limitations ──
        lim_rows = [{
            "Limitation":         l["limitation"],
            "Severity":           l["severity"],
            "Affects":            l["affects"],
            "Description":        l["description"],
            "Recommended Action": l["action"]
        } for l in SCORE_LIMITATIONS]
        pd.DataFrame(lim_rows).to_excel(
            writer, sheet_name="Score Limitations", index=False
        )

        ## ── TAB 6: Scenario Results ──
        if scenario_results:
            flag_sym = {"green": "✓", "yellow": "!", "red": "⚠", "gray": "—"}
            scen_rows = []

            for ratio_name, bench in BENCHMARKS.items():
                row = {
                    "Ratio":    bench["label"],
                    "Baseline": format_ratio_value(ratio_name, ratios.get(ratio_name))
                }
                for label, result in scenario_results.items():
                    if result:
                        val = result["scenario_ratios"].get(ratio_name)
                        flg = result["status_flags"].get(ratio_name, "gray")
                        row[label] = f"{format_ratio_value(ratio_name, val)} {flag_sym.get(flg,'')}"
                    else:
                        row[label] = "—"
                scen_rows.append(row)

            ## Composite score row
            comp_row = {
                "Ratio":    "COMPOSITE SCORE",
                "Baseline": str(composite_result.get("composite", "N/A"))
            }
            for label, result in scenario_results.items():
                if result:
                    sc = result["scenario_composite"].get("composite")
                    bd = result["scenario_composite"].get("band", "")
                    comp_row[label] = f"{sc} — {bd}" if sc else "N/A"
                else:
                    comp_row[label] = "—"
            scen_rows.append(comp_row)

            ## Insight sentences
            scen_rows.append({"Ratio": "", "Baseline": ""})
            scen_rows.append({
                "Ratio":    "SCENARIO INSIGHTS",
                "Baseline": ""
            })
            if band_change_pct:
                scen_rows.append({
                    "Ratio":    "Band Change Detection",
                    "Baseline": f"Score drops from {band} to next lower band at approximately −{band_change_pct}% revenue decline."
                })
            if breakpoint_pct:
                scen_rows.append({
                    "Ratio":    "Surplus Breakpoint",
                    "Baseline": f"Operating surplus becomes negative at approximately −{breakpoint_pct}% revenue decline."
                })
            if most_impacted_dim:
                scen_rows.append({
                    "Ratio":    "Most Impacted Dimension",
                    "Baseline": f"Under the active scenario, {most_impacted_dim.capitalize()} takes the hardest hit, dropping from {most_impacted_baseline} to {most_impacted_scenario}."
                })
            scen_rows.append({
                "Ratio":    "Balance Sheet Note",
                "Baseline": "Working Capital Ratio and Months of Runway are held constant in all scenarios. A sustained revenue decline would erode these over time — treat as a floor, not a stable baseline."
            })

            pd.DataFrame(scen_rows).to_excel(
                writer, sheet_name="Scenario Results", index=False
            )

        ## ── TAB 7: AI Analysis Framework ──
        ## Condensed Part 9 of BBS Financial Health Assessment Framework Playbook v1.0
        ## Full analytical guidance lives in the separate Playbook document.
        framework_lines = [
            "BBS FINANCIAL HEALTH ASSESSMENT — AI ANALYSIS INSTRUCTIONS",
            "Version 1.0 | April 2026",
            "Internal Use: BBS Analysts and AI-Assisted Analysis Workflows",
            "",
            "════════════════════════════════════════════════════════════",
            "REFERENCE DOCUMENT",
            "════════════════════════════════════════════════════════════",
            "",
            "This analysis must be conducted using the BBS Financial Health Assessment",
            "Framework Playbook (Version 1.0, April 2026) as the governing analytical standard.",
            "Refer to the full Playbook for:",
            "  - Dimension definitions and analytical guidance (Parts 6 and 7)",
            "  - Complete threshold tables with benchmark citations (Appendix A)",
            "  - Red Flag Trigger Library (Part 5)",
            "  - Story arc construction guidance (Part 8)",
            "  - Tone calibration by overall financial condition (Part 8.3)",
            "  - Glossary of plain-language term definitions (Appendix C)",
            "",
            "════════════════════════════════════════════════════════════",
            "STEP 1 — READ CONTEXT BEFORE ANYTHING ELSE",
            "════════════════════════════════════════════════════════════",
            "",
            "Open the Organization Profile tab first. Note:",
            "  - Organization name, fiscal year, and org type",
            "  - Data tier declared (Tier 1 / Tier 2 / Tier 3)",
            "  - Score confidence level (how many of 8 indicators were available)",
            "  - Key Finding sentence generated by the dashboard",
            "  - Primary Strength and Primary Risk dimension labels",
            "  - Revenue Concentration Flag if present",
            "  - Any excluded dimensions or active flags",
            "",
            "The data tier governs what you can and cannot conclude.",
            "  Tier 1: Full picture — audited financials + 990 + budget + YTD",
            "  Tier 2: Partial picture — unaudited management statements + budget",
            "  Tier 3: Limited picture — budget only or balance sheet only",
            "",
            "If the data tier is Tier 2 or Tier 3, every section of the output",
            "must carry the appropriate tier disclosure language from the Playbook (Part 3.2).",
            "",
            "════════════════════════════════════════════════════════════",
            "STEP 2 — RUN THE RED FLAG SCAN BEFORE SCORING",
            "════════════════════════════════════════════════════════════",
            "",
            "Before analyzing any dimension, scan the Raw Inputs and Ratio Results",
            "tabs for the following conditions. Note all triggers before beginning.",
            "A triggered red flag does not automatically lower a rating — it means:",
            "investigate before accepting the headline figure at face value.",
            "",
            "Balance Sheet Red Flags:",
            "  - Total Liabilities exceed Total Assets → technical insolvency",
            "  - Debt ratio materially above prior period → identify cause before rating",
            "  - Low cash with high receivables at period-end → timing vs structural?",
            "",
            "Revenue Red Flags:",
            "  - Revenue Concentration Flag = CRITICAL or ELEVATED → note prominently",
            "  - Fundraising Efficiency flagged as proxy → ratio may be substantially overstated",
            "  - Operating Surplus Margin note re: investment returns → operational margin",
            "    may be substantially lower than the reported figure",
            "",
            "Structural Red Flags:",
            "  - Score based on fewer than 6 of 8 indicators → confidence is limited",
            "  - Floor rule triggered (Program Efficiency < 50%) → structural concern",
            "  - Any dimension fully excluded → weight redistributed, note this explicitly",
            "",
            "════════════════════════════════════════════════════════════",
            "STEP 3 — DETERMINE WHICH DIMENSIONS TO ANALYZE",
            "════════════════════════════════════════════════════════════",
            "",
            "DIMENSIONS SUPPORTED BY THIS DATA SET:",
            "",
            "  Liquidity & Short-Term Solvency (Playbook Section 2.1)",
            "    Data: Current Ratio (reference), Working Capital Ratio, Months of Runway",
            "    Note: Days Cash on Hand requires Cash & Cash Equivalents separately.",
            "    If unavailable, use working capital as proxy and flag the limitation.",
            "",
            "  Debt & Leverage (Playbook Section 2.3)",
            "    Data: Debt-to-Asset Ratio, total liabilities composition",
            "",
            "  Expense Structure & Cost Management (Playbook Section 2.7)",
            "    Data: Program Efficiency %, Admin Expense %,",
            "    Fundraising Efficiency (flag proxy if present)",
            "",
            "  Budget Performance & Operating Trends (Playbook Section 2.8)",
            "    Data: Operating Surplus Margin, Revenue Growth Rate,",
            "    scenario modeling results from Scenario Results tab",
            "",
            "  Revenue Concentration Risk (Playbook Section 2.6) — PARTIAL",
            "    Data: Top Funder % if entered. Full analysis requires revenue by source type.",
            "    If Top Funder % is not entered, note as partially assessable only.",
            "",
            "DIMENSIONS NOT SUPPORTED BY THIS DATA SET:",
            "Include this exact language for each unsupported dimension:",
            "",
            "  Asset Base & Capitalization (Playbook Section 2.2)",
            "  'Not assessed — Fixed Assets and investment portfolio breakdown not",
            "  currently collected by the BBS Financial Dashboard.",
            "  Required: Audited balance sheet with asset composition detail.'",
            "",
            "  Operating Reserve Coverage (Playbook Section 2.4)",
            "  'Not assessed — Audit Note 11 (Liquidity and Availability) not collected.",
            "  Required: Audited financial statements (Tier 1) or management statements",
            "  with unrestricted net asset detail (Tier 2).'",
            "",
            "  Net Asset Flexibility (Playbook Section 2.5)",
            "  'Not assessed — Restricted vs. Unrestricted Net Assets not collected.",
            "  Required: Audited financial statements (Tier 1).'",
            "",
            "  Budget-to-Actual Variance (Playbook Section 2.8)",
            "  'Partially assessed — Budgeted Revenue and Expenses not collected.",
            "  Operating trend analysis available from Revenue Growth Rate and",
            "  Operating Surplus Margin only.'",
            "",
            "════════════════════════════════════════════════════════════",
            "STEP 4 — HANDLE MISSING AND PARTIAL DATA",
            "════════════════════════════════════════════════════════════",
            "",
            "RULE 1: Never estimate or assume a figure without flagging it explicitly.",
            "If a number is not in the provided data, state this. Do not fill gaps.",
            "",
            "RULE 2: If Fundraising Efficiency is flagged as proxy, include this language",
            "wherever the ratio appears:",
            "  'Note: Fundraising Efficiency is calculated using Total Revenue as a proxy",
            "  for Fundraising Income. This figure may be overstated for organizations with",
            "  significant non-fundraising revenue. Verify against fundraising-specific",
            "  income before presenting to client.'",
            "",
            "RULE 3: If a section cannot be completed due to missing data, use this format:",
            "  [SECTION NAME] — DATA INSUFFICIENT FOR FULL ASSESSMENT",
            "  Available data: [list what was available]",
            "  Missing data: [list exactly what is needed]",
            "  To complete this section: [specific document or input required]",
            "  Impact on overall rating: [state effect on composite rating]",
            "",
            "RULE 4: If score is based on fewer than 6 of 8 indicators, include this",
            "disclosure at the top of the Executive Summary:",
            "  'Score confidence is limited. This assessment is based on [X] of 8",
            "  financial indicators. [List excluded indicators]. The overall rating should",
            "  be treated as directional rather than definitive until complete data",
            "  is available.'",
            "",
            "RULE 5: For conflicting figures between tabs, state the discrepancy,",
            "identify which figure was used, and explain why.",
            "",
            "════════════════════════════════════════════════════════════",
            "STEP 5 — PRODUCE THE OUTPUT",
            "════════════════════════════════════════════════════════════",
            "",
            "Structure the output using the BBS Financial Health Assessment Output",
            "Template (Document 2). Follow this sequence:",
            "",
            "  1. Cover (org name, period, data tier, prepared by BBS)",
            "  2. Executive Summary — max one page:",
            "       3-4 sentences org context",
            "       2-3 key strengths with supporting figures",
            "       2-3 key risks with supporting figures",
            "       Overall rating statement",
            "       Top 3 action items",
            "  3. Overall Financial Health Summary table (all assessed dimensions)",
            "  4. Data Sources & Scope section",
            "  5. Key Limitations & Data Gaps — MANDATORY, must be specific",
            "  6. Section-by-section dimension analysis (assessed dimensions only)",
            "     Each section must include:",
            "       Data table with figures and source citations",
            "       Key findings bullets",
            "       Rating (STRONG / MODERATE / ELEVATED / CRITICAL)",
            "       Direction indicator (UP / STABLE / DOWN / N/A)",
            "       'What This Means' block — plain language, no jargon,",
            "       answers: what does this number tell us, why does it matter,",
            "       what should leadership do",
            "  7. Overall Organizational Sustainability section",
            "  8. Recommendations (Immediate / Near-Term / Long-Term)",
            "",
            "CRITICAL OUTPUT RULES:",
            "  - Do NOT lead with the composite score number",
            "  - Lead with what the score means for this organization",
            "  - Every figure must carry a source tag citing its tab",
            "    e.g., 'Source: Ratio Results tab, BBS Financial Dashboard'",
            "  - Every threshold must cite its benchmark authority",
            "    e.g., 'Benchmark: NFF — 90 days minimum'",
            "  - 'What This Means' block is MANDATORY in every section",
            "  - Tone follows overall rating per Playbook Part 8.3:",
            "    STRONG = affirming, forward-looking",
            "    MODERATE = balanced, name the gaps specifically",
            "    ELEVATED = direct, name the risk, give clear actions",
            "    CRITICAL = urgent and constructive, state severity clearly",
            "",
            "REFERENCE THE CONTRIBUTION BREAKDOWN:",
            "  The Dimension Scores tab shows how many points each dimension",
            "  contributed to the composite. When explaining the overall score",
            "  in the Executive Summary and Overall Sustainability section,",
            "  reference which dimension drove the score and which pulled it down.",
            "  Example: 'Sustainability contributed 37 of its possible 40 points,",
            "  while Efficiency contributed 29 of 35.'",
            "",
            "REFERENCE THE SCENARIO INSIGHTS:",
            "  The Scenario Results tab contains three pre-calculated insight sentences:",
            "  Band Change Detection, Surplus Breakpoint, and Most Impacted Dimension.",
            "  Use all three when writing the scenario section and recommendations.",
            "  These are the most actionable outputs for client conversations.",
            "",
            "TARGET LENGTH: Match the Output Template structure. Length is",
            "determined by the data — if only 5 dimensions are assessable, the",
            "document will be shorter. Do not pad. Do not compress genuine findings.",
            "",
            "════════════════════════════════════════════════════════════",
            "DATA SOURCE REFERENCE",
            "════════════════════════════════════════════════════════════",
            "",
            "All data for this analysis comes from the following tabs:",
            "  Tab 1 — Organization Profile: context, tier, confidence, key finding",
            "  Tab 2 — Raw Inputs: all financial inputs with data source tags",
            "  Tab 3 — Ratio Results: calculated ratios with tiers, flags, notes",
            "  Tab 4 — Dimension Scores: sub-scores, contribution breakdown",
            "  Tab 5 — Score Limitations: known limitations with severity levels",
            "  Tab 6 — Scenario Results: revenue stress scenarios + insight sentences",
            "",
            "When citing data in the output, always reference the specific tab.",
            "Example: 'Source: Raw Inputs tab — Total Revenue $5,095,917,",
            "Audited Financials, FY2025'",
            "",
            "════════════════════════════════════════════════════════════",
            "END OF AI ANALYSIS INSTRUCTIONS",
            "Refer to BBS Financial Health Assessment Framework Playbook v1.0",
            "for complete analytical guidance.",
            "════════════════════════════════════════════════════════════"
        ]

        pd.DataFrame(
            [[line] for line in framework_lines],
            columns=["AI Analysis Framework — Instructions for Copilot / Claude"]
        ).to_excel(writer, sheet_name="AI Analysis Framework", index=False)

    output.seek(0)
    return output


## ============================================================
## SECTION 12 — STREAMLIT UI
## BBS color scheme. Logo in header.
## Runs top to bottom every time user interacts.
## ============================================================

## ── BBS Header with Logo ──
col_logo, col_header = st.columns([1, 5])
with col_logo:
    ## Try to load the BBS logo from the repo.
    ## File must be named bbs_logo.png and placed in the same
    ## directory as app.py in the GitHub repo.
    try:
        st.image("bbs_logo.png", width=90)
    except Exception:
        st.markdown(
            "<div style='font-size:20px; font-weight:700; color:#2E8B57; "
            "padding-top:10px;'>BBS</div>",
            unsafe_allow_html=True
        )

with col_header:
    st.markdown("""
    <div style="padding: 8px 0 12px 0;
                border-bottom: 1px solid rgba(255,255,255,0.07);">
        <div style="font-size: 11px; color: #2E8B57;
                    letter-spacing: 0.14em;
                    text-transform: uppercase;
                    margin-bottom: 3px;">
            Bridge Builder Strategies
        </div>
        <div style="font-size: 24px; font-weight: 600;
                    color: #E8EAF0; letter-spacing: -0.01em;
                    line-height: 1.2;">
            Nonprofit Financial Health Dashboard
        </div>
        <div style="font-size: 12px; color: #4A5568; margin-top: 2px;">
            Internal Consulting Tool &nbsp;·&nbsp; v3.0 Prototype
        </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='margin-top:20px;'></div>", unsafe_allow_html=True)


## ============================================================
## UI PART A — ORGANIZATION INFO
## ============================================================

st.markdown("### Organization Setup")

ca1, ca2, ca3 = st.columns([2, 1, 2])
with ca1:
    org_name = st.text_input("Organization Name", placeholder="e.g. Sheltering Wings")
with ca2:
    fiscal_year = st.number_input("Fiscal Year", min_value=2000, max_value=2030, value=2025, step=1)
with ca3:
    org_profile = st.selectbox("Organization Profile", ORG_PROFILES,
        help="Sets consulting context. All profiles use the same weights currently — differentiated weighting is a future iteration pending BBS approval.")

data_profile = st.selectbox("Available Data Profile", [
    "Tier 1 — Full Audit + 990 + Budget + YTD (full confidence)",
    "Tier 2 — Management Financials + Budget (moderate confidence)",
    "Tier 3 — Balance Sheet or Budget Only (limited confidence)"
])

st.divider()


## ============================================================
## UI PART B — FINANCIAL INPUTS
## ============================================================

st.markdown("### Financial Inputs")
st.caption(
    "Enter figures from client documents. Tag each source. "
    "Check N/A if data was not provided — affects partial scoring logic."
)

def input_field(label, key, help_text=""):
    """Renders a labeled number input with source tag and N/A checkbox."""
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        val = st.number_input(
            label, min_value=0.0, value=0.0, step=1000.0,
            format="%.2f", key=f"{key}_val", help=help_text
        )
    with c2:
        src = st.selectbox("Source", DATA_SOURCE_OPTIONS,
                           key=f"{key}_src", label_visibility="collapsed")
    with c3:
        na = st.checkbox("N/A", key=f"{key}_na",
                         help="Check if this data was not provided by the client.")
    return (None if na else val), src


## Income Statement
st.markdown("**Income Statement**")
inc_l, inc_r = st.columns(2)
with inc_l:
    total_revenue,        src_rev   = input_field("Total Revenue ($)",          "total_revenue",
        "All income: donations, grants, government funding, earned revenue.")
    program_expenses,     src_prog  = input_field("Program Expenses ($)",        "program_expenses",
        "Expenses directly tied to mission delivery and programs.")
    fundraising_expenses, src_fexp  = input_field("Fundraising Expenses ($)",    "fundraising_expenses",
        "Expenses for fundraising activities and donor engagement.")
with inc_r:
    total_expenses,       src_exp   = input_field("Total Expenses ($)",          "total_expenses",
        "All organizational expenses.")
    admin_expenses,       src_admin = input_field("Administrative Expenses ($)", "admin_expenses",
        "Overhead and general administration expenses.")
    prior_year_revenue,   src_prior = input_field("Prior Year Revenue ($)",      "prior_year_revenue",
        "Total revenue from the previous fiscal year — used for growth rate calculation.")

## Fundraising Income (optional — improves accuracy)
st.markdown("**Fundraising Income** *(optional — improves Fundraising Efficiency accuracy)*")
st.caption(
    "Revenue from fundraising events and campaigns only. "
    "Do NOT include general contributions or grants. "
    "When provided, replaces Total Revenue in the Fundraising Efficiency formula. "
    "Mark N/A if not separately tracked — Total Revenue will be used as proxy with a warning."
)
fundraising_income, src_finc = input_field("Fundraising Income ($)", "fundraising_income",
    "Fundraising-specific revenue only. Not total contributions.")

## Revenue Concentration (optional signal)
st.markdown("**Revenue Concentration** *(optional — concentration risk signal)*")
st.caption(
    "Enter the dollar amount from your single largest funder or revenue source. "
    "Used to calculate concentration risk as a % of total revenue. "
    "Does not affect the composite score — displayed as a signal flag only."
)
top_funder_revenue, src_top = input_field("Top Funder Revenue ($)", "top_funder_revenue",
    "Revenue from single largest funder or revenue source.")

## Balance Sheet
st.markdown("**Balance Sheet**")
bs_l, bs_r = st.columns(2)
with bs_l:
    current_assets,      src_ca = input_field("Current Assets ($)",      "current_assets",
        "Cash and assets convertible to cash within 12 months.")
    total_assets,        src_ta = input_field("Total Assets ($)",        "total_assets",
        "All organizational assets.")
with bs_r:
    current_liabilities, src_cl = input_field("Current Liabilities ($)", "current_liabilities",
        "Obligations due within 12 months.")
    total_liabilities,   src_tl = input_field("Total Liabilities ($)",   "total_liabilities",
        "All organizational obligations.")

## Assemble input and source tag dicts
inputs = {
    "total_revenue":        total_revenue,
    "total_expenses":       total_expenses,
    "program_expenses":     program_expenses,
    "admin_expenses":       admin_expenses,
    "fundraising_expenses": fundraising_expenses,
    "fundraising_income":   fundraising_income,
    "top_funder_revenue":   top_funder_revenue,
    "current_assets":       current_assets,
    "current_liabilities":  current_liabilities,
    "total_assets":         total_assets,
    "total_liabilities":    total_liabilities,
    "prior_year_revenue":   prior_year_revenue
}
source_tags = {
    "total_revenue":        src_rev,
    "total_expenses":       src_exp,
    "program_expenses":     src_prog,
    "admin_expenses":       src_admin,
    "fundraising_expenses": src_fexp,
    "fundraising_income":   src_finc,
    "top_funder_revenue":   src_top,
    "current_assets":       src_ca,
    "current_liabilities":  src_cl,
    "total_assets":         src_ta,
    "total_liabilities":    src_tl,
    "prior_year_revenue":   src_prior
}

st.divider()


## ============================================================
## UI PART C — CALCULATE BUTTON
## ============================================================

if st.button("Calculate Financial Health Score", type="primary", use_container_width=True):

    ## Quick pre-run to check fundraising proxy warning
    ratios_pre, flags_pre = calculate_ratios(inputs)
    fe_val = ratios_pre.get("fundraising_efficiency")

    errors, warnings = validate_inputs(inputs, fe_val)

    if errors:
        for err in errors:
            st.error(f"Input Error: {err}")
    else:
        for warn in warnings:
            st.warning(warn)

        ratios, flags         = calculate_ratios(inputs)
        composite_result      = calculate_composite(ratios, flags)

        ## Pre-calculate scenario insights
        band_change_pct        = find_band_change_decline(inputs, ratios, composite_result)
        breakpoint_pct         = find_surplus_breakpoint(ratios)
        mi_dim, mi_base, mi_sc = find_most_impacted_dimension(
            inputs, ratios, composite_result, 0.20
        )

        st.session_state.update({
            "ratios":            ratios,
            "flags":             flags,
            "composite_result":  composite_result,
            "inputs":            inputs,
            "source_tags":       source_tags,
            "org_name":          org_name,
            "fiscal_year":       fiscal_year,
            "org_profile":       org_profile,
            "data_profile":      data_profile,
            "calculated":        True,
            "band_change_pct":   band_change_pct,
            "breakpoint_pct":    breakpoint_pct,
            "mi_dim":            mi_dim,
            "mi_base":           mi_base,
            "mi_sc":             mi_sc
        })


## ============================================================
## UI PART D — RESULTS
## Panels: Key Finding → Score Card → Contribution Breakdown
##       → Ratio Table → Scenario Modeling → Limitations
##       → Data Gaps → Export
## ============================================================

if st.session_state.get("calculated"):

    ratios           = st.session_state["ratios"]
    flags            = st.session_state["flags"]
    cr               = st.session_state["composite_result"]
    saved_inputs     = st.session_state["inputs"]
    saved_sources    = st.session_state["source_tags"]
    saved_org        = st.session_state.get("org_name", "Organization")
    saved_year       = st.session_state.get("fiscal_year", 2025)
    saved_profile    = st.session_state.get("org_profile", ORG_PROFILES[0])
    saved_data_prof  = st.session_state.get("data_profile", "")
    band_change_pct  = st.session_state.get("band_change_pct")
    breakpoint_pct   = st.session_state.get("breakpoint_pct")
    mi_dim           = st.session_state.get("mi_dim")
    mi_base          = st.session_state.get("mi_base")
    mi_sc            = st.session_state.get("mi_sc")

    score  = cr["composite"]
    band   = cr["band"]
    color  = BAND_COLORS.get(band, "#6B7A8E")
    avail  = cr["available_ratios"]
    total  = cr["total_ratios"]
    excl   = cr["excluded_dims"]
    ps     = cr.get("primary_strength")
    pr     = cr.get("primary_risk")

    caveat = f"Score based on {avail} of {total} indicators"
    if excl:
        caveat += f" — {', '.join([d.capitalize() for d in excl])} excluded"

    ## Data confidence statement
    if avail == total:
        confidence_label = "High — all 8 indicators available"
        confidence_color = "#4CAF82"
    elif avail >= 6:
        confidence_label = f"Moderate — {avail} of {total} indicators available"
        confidence_color = "#E8A020"
    else:
        confidence_label = f"Limited — only {avail} of {total} indicators available"
        confidence_color = "#E05050"

    st.markdown(f"## Assessment — {saved_org} ({saved_year})")

    ## Data confidence banner
    st.markdown(f"""
    <div style="background:#132030; border-left:3px solid {confidence_color};
                border-radius:0 8px 8px 0; padding:10px 16px; margin-bottom:16px;
                display:flex; align-items:center; gap:12px;">
        <div style="font-size:11px; color:{confidence_color}; font-weight:600;
                    text-transform:uppercase; letter-spacing:0.08em; white-space:nowrap;">
            Data Confidence
        </div>
        <div style="font-size:13px; color:#C0C8D4;">{confidence_label}</div>
    </div>
    """, unsafe_allow_html=True)

    ## ── PANEL 1: KEY FINDING ──
    key_finding = cr.get("key_finding", "")
    if key_finding:
        st.markdown(f"""
        <div style="background:#132030; border-left:4px solid {color};
                    border-radius:0 10px 10px 0; padding:16px 20px; margin-bottom:20px;">
            <div style="font-size:11px; color:#4A5568; text-transform:uppercase;
                        letter-spacing:0.08em; margin-bottom:5px;">Key Finding</div>
            <div style="font-size:15px; color:#E8EAF0; line-height:1.6;">{key_finding}</div>
        </div>
        """, unsafe_allow_html=True)

    ## ── PANEL 2: SCORE CARD + DIMENSION CARDS ──
    sc1, sc2 = st.columns([1, 2])

    with sc1:
        ## Primary strength / risk badges
        ps_badge = f"<div style='font-size:11px; color:#4CAF82; margin-bottom:4px;'>▲ {ps.capitalize()}</div>" if ps else ""
        pr_badge = f"<div style='font-size:11px; color:#E8A020; margin-top:4px;'>▼ {pr.capitalize()}</div>" if pr else ""
        st.markdown(f"""
        <div style="background:#132030; border-radius:14px; padding:24px 20px;
                    text-align:center; border:2px solid {color}; height:100%;">
            <div style="font-size:10px; color:#4A5568; letter-spacing:0.12em;
                        text-transform:uppercase; margin-bottom:4px;">
                Composite Score
            </div>
            <div style="font-size:64px; font-weight:700; color:{color}; line-height:1;">
                {score if score else "N/A"}
            </div>
            <div style="font-size:11px; color:#4A5568; margin-top:1px;">out of 100</div>
            <div style="font-size:19px; font-weight:600; color:{color}; margin-top:8px;">
                {band if band else "N/A"}
            </div>
            <div style="height:1px; background:rgba(255,255,255,0.07); margin:10px 0;"></div>
            {ps_badge}
            {pr_badge}
            <div style="font-size:10px; color:#3A4558; margin-top:8px; line-height:1.5;">
                {caveat}
            </div>
        </div>
        """, unsafe_allow_html=True)

    with sc2:
        ## Dimension cards with contribution breakdown
        dims_config = [
            ("Sustainability", "sustainability", "#2E8B57", "40%"),
            ("Efficiency",     "efficiency",     "#7C5CBF", "35%"),
            ("Solvency",       "solvency",       "#2F6FA8", "25%")
        ]
        dc1, dc2, dc3 = st.columns(3)

        for col, (label, key, clr, weight) in zip([dc1, dc2, dc3], dims_config):
            dim_val  = cr["dimension_scores"].get(key)
            contrib  = cr["contribution"].get(key, {})
            display  = f"{dim_val:.0f}" if dim_val is not None else "—"
            pts_line = (f"{contrib.get('contributed','—')}/{contrib.get('max','—')} pts"
                        if contrib else weight + " weight")
            note     = "Excluded" if key in excl else ""

            with col:
                st.markdown(f"""
                <div style="background:#132030; border-radius:10px; padding:16px 12px;
                            text-align:center; border-top:3px solid {clr};
                            border-left:1px solid rgba(255,255,255,0.06);
                            border-right:1px solid rgba(255,255,255,0.06);
                            border-bottom:1px solid rgba(255,255,255,0.06);
                            margin-bottom:10px;">
                    <div style="font-size:10px; color:{clr}; text-transform:uppercase;
                                letter-spacing:0.08em; margin-bottom:5px;">{label}</div>
                    <div style="font-size:34px; font-weight:700; color:{clr}; line-height:1;">
                        {display}
                    </div>
                    <div style="font-size:10px; color:#4A5568; margin-top:3px;">
                        {note or pts_line}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        ## Contribution breakdown row
        if cr["contribution"]:
            contrib_parts = []
            for dim, data in cr["contribution"].items():
                clr_map = {"sustainability": "#2E8B57", "efficiency": "#7C5CBF", "solvency": "#2F6FA8"}
                clr = clr_map.get(dim, "#6B7A8E")
                contrib_parts.append(
                    f"<span style='color:{clr}; font-weight:600;'>{dim.capitalize()}</span> "
                    f"<span style='color:#8A95A8;'>{data['contributed']}/{data['max']} pts</span>"
                )
            st.markdown(
                "<div style='font-size:12px; color:#4A5568; margin-top:4px; text-align:center;'>"
                + " &nbsp;·&nbsp; ".join(contrib_parts) + "</div>",
                unsafe_allow_html=True
            )

        ## Floor rule warning
        if cr["floor_rule"]:
            st.warning(
                "⚠️ **Floor Rule Triggered** — Program spending is below 50% of total expenses. "
                "This is a structural concern about mission alignment. "
                "The composite score may not fully reflect organizational risk."
            )

    st.divider()

    ## ── PANEL 3: REVENUE CONCENTRATION SIGNAL ──
    conc_pct = ratios.get("concentration_pct")
    if conc_pct is not None:
        if conc_pct > CONCENTRATION_CRITICAL:
            conc_color = "#E05050"
            conc_label = "CRITICAL"
        elif conc_pct > CONCENTRATION_ELEVATED:
            conc_color = "#E8A020"
            conc_label = "ELEVATED"
        else:
            conc_color = "#4CAF82"
            conc_label = "LOW RISK"

        st.markdown(f"""
        <div style="background:#132030; border:1px solid rgba(255,255,255,0.07);
                    border-left:4px solid {conc_color}; border-radius:0 10px 10px 0;
                    padding:14px 18px; margin-bottom:16px;">
            <div style="display:flex; align-items:center; gap:10px;">
                <span style="font-size:10px; font-weight:600; color:{conc_color};
                             text-transform:uppercase; letter-spacing:0.08em;
                             padding:2px 8px; background:rgba(255,255,255,0.04);
                             border-radius:4px;">{conc_label}</span>
                <span style="font-size:13px; color:#E8EAF0; font-weight:500;">
                    Revenue Concentration Signal
                </span>
                <span style="font-size:13px; color:{conc_color}; font-weight:600; margin-left:auto;">
                    {conc_pct*100:.1f}% from top funder
                </span>
            </div>
            <div style="font-size:12px; color:#6B7A8E; margin-top:6px;">
                Signal only — not included in composite score.
                Threshold: &gt;30% Elevated · &gt;40% Critical
                (pending supervisor confirmation).
            </div>
        </div>
        """, unsafe_allow_html=True)

    ## ── PANEL 4: RATIO SUMMARY TABLE ──
    st.subheader("Ratio Summary")

    ratio_rows = []
    for ratio_name, bench in BENCHMARKS.items():
        value     = ratios.get(ratio_name)
        score_val = tier_score(ratio_name, value)
        flag      = flags.get(ratio_name, "clean")

        if flag == "proxy":
            tier_display = "⚠️ See Note"
        elif score_val is not None:
            emoji_map    = {100: "🟢", 75: "🔵", 50: "🟡", 25: "🔴"}
            tier_display = f"{emoji_map.get(score_val,'')} {get_tier_label(score_val)}"
        else:
            tier_display = "⬜ Unavailable"

        note = bench.get("note") or ""
        if flag == "proxy":
            note = ("Total Revenue used as proxy. May overstate result significantly. "
                    "Enter Fundraising Income in the dedicated field for accuracy. " + note)

        ratio_rows.append({
            "Ratio":     bench["label"],
            "Value":     format_ratio_value(ratio_name, value),
            "Tier":      tier_display,
            "Score":     score_val if score_val is not None else "—",
            "Dimension": bench["dimension"].capitalize(),
            "Note":      (note[:120] + "...") if len(note) > 120 else note
        })

    ## Current ratio reference
    cr_val = ratios.get("current_ratio")
    ratio_rows.append({
        "Ratio":     "Current Ratio (reference — not scored)",
        "Value":     f"{cr_val:.2f}" if cr_val is not None else "—",
        "Tier":      "📋 Reference",
        "Score":     "—",
        "Dimension": "Reference",
        "Note":      "1.5–2.0 is healthy. >3.0 may indicate underinvestment of reserves."
    })

    st.dataframe(pd.DataFrame(ratio_rows), use_container_width=True, hide_index=True)
    st.divider()

    ## ── PANEL 5: SCENARIO MODELING ──
    st.subheader("Scenario Modeling")
    st.caption(
        "Simulates revenue decline impact. Only Operating Surplus Margin and "
        "Revenue Growth Rate recalculate — all other ratios held constant because "
        "expenses, assets, and debt do not change instantly when revenue drops."
    )

    ## Scenario insight sentences (displayed prominently above the chart)
    insights_shown = any([band_change_pct, breakpoint_pct, mi_dim])
    if insights_shown:
        st.markdown("**Key Insights**")
        insight_cols = st.columns(3)
        with insight_cols[0]:
            if band_change_pct:
                st.markdown(f"""
                <div style="background:#132030; border-radius:8px; padding:12px 14px;
                            border-top:2px solid #E05050;">
                    <div style="font-size:10px; color:#E05050; text-transform:uppercase;
                                letter-spacing:0.07em; margin-bottom:4px;">Band Change</div>
                    <div style="font-size:13px; color:#E8EAF0; line-height:1.5;">
                        Score drops from <strong style="color:{color};">{band}</strong>
                        to next lower band at approximately
                        <strong style="color:#E05050;">−{band_change_pct}%</strong>
                        revenue decline.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="background:#132030; border-radius:8px; padding:12px 14px;
                            border-top:2px solid #3A4558;">
                    <div style="font-size:10px; color:#4A5568; text-transform:uppercase;
                                letter-spacing:0.07em; margin-bottom:4px;">Band Change</div>
                    <div style="font-size:12px; color:#6B7A8E;">
                        Score stays in current band through −50% decline.
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with insight_cols[1]:
            if breakpoint_pct:
                st.markdown(f"""
                <div style="background:#132030; border-radius:8px; padding:12px 14px;
                            border-top:2px solid #E8A020;">
                    <div style="font-size:10px; color:#E8A020; text-transform:uppercase;
                                letter-spacing:0.07em; margin-bottom:4px;">Surplus Breakpoint</div>
                    <div style="font-size:13px; color:#E8EAF0; line-height:1.5;">
                        Operating surplus becomes negative at
                        <strong style="color:#E8A020;">−{breakpoint_pct}%</strong>
                        revenue decline.
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="background:#132030; border-radius:8px; padding:12px 14px;
                            border-top:2px solid #3A4558;">
                    <div style="font-size:10px; color:#4A5568; text-transform:uppercase;
                                letter-spacing:0.07em; margin-bottom:4px;">Surplus Breakpoint</div>
                    <div style="font-size:12px; color:#6B7A8E;">
                        Already in deficit or insufficient data.
                    </div>
                </div>
                """, unsafe_allow_html=True)

        with insight_cols[2]:
            if mi_dim:
                mi_color = DIMENSION_COLORS.get(mi_dim, "#6B7A8E")
                st.markdown(f"""
                <div style="background:#132030; border-radius:8px; padding:12px 14px;
                            border-top:2px solid {mi_color};">
                    <div style="font-size:10px; color:{mi_color}; text-transform:uppercase;
                                letter-spacing:0.07em; margin-bottom:4px;">Most Impacted (−20%)</div>
                    <div style="font-size:13px; color:#E8EAF0; line-height:1.5;">
                        <strong style="color:{mi_color};">{mi_dim.capitalize()}</strong>
                        drops from {mi_base} to
                        <strong style="color:#E05050;">{mi_sc}</strong>
                        under a −20% revenue scenario.
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("<div style='margin-top:16px;'></div>", unsafe_allow_html=True)

    ## Scenario selector
    sc_col1, sc_col2 = st.columns([2, 3])
    with sc_col1:
        preset_choice = st.radio(
            "Select scenario",
            ["−10% Revenue", "−20% Revenue", "−25% Revenue", "Custom"],
            horizontal=True
        )
        if preset_choice == "Custom":
            custom_pct     = st.slider("Custom decline (%)", 0, 50, 15, 1)
            active_decline = custom_pct / 100
        else:
            active_decline = {"−10% Revenue": 0.10, "−20% Revenue": 0.20, "−25% Revenue": 0.25}[preset_choice]

    active_scenario = run_scenario(saved_inputs, ratios, cr, active_decline)

    if active_scenario:
        baseline_score = cr.get("composite")
        scenario_score = active_scenario["scenario_composite"].get("composite")
        scenario_band  = active_scenario["scenario_composite"].get("band")
        delta = (scenario_score - baseline_score) if (baseline_score and scenario_score) else None

        with sc_col2:
            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Baseline Score", f"{baseline_score}/100" if baseline_score else "N/A")
            with m2:
                st.metric(
                    f"Scenario ({int(active_decline*100)}% decline)",
                    f"{scenario_score}/100" if scenario_score else "N/A",
                    delta=f"{delta:+.0f} pts" if delta is not None else None,
                    delta_color="inverse"
                )
            with m3:
                sc_color = BAND_COLORS.get(scenario_band, "#6B7A8E")
                st.metric("Scenario Band", scenario_band or "N/A")

        ## Scenario bar chart with band reference lines
        if baseline_score and scenario_score:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Baseline", x=["Score"], y=[baseline_score],
                marker_color="#2E8B57",
                text=[f"{baseline_score}"], textposition="outside",
                textfont=dict(color="#E8EAF0", size=14)
            ))
            fig.add_trace(go.Bar(
                name=f"−{int(active_decline*100)}% Revenue", x=["Score"], y=[scenario_score],
                marker_color="#E05050",
                text=[f"{scenario_score}"], textposition="outside",
                textfont=dict(color="#E8EAF0", size=14)
            ))

            ## Band reference lines at 80, 60, 40
            for threshold, label, lcolor in [
                (80, "Strong / Stable", "#4CAF82"),
                (60, "Stable / Watchlist", "#E8A020"),
                (40, "Watchlist / Distressed", "#E05050")
            ]:
                fig.add_hline(
                    y=threshold,
                    line_dash="dot",
                    line_color=lcolor,
                    line_width=1,
                    annotation_text=label,
                    annotation_position="right",
                    annotation_font=dict(color=lcolor, size=10)
                )

            fig.update_layout(
                barmode="group", height=300,
                margin=dict(t=30, b=10, l=10, r=80),
                yaxis=dict(range=[0, 115], title="Score", color="#6B7A8E", gridcolor="rgba(255,255,255,0.05)"),
                xaxis=dict(color="#6B7A8E"),
                plot_bgcolor="#132030",
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(font=dict(color="#8A95A8", size=11), bgcolor="rgba(0,0,0,0)"),
                font=dict(color="#8A95A8")
            )
            st.plotly_chart(fig, use_container_width=True)

        ## Ratio impact table
        st.markdown("**Ratio-level impact**")
        flag_sym_map = {"green": "🟢 No change", "yellow": "🟡 Degraded", "red": "🔴 Critical", "gray": "⬜ N/A"}
        scen_rows = []
        for ratio_name, bench in BENCHMARKS.items():
            scen_rows.append({
                "Ratio":    bench["label"],
                "Baseline": format_ratio_value(ratio_name, ratios.get(ratio_name)),
                "Scenario": format_ratio_value(ratio_name, active_scenario["scenario_ratios"].get(ratio_name)),
                "Status":   flag_sym_map.get(active_scenario["status_flags"].get(ratio_name, "gray"), "⬜"),
                "Changes?": "Yes — recalculates" if ratio_name in SCENARIO_CHANGES else "Held constant"
            })
        st.dataframe(pd.DataFrame(scen_rows), use_container_width=True, hide_index=True)

        st.caption(
            "⚠️ Balance sheet metrics (Working Capital Ratio, Months of Runway) "
            "are held constant across all scenarios. A sustained revenue decline "
            "would erode these over time — treat as a floor, not a stable baseline."
        )

    st.divider()

    ## ── PANEL 6: WHAT THIS SCORE DOES NOT CAPTURE ──
    st.subheader("What This Score Does Not Capture")

    st.markdown(f"""
    <div style="background:#132030; border-left:4px solid #E8A020;
                border-radius:0 10px 10px 0; padding:16px 20px; margin-bottom:16px;">
        <div style="font-size:16px; font-weight:600; color:#E8EAF0; line-height:1.5;">
            A score of {score}/100 means the financial ratios are healthy.
            It does not mean there are no financial risks.
        </div>
    </div>
    """, unsafe_allow_html=True)

    severity_colors = {
        "High":       "#E05050",
        "Medium":     "#E8A020",
        "Low":        "#2E8B57",
        "Structural": "#7C5CBF"
    }
    for lim in SCORE_LIMITATIONS:
        sc = severity_colors.get(lim["severity"], "#6B7A8E")
        st.markdown(f"""
        <div style="background:#132030; border-radius:8px; padding:13px 16px;
                    margin-bottom:8px; border:1px solid rgba(255,255,255,0.05);">
            <div style="display:flex; align-items:center; gap:8px; margin-bottom:3px;">
                <span style="font-size:9px; font-weight:600; color:{sc};
                             padding:2px 7px; background:rgba(255,255,255,0.04);
                             border-radius:3px; text-transform:uppercase;
                             letter-spacing:0.06em;">{lim["severity"]}</span>
                <span style="font-size:13px; font-weight:500; color:#E8EAF0;">
                    {lim["limitation"]}
                </span>
            </div>
            <div style="font-size:12px; color:#6B7A8E; line-height:1.5; margin-top:3px;">
                {lim["description"]}
            </div>
            <div style="font-size:11px; color:{sc}; margin-top:5px;">
                → {lim["action"]}
            </div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    ## ── PANEL 7: DATA GAPS ──
    st.subheader("Data Gaps")

    unavailable_fields = [k for k, v in saved_inputs.items() if v is None]
    unavailable_ratios = [BENCHMARKS[r]["label"] for r in BENCHMARKS if ratios.get(r) is None]

    field_labels_display = {
        "total_revenue":        "Total Revenue",
        "total_expenses":       "Total Expenses",
        "program_expenses":     "Program Expenses",
        "admin_expenses":       "Administrative Expenses",
        "fundraising_expenses": "Fundraising Expenses",
        "fundraising_income":   "Fundraising Income",
        "top_funder_revenue":   "Top Funder Revenue",
        "current_assets":       "Current Assets",
        "current_liabilities":  "Current Liabilities",
        "total_assets":         "Total Assets",
        "total_liabilities":    "Total Liabilities",
        "prior_year_revenue":   "Prior Year Revenue"
    }

    ## Exclude optional fields from the gap count
    optional_fields = {"fundraising_income", "top_funder_revenue"}
    required_unavailable = [f for f in unavailable_fields if f not in optional_fields]

    if not required_unavailable:
        st.success("All required input fields were provided. No data gaps detected.")
    else:
        st.warning(
            f"{len(required_unavailable)} required field(s) unavailable, "
            f"affecting {len(unavailable_ratios)} ratio(s)."
        )
        gap_rows = []
        for f in required_unavailable:
            affected = [
                BENCHMARKS[r]["label"] for r in BENCHMARKS
                if ratios.get(r) is None
                and f in {
                    "total_revenue":     ["operating_surplus_margin", "revenue_growth_rate", "fundraising_efficiency"],
                    "total_expenses":    ["program_efficiency", "admin_expense_pct", "operating_surplus_margin", "working_capital_ratio", "months_runway"],
                    "program_expenses":  ["program_efficiency"],
                    "admin_expenses":    ["admin_expense_pct"],
                    "fundraising_expenses": ["fundraising_efficiency"],
                    "current_assets":    ["working_capital_ratio", "months_runway", "current_ratio"],
                    "current_liabilities": ["working_capital_ratio", "current_ratio"],
                    "total_assets":      ["debt_ratio"],
                    "total_liabilities": ["debt_ratio"],
                    "prior_year_revenue": ["revenue_growth_rate"]
                }.get(f, [])
            ]
            gap_rows.append({
                "Unavailable Field":  field_labels_display.get(f, f),
                "Affected Ratios":    ", ".join(affected) if affected else "See ratio table",
                "Impact":             "Excluded from scoring and composite calculation"
            })
        st.dataframe(pd.DataFrame(gap_rows), use_container_width=True, hide_index=True)

        if excl:
            st.error(
                f"Dimension(s) fully excluded from scoring: "
                f"{', '.join([d.capitalize() for d in excl])}. "
                f"Weights redistributed proportionally."
            )

    st.divider()

    ## ── PANEL 8: EXPORT ──
    st.subheader("Export")
    st.caption(
        "Downloads a 7-tab Excel file. Open in Excel and use Copilot or Claude "
        "with the AI Analysis Framework tab as your prompt context to generate "
        "a structured narrative assessment following BBS standards."
    )

    ## Pre-run all standard scenarios
    all_scenarios = {}
    for pct in SCENARIO_PRESETS:
        all_scenarios[f"−{int(pct*100)}% Revenue"] = run_scenario(
            saved_inputs, ratios, cr, pct
        )
    if preset_choice == "Custom":
        all_scenarios[f"−{int(active_decline*100)}% Revenue (custom)"] = active_scenario

    excel_file = generate_excel(
        saved_inputs, saved_sources, ratios, flags,
        cr, all_scenarios,
        saved_org, saved_year, saved_profile, saved_data_prof,
        date.today(),
        band_change_pct, breakpoint_pct,
        mi_dim, mi_base, mi_sc
    )

    safe_name = (saved_org or "Organization").replace(" ", "_").replace("/", "-")
    st.download_button(
        label="⬇️  Download Excel Report (7 tabs)",
        data=excel_file,
        file_name=f"BBS_Financial_Assessment_{safe_name}_{saved_year}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )


## ============================================================
## SECTION 13 — METHODOLOGY EXPANDER
## ============================================================

st.divider()
with st.expander("About this tool — Methodology & Sources"):
    st.markdown("""
    **Scoring Model**

    Three-dimension model: Sustainability (40%), Efficiency (35%), Solvency (25%).
    Eight ratios convert to standardized tier scores — Excellent (100), Strong (75),
    Average (50), Issues (25) — grounded in Charity Navigator's Accountability &
    Finance methodology and Nonprofit Finance Fund (NFF) benchmarks.

    **Contribution Breakdown**

    The composite score shows how many points each dimension contributed.
    For example: Sustainability 37/40 pts · Efficiency 29/35 pts · Solvency 22/25 pts.
    This makes the score self-explanatory and auditable.

    **Scenario Insights**

    Three pre-calculated insight sentences accompany every scenario analysis:
    Band Change Detection (exact decline % that moves the score to the next band),
    Surplus Breakpoint (exact decline % that puts the org into deficit), and
    Most Impacted Dimension (which dimension takes the hardest hit at −20% revenue).

    **Fundraising Efficiency**

    When Fundraising Income is provided separately, it is used as the numerator
    (correct formula). When not provided, Total Revenue is used as proxy and the
    ratio is flagged. A ratio exceeding 50:1 triggers an automatic validation warning.

    **Revenue Concentration Signal**

    Top Funder as a % of Total Revenue. Signal only — not included in composite score.
    >30% = Elevated flag. >40% = Critical flag. Thresholds pending supervisor confirmation.

    **Partial Data**

    Unavailable inputs return null — not zero. Ratios with null inputs are excluded.
    If an entire dimension is unavailable, its weight redistributes proportionally.
    The composite score carries a confidence statement and caveat.

    **AI Analysis Framework (Tab 7)**

    The Excel export includes a condensed version of Part 9 of the BBS Financial
    Health Assessment Framework Playbook (v1.0, April 2026). Consultants open the
    Excel in Copilot or Claude and use Tab 7 as the prompt context to generate a
    structured narrative assessment following BBS standards. The full Playbook
    is a separate document that provides complete analytical guidance.

    **Framework Scope**

    This dashboard supports approximately 5 of the 9 fixed core dimensions in the
    BBS Framework Playbook. Operating Reserve Coverage, Net Asset Flexibility, and
    full Asset Base analysis require additional input fields added in a future version.
    Tab 7 explicitly scopes what the AI can and cannot analyze from this data set.

    **Limitations**

    This tool is a decision-support instrument. It does not replace professional
    accounting review. Composite score reflects quantitative ratios only.

    *v3.0 Prototype — Bridge Builder Strategies BRIDGE Project, April 2026*
    """)
