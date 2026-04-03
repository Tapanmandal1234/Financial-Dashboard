## ============================================================
## BBS NONPROFIT FINANCIAL HEALTH DASHBOARD
## Bridge Builder Strategies — BRIDGE Project
## Author: Tapan Mandal
## Version: 1.0 Prototype
## ============================================================
## HOW TO RUN IN COLAB:
##   1. Put %%writefile app.py at the very top of your Colab cell
##   2. Run that cell — it saves this file
##   3. Run a second cell with: !streamlit run app.py &
##      and use ngrok to get a preview URL
## ============================================================


## ============================================================
## SECTION 1 — IMPORTS
## These are the libraries the app needs.
## Streamlit = the web app framework
## Pandas = data handling for export
## Plotly = charts
## OpenPyXL = Excel file creation
## IO = handles file download in memory
## ============================================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from io import BytesIO


## ============================================================
## SECTION 2 — PAGE CONFIGURATION
## This must be the FIRST Streamlit command in the file.
## Sets the browser tab title, icon, and layout width.
## ============================================================

st.set_page_config(
    page_title="BBS Financial Dashboard",
    page_icon="📊",
    layout="wide"
)


## ============================================================
## SECTION 3 — CONFIG
## Every number a supervisor might want to change lives here.
## Nothing is hardcoded in the calculation functions below.
## If BBS wants to adjust weights or thresholds after review,
## this is the ONLY section that needs to change.
## ============================================================

## -- Dimension weights --
## Sustainability = can they keep operating under pressure?
## Efficiency     = are they spending money the right way?
## Solvency       = is the balance sheet structurally sound?
DIMENSION_WEIGHTS = {
    "sustainability": 0.40,
    "efficiency":     0.35,
    "solvency":       0.25
}

## -- Which ratios belong to which dimension --
DIMENSIONS = {
    "sustainability": ["operating_surplus_margin", "revenue_growth_rate", "months_runway"],
    "efficiency":     ["program_efficiency", "admin_expense_pct", "fundraising_efficiency"],
    "solvency":       ["working_capital_ratio", "debt_ratio"]
}

## -- Floor rule threshold --
## If program efficiency drops below this, show a reliability warning
## regardless of the composite score. Borrowed from Charity Navigator.
FLOOR_RULE_THRESHOLD = 0.50

## -- Score bands --
## What the composite score means at different levels
SCORE_BANDS = {
    "Strong":     (80, 100),
    "Stable":     (60, 79),
    "Watchlist":  (40, 59),
    "Distressed": (0,  39)
}

## -- Colors for each band (used in UI display) --
BAND_COLORS = {
    "Strong":     "#4ade80",
    "Stable":     "#2dd4bf",
    "Watchlist":  "#fbbf24",
    "Distressed": "#f87171"
}

## -- Benchmark tiers --
## Each ratio maps to one of four performance tiers.
## Tier scores: Excellent=100, Strong=75, Average=50, Issues=25
## Direction = "higher" means higher ratio value is better
## Direction = "lower"  means lower ratio value is better (inverted)
## Thresholds are grounded in Charity Navigator's published methodology.
BENCHMARKS = {
    "program_efficiency": {
        "label":     "Program Efficiency",
        "direction": "higher",
        "excellent": 0.75,
        "strong":    0.65,
        "average":   0.50,
        "format":    "percent",
        "dimension": "efficiency"
    },
    "admin_expense_pct": {
        "label":     "Admin Expense %",
        "direction": "lower",   ## lower overhead = better score
        "excellent": 0.15,
        "strong":    0.20,
        "average":   0.30,
        "format":    "percent",
        "dimension": "efficiency"
    },
    "fundraising_efficiency": {
        "label":     "Fundraising Efficiency",
        "direction": "higher",
        "excellent": 5.0,
        "strong":    3.0,
        "average":   2.0,
        "format":    "dollar",  ## shown as $X.XX raised per $1 spent
        "dimension": "efficiency"
    },
    "operating_surplus_margin": {
        "label":     "Operating Surplus Margin",
        "direction": "higher",
        "excellent": 0.10,
        "strong":    0.05,
        "average":   0.00,
        "format":    "percent",
        "dimension": "sustainability"
    },
    "working_capital_ratio": {
        "label":     "Working Capital Ratio",
        "direction": "higher",
        "excellent": 0.50,
        "strong":    0.25,
        "average":   0.08,
        "format":    "months",  ## shown as months of buffer
        "dimension": "solvency"
    },
    "debt_ratio": {
        "label":     "Debt Ratio",
        "direction": "lower",   ## lower debt = better score
        "excellent": 0.25,
        "strong":    0.40,
        "average":   0.60,
        "format":    "percent",
        "dimension": "solvency"
    },
    "revenue_growth_rate": {
        "label":     "Revenue Growth Rate",
        "direction": "higher",
        "excellent": 0.10,
        "strong":    0.05,
        "average":   0.00,
        "format":    "percent",
        "dimension": "sustainability"
    },
    "months_runway": {
        "label":     "Months of Operating Runway",
        "direction": "higher",
        "excellent": 6.0,
        "strong":    3.0,
        "average":   1.0,
        "format":    "months",
        "dimension": "sustainability"
    }
}

## -- Scenario presets (as decimals) --
SCENARIO_PRESETS = [0.10, 0.20, 0.25]

## -- Ratios that change in scenarios vs ratios that stay constant --
## Only revenue-driven ratios change. Everything else is locked
## because expenses, assets, and liabilities don't change instantly
## when revenue drops.
SCENARIO_CHANGES  = ["operating_surplus_margin", "revenue_growth_rate"]
SCENARIO_CONSTANT = ["program_efficiency", "admin_expense_pct",
                     "fundraising_efficiency", "working_capital_ratio",
                     "debt_ratio", "months_runway"]

