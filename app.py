## ============================================================
## BBS NONPROFIT FINANCIAL HEALTH DASHBOARD
## Bridge Builder Strategies — BRIDGE Project
## Author: Tapan Mandal
## Version: 2.0 Prototype
## ============================================================
## CHANGES FROM V1:
##   - Fundraising Income added as separate optional input
##   - Three-level fundraising efficiency logic
##   - "What This Score Does Not Capture" limitations panel
##   - Admin % context note in ratio table
##   - Scenario balance sheet caveat
##   - Fundraising efficiency > 50:1 validation warning
##   - Visual redesign: score card, dimension cards, BBS header
##   - Excel expanded to 7 tabs including AI Analysis Framework
##   - Output leads with Key Finding, not score number
## ============================================================


## ============================================================
## SECTION 1 — IMPORTS
## ============================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO
from datetime import date


## ============================================================
## SECTION 2 — PAGE CONFIGURATION
## Must be the FIRST Streamlit command in the file.
## ============================================================

st.set_page_config(
    page_title="BBS Financial Dashboard",
    page_icon="📊",
    layout="wide"
)


## ============================================================
## SECTION 3 — CUSTOM CSS
## Visual styling only — does not affect any calculations.
## ============================================================

st.markdown("""
<style>
    .main { background-color: #0f1117; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }

    [data-testid="metric-container"] {
        background: #1e2333;
        border-radius: 10px;
        padding: 16px;
        border: 1px solid rgba(255,255,255,0.08);
    }
    [data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
    }
    [data-testid="baseButton-primary"] {
        background: #2dd4bf !important;
        color: #0f1117 !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        border: none !important;
    }
    [data-testid="baseButton-secondary"] {
        border-radius: 8px !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
    }
    [data-testid="stNumberInput"] input {
        background: #1e2333;
        border-radius: 6px;
    }
    [data-testid="stExpander"] {
        background: #1e2333;
        border-radius: 10px;
        border: 1px solid rgba(255,255,255,0.08) !important;
    }
    hr { border-color: rgba(255,255,255,0.08) !important; }
    h2 {
        border-bottom: 2px solid #2dd4bf;
        padding-bottom: 8px;
        margin-top: 8px !important;
    }
    h3 { color: #e8eaf0 !important; }
</style>
""", unsafe_allow_html=True)


## ============================================================
## SECTION 4 — CONFIG
## Every number a supervisor might adjust lives here.
## Nothing hardcoded in calculation functions.
## ============================================================

DIMENSION_WEIGHTS = {
    "sustainability": 0.40,
    "efficiency":     0.35,
    "solvency":       0.25
}

DIMENSIONS = {
    "sustainability": ["operating_surplus_margin", "revenue_growth_rate", "months_runway"],
    "efficiency":     ["program_efficiency", "admin_expense_pct", "fundraising_efficiency"],
    "solvency":       ["working_capital_ratio", "debt_ratio"]
}

## Floor rule: program efficiency below this triggers reliability warning
FLOOR_RULE_THRESHOLD = 0.50

## Fundraising proxy warning: ratio above this likely reflects wrong numerator
FUNDRAISING_PROXY_WARNING_THRESHOLD = 50.0

SCORE_BANDS = {
    "Strong":     (80, 100),
    "Stable":     (60, 79),
    "Watchlist":  (40, 59),
    "Distressed": (0,  39)
}

BAND_COLORS = {
    "Strong":     "#4ade80",
    "Stable":     "#2dd4bf",
    "Watchlist":  "#fbbf24",
    "Distressed": "#f87171"
}

## Benchmark tiers per ratio
## direction: "higher" = bigger value is better
##            "lower"  = smaller value is better (inverted scoring)
## Thresholds grounded in Charity Navigator methodology
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
        "note":        "Benchmark reflects sector median (~15-20%). Complex multi-program organizations with infrastructure costs typically range 20-28%. Average rating does not automatically indicate inefficiency."
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
        "note":        "For organizations with investment portfolios, this figure includes investment returns which are not operationally generated. If investment return is significant, operational margin may be substantially lower than reported."
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
        "note":        "Includes restricted grant revenue. For organizations where one or two grantors drive the majority of revenue, this may overstate sustainable growth."
    },
    "months_runway": {
        "label":       "Months of Operating Runway",
        "direction":   "higher",
        "excellent":   6.0, "strong": 3.0, "average": 1.0,
        "format":      "months",
        "dimension":   "sustainability",
        "description": "Months org could operate using current assets if revenue stopped",
        "note":        "Calculated from total current assets. For greater precision, use liquid assets available for general use from the audit liquidity note (Note 11 or equivalent)."
    }
}

SCENARIO_PRESETS  = [0.10, 0.20, 0.25]
SCENARIO_CHANGES  = ["operating_surplus_margin", "revenue_growth_rate"]
SCENARIO_CONSTANT = [
    "program_efficiency", "admin_expense_pct", "fundraising_efficiency",
    "working_capital_ratio", "debt_ratio", "months_runway"
]

DATA_SOURCE_OPTIONS = [
    "Audited Financials", "IRS Form 990",
    "YTD Projection", "Budget Estimate"
]

ORG_PROFILES = [
    "Service-Delivery Nonprofit",
    "Advocacy / Capacity-Building",
    "Community / Cultural Organization"
]