## -- Data source tag options (shown next to each input field) --
DATA_SOURCE_OPTIONS = [
    "Audited Financials",
    "IRS Form 990",
    "YTD Projection",
    "Budget Estimate"
]

## -- Org profile options --
## UI selector only for now — all profiles use the same weights.
## Differentiated weighting is designed for future iteration.
ORG_PROFILES = [
    "Service-Delivery Nonprofit",
    "Advocacy / Capacity-Building",
    "Community / Cultural Organization"
]


## ============================================================
## SECTION 4 — VALIDATION FUNCTIONS
## Run before any calculation.
## Returns a list of error messages (empty list = all clear).
## Hard errors block calculation.
## Soft warnings surface alongside results.
## ============================================================

def validate_inputs(inputs):
    """
    Checks inputs for logical errors before any ratio is calculated.
    Returns two lists: errors (block calculation) and warnings (show but continue).
    """
    errors   = []
    warnings = []

    rev  = inputs.get("total_revenue")
    exp  = inputs.get("total_expenses")
    prog = inputs.get("program_expenses")
    ta   = inputs.get("total_assets")
    tl   = inputs.get("total_liabilities")

    ## Hard error: revenue must be non-negative
    if rev is not None and rev < 0:
        errors.append("Total Revenue cannot be negative.")

    ## Hard error: expenses must be non-negative
    if exp is not None and exp < 0:
        errors.append("Total Expenses cannot be negative.")

    ## Hard error: program expenses cannot exceed total expenses
    if prog is not None and exp is not None:
        if prog > exp:
            errors.append("Program Expenses cannot exceed Total Expenses.")

    ## Soft warning: liabilities should not exceed assets
    if ta is not None and tl is not None:
        if tl > ta:
            warnings.append(
                "Total Liabilities exceed Total Assets — "
                "organization may be technically insolvent."
            )

    return errors, warnings


## ============================================================
## SECTION 5 — RATIO CALCULATION FUNCTIONS
## Takes the validated input dict and returns all ratio values.
## Returns None for any ratio where inputs are unavailable.
## None (unavailable) and 0 (zero) are treated differently
## throughout the scoring model — never substitute one for the other.
## ============================================================

def calculate_ratios(inputs):
    """
    Calculates all 8 scored ratios plus Current Ratio as reference.
    Returns a dict of {ratio_name: value or None}.
    None means the input was unavailable — not that the value is zero.
    """

    ## Pull all inputs from the dict (None if marked unavailable)
    rev      = inputs.get("total_revenue")
    exp      = inputs.get("total_expenses")
    prog     = inputs.get("program_expenses")
    admin    = inputs.get("admin_expenses")
    fund     = inputs.get("fundraising_expenses")
    ca       = inputs.get("current_assets")
    cl       = inputs.get("current_liabilities")
    ta       = inputs.get("total_assets")
    tl       = inputs.get("total_liabilities")
    prior    = inputs.get("prior_year_revenue")

    ratios = {}

    ## -- R1: Program Efficiency --
    ## What % of spending goes to mission programs
    if prog is not None and exp is not None and exp > 0:
        ratios["program_efficiency"] = prog / exp
    else:
        ratios["program_efficiency"] = None

    ## -- R2: Admin Expense % --
    ## What % of spending is overhead/administration
    if admin is not None and exp is not None and exp > 0:
        ratios["admin_expense_pct"] = admin / exp
    else:
        ratios["admin_expense_pct"] = None

    ## -- R3: Fundraising Efficiency --
    ## Dollars raised per dollar spent on fundraising
    if rev is not None and fund is not None and fund > 0:
        ratios["fundraising_efficiency"] = rev / fund
    else:
        ratios["fundraising_efficiency"] = None

    ## -- R4: Operating Surplus Margin --
    ## Whether revenue exceeds expenses (positive = surplus, negative = deficit)
    if rev is not None and exp is not None and rev > 0:
        ratios["operating_surplus_margin"] = (rev - exp) / rev
    else:
        ratios["operating_surplus_margin"] = None

    ## -- R5: Working Capital Ratio --
    ## Months of operating buffer (replaces Current Ratio in scoring)
    if ca is not None and cl is not None and exp is not None and exp > 0:
        ratios["working_capital_ratio"] = (ca - cl) / exp
    else:
        ratios["working_capital_ratio"] = None

    ## -- R6: Debt Ratio --
    ## What % of total assets is financed by debt
    if tl is not None and ta is not None and ta > 0:
        ratios["debt_ratio"] = tl / ta
    else:
        ratios["debt_ratio"] = None

    ## -- R7: Revenue Growth Rate --
    ## Year-over-year revenue change
    if rev is not None and prior is not None and prior > 0:
        ratios["revenue_growth_rate"] = (rev - prior) / prior
    else:
        ratios["revenue_growth_rate"] = None

    ## -- R8: Months of Operating Runway --
    ## How many months the org could operate using only current assets
    if ca is not None and exp is not None and exp > 0:
        ratios["months_runway"] = ca / (exp / 12)
    else:
        ratios["months_runway"] = None

    ## -- R9: Current Ratio (reference only — not scored) --
    ## Kept from Matthew's original tool for familiarity
    ## NOT included in the composite score
    if ca is not None and cl is not None and cl > 0:
        ratios["current_ratio"] = ca / cl
    else:
        ratios["current_ratio"] = None

    return ratios


## ============================================================
## SECTION 6 — TIER SCORING FUNCTION
## Converts a ratio value to a standardized score: 100, 75, 50, or 25.
## Handles both directions (higher better vs lower better).
## Returns None if value is None (unavailable input).
## ============================================================

def tier_score(ratio_name, value):
    """
    Maps a ratio value to a performance tier score.
    Excellent = 100, Strong = 75, Average = 50, Issues = 25.
    Returns None if value is None.
    """

    ## If the value is unavailable, propagate None
    if value is None:
        return None

    bench = BENCHMARKS.get(ratio_name)
    if bench is None:
        return None  ## ratio not found in config

    direction = bench["direction"]
    excellent = bench["excellent"]
    strong    = bench["strong"]
    average   = bench["average"]

    ## For "higher is better" ratios (most ratios)
    if direction == "higher":
        if value >= excellent:
            return 100
        elif value >= strong:
            return 75
        elif value >= average:
            return 50
        else:
            return 25

    ## For "lower is better" ratios (admin %, debt ratio)
    ## The threshold logic is inverted — smaller values earn higher scores
    else:
        if value <= excellent:
            return 100
        elif value <= strong:
            return 75
        elif value <= average:
            return 50
        else:
            return 25


def get_tier_label(score):
    """
    Converts a numeric tier score to its label.
    Used for display in the ratio table.
    """
    labels = {100: "Excellent", 75: "Strong", 50: "Average", 25: "Issues"}
    return labels.get(score, "N/A")


def get_tier_color(score):
    """
    Returns a color hex for each tier.
    Used for status indicators in the ratio table and scenario flags.
    """
    colors = {
        100: "#4ade80",  ## green
        75:  "#2dd4bf",  ## teal
        50:  "#fbbf24",  ## amber
        25:  "#f87171"   ## red
    }
    return colors.get(score, "#9aa0b4")  ## gray for unavailable


## ============================================================
## SECTION 7 — COMPOSITE SCORING FUNCTION
## Groups ratios into dimensions, calculates sub-scores,
## applies weights, and handles partial data gracefully.
## Returns the composite score, dimension sub-scores,
## data gap flags, and floor rule flag.
## ============================================================

def calculate_composite(ratios):
    """
    Calculates the composite financial health score (0-100).

    Handles three partial data cases:
    Case A: One ratio unavailable in a dimension
            → calculate from remaining ratios, include dimension at full weight
    Case B: All ratios unavailable in a dimension
            → exclude dimension, redistribute its weight proportionally
    Case C: Two dimensions fully unavailable
            → calculate from remaining dimension, show strong warning

    Returns a dict with:
        composite         = final score (int, 0-100) or None
        dimension_scores  = {dim_name: score or None}
        available_ratios  = count of ratios that were scored
        total_ratios      = total possible scored ratios (8)
        excluded_dims     = list of dimension names that were excluded
        floor_rule        = True if program efficiency < threshold
        band              = score band label (Strong/Stable/Watchlist/Distressed)
    """

    result = {
        "composite":        None,
        "dimension_scores": {},
        "available_ratios": 0,
        "total_ratios":     8,
        "excluded_dims":    [],
        "floor_rule":       False,
        "band":             None
    }

    ## -- Check floor rule before scoring --
    prog_eff = ratios.get("program_efficiency")
    if prog_eff is not None and prog_eff < FLOOR_RULE_THRESHOLD:
        result["floor_rule"] = True

    ## -- Calculate each dimension sub-score --
    dimension_scores  = {}
    available_by_dim  = {}

    for dim_name, ratio_list in DIMENSIONS.items():
        scores_in_dim = []
        available_in_dim = 0

        for ratio_name in ratio_list:
            val   = ratios.get(ratio_name)
            score = tier_score(ratio_name, val)

            if score is not None:
                scores_in_dim.append(score)
                available_in_dim += 1
                result["available_ratios"] += 1

        ## If at least one ratio is available, calculate sub-score
        if scores_in_dim:
            dimension_scores[dim_name]  = sum(scores_in_dim) / len(scores_in_dim)
            available_by_dim[dim_name]  = available_in_dim
        else:
            ## Case B: entire dimension unavailable
            dimension_scores[dim_name] = None
            result["excluded_dims"].append(dim_name)

    result["dimension_scores"] = dimension_scores

    ## -- Calculate composite with weight redistribution --
    ## Only include dimensions that have at least one available ratio
    available_dims = {
        dim: score
        for dim, score in dimension_scores.items()
        if score is not None
    }

    if not available_dims:
        ## No data at all — cannot produce a score
        return result

    ## Redistribute weights across available dimensions only
    total_available_weight = sum(
        DIMENSION_WEIGHTS[dim]
        for dim in available_dims
    )

    composite = 0
    for dim, score in available_dims.items():
        adjusted_weight = DIMENSION_WEIGHTS[dim] / total_available_weight
        composite += score * adjusted_weight

    ## Round to nearest integer
    result["composite"] = round(composite)

    ## -- Assign score band --
    for band_label, (low, high) in SCORE_BANDS.items():
        if low <= result["composite"] <= high:
            result["band"] = band_label
            break

    return result


## ============================================================
## SECTION 8 — SCENARIO ENGINE
## Simulates revenue decline scenarios.
## Only Operating Surplus Margin and Revenue Growth Rate change.
## All other ratios are held constant because:
##   - Expenses don't change instantly when revenue drops
##   - Asset balances are not dynamically modeled
##   - Debt structure changes slowly over time
## ============================================================