## Score limitations — used in dashboard panel and Excel Tab 5
SCORE_LIMITATIONS = [
    {
        "limitation":  "Operating Surplus Margin includes investment returns",
        "severity":    "High",
        "affects":     "Sustainability score",
        "description": "Investment returns are not operationally generated and cannot be relied upon year to year. If a significant portion of the surplus comes from investment return, the true operational margin may be substantially lower than reported.",
        "action":      "Request investment return breakdown. Recalculate operational margin separately if needed."
    },
    {
        "limitation":  "Revenue Growth Rate includes restricted grant revenue",
        "severity":    "Medium",
        "affects":     "Sustainability score",
        "description": "Growth driven by a single restricted funder is not the same as sustainable diversified revenue growth. For high grant-concentration organizations, this ratio may overstate sustainability.",
        "action":      "Review unrestricted revenue trend separately. Ask: what specifically drove the growth?"
    },
    {
        "limitation":  "Months of Runway calculated from total current assets",
        "severity":    "Low",
        "affects":     "Sustainability score",
        "description": "Total current assets may include receivables that are restricted or not immediately liquid. The audit liquidity note (Note 11) typically discloses a more precise figure.",
        "action":      "Cross-reference with audit Note 11 (Liquidity and Availability) if available."
    },
    {
        "limitation":  "Fundraising Efficiency may use Total Revenue as proxy",
        "severity":    "Medium",
        "affects":     "Efficiency score",
        "description": "When Fundraising Income is not separately tracked, Total Revenue is used as the numerator. For organizations with significant grant, investment, or program revenue, this can substantially overstate fundraising return.",
        "action":      "Check if Fundraising Income is tracked separately in the audit. Enter it in the dedicated field if available."
    },
    {
        "limitation":  "Composite score reflects financial ratios only",
        "severity":    "Structural",
        "affects":     "Overall score",
        "description": "The score does not capture: revenue concentration risk, grant compliance issues, program-level cost sustainability, subsidiary obligations, sunsetting program staff costs, or early-year performance trends.",
        "action":      "Supplement with qualitative organizational assessment. A high score means ratios are healthy — not that there are no financial risks."
    }
]


## ============================================================
## SECTION 5 — VALIDATION
## Run before any calculation.
## Hard errors block output. Warnings show alongside results.
## ============================================================

def validate_inputs(inputs, fundraising_efficiency_value=None):
    errors   = []
    warnings = []

    rev  = inputs.get("total_revenue")
    exp  = inputs.get("total_expenses")
    prog = inputs.get("program_expenses")
    ta   = inputs.get("total_assets")
    tl   = inputs.get("total_liabilities")

    if rev  is not None and rev  < 0: errors.append("Total Revenue cannot be negative.")
    if exp  is not None and exp  < 0: errors.append("Total Expenses cannot be negative.")
    if prog is not None and exp is not None and prog > exp:
        errors.append("Program Expenses cannot exceed Total Expenses.")
    if ta   is not None and tl is not None and tl > ta:
        warnings.append("Total Liabilities exceed Total Assets — organization may be technically insolvent.")

    ## Fundraising proxy overstatement check
    if fundraising_efficiency_value is not None:
        if fundraising_efficiency_value > FUNDRAISING_PROXY_WARNING_THRESHOLD:
            warnings.append(
                f"Fundraising Efficiency of {fundraising_efficiency_value:.1f}:1 "
                f"likely reflects non-fundraising revenue in the numerator. "
                f"Enter Fundraising Income separately in the dedicated field "
                f"for an accurate result. Treat current ratio as unverified."
            )

    return errors, warnings


## ============================================================
## SECTION 6 — RATIO CALCULATIONS
## None = data unavailable (not zero).
## Returns ratios dict + flags dict (proxy/clean/unavailable).
## ============================================================

def calculate_ratios(inputs):
    rev      = inputs.get("total_revenue")
    exp      = inputs.get("total_expenses")
    prog     = inputs.get("program_expenses")
    admin    = inputs.get("admin_expenses")
    fund_exp = inputs.get("fundraising_expenses")
    fund_inc = inputs.get("fundraising_income")   ## NEW optional field
    ca       = inputs.get("current_assets")
    cl       = inputs.get("current_liabilities")
    ta       = inputs.get("total_assets")
    tl       = inputs.get("total_liabilities")
    prior    = inputs.get("prior_year_revenue")

    ratios = {}
    flags  = {}  ## tracks "clean", "proxy", or "unavailable" per ratio

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

    ## R5 — Working Capital Ratio
    ## Value × 12 = months of buffer (shown in display)
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

    ## R8 — Months of Operating Runway (returns months directly)
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

    return ratios, flags


## ============================================================
## SECTION 7 — TIER SCORING
## Maps ratio value → 100, 75, 50, or 25.
## Handles both higher-is-better and lower-is-better directions.
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
        ## Inverted — lower value earns higher score
        if value <= excellent: return 100
        elif value <= strong:  return 75
        elif value <= average: return 50
        else:                  return 25

def get_tier_label(score):
    return {100: "Excellent", 75: "Strong", 50: "Average", 25: "Issues"}.get(score, "N/A")

def get_tier_color(score):
    return {100: "#4ade80", 75: "#2dd4bf", 50: "#fbbf24", 25: "#f87171"}.get(score, "#9aa0b4")


## ============================================================
## SECTION 8 — COMPOSITE SCORING
## Three partial data cases:
##   A: One ratio unavailable → score remaining, include dimension
##   B: Full dimension unavailable → exclude, redistribute weight
##   C: Two dimensions unavailable → score one, strong warning
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
        "key_finding":      ""
    }

    ## Floor rule
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

    ## Composite with proportional weight redistribution
    available_dims = {d: s for d, s in dimension_scores.items() if s is not None}
    if not available_dims:
        return result

    total_weight = sum(DIMENSION_WEIGHTS[d] for d in available_dims)
    composite    = sum(
        score * (DIMENSION_WEIGHTS[dim] / total_weight)
        for dim, score in available_dims.items()
    )
    result["composite"] = round(composite)

    for band_label, (low, high) in SCORE_BANDS.items():
        if low <= result["composite"] <= high:
            result["band"] = band_label
            break

    result["key_finding"] = generate_key_finding(result, ratios, flags or {})
    return result