def run_scenario(inputs, ratios, baseline_composite_result, decline_pct):
    """
    Applies a revenue decline shock and recalculates affected ratios.

    Parameters:
        inputs                  = original input dict
        ratios                  = baseline calculated ratios
        baseline_composite      = result dict from calculate_composite()
        decline_pct             = decimal decline (0.10 for 10%, 0.20 for 20%)

    Returns a dict with:
        scenario_revenue        = adjusted revenue amount
        scenario_ratios         = updated ratio values (only changed ones updated)
        scenario_composite      = recalculated composite result dict
        status_flags            = {ratio_name: "green"/"yellow"/"red"}
    """

    rev   = inputs.get("total_revenue")
    exp   = inputs.get("total_expenses")
    prior = inputs.get("prior_year_revenue")

    ## Step 1 — Apply revenue shock
    ## Expenses stay the same — org cannot cut fixed costs immediately
    if rev is None:
        return None

    scenario_revenue = rev * (1 - decline_pct)

    ## Step 2 — Recalculate only the two affected ratios
    scenario_ratios = ratios.copy()

    ## Operating Surplus Margin: uses scenario revenue, same expenses
    if exp is not None and scenario_revenue > 0:
        scenario_ratios["operating_surplus_margin"] = (
            (scenario_revenue - exp) / scenario_revenue
        )
    else:
        scenario_ratios["operating_surplus_margin"] = None

    ## Revenue Growth Rate: uses scenario revenue, same prior year
    if prior is not None and prior > 0:
        scenario_ratios["revenue_growth_rate"] = (
            (scenario_revenue - prior) / prior
        )
    else:
        scenario_ratios["revenue_growth_rate"] = None

    ## Step 3-5 — Recalculate composite with updated ratios
    scenario_composite = calculate_composite(scenario_ratios)

    ## -- Generate status flags per ratio --
    ## Compare baseline tier score to scenario tier score
    ## Green  = tier did not change
    ## Yellow = dropped one tier
    ## Red    = dropped two or more tiers or crossed into Issues (25)
    status_flags = {}

    for ratio_name in BENCHMARKS.keys():
        baseline_val  = ratios.get(ratio_name)
        scenario_val  = scenario_ratios.get(ratio_name)

        baseline_score  = tier_score(ratio_name, baseline_val)
        scenario_score  = tier_score(ratio_name, scenario_val)

        if baseline_score is None or scenario_score is None:
            status_flags[ratio_name] = "gray"
        elif scenario_score == baseline_score:
            status_flags[ratio_name] = "green"
        elif baseline_score - scenario_score == 25:
            status_flags[ratio_name] = "yellow"
        else:
            status_flags[ratio_name] = "red"

    return {
        "scenario_revenue": scenario_revenue,
        "scenario_ratios":  scenario_ratios,
        "scenario_composite": scenario_composite,
        "status_flags":     status_flags
    }


## ============================================================
## SECTION 9 — FORMATTING HELPERS
## Small utility functions for displaying values cleanly in the UI.
## ============================================================

def format_value(value, fmt):
    """
    Formats a ratio value for display based on its format type.
    """
    if value is None:
        return "—"
    if fmt == "percent":
        return f"{value * 100:.1f}%"
    elif fmt == "dollar":
        return f"${value:.2f}"
    elif fmt == "months":
        ## Working Capital Ratio is expressed as a fraction of annual expenses
        ## Multiply by 12 to convert to months for display
        if "working_capital" in fmt or value < 3:
            return f"{value * 12:.1f} months" if value < 3 else f"{value:.1f}"
        return f"{value:.1f} months"
    return f"{value:.3f}"

def format_ratio_value(ratio_name, value):
    """
    Formats a ratio value using its configured format type.
    """
    if value is None:
        return "—"
    fmt = BENCHMARKS.get(ratio_name, {}).get("format", "decimal")

    if fmt == "percent":
        return f"{value * 100:.1f}%"
    elif fmt == "dollar":
        return f"${value:.2f} per $1"
    elif fmt == "months":
        ## Working capital ratio: multiply by 12 to show months
        if ratio_name == "working_capital_ratio":
            return f"{value * 12:.1f} months"
        return f"{value:.1f} months"
    return f"{value:.3f}"

def get_score_band(score):
    """
    Returns the band label for a given composite score.
    """
    if score is None:
        return "N/A"
    for band_label, (low, high) in SCORE_BANDS.items():
        if low <= score <= high:
            return band_label
    return "N/A"


## ============================================================
## SECTION 10 — EXPORT FUNCTION
## Generates a downloadable Excel file with three tabs:
##   Tab 1: Raw Inputs (with data source tags)
##   Tab 2: Ratio Results (values, tiers, dimension scores, composite)
##   Tab 3: Scenario Results (all four scenarios side by side)
## ============================================================

def generate_excel(inputs, source_tags, ratios, composite_result, scenario_results, org_name, fiscal_year):
    """
    Creates an Excel workbook in memory and returns it as bytes.
    The BytesIO object can be passed directly to st.download_button().
    """
    output = BytesIO()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:

        ## -- Tab 1: Raw Inputs --
        inputs_data = []
        field_labels = {
            "total_revenue":      "Total Revenue ($)",
            "total_expenses":     "Total Expenses ($)",
            "program_expenses":   "Program Expenses ($)",
            "admin_expenses":     "Administrative Expenses ($)",
            "fundraising_expenses": "Fundraising Expenses ($)",
            "current_assets":     "Current Assets ($)",
            "current_liabilities":"Current Liabilities ($)",
            "total_assets":       "Total Assets ($)",
            "total_liabilities":  "Total Liabilities ($)",
            "prior_year_revenue": "Prior Year Revenue ($)"
        }
        for key, label in field_labels.items():
            value  = inputs.get(key)
            source = source_tags.get(key, "—")
            inputs_data.append({
                "Field":       label,
                "Value":       value if value is not None else "Unavailable",
                "Data Source": source
            })

        df_inputs = pd.DataFrame(inputs_data)
        df_inputs.to_excel(writer, sheet_name="Raw Inputs", index=False)

        ## -- Tab 2: Ratio Results --
        ratios_data = []
        for ratio_name, bench in BENCHMARKS.items():
            value  = ratios.get(ratio_name)
            score  = tier_score(ratio_name, value)
            ratios_data.append({
                "Ratio":          bench["label"],
                "Value":          format_ratio_value(ratio_name, value),
                "Tier":           get_tier_label(score) if score else "Unavailable",
                "Tier Score":     score if score else "—",
                "Dimension":      bench["dimension"].capitalize()
            })

        ## Add current ratio as reference
        cr = ratios.get("current_ratio")
        ratios_data.append({
            "Ratio":     "Current Ratio (reference only)",
            "Value":     f"{cr:.2f}" if cr is not None else "—",
            "Tier":      "Reference — not scored",
            "Tier Score": "—",
            "Dimension": "Reference"
        })

        ## Add dimension sub-scores and composite
        ratios_data.append({"Ratio": "", "Value": "", "Tier": "", "Tier Score": "", "Dimension": ""})
        for dim, score in composite_result["dimension_scores"].items():
            ratios_data.append({
                "Ratio":     f"{dim.capitalize()} Dimension Score",
                "Value":     f"{score:.1f}" if score is not None else "Excluded",
                "Tier":      "",
                "Tier Score": "",
                "Dimension": dim.capitalize()
            })
        ratios_data.append({
            "Ratio":     "COMPOSITE HEALTH SCORE",
            "Value":     f"{composite_result['composite']} — {composite_result['band']}",
            "Tier":      "",
            "Tier Score": "",
            "Dimension": "All"
        })

        df_ratios = pd.DataFrame(ratios_data)
        df_ratios.to_excel(writer, sheet_name="Ratio Results", index=False)

        ## -- Tab 3: Scenario Results --
        if scenario_results:
            scenario_data = []
            for ratio_name, bench in BENCHMARKS.items():
                row = {"Ratio": bench["label"]}
                row["Baseline"] = format_ratio_value(
                    ratio_name, ratios.get(ratio_name)
                )
                for label, result in scenario_results.items():
                    if result:
                        val = result["scenario_ratios"].get(ratio_name)
                        row[label] = format_ratio_value(ratio_name, val)
                    else:
                        row[label] = "—"
                scenario_data.append(row)

            ## Add composite scores row
            score_row = {"Ratio": "COMPOSITE SCORE"}
            score_row["Baseline"] = str(composite_result["composite"])
            for label, result in scenario_results.items():
                if result:
                    score_row[label] = str(result["scenario_composite"]["composite"])
                else:
                    score_row[label] = "—"
            scenario_data.append(score_row)

            df_scenarios = pd.DataFrame(scenario_data)
            df_scenarios.to_excel(writer, sheet_name="Scenario Results", index=False)

    output.seek(0)
    return output


## ============================================================
## SECTION 11 — STREAMLIT UI
## Everything below here is the visual interface.
## It calls the functions above and displays results.
## Streamlit runs this top to bottom every time the user
## interacts with any input widget.
## ============================================================

## -- App header --
st.title("📊 Nonprofit Financial Health Dashboard")
st.caption("Bridge Builder Strategies — Internal Consulting Tool")
st.divider()

## ============================================================
## UI PART A — ORGANIZATION INFO & PROFILE
## ============================================================

col_left, col_mid, col_right = st.columns([2, 2, 2])

with col_left:
    org_name = st.text_input(
        "Organization Name",
        placeholder="e.g. Sheltering Wings"
    )

with col_mid:
    fiscal_year = st.number_input(
        "Fiscal Year",
        min_value=2000,
        max_value=2030,
        value=2025,
        step=1
    )

with col_right:
    org_profile = st.selectbox(
        "Organization Profile",
        ORG_PROFILES,
        help="Selects the consulting context. All profiles currently use the same weights. Profile-based weighting is designed for future iteration."
    )

## -- Data profile selector --
## Pre-signals what data is available so consultants
## can set expectations before filling in fields
data_profile = st.selectbox(
    "Available Data Profile",
    [
        "Full Audit + 990 (all fields available)",
        "Balance Sheet + YTD + Budget (partial — no prior year)",
        "Balance Sheet Only (minimal data)"
    ],
    help="Select based on what documents the client provided. Affects which fields are expected to be available."
)

st.divider()

## ============================================================
## UI PART B — FINANCIAL INPUT FORM
## 10 numeric fields organized into two groups:
##   Group 1: Income Statement (revenue + expenses)
##   Group 2: Balance Sheet (assets + liabilities)
## Each field has a data source tag and unavailable checkbox.
## ============================================================

st.subheader("Financial Inputs")
st.caption("Enter figures from client financial documents. Tag the source and mark fields unavailable if data was not provided.")

## -- Helper function to render one input field --
def input_field(label, key, help_text=""):
    """
    Renders a labeled number input with a data source tag and
    unavailable checkbox. Returns (value_or_None, source_tag_string).
    """
    col1, col2, col3 = st.columns([3, 2, 1])
    with col1:
        value = st.number_input(
            label,
            min_value=0.0,
            value=0.0,
            step=1000.0,
            format="%.2f",
            key=f"{key}_val",
            help=help_text,
            label_visibility="visible"
        )
    with col2:
        source = st.selectbox(
            "Source",
            DATA_SOURCE_OPTIONS,
            key=f"{key}_src",
            label_visibility="collapsed"
        )
    with col3:
        unavailable = st.checkbox(
            "N/A",
            key=f"{key}_na",
            help="Check if this data was not provided by the client."
        )

    ## If unavailable is checked, return None for this field
    final_value = None if unavailable else value
    return final_value, source

## -- Income Statement Group --
st.markdown("**Income Statement**")
ic1, ic2 = st.columns(2)

with ic1:
    total_revenue, src_rev = input_field(
        "Total Revenue ($)",
        "total_revenue",
        "All income including donations, grants, government funding, and earned revenue."
    )
    program_expenses, src_prog = input_field(
        "Program Expenses ($)",
        "program_expenses",
        "Expenses directly related to mission delivery and program services."
    )
    fundraising_expenses, src_fund = input_field(
        "Fundraising Expenses ($)",
        "fundraising_expenses",
        "Expenses related to fundraising activities and donor engagement."
    )