def generate_key_finding(composite_result, ratios, flags):
    """Produces plain-language finding that leads the output."""
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
    base = base_map.get(band, "financial ratios reflect mixed performance across dimensions")

    dim_scores = {k: v for k, v in composite_result["dimension_scores"].items() if v is not None}
    if dim_scores:
        strongest = max(dim_scores, key=dim_scores.get)
        weakest   = min(dim_scores, key=dim_scores.get)
        finding   = (
            f"This organization's {base}. "
            f"Strongest dimension: {strongest.capitalize()} ({dim_scores[strongest]:.0f}/100). "
        )
        if strongest != weakest:
            finding += f"Area for attention: {weakest.capitalize()} ({dim_scores[weakest]:.0f}/100)."
    else:
        finding = f"This organization's {base}."

    if flags.get("fundraising_efficiency") == "proxy":
        finding += " Note: Fundraising Efficiency uses Total Revenue as a proxy — verify against fundraising-specific income."

    return finding


## ============================================================
## SECTION 9 — SCENARIO ENGINE
## Only Operating Surplus Margin and Revenue Growth Rate change.
## All other ratios held constant.
## ============================================================

def run_scenario(inputs, ratios, composite_result, decline_pct):
    rev   = inputs.get("total_revenue")
    exp   = inputs.get("total_expenses")
    prior = inputs.get("prior_year_revenue")

    if rev is None:
        return None

    scenario_revenue = rev * (1 - decline_pct)
    scenario_ratios  = ratios.copy()

    ## Recalculate the two affected ratios
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

    ## Status flags
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


## ============================================================
## SECTION 10 — FORMATTING HELPERS
## ============================================================

def format_ratio_value(ratio_name, value):
    if value is None:
        return "—"
    fmt = BENCHMARKS.get(ratio_name, {}).get("format", "decimal")
    if fmt == "percent":    return f"{value * 100:.1f}%"
    elif fmt == "dollar":   return f"${value:.2f} per $1"
    elif fmt == "months_wc": return f"{value * 12:.1f} months"
    elif fmt == "months":   return f"{value:.1f} months"
    return f"{value:.3f}"

def format_currency(value):
    if value is None: return "—"
    return f"${value:,.2f}"


## ============================================================
## SECTION 11 — EXCEL EXPORT (7 TABS)
## Tab 1: Organization Profile
## Tab 2: Raw Inputs
## Tab 3: Ratio Results (with flags and notes)
## Tab 4: Dimension Scores
## Tab 5: Score Limitations
## Tab 6: Scenario Results
## Tab 7: AI Analysis Framework (Copilot/Claude prompt)
## ============================================================