with ic2:
    total_expenses, src_exp = input_field(
        "Total Expenses ($)",
        "total_expenses",
        "All organizational expenses including program, admin, and fundraising."
    )
    admin_expenses, src_admin = input_field(
        "Administrative Expenses ($)",
        "admin_expenses",
        "General and administrative overhead expenses. New field — check your financial statement for this line item."
    )
    prior_year_revenue, src_prior = input_field(
        "Prior Year Revenue ($)",
        "prior_year_revenue",
        "Total revenue from the previous fiscal year. Used to calculate revenue growth rate."
    )

## -- Balance Sheet Group --
st.markdown("**Balance Sheet**")
bs1, bs2 = st.columns(2)

with bs1:
    current_assets, src_ca = input_field(
        "Current Assets ($)",
        "current_assets",
        "Cash and assets convertible to cash within 12 months."
    )
    total_assets, src_ta = input_field(
        "Total Assets ($)",
        "total_assets",
        "All organizational assets including current, fixed, and restricted."
    )

with bs2:
    current_liabilities, src_cl = input_field(
        "Current Liabilities ($)",
        "current_liabilities",
        "Obligations due within 12 months."
    )
    total_liabilities, src_tl = input_field(
        "Total Liabilities ($)",
        "total_liabilities",
        "All organizational obligations including current and long-term."
    )

## -- Assemble inputs dict for calculation functions --
inputs = {
    "total_revenue":       total_revenue,
    "total_expenses":      total_expenses,
    "program_expenses":    program_expenses,
    "admin_expenses":      admin_expenses,
    "fundraising_expenses":fundraising_expenses,
    "current_assets":      current_assets,
    "current_liabilities": current_liabilities,
    "total_assets":        total_assets,
    "total_liabilities":   total_liabilities,
    "prior_year_revenue":  prior_year_revenue
}

## -- Assemble source tags dict for export --
source_tags = {
    "total_revenue":       src_rev,
    "total_expenses":      src_exp,
    "program_expenses":    src_prog,
    "admin_expenses":      src_admin,
    "fundraising_expenses":src_fund,
    "current_assets":      src_ca,
    "current_liabilities": src_cl,
    "total_assets":        src_ta,
    "total_liabilities":   src_tl,
    "prior_year_revenue":  src_prior
}

st.divider()

## ============================================================
## UI PART C — CALCULATE BUTTON AND VALIDATION
## User clicks Calculate to trigger the full scoring pipeline.
## Results persist in Streamlit session state so the page
## doesn't reset every time the user scrolls.
## ============================================================

if st.button("Calculate Financial Health Score", type="primary", use_container_width=True):

    ## Run validation first
    errors, warnings = validate_inputs(inputs)

    if errors:
        ## Hard errors — block calculation
        for err in errors:
            st.error(f"Input Error: {err}")
    else:
        ## Soft warnings — show but continue
        for warn in warnings:
            st.warning(warn)

        ## Run the full calculation pipeline
        ratios          = calculate_ratios(inputs)
        composite_result = calculate_composite(ratios)

        ## Save to session state so results persist during interaction
        st.session_state["ratios"]           = ratios
        st.session_state["composite_result"] = composite_result
        st.session_state["inputs"]           = inputs
        st.session_state["source_tags"]      = source_tags
        st.session_state["org_name"]         = org_name
        st.session_state["fiscal_year"]      = fiscal_year
        st.session_state["calculated"]       = True

## ============================================================
## UI PART D — RESULTS DISPLAY
## Only shown after the user clicks Calculate.
## Organized into four panels:
##   Panel 1: Snapshot (score, band, key flags)
##   Panel 2: Ratio Summary Table
##   Panel 3: Scenario Modeling
##   Panel 4: Data Gaps
## ============================================================

if st.session_state.get("calculated"):

    ratios           = st.session_state["ratios"]
    composite_result = st.session_state["composite_result"]
    saved_inputs     = st.session_state["inputs"]
    saved_sources    = st.session_state["source_tags"]
    saved_org        = st.session_state.get("org_name", "Organization")
    saved_year       = st.session_state.get("fiscal_year", 2025)

    ## --------------------------------------------------------
    ## PANEL 1 — SNAPSHOT
    ## Large score display + band + caveat + dimension sub-scores
    ## --------------------------------------------------------

    st.subheader(f"Results — {saved_org} ({saved_year})")

    score  = composite_result["composite"]
    band   = composite_result["band"]
    color  = BAND_COLORS.get(band, "#9aa0b4")
    avail  = composite_result["available_ratios"]
    total  = composite_result["total_ratios"]
    excl   = composite_result["excluded_dims"]

    ## Build caveat string if data is partial
    if avail < total or excl:
        caveat = f"Score based on {avail} of {total} indicators"
        if excl:
            caveat += f" — {', '.join([d.capitalize() for d in excl])} dimension(s) excluded"
    else:
        caveat = f"Score based on all {total} indicators"

    ## Score display
    snap1, snap2, snap3 = st.columns([1, 2, 1])

    with snap1:
        st.metric(label="Composite Score", value=f"{score}/100" if score else "N/A")
        st.markdown(f"<span style='color:{color}; font-size:18px; font-weight:600;'>{band}</span>", unsafe_allow_html=True)
        st.caption(caveat)

    with snap2:
        ## Dimension sub-scores
        dim_scores = composite_result["dimension_scores"]
        d1, d2, d3 = st.columns(3)
        with d1:
            s = dim_scores.get("sustainability")
            st.metric("Sustainability", f"{s:.0f}" if s else "—")
            st.caption("40% weight")
        with d2:
            s = dim_scores.get("efficiency")
            st.metric("Efficiency", f"{s:.0f}" if s else "—")
            st.caption("35% weight")
        with d3:
            s = dim_scores.get("solvency")
            st.metric("Solvency", f"{s:.0f}" if s else "—")
            st.caption("25% weight")

    with snap3:
        ## Floor rule warning
        if composite_result["floor_rule"]:
            st.warning(
                "⚠️ **Floor Rule Triggered**\n\n"
                "Program spending is below 50% of total expenses. "
                "This is a structural concern about mission alignment. "
                "The composite score may not fully reflect organizational risk."
            )

    st.divider()

    ## --------------------------------------------------------
    ## PANEL 2 — RATIO SUMMARY TABLE
    ## All 8 scored ratios + current ratio reference
    ## Shows value, tier, benchmark context, dimension
    ## --------------------------------------------------------

    st.subheader("Ratio Summary")

    ratio_rows = []

    for ratio_name, bench in BENCHMARKS.items():
        value  = ratios.get(ratio_name)
        score  = tier_score(ratio_name, value)
        label  = get_tier_label(score) if score is not None else "Unavailable"
        clr    = get_tier_color(score) if score is not None else "#9aa0b4"

        ratio_rows.append({
            "Ratio":      bench["label"],
            "Value":      format_ratio_value(ratio_name, value),
            "Tier":       f"🟢 {label}" if label == "Excellent"
                          else f"🔵 {label}" if label == "Strong"
                          else f"🟡 {label}" if label == "Average"
                          else f"🔴 {label}" if label == "Issues"
                          else f"⬜ {label}",
            "Score":      score if score is not None else "—",
            "Dimension":  bench["dimension"].capitalize()
        })

    ## Add current ratio reference row
    cr = ratios.get("current_ratio")
    ratio_rows.append({
        "Ratio":     "Current Ratio (reference — not scored)",
        "Value":     f"{cr:.2f}" if cr is not None else "—",
        "Tier":      "📋 Reference only",
        "Score":     "—",
        "Dimension": "Reference"
    })

    df_ratios = pd.DataFrame(ratio_rows)
    st.dataframe(df_ratios, use_container_width=True, hide_index=True)

    st.divider()

    ## --------------------------------------------------------
    ## PANEL 3 — SCENARIO MODELING
    ## Live revenue decline simulation
    ## User selects a preset or enters custom decline %
    ## Only Surplus Margin and Growth Rate change
    ## --------------------------------------------------------

    st.subheader("Scenario Modeling")
    st.caption(
        "Simulates the impact of revenue decline on financial health. "
        "Only Operating Surplus Margin and Revenue Growth Rate update — "
        "all other ratios are held constant because expenses, assets, "
        "and debt do not change instantly when revenue drops."
    )

    ## Scenario selector
    scen_col1, scen_col2 = st.columns([2, 3])

    with scen_col1:
        preset_choice = st.radio(
            "Select scenario",
            ["−10% Revenue", "−20% Revenue", "−25% Revenue", "Custom"],
            horizontal=True
        )
        if preset_choice == "Custom":
            custom_pct = st.slider(
                "Custom revenue decline (%)",
                min_value=0,
                max_value=50,
                value=15,
                step=1
            )
            active_decline = custom_pct / 100
        else:
            preset_map = {
                "−10% Revenue": 0.10,
                "−20% Revenue": 0.20,
                "−25% Revenue": 0.25
            }
            active_decline = preset_map[preset_choice]

    ## Run the active scenario
    active_scenario = run_scenario(
        saved_inputs,
        ratios,
        composite_result,
        active_decline
    )

    if active_scenario:
        with scen_col2:
            ## Score comparison
            baseline_score  = composite_result["composite"]
            scenario_score  = active_scenario["scenario_composite"]["composite"]
            scenario_band   = active_scenario["scenario_composite"]["band"]
            score_delta     = scenario_score - baseline_score if (baseline_score and scenario_score) else None

            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Baseline Score", f"{baseline_score}/100" if baseline_score else "N/A")
            with m2:
                st.metric(
                    "Scenario Score",
                    f"{scenario_score}/100" if scenario_score else "N/A",
                    delta=f"{score_delta:+.0f} pts" if score_delta is not None else None,
                    delta_color="inverse"
                )
            with m3:
                band_color = BAND_COLORS.get(scenario_band, "#9aa0b4")
                st.metric("Scenario Band", scenario_band if scenario_band else "N/A")

        ## Scenario bar chart — baseline vs scenario
        if baseline_score and scenario_score:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                name="Baseline",
                x=["Financial Health Score"],
                y=[baseline_score],
                marker_color="#2dd4bf",
                text=[f"{baseline_score}"],
                textposition="outside"
            ))
            fig.add_trace(go.Bar(
                name=f"Scenario ({int(active_decline*100)}% decline)",
                x=["Financial Health Score"],
                y=[scenario_score],
                marker_color="#f87171",
                text=[f"{scenario_score}"],
                textposition="outside"
            ))
            fig.update_layout(
                barmode="group",
                height=300,
                margin=dict(t=20, b=20, l=20, r=20),
                showlegend=True,
                yaxis=dict(range=[0, 110], title="Score"),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig, use_container_width=True)

        ## Ratio-level scenario changes with status flags
        st.markdown("**Ratio-level impact**")
        flag_map = {"green": "🟢", "yellow": "🟡", "red": "🔴", "gray": "⬜"}

        scen_rows = []
        for ratio_name, bench in BENCHMARKS.items():
            baseline_val  = ratios.get(ratio_name)
            scenario_val  = active_scenario["scenario_ratios"].get(ratio_name)
            flag          = active_scenario["status_flags"].get(ratio_name, "gray")
            changed       = ratio_name in SCENARIO_CHANGES

            scen_rows.append({
                "Ratio":          bench["label"],
                "Baseline":       format_ratio_value(ratio_name, baseline_val),
                "Scenario":       format_ratio_value(ratio_name, scenario_val),
                "Status":         flag_map.get(flag, "⬜"),
                "Changes?":       "Yes" if changed else "Held constant"
            })

        df_scen = pd.DataFrame(scen_rows)
        st.dataframe(df_scen, use_container_width=True, hide_index=True)

    st.divider()

    ## --------------------------------------------------------
    ## PANEL 4 — DATA GAPS
    ## Explicitly lists any unavailable fields and their impact
    ## This is one of the strongest features of the tool —
    ## it makes incomplete data visible rather than hiding it
    ## --------------------------------------------------------

    st.subheader("Data Gaps")

    ## Find which inputs were marked unavailable
    unavailable_fields = [k for k, v in saved_inputs.items() if v is None]

    ## Find which ratios couldn't be calculated
    unavailable_ratios = [
        BENCHMARKS[r]["label"]
        for r in BENCHMARKS
        if ratios.get(r) is None
    ]

    if not unavailable_fields:
        st.success("All input fields were available. No data gaps detected.")
    else:
        st.warning(
            f"{len(unavailable_fields)} field(s) were marked unavailable, "
            f"affecting {len(unavailable_ratios)} ratio(s)."
        )

        field_labels = {
            "total_revenue":       "Total Revenue",
            "total_expenses":      "Total Expenses",
            "program_expenses":    "Program Expenses",
            "admin_expenses":      "Administrative Expenses",
            "fundraising_expenses":"Fundraising Expenses",
            "current_assets":      "Current Assets",
            "current_liabilities": "Current Liabilities",
            "total_assets":        "Total Assets",
            "total_liabilities":   "Total Liabilities",
            "prior_year_revenue":  "Prior Year Revenue"
        }

        gap_rows = []
        for field in unavailable_fields:
            gap_rows.append({
                "Unavailable Field": field_labels.get(field, field),
                "Impact":           "Affects ratio calculation — excluded from score"
            })

        st.dataframe(pd.DataFrame(gap_rows), use_container_width=True, hide_index=True)

        if composite_result["excluded_dims"]:
            st.error(
                f"The following dimension(s) were fully excluded from scoring due to missing data: "
                f"{', '.join([d.capitalize() for d in composite_result['excluded_dims']])}. "
                f"Weights were redistributed proportionally across available dimensions."
            )

    st.divider()

    ## --------------------------------------------------------
    ## PANEL 5 — EXCEL EXPORT
    ## Generates downloadable Excel file on button click
    ## Three tabs: Raw Inputs, Ratio Results, Scenario Results
    ## --------------------------------------------------------

    st.subheader("Export")

    ## Pre-run all four standard scenarios for export
    all_scenarios = {}
    for pct in SCENARIO_PRESETS:
        label = f"−{int(pct*100)}% Revenue"
        all_scenarios[label] = run_scenario(
            saved_inputs, ratios, composite_result, pct
        )
    ## Add active custom scenario if it was custom
    if preset_choice == "Custom":
        all_scenarios[f"−{int(active_decline*100)}% Revenue (custom)"] = active_scenario

    excel_file = generate_excel(
        saved_inputs,
        saved_sources,
        ratios,
        composite_result,
        all_scenarios,
        saved_org,
        saved_year
    )

    st.download_button(
        label="⬇️ Download Excel Report",
        data=excel_file,
        file_name=f"BBS_Financial_Assessment_{saved_org}_{saved_year}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.caption(
        "Excel file contains three tabs: Raw Inputs (with data sources), "
        "Ratio Results (values, tiers, scores), and Scenario Results "
        "(all standard scenarios side by side)."
    )