def generate_excel(
    inputs, source_tags, ratios, flags, composite_result,
    scenario_results, org_name, fiscal_year, org_profile,
    data_profile, assessment_date
):
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        ## ---- TAB 1: Organization Profile ----
        score = composite_result.get("composite")
        band  = composite_result.get("band")
        avail = composite_result.get("available_ratios")
        total = composite_result.get("total_ratios")
        excl  = composite_result.get("excluded_dims", [])

        profile_rows = [
            {"Field": "Organization Name",    "Value": org_name or "Not specified"},
            {"Field": "Fiscal Year",           "Value": str(fiscal_year)},
            {"Field": "Assessment Date",       "Value": str(assessment_date)},
            {"Field": "Org Profile",           "Value": org_profile},
            {"Field": "Data Profile",          "Value": data_profile},
            {"Field": "Assessed By",           "Value": "Bridge Builder Strategies"},
            {"Field": "Overall Score",         "Value": f"{score}/100" if score else "N/A"},
            {"Field": "Score Band",            "Value": band or "N/A"},
            {"Field": "Score Confidence",      "Value": f"{avail} of {total} indicators available"},
            {"Field": "Excluded Dimensions",   "Value": ", ".join(excl) if excl else "None"},
            {"Field": "Floor Rule Triggered",  "Value": str(composite_result.get("floor_rule", False))},
            {"Field": "Key Finding",           "Value": composite_result.get("key_finding", "")}
        ]
        pd.DataFrame(profile_rows).to_excel(
            writer, sheet_name="Organization Profile", index=False
        )

        ## ---- TAB 2: Raw Inputs ----
        field_labels = {
            "total_revenue":        "Total Revenue ($)",
            "total_expenses":       "Total Expenses ($)",
            "program_expenses":     "Program Expenses ($)",
            "admin_expenses":       "Administrative Expenses ($)",
            "fundraising_expenses": "Fundraising Expenses ($)",
            "fundraising_income":   "Fundraising Income ($)",
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
                if value is not None:
                    status = "Verified — used as Fundraising Efficiency numerator"
                else:
                    status = "Not provided — Total Revenue used as proxy"
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

        ## ---- TAB 3: Ratio Results ----
        ratio_rows = []
        for ratio_name, bench in BENCHMARKS.items():
            value      = ratios.get(ratio_name)
            score_val  = tier_score(ratio_name, value)
            flag       = flags.get(ratio_name, "clean")
            tier_label = get_tier_label(score_val) if score_val else "Unavailable"

            if flag == "proxy":
                tier_label  = "See Note — Proxy Used"
                data_flag   = "Proxy — Total Revenue used as numerator"
            elif flag == "unavailable":
                data_flag   = "Unavailable"
            else:
                data_flag   = "Clean"

            ratio_rows.append({
                "Ratio":      bench["label"],
                "Value":      format_ratio_value(ratio_name, value),
                "Tier":       tier_label,
                "Tier Score": score_val if score_val else "—",
                "Dimension":  bench["dimension"].capitalize(),
                "Data Flag":  data_flag,
                "Note":       bench.get("note") or ""
            })

        ## Current ratio reference row
        cr = ratios.get("current_ratio")
        ratio_rows.append({
            "Ratio":      "Current Ratio (reference — not scored)",
            "Value":      f"{cr:.2f}" if cr is not None else "—",
            "Tier":       "Reference only",
            "Tier Score": "—",
            "Dimension":  "Reference",
            "Data Flag":  "Reference",
            "Note":       "1.5-2.0 is healthy. >3.0 may indicate underinvestment of reserves."
        })

        ## Spacer and dimension summary rows
        ratio_rows.append({k: "" for k in ratio_rows[0].keys()})
        for dim, dim_score in composite_result["dimension_scores"].items():
            ratio_rows.append({
                "Ratio":      f"— {dim.capitalize()} Dimension Score",
                "Value":      f"{dim_score:.1f}/100" if dim_score else "Excluded",
                "Tier":       "",
                "Tier Score": "",
                "Dimension":  dim.capitalize(),
                "Data Flag":  "",
                "Note":       f"Weight: {DIMENSION_WEIGHTS[dim]*100:.0f}%"
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

        ## ---- TAB 4: Dimension Scores ----
        dim_rows = []
        for dim in ["sustainability", "efficiency", "solvency"]:
            dim_score   = composite_result["dimension_scores"].get(dim)
            ratio_names = DIMENSIONS[dim]
            available   = sum(1 for r in ratio_names if ratios.get(r) is not None)
            scored      = {r: tier_score(r, ratios.get(r)) for r in ratio_names if tier_score(r, ratios.get(r)) is not None}
            strongest   = BENCHMARKS[max(scored, key=scored.get)]["label"] if scored else "—"
            weakest     = BENCHMARKS[min(scored, key=scored.get)]["label"] if scored else "—"

            dim_rows.append({
                "Dimension":        dim.capitalize(),
                "Weight":           f"{DIMENSION_WEIGHTS[dim]*100:.0f}%",
                "Sub-Score":        f"{dim_score:.1f}" if dim_score else "Excluded",
                "Ratios Available": f"{available} of {len(ratio_names)}",
                "Strongest Ratio":  strongest,
                "Weakest Ratio":    weakest,
                "Status":           "Included" if dim_score else "Excluded — insufficient data"
            })
        pd.DataFrame(dim_rows).to_excel(
            writer, sheet_name="Dimension Scores", index=False
        )

        ## ---- TAB 5: Score Limitations ----
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

        ## ---- TAB 6: Scenario Results ----
        if scenario_results:
            scen_rows = []
            flag_sym  = {"green": "✓", "yellow": "!", "red": "⚠", "gray": "—"}

            for ratio_name, bench in BENCHMARKS.items():
                row = {
                    "Ratio":    bench["label"],
                    "Baseline": format_ratio_value(ratio_name, ratios.get(ratio_name))
                }
                for label, result in scenario_results.items():
                    if result:
                        val  = result["scenario_ratios"].get(ratio_name)
                        flg  = result["status_flags"].get(ratio_name, "gray")
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

            ## Caveat row
            scen_rows.append({
                "Ratio":    "NOTE",
                "Baseline": "Balance sheet metrics (Working Capital, Runway) are held constant. A sustained revenue decline would erode these over time — treat as floor, not stable baseline."
            })

            pd.DataFrame(scen_rows).to_excel(
                writer, sheet_name="Scenario Results", index=False
            )

        ## ---- TAB 7: AI Analysis Framework ----
        ## Prompt guide for Copilot or Claude.
        ## Consultant opens Excel, opens Copilot, pastes this as context,
        ## and asks for an analysis. Every consultant follows the same framework.
        framework_lines = [
            "BBS FINANCIAL ANALYSIS FRAMEWORK — AI AGENT INSTRUCTIONS",
            "",
            "You are a nonprofit financial analyst at Bridge Builder Strategies.",
            "The preceding tabs contain a structured financial health assessment.",
            "Use ALL tabs as context. Do not analyze from any single tab in isolation.",
            "",
            "═══════════════════════════════════════════════",
            "STEP 1 — READ CONTEXT FIRST",
            "═══════════════════════════════════════════════",
            "Read the Organization Profile tab first.",
            "Note the org type, score confidence level, and key finding.",
            "Adjust your analysis depth based on how many indicators were available.",
            "If Score Confidence shows fewer than 6 of 8 indicators, note this explicitly.",
            "",
            "═══════════════════════════════════════════════",
            "STEP 2 — ANALYSIS STRUCTURE",
            "═══════════════════════════════════════════════",
            "Produce a narrative analysis with these exact sections:",
            "",
            "1. EXECUTIVE SUMMARY (3-4 sentences)",
            "   Do NOT lead with the score number.",
            "   Lead with what the score means for this organization.",
            "   State the two most important findings.",
            "   Reference the Key Finding field from the Organization Profile tab.",
            "",
            "2. DIMENSION ANALYSIS — one paragraph per dimension",
            "   For each of Sustainability, Efficiency, Solvency:",
            "   - State the sub-score and what it means operationally",
            "   - Name the strongest ratio and why it matters",
            "   - Name any ratio with a flag or note and explain the implication",
            "   - Interpret — do not just restate the numbers",
            "",
            "3. KEY RISKS (3-5 bullets)",
            "   Reference the Score Limitations tab explicitly.",
            "   Prioritize High severity limitations first.",
            "   Connect each limitation to a specific operational risk for this org.",
            "",
            "4. SCENARIO IMPLICATIONS",
            "   Reference the Scenario Results tab.",
            "   Answer: at what revenue decline does the score drop a full band?",
            "   Answer: at what decline does operating surplus go negative?",
            "   What does that threshold mean operationally for this org type?",
            "",
            "5. RECOMMENDATIONS (3-5 specific actions)",
            "   Each recommendation must cite a specific ratio or limitation.",
            "   Format: Because [finding from the data], we recommend [specific action].",
            "   Recommendations should be actionable within 12 months.",
            "",
            "═══════════════════════════════════════════════",
            "STEP 3 — CRITICAL CONSTRAINTS",
            "═══════════════════════════════════════════════",
            "NEVER present the composite score as the complete financial picture.",
            "ALWAYS reference the Score Limitations tab in your analysis.",
            "FLAG any ratio marked as Proxy or with a note in the Ratio Results tab.",
            "",
            "For Service-Delivery Nonprofits:",
            "  Weight operational continuity risks higher than efficiency concerns.",
            "  People depend on these services — funding disruption has human consequences.",
            "",
            "For Advocacy / Capacity-Building:",
            "  Weight balance sheet strength and funder diversity.",
            "",
            "For Community / Cultural Organizations:",
            "  Weight efficiency and donor trust metrics.",
            "",
            "The most important sentence in any analysis you produce:",
            "  A composite score reflects financial ratios only.",
            "  It does not reflect revenue concentration, compliance risk,",
            "  program sustainability, subsidiary obligations, or leadership capacity.",
            "",
            "═══════════════════════════════════════════════",
            "STEP 4 — OUTPUT FORMAT",
            "═══════════════════════════════════════════════",
            "Target length: 600-900 words.",
            "Use the section headers above.",
            "Write for a nonprofit executive director and board — not a financial analyst.",
            "Plain language. No jargon unless explained.",
            "",
            "End every analysis with this exact paragraph:",
            "  This assessment reflects FY[year] financial ratios only.",
            "  A complete organizational assessment requires contextual, programmatic,",
            "  and operational analysis beyond what any ratio-based tool can produce.",
            "  Bridge Builder Strategies recommends supplementing this score with a",
            "  qualitative review of program sustainability, funder relationships,",
            "  and organizational risk factors before presenting findings to a board."
        ]

        pd.DataFrame(
            [[line] for line in framework_lines],
            columns=["AI Analysis Framework — Instructions for Copilot / Claude"]
        ).to_excel(writer, sheet_name="AI Analysis Framework", index=False)

    output.seek(0)
    return output


## ============================================================
## SECTION 12 — STREAMLIT UI
## Runs top to bottom every time user interacts with any widget.
## ============================================================

## -- BBS Header --
st.markdown("""
<div style="padding: 20px 0 16px 0;
            border-bottom: 1px solid rgba(255,255,255,0.08);
            margin-bottom: 28px;">
    <div style="font-size: 11px; color: #2dd4bf;
                letter-spacing: 0.12em;
                text-transform: uppercase;
                margin-bottom: 4px;">
        Bridge Builder Strategies
    </div>
    <div style="font-size: 26px; font-weight: 600;
                color: #e8eaf0; letter-spacing: -0.01em;">
        Nonprofit Financial Health Dashboard
    </div>
    <div style="font-size: 13px; color: #5c6480; margin-top: 2px;">
        Internal Consulting Tool — v2.0 Prototype
    </div>
</div>
""", unsafe_allow_html=True)


## ============================================================
## UI PART A — ORGANIZATION INFO
## ============================================================

col_a, col_b, col_c = st.columns([2, 1, 2])
with col_a:
    org_name    = st.text_input("Organization Name", placeholder="e.g. Sheltering Wings")
with col_b:
    fiscal_year = st.number_input("Fiscal Year", min_value=2000, max_value=2030, value=2025, step=1)
with col_c:
    org_profile = st.selectbox("Organization Profile", ORG_PROFILES,
        help="Profile context. All profiles use the same weights currently — differentiated weighting is a future iteration pending BBS approval.")

data_profile = st.selectbox("Available Data Profile", [
    "Full Audit + 990 (all fields available)",
    "Balance Sheet + YTD + Budget (partial — no prior year revenue)",
    "Balance Sheet Only (minimal data)"
])

st.divider()


## ============================================================
## UI PART B — INPUT FORM
## ============================================================

st.subheader("Financial Inputs")
st.caption("Enter figures from client documents. Tag each source. Check N/A if the client did not provide that figure.")

def input_field(label, key, help_text=""):
    c1, c2, c3 = st.columns([3, 2, 1])
    with c1:
        val = st.number_input(label, min_value=0.0, value=0.0, step=1000.0,
                              format="%.2f", key=f"{key}_val", help=help_text)
    with c2:
        src = st.selectbox("Source", DATA_SOURCE_OPTIONS,
                           key=f"{key}_src", label_visibility="collapsed")
    with c3:
        na = st.checkbox("N/A", key=f"{key}_na",
                         help="Check if this data was not provided.")
    return (None if na else val), src


## Income Statement
st.markdown("**Income Statement**")
inc_l, inc_r = st.columns(2)
with inc_l:
    total_revenue,        src_rev   = input_field("Total Revenue ($)",         "total_revenue",
        "All income: donations, grants, government funding, earned revenue.")
    program_expenses,     src_prog  = input_field("Program Expenses ($)",       "program_expenses",
        "Expenses directly tied to mission delivery and programs.")
    fundraising_expenses, src_fexp  = input_field("Fundraising Expenses ($)",   "fundraising_expenses",
        "Expenses for fundraising activities and donor engagement.")
with inc_r:
    total_expenses,       src_exp   = input_field("Total Expenses ($)",         "total_expenses",
        "All organizational expenses.")
    admin_expenses,       src_admin = input_field("Administrative Expenses ($)","admin_expenses",
        "Overhead and general administration expenses.")
    prior_year_revenue,   src_prior = input_field("Prior Year Revenue ($)",     "prior_year_revenue",
        "Total revenue from the previous fiscal year — used for growth rate.")

## Fundraising Income — new optional field
st.markdown("**Fundraising Income** *(optional — improves accuracy)*")
st.caption(
    "Revenue generated specifically from fundraising events and campaigns. "
    "Do NOT include general contributions or grants. "
    "When provided, replaces Total Revenue in the Fundraising Efficiency formula. "
    "Mark N/A if not separately tracked — Total Revenue will be used as a proxy with a warning."
)
fundraising_income, src_finc = input_field(
    "Fundraising Income ($)", "fundraising_income",
    "Fundraising-specific revenue only (events, campaigns). Not total contributions."
)

## Balance Sheet
st.markdown("**Balance Sheet**")
bs_l, bs_r = st.columns(2)
with bs_l:
    current_assets,      src_ca = input_field("Current Assets ($)",     "current_assets",
        "Cash and assets convertible to cash within 12 months.")
    total_assets,        src_ta = input_field("Total Assets ($)",       "total_assets",
        "All organizational assets including current, fixed, and restricted.")
with bs_r:
    current_liabilities, src_cl = input_field("Current Liabilities ($)","current_liabilities",
        "Obligations due within 12 months.")
    total_liabilities,   src_tl = input_field("Total Liabilities ($)",  "total_liabilities",
        "All organizational obligations.")

## Assemble dicts
inputs = {
    "total_revenue":        total_revenue,
    "total_expenses":       total_expenses,
    "program_expenses":     program_expenses,
    "admin_expenses":       admin_expenses,
    "fundraising_expenses": fundraising_expenses,
    "fundraising_income":   fundraising_income,
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

    ## Quick pre-calculation to check fundraising proxy warning
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

        st.session_state["ratios"]           = ratios
        st.session_state["flags"]            = flags
        st.session_state["composite_result"] = composite_result
        st.session_state["inputs"]           = inputs
        st.session_state["source_tags"]      = source_tags
        st.session_state["org_name"]         = org_name
        st.session_state["fiscal_year"]      = fiscal_year
        st.session_state["org_profile"]      = org_profile
        st.session_state["data_profile"]     = data_profile
        st.session_state["calculated"]       = True


## ============================================================
## UI PART D — RESULTS
## Only shown after Calculate is clicked.
## ============================================================

if st.session_state.get("calculated"):

    ratios           = st.session_state["ratios"]
    flags            = st.session_state["flags"]
    composite_result = st.session_state["composite_result"]
    saved_inputs     = st.session_state["inputs"]
    saved_sources    = st.session_state["source_tags"]
    saved_org        = st.session_state.get("org_name", "Organization")
    saved_year       = st.session_state.get("fiscal_year", 2025)
    saved_profile    = st.session_state.get("org_profile", ORG_PROFILES[0])
    saved_data_prof  = st.session_state.get("data_profile", "")

    score = composite_result["composite"]
    band  = composite_result["band"]
    color = BAND_COLORS.get(band, "#9aa0b4")
    avail = composite_result["available_ratios"]
    total = composite_result["total_ratios"]
    excl  = composite_result["excluded_dims"]

    caveat = f"Score based on {avail} of {total} indicators"
    if excl:
        caveat += f" — {', '.join([d.capitalize() for d in excl])} excluded"

    st.subheader(f"Assessment — {saved_org} ({saved_year})")

    ## -- PANEL 1: KEY FINDING (leads output) --
    key_finding = composite_result.get("key_finding", "")
    if key_finding:
        st.markdown(f"""
        <div style="background:#1e2333; border-left:4px solid {color};
                    border-radius:0 10px 10px 0; padding:16px 20px; margin-bottom:20px;">
            <div style="font-size:11px; color:#5c6480; text-transform:uppercase;
                        letter-spacing:0.08em; margin-bottom:6px;">Key Finding</div>
            <div style="font-size:15px; color:#e8eaf0; line-height:1.6;">
                {key_finding}
            </div>
        </div>""", unsafe_allow_html=True)

    ## -- PANEL 2: SCORE CARD + DIMENSION BREAKDOWN --
    sc1, sc2 = st.columns([1, 2])

    with sc1:
        st.markdown(f"""
        <div style="background:#1e2333; border-radius:16px; padding:28px 24px;
                    text-align:center; border:2px solid {color}; height:100%;">
            <div style="font-size:11px; color:#9aa0b4; letter-spacing:0.1em;
                        text-transform:uppercase; margin-bottom:6px;">Composite Score</div>
            <div style="font-size:68px; font-weight:700; color:{color}; line-height:1;">
                {score if score else "N/A"}
            </div>
            <div style="font-size:12px; color:#5c6480; margin-top:2px;">out of 100</div>
            <div style="font-size:20px; font-weight:600; color:{color}; margin-top:10px;">
                {band if band else "N/A"}
            </div>
            <div style="font-size:11px; color:#5c6480; margin-top:8px; line-height:1.5;">
                {caveat}
            </div>
        </div>""", unsafe_allow_html=True)

    with sc2:
        dims_config = [
            ("Sustainability", "sustainability", "#2dd4bf", "40%"),
            ("Efficiency",     "efficiency",     "#a78bfa", "35%"),
            ("Solvency",       "solvency",       "#60a5fa", "25%")
        ]
        dc1, dc2, dc3 = st.columns(3)
        for col, (label, key, clr, weight) in zip([dc1, dc2, dc3], dims_config):
            dim_val = composite_result["dimension_scores"].get(key)
            display = f"{dim_val:.0f}" if dim_val is not None else "—"
            note    = "Excluded" if key in excl else weight + " weight"
            with col:
                st.markdown(f"""
                <div style="background:#1e2333; border-radius:12px; padding:18px 16px;
                            text-align:center; border-top:3px solid {clr};
                            border:1px solid rgba(255,255,255,0.08);
                            border-top:3px solid {clr}; margin-bottom:12px;">
                    <div style="font-size:11px; color:{clr}; text-transform:uppercase;
                                letter-spacing:0.08em; margin-bottom:6px;">{label}</div>
                    <div style="font-size:38px; font-weight:700; color:{clr}; line-height:1;">
                        {display}
                    </div>
                    <div style="font-size:11px; color:#5c6480; margin-top:4px;">{note}</div>
                </div>""", unsafe_allow_html=True)

        if composite_result["floor_rule"]:
            st.warning(
                "⚠️ **Floor Rule Triggered** — Program spending is below 50% of total expenses. "
                "This is a structural concern about mission alignment. "
                "The composite score may not fully reflect organizational risk."
            )

    st.divider()

    ## -- PANEL 3: RATIO SUMMARY TABLE --
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

        ## Build note
        note = bench.get("note") or ""
        if flag == "proxy":
            note = (
                "Total Revenue used as proxy for Fundraising Income. "
                "May be substantially overstated for organizations with "
                "significant non-fundraising revenue. "
                "Enter Fundraising Income in the dedicated field for an accurate result. "
                + note
            )

        ratio_rows.append({
            "Ratio":     bench["label"],
            "Value":     format_ratio_value(ratio_name, value),
            "Tier":      tier_display,
            "Score":     score_val if score_val is not None else "—",
            "Dimension": bench["dimension"].capitalize(),
            "Note":      (note[:130] + "...") if len(note) > 130 else note
        })

    ## Current ratio reference
    cr = ratios.get("current_ratio")
    ratio_rows.append({
        "Ratio":     "Current Ratio (reference — not scored)",
        "Value":     f"{cr:.2f}" if cr is not None else "—",
        "Tier":      "📋 Reference",
        "Score":     "—",
        "Dimension": "Reference",
        "Note":      "1.5-2.0 is healthy. >3.0 may indicate underinvestment of reserves."
    })

    st.dataframe(pd.DataFrame(ratio_rows), use_container_width=True, hide_index=True)
    st.divider()

    ## -- PANEL 4: SCENARIO MODELING --
    st.subheader("Scenario Modeling")
    st.caption(
        "Simulates revenue decline impact on financial health. "
        "Only Operating Surplus Margin and Revenue Growth Rate recalculate — "
        "all other ratios held constant because expenses, assets, and debt "
        "do not change instantly when revenue drops."
    )

    sc_col1, sc_col2 = st.columns([2, 3])
    with sc_col1:
        preset_choice = st.radio(
            "Select scenario",
            ["−10% Revenue", "−20% Revenue", "−25% Revenue", "Custom"],
            horizontal=True
        )
        if preset_choice == "Custom":
            custom_pct    = st.slider("Custom decline (%)", 0, 50, 15, 1)
            active_decline = custom_pct / 100
        else:
            active_decline = {"−10% Revenue": 0.10, "−20% Revenue": 0.20, "−25% Revenue": 0.25}[preset_choice]

    active_scenario = run_scenario(saved_inputs, ratios, composite_result, active_decline)

    if active_scenario:
        baseline_score = composite_result.get("composite")
        scenario_score = active_scenario["scenario_composite"].get("composite")
        scenario_band  = active_scenario["scenario_composite"].get("band")
        delta          = (scenario_score - baseline_score) if (baseline_score and scenario_score) else None

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
                st.metric("Scenario Band", scenario_band or "N/A")

        ## Bar chart
        if baseline_score and scenario_score:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Baseline", x=["Score"], y=[baseline_score],
                marker_color="#2dd4bf", text=[f"{baseline_score}"],
                textposition="outside", textfont=dict(color="#e8eaf0")
            ))
            fig.add_trace(go.Bar(
                name=f"−{int(active_decline*100)}% Revenue", x=["Score"], y=[scenario_score],
                marker_color="#f87171", text=[f"{scenario_score}"],
                textposition="outside", textfont=dict(color="#e8eaf0")
            ))
            fig.update_layout(
                barmode="group", height=280,
                margin=dict(t=30, b=10, l=10, r=10),
                yaxis=dict(range=[0, 115], title="Score", color="#9aa0b4"),
                xaxis=dict(color="#9aa0b4"),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(font=dict(color="#9aa0b4"), bgcolor="rgba(0,0,0,0)"),
                font=dict(color="#9aa0b4")
            )
            st.plotly_chart(fig, use_container_width=True)

        ## Ratio-level impact table
        st.markdown("**Ratio impact**")
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
            "⚠️ Balance sheet metrics (Working Capital Ratio, Months of Runway) are held "
            "constant across all scenarios. In practice, a sustained revenue decline would "
            "erode cash reserves, reduce working capital, and compress actual runway over time. "
            "Treat these figures as a floor — not a stable baseline — under stress conditions."
        )

    st.divider()

    ## -- PANEL 5: WHAT THIS SCORE DOES NOT CAPTURE --
    st.subheader("What This Score Does Not Capture")

    st.markdown(f"""
    <div style="background:#1e2333; border-left:4px solid #fbbf24;
                border-radius:0 10px 10px 0; padding:16px 20px; margin-bottom:16px;">
        <div style="font-size:16px; font-weight:600; color:#e8eaf0; line-height:1.5;">
            A score of {score}/100 means the financial ratios are healthy.
            It does not mean there are no financial risks.
        </div>
    </div>""", unsafe_allow_html=True)

    severity_colors = {"High": "#f87171", "Medium": "#fbbf24", "Low": "#2dd4bf", "Structural": "#a78bfa"}
    for lim in SCORE_LIMITATIONS:
        sev_color = severity_colors.get(lim["severity"], "#9aa0b4")
        st.markdown(f"""
        <div style="background:#1e2333; border-radius:8px; padding:14px 18px;
                    margin-bottom:8px; border:1px solid rgba(255,255,255,0.06);">
            <div style="display:flex; align-items:center; gap:10px; margin-bottom:4px;">
                <span style="background:rgba(255,255,255,0.05); color:{sev_color};
                             font-size:10px; font-weight:600; padding:2px 8px;
                             border-radius:4px; text-transform:uppercase; letter-spacing:0.06em;">
                    {lim["severity"]}
                </span>
                <span style="font-size:14px; font-weight:500; color:#e8eaf0;">
                    {lim["limitation"]}
                </span>
            </div>
            <div style="font-size:13px; color:#9aa0b4; line-height:1.5; margin-top:4px;">
                {lim["description"]}
            </div>
            <div style="font-size:12px; color:{sev_color}; margin-top:6px;">
                → {lim["action"]}
            </div>
        </div>""", unsafe_allow_html=True)

    st.divider()

    ## -- PANEL 6: DATA GAPS --
    st.subheader("Data Gaps")

    unavailable_fields = [k for k, v in saved_inputs.items() if v is None]
    unavailable_ratios = [BENCHMARKS[r]["label"] for r in BENCHMARKS if ratios.get(r) is None]

    if not unavailable_fields:
        st.success("All input fields were provided. No data gaps detected.")
    else:
        st.warning(f"{len(unavailable_fields)} field(s) unavailable, affecting {len(unavailable_ratios)} ratio(s).")
        field_labels_display = {
            "total_revenue": "Total Revenue", "total_expenses": "Total Expenses",
            "program_expenses": "Program Expenses", "admin_expenses": "Administrative Expenses",
            "fundraising_expenses": "Fundraising Expenses", "fundraising_income": "Fundraising Income",
            "current_assets": "Current Assets", "current_liabilities": "Current Liabilities",
            "total_assets": "Total Assets", "total_liabilities": "Total Liabilities",
            "prior_year_revenue": "Prior Year Revenue"
        }
        st.dataframe(pd.DataFrame([{
            "Unavailable Field": field_labels_display.get(f, f),
            "Impact": "Excluded from dependent ratio calculations"
        } for f in unavailable_fields]), use_container_width=True, hide_index=True)

        if excl:
            st.error(
                f"Dimension(s) fully excluded: {', '.join([d.capitalize() for d in excl])}. "
                f"Weights redistributed proportionally across remaining dimensions."
            )

    st.divider()

    ## -- PANEL 7: EXPORT --
    st.subheader("Export")
    st.caption(
        "Downloads a 7-tab Excel file ready for AI analysis. "
        "Open in Excel, launch Copilot, and use the AI Analysis Framework tab "
        "as your prompt context to generate a structured narrative assessment."
    )

    ## Pre-run all standard scenarios
    all_scenarios = {}
    for pct in SCENARIO_PRESETS:
        all_scenarios[f"−{int(pct*100)}% Revenue"] = run_scenario(
            saved_inputs, ratios, composite_result, pct
        )
    if preset_choice == "Custom":
        all_scenarios[f"−{int(active_decline*100)}% Revenue (custom)"] = active_scenario

    excel_file = generate_excel(
        saved_inputs, saved_sources, ratios, flags,
        composite_result, all_scenarios,
        saved_org, saved_year, saved_profile, saved_data_prof,
        date.today()
    )

    st.download_button(
        label="⬇️ Download Excel Report (7 tabs)",
        data=excel_file,
        file_name=f"BBS_Financial_Assessment_{(saved_org or 'Organization').replace(' ','_')}_{saved_year}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )


## ============================================================
## SECTION 13 — METHODOLOGY NOTE
## ============================================================

st.divider()
with st.expander("About this tool — Methodology & Sources"):
    st.markdown("""
    **Scoring Model**

    Three-dimension model: Sustainability (40%), Efficiency (35%), Solvency (25%).
    Eight ratios convert to standardized tier scores (Excellent=100, Strong=75,
    Average=50, Issues=25) grounded in Charity Navigator's published
    Accountability & Finance methodology.

    **Fundraising Efficiency**

    When Fundraising Income is provided separately, it is used as the numerator
    (correct formula). When not provided, Total Revenue is used as proxy and the
    ratio is flagged. A ratio exceeding 50:1 triggers an automatic validation warning.

    **Partial Data**

    Unavailable inputs return null — not zero. Ratios with null inputs are excluded
    from scoring. If an entire dimension is unavailable, its weight redistributes
    proportionally.

    **Scenario Modeling**

    Revenue declines with expenses held constant. Only Operating Surplus Margin
    and Revenue Growth Rate recalculate. Balance sheet metrics are held at
    baseline — a sustained decline would erode these over time.

    **Excel Export — 7 Tabs**

    Organization Profile, Raw Inputs, Ratio Results, Dimension Scores,
    Score Limitations, Scenario Results, AI Analysis Framework.
    The AI Framework tab contains structured instructions for Copilot or Claude
    to generate a consistent narrative analysis from the structured data.

    **Limitations**

    This tool is a decision-support instrument, not a substitute for professional
    accounting review. Composite score reflects quantitative ratios only.

    *v2.0 Prototype — Bridge Builder Strategies BRIDGE Project, 2026*
    """)