## ============================================================
## SECTION 12 — METHODOLOGY NOTE
## Collapsed expander at the bottom explaining the approach.
## Gives consultants and reviewers context on the scoring model.
## ============================================================

st.divider()

with st.expander("About this tool — Methodology & Sources"):
    st.markdown("""
    **Scoring Model**

    This dashboard uses a three-dimension scoring model. Eight financial ratios
    are grouped into Sustainability (40%), Efficiency (35%), and Solvency (25%)
    dimensions. Each ratio is benchmarked against established nonprofit financial
    standards and converted to a standardized tier score (Excellent=100,
    Strong=75, Average=50, Issues=25). Dimension sub-scores are averaged within
    each dimension, then combined using the weights above to produce a composite
    score of 0–100.

    **Benchmark Sources**

    Benchmark thresholds are grounded in Charity Navigator's published
    Accountability & Finance methodology, which is the most widely used
    nonprofit financial rating framework in the United States.

    **Partial Data**

    When input fields are unavailable, the affected ratios are excluded from
    scoring rather than assumed to be zero. The composite score displays a
    caveat showing how many of the eight indicators contributed to the result.
    If an entire dimension is unavailable, its weight is redistributed
    proportionally across remaining dimensions.

    **Scenario Modeling**

    Scenario modeling applies a revenue decline shock while holding expenses,
    assets, and liabilities constant. This reflects the real-world constraint
    that organizations cannot immediately cut fixed costs when revenue drops.
    Only Operating Surplus Margin and Revenue Growth Rate recalculate in
    scenarios — all other ratios are held at baseline values.

    **Limitations**

    This tool is a decision-support instrument, not a substitute for full
    financial audit or professional accounting review. Scores should be
    interpreted in context alongside qualitative organizational factors.
    Profile-based weight differentiation (different weights per org type)
    is designed for future iteration pending BBS methodology approval.

    **Version**

    v1.0 Prototype — Bridge Builder Strategies BRIDGE Project, 2026.
    """)
