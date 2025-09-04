import streamlit as st

from asf_levies_model_app.utils.app_utils import (
    instantiate_levies,
    get_approach_weights,
    instantiate_tariffs,
    update_electricity_tariff_policy_cost,
    update_gas_tariff_policy_cost,
    instantiate_archetype_consumers,
    calculate_unit_cost_ratio,
    make_all_archetypes_xy_chart,
    create_archetype_reference_table,
    get_data_sources_info,
    validate_app_rates_against_ofgem,
    analyze_heat_pump_economics,
    get_tidy_summary,
    tidy_to_pivot_summary,
    make_archetype_bill_change_chart,
)

from asf_levies_model.summary import set_common_denominators
import asf_levies_model.getters.load_data as data
import copy
import traceback
from datetime import datetime

st.set_page_config(
    page_title="NESTA Levies Rebalancing Model + Heat Pump Analysis", page_icon="🏠", layout="wide"
)

st.title("UK Energy Policy Levies Rebalancing & Heat Pump Analysis App")
st.markdown("**This app is a simplified extension of original work by the [A Sustainable Future](https://www.nesta.org.uk/sustainable-future/) team at Nesta**")
st.header("Original NESTA Rebalancing App")

# Create styled panels for links
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div style="
        background-color: #f0f8ff;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        text-align: center;
        margin: 10px 0;
    ">
        <h4 style="margin-top: 0; color: #1f77b4;">📖 Background</h4>
        <p style="margin-bottom: 0;">
            <a href="https://medium.com/data-analytics-at-nesta/a-model-for-experimenting-with-energy-bills-rebalancing-levies-with-python-and-streamlit-08182638e8fc"
               target="_blank" style="text-decoration: none; color: #1f77b4; font-weight: 500;">
               Medium Article<br><small>Original NESTA model explanation</small>
            </a>
        </p>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style="
        background-color: #f0f8ff;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        text-align: center;
        margin: 10px 0;
    ">
        <h4 style="margin-top: 0; color: #1f77b4;">🚀 Live App</h4>
        <p style="margin-bottom: 0;">
            <a href="https://nesta-levies-model.streamlit.app/"
               target="_blank" style="text-decoration: none; color: #1f77b4; font-weight: 500;">
               Original NESTA App<br><small>Production Streamlit application</small>
            </a>
        </p>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div style="
        background-color: #f0f8ff;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #e0e0e0;
        text-align: center;
        margin: 10px 0;
    ">
        <h4 style="margin-top: 0; color: #1f77b4;">📂 Source Code</h4>
        <p style="margin-bottom: 0;">
            <a href="https://github.com/nesta-uk/asf-levies-model"
               target="_blank" style="text-decoration: none; color: #1f77b4; font-weight: 500;">
               ASF Levies Model<br><small>GitHub repository & documentation</small>
            </a>
        </p>
    </div>
    """, unsafe_allow_html=True)


# Instantiate baseline levies as LevyCollection (rebalanced to denominators)
@st.cache_data
def load_levies():
    fileobject = data.download_annex_4(as_fileobject=True)
    levies = instantiate_levies(fileobject)
    fileobject.close()
    return levies

# Create dictionary of denominators for each levy
supply_elec = 96_517_461.0
supply_gas = 266_505_188.0
customers_elec = 29_239_936
customers_gas = 24_605_467

denominators = set_common_denominators(
    levies,
    supply_elec=supply_elec,
    supply_gas=supply_gas,
    customers_elec=customers_elec,
    customers_gas=customers_gas,
)

# CONSTITUTIONAL APPROACH: Calculate All 3 Scenarios Simultaneously
# No session state, no switching, no crashes - just clean parallel calculation

st.markdown("---")
st.markdown("### 🎯 Policy Scenario Comparison")
st.markdown("**All three policy scenarios calculated simultaneously for comprehensive comparison**")

# Static scenario explanation panels
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    <div style='padding: 20px; background: linear-gradient(135deg, #f0f8ff 0%, #e6f3ff 100%); border-radius: 10px; border-left: 5px solid #1f77b4; margin-bottom: 10px;'>
        <h4 style='margin: 0 0 10px 0; color: #1f77b4;'>📊 Status Quo</h4>
        <p style='margin: 0; font-size: 14px; color: #333;'>
            <strong>Current levy distribution maintained</strong><br>
            All 7 policy levies remain split between electricity and gas bills as they are today.
            This represents the baseline scenario for comparison.
        </p>
        <ul style='margin: 5px 0 0 20px; font-size: 13px; color: #666;'>
            <li>No changes to current system</li>
            <li>Electricity bills remain expensive relative to gas</li>
            <li>Heat pumps face cost disadvantage</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
    <div style='padding: 20px; background: linear-gradient(135deg, #fff0f0 0%, #ffe6e6 100%); border-radius: 10px; border-left: 5px solid #d62728; margin-bottom: 10px;'>
        <h4 style='margin: 0 0 10px 0; color: #d62728;'>⚖️ Complete Rebalancing</h4>
        <p style='margin: 0; font-size: 14px; color: #333;'>
            <strong>Move ALL electricity levies to gas bills</strong><br>
            All 7 policy levies (RO, AAHEDC, FIT, ECO, WHD, GGL, NCC) are moved entirely to gas bills.
            Maximum reduction in electricity-to-gas cost ratio.
        </p>
        <ul style='margin: 5px 0 0 20px; font-size: 13px; color: #666;'>
            <li>Electricity bills reduced significantly</li>
            <li>Gas bills increased proportionally</li>
            <li>Maximum heat pump advantage</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
    <div style='padding: 20px; background: linear-gradient(135deg, #f0fff0 0%, #e6ffe6 100%); border-radius: 10px; border-left: 5px solid #2ca02c; margin-bottom: 10px;'>
        <h4 style='margin: 0 0 10px 0; color: #2ca02c;'>🎯 Targeted Rebalancing</h4>
        <p style='margin: 0; font-size: 14px; color: #333;'>
            <strong>Move RO and FIT levies only to gas bills</strong><br>
            Only the Renewables Obligation (RO) and Feed-in Tariffs (FIT) are moved to gas bills.
            Moderate reduction in electricity-to-gas cost ratio.
        </p>
        <ul style='margin: 5px 0 0 20px; font-size: 13px; color: #666;'>
            <li>Focused on renewable support costs</li>
            <li>Balanced approach to rebalancing</li>
            <li>Modest heat pump improvement</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# Policy Levies Reference Table
st.markdown("---")
st.markdown("#### 📋 Policy Scheme Levies Reference")
st.markdown("*Table 1: Policy scheme levies included in the Ofgem energy price cap, their total scheme amounts and estimated domestic share*")

levy_table_html = """
<table style="width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 14px;">
    <thead>
        <tr style="background-color: #f8f9fa; border-bottom: 2px solid #dee2e6;">
            <th style="padding: 12px; text-align: left; border: 1px solid #dee2e6; font-weight: bold;">Levy</th>
            <th style="padding: 12px; text-align: left; border: 1px solid #dee2e6; font-weight: bold;">Full Name</th>
            <th style="padding: 12px; text-align: right; border: 1px solid #dee2e6; font-weight: bold;">Total Scheme (£B)</th>
            <th style="padding: 12px; text-align: right; border: 1px solid #dee2e6; font-weight: bold;">Domestic Share (%)</th>
            <th style="padding: 12px; text-align: right; border: 1px solid #dee2e6; font-weight: bold;">Electricity (%)</th>
            <th style="padding: 12px; text-align: right; border: 1px solid #dee2e6; font-weight: bold;">Gas (%)</th>
        </tr>
    </thead>
    <tbody>
        <tr style="border-bottom: 1px solid #dee2e6;">
            <td style="padding: 10px; border: 1px solid #dee2e6; font-weight: bold; color: #2ca02c;">RO</td>
            <td style="padding: 10px; border: 1px solid #dee2e6;">Renewables Obligation</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">£6.8</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">85%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; background-color: #fff3cd;">100%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">0%</td>
        </tr>
        <tr style="border-bottom: 1px solid #dee2e6; background-color: #f8f9fa;">
            <td style="padding: 10px; border: 1px solid #dee2e6; font-weight: bold; color: #d62728;">FIT</td>
            <td style="padding: 10px; border: 1px solid #dee2e6;">Feed-in Tariffs</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">£1.2</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">82%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; background-color: #fff3cd;">100%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">0%</td>
        </tr>
        <tr style="border-bottom: 1px solid #dee2e6;">
            <td style="padding: 10px; border: 1px solid #dee2e6; font-weight: bold; color: #ff7f0e;">ECO</td>
            <td style="padding: 10px; border: 1px solid #dee2e6;">Energy Company Obligation</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">£2.7</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">100%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; background-color: #e6f3ff;">80%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; background-color: #e6f3ff;">20%</td>
        </tr>
        <tr style="border-bottom: 1px solid #dee2e6; background-color: #f8f9fa;">
            <td style="padding: 10px; border: 1px solid #dee2e6; font-weight: bold; color: #1f77b4;">WHD</td>
            <td style="padding: 10px; border: 1px solid #dee2e6;">Warm Homes Discount</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">£0.3</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">100%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; background-color: #e6f3ff;">67%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; background-color: #e6f3ff;">33%</td>
        </tr>
        <tr style="border-bottom: 1px solid #dee2e6;">
            <td style="padding: 10px; border: 1px solid #dee2e6; font-weight: bold; color: #9467bd;">AAHEDC</td>
            <td style="padding: 10px; border: 1px solid #dee2e6;">Assistance for Areas with High Electricity Distribution Costs</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">£0.04</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">100%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; background-color: #fff3cd;">100%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">0%</td>
        </tr>
        <tr style="border-bottom: 1px solid #dee2e6; background-color: #f8f9fa;">
            <td style="padding: 10px; border: 1px solid #dee2e6; font-weight: bold; color: #8c564b;">GGL</td>
            <td style="padding: 10px; border: 1px solid #dee2e6;">Green Gas Levy</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">£0.14</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">100%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">0%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; background-color: #fff3cd;">100%</td>
        </tr>
        <tr style="border-bottom: 1px solid #dee2e6;">
            <td style="padding: 10px; border: 1px solid #dee2e6; font-weight: bold; color: #e377c2;">NCC</td>
            <td style="padding: 10px; border: 1px solid #dee2e6;">Network Charging Compensation</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">£0.2</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">85%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right; background-color: #fff3cd;">100%</td>
            <td style="padding: 10px; border: 1px solid #dee2e6; text-align: right;">0%</td>
        </tr>
    </tbody>
</table>
"""

st.markdown(levy_table_html, unsafe_allow_html=True)

st.markdown("**Legend:**")
col_a, col_b, col_c = st.columns(3)
with col_a:
    st.markdown("🟡 **Electricity only** (100% electricity, 0% gas)")
with col_b:
    st.markdown("🔵 **Mixed funding** (split between electricity & gas)")
with col_c:
    st.markdown("🟠 **Gas only** (0% electricity, 100% gas)")

st.markdown("---")

# Calculate weights for all three scenarios
st.write("🔍 Calculating all scenarios...")

try:
    # Scenario 1: Current (Status Quo)
    current_weights = get_approach_weights(copy.deepcopy(levies), "Current")
    current_levies = levies.rebalance_levies(current_weights, scenario_name="Current")

    # Scenario 2: Complete Rebalancing
    complete_weights = get_approach_weights(copy.deepcopy(levies), "Rebalance all levies on electricity to gas")
    complete_levies = levies.rebalance_levies(complete_weights, scenario_name="Complete")

    # Scenario 3: Targeted Rebalancing (RO + FIT)
    targeted_weights = get_approach_weights(copy.deepcopy(levies), "Rebalance RO and FIT levies from electricity to gas")
    targeted_levies = levies.rebalance_levies(targeted_weights, scenario_name="Targeted")

    st.write("✅ All scenarios calculated successfully")

except Exception as e:
    st.error(f"❌ SCENARIO CALCULATION FAILED: {type(e).__name__}: {str(e)}")
    st.code(traceback.format_exc())
    st.stop()


# Calculate tariffs for all 3 scenarios
@st.cache_data
def load_base_tariffs():
    fileobject = data.download_annex_9(as_fileobject=True)
    tariffs = instantiate_tariffs(
        fileobject_annex_9=fileobject, payment_method="Other Payment"
    )
    fileobject.close()
    return tariffs

base_tariffs = load_base_tariffs()

# Scenario 1: Current (Status Quo)
current_electricity_tariff = update_electricity_tariff_policy_cost(
    copy.deepcopy(base_tariffs)["electricity"], current_levies
)
current_gas_tariff = update_gas_tariff_policy_cost(
    copy.deepcopy(base_tariffs)["gas"], current_levies
)

# Scenario 2: Complete Rebalancing
complete_electricity_tariff = update_electricity_tariff_policy_cost(
    copy.deepcopy(base_tariffs)["electricity"], complete_levies
)
complete_gas_tariff = update_gas_tariff_policy_cost(
    copy.deepcopy(base_tariffs)["gas"], complete_levies
)

# Scenario 3: Targeted Rebalancing (RO + FIT)
targeted_electricity_tariff = update_electricity_tariff_policy_cost(
    copy.deepcopy(base_tariffs)["electricity"], targeted_levies
)
targeted_gas_tariff = update_gas_tariff_policy_cost(
    copy.deepcopy(base_tariffs)["gas"], targeted_levies
)


# Create consumers for all 3 scenarios
@st.cache_data
def load_archetypes():
    return data.ofgem_archetypes_data()

ofgem_archetypes_df = load_archetypes()

# Filter to primary archetypes only (first 25 rows including header) to exclude distributional data
primary_archetypes_df = ofgem_archetypes_df.iloc[0:25]

# Create consumers for all scenarios
current_consumers = instantiate_archetype_consumers(
    primary_archetypes_df, current_gas_tariff, current_electricity_tariff
)
complete_consumers = instantiate_archetype_consumers(
    primary_archetypes_df, complete_gas_tariff, complete_electricity_tariff
)
targeted_consumers = instantiate_archetype_consumers(
    primary_archetypes_df, targeted_gas_tariff, targeted_electricity_tariff
)

# Calculate results for all 3 scenarios
# Unit cost ratios
current_ratio = calculate_unit_cost_ratio(current_electricity_tariff, current_gas_tariff)
complete_ratio = calculate_unit_cost_ratio(complete_electricity_tariff, complete_gas_tariff)
targeted_ratio = calculate_unit_cost_ratio(targeted_electricity_tariff, targeted_gas_tariff)

# Cost to taxpayers for each scenario
current_cost_to_tax = sum(
    current_weights[levy.short_name]["new_tax_weight"] * levy.revenue
    for levy in current_levies
)
complete_cost_to_tax = sum(
    complete_weights[levy.short_name]["new_tax_weight"] * levy.revenue
    for levy in complete_levies
)
targeted_cost_to_tax = sum(
    targeted_weights[levy.short_name]["new_tax_weight"] * levy.revenue
    for levy in targeted_levies
)

# Energy price caps (typical household bills)
current_price_cap = (
    current_electricity_tariff.calculate_total_consumption(2.7, vat=True) +
    current_gas_tariff.calculate_total_consumption(11.5, vat=True)
)
complete_price_cap = (
    complete_electricity_tariff.calculate_total_consumption(2.7, vat=True) +
    complete_gas_tariff.calculate_total_consumption(11.5, vat=True)
)
targeted_price_cap = (
    targeted_electricity_tariff.calculate_total_consumption(2.7, vat=True) +
    targeted_gas_tariff.calculate_total_consumption(11.5, vat=True)
)

# Update data period status now that tariffs are loaded
start = current_electricity_tariff.price_cap_period.left
end = current_electricity_tariff.price_cap_period.right
current_date = datetime.now().date()

# Ensure start and end are date objects for comparison
start_date = start.date() if hasattr(start, 'date') else start
end_date = end.date() if hasattr(end, 'date') else end

is_current = current_date <= end_date  # Current or future data is valid
status_icon = "✅" if is_current else "❌"
period_text = f"{start_date.day} {start_date.strftime('%B')} - {end_date.day} {end_date.strftime('%B')} {end_date.year}"

# Enhanced data sources section
with st.expander("📊 **Data Sources**", expanded=True):

    # Config file management
    st.markdown("### 🔧 Configuration Management")
    st.markdown("**Config file contains links to Ofgem Annexes 4 and 9 used for calculation and must be updated manually to point to the latest versions.**")
    st.markdown("📁 [View config file on GitHub](https://github.com/kinetiknrg/asf_levies_model/blob/dev/asf_levies_model/config/base.yaml)")

    # Get data sources info for validation rates
    data_info = get_data_sources_info()

    # Date information at top with medium font
    st.markdown("##### 📅 Data Currency Status")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"<div style='font-size: 16px'><b>Current Date</b><br>{data_info['current_date']}</div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div style='font-size: 16px'><b>Config Updated</b><br>{data_info['config_updated']}</div>", unsafe_allow_html=True)
    with col3:
        days_text = f"{data_info['days_since_update']} days ago" if isinstance(data_info['days_since_update'], int) else data_info['days_since_update']
        st.markdown(f"<div style='font-size: 16px'><b>Days Since Update</b><br>{days_text}</div>", unsafe_allow_html=True)
    with col4:
        # Dynamic data period with status indicator
        st.markdown(f"<div style='font-size: 16px'><b>28AD Charge Restriction Period</b><br>{status_icon} {period_text}</div>", unsafe_allow_html=True)

    st.markdown("---")

    # Official Ofgem Data Sources
    st.markdown("### Official Ofgem Data Sources")
    st.markdown("This analysis uses **Energy price cap (default tariff) levels** data published by **[Ofgem](https://www.ofgem.gov.uk/energy-regulation/domestic-and-non-domestic/energy-pricing-rules/energy-price-cap/energy-price-cap-default-tariff-levels)**:")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📋 Policy Cost Data (Annex 4)**")
        st.markdown(f"[Current Ofgem Annex 4]({data_info['ofgem_annex_4']})")
        st.caption("Contains levy rates, revenues, and policy scheme parameters")

    with col2:
        st.markdown("**💰 Tariff Data (Annex 9)**")
        st.markdown(f"[Current Ofgem Annex 9]({data_info['ofgem_annex_9']})")
        st.caption("Contains energy price cap methodology and tariff components")

    st.info("🔍 **Data Currency**: Ofgem updates energy price cap data quarterly.")
    st.warning("⚠️ **Important**: Analysis results reflect the specific Ofgem data period loaded. CHECK IT'S UP TO DATE")

# Summary metrics for all 3 scenarios
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📊 Status Quo")
    st.metric("Elec/Gas Ratio", f"{current_ratio:.2f}")
    st.metric("Taxpayer Cost", f"£{current_cost_to_tax/1_000_000_000:.2f}B/yr")
    st.metric("Typical Bill", f"£{current_price_cap:.0f}/yr")

with col2:
    st.markdown("### ⚖️ Complete Rebalancing")
    ratio_change = current_ratio - complete_ratio
    cost_change = (complete_cost_to_tax - current_cost_to_tax) / 1_000_000_000
    bill_change = complete_price_cap - current_price_cap

    st.metric("Elec/Gas Ratio", f"{complete_ratio:.2f}", f"{-ratio_change:+.2f}")
    st.metric("Taxpayer Cost", f"£{complete_cost_to_tax/1_000_000_000:.2f}B/yr", f"£{cost_change:+.2f}B/yr")
    st.metric("Typical Bill", f"£{complete_price_cap:.0f}/yr", f"£{bill_change:+.0f}/yr")

with col3:
    st.markdown("### 🎯 Targeted Rebalancing")
    ratio_change_t = current_ratio - targeted_ratio
    cost_change_t = (targeted_cost_to_tax - current_cost_to_tax) / 1_000_000_000
    bill_change_t = targeted_price_cap - current_price_cap

    st.metric("Elec/Gas Ratio", f"{targeted_ratio:.2f}", f"{-ratio_change_t:+.2f}")
    st.metric("Taxpayer Cost", f"£{targeted_cost_to_tax/1_000_000_000:.2f}B/yr", f"£{cost_change_t:+.2f}B/yr")
    st.metric("Typical Bill", f"£{targeted_price_cap:.0f}/yr", f"£{bill_change_t:+.0f}/yr")

# Data period status
st.markdown("---")
if current_date < start_date:
    st.success(f"**📅 Data Period (Future)**: {period_text}")
elif start_date <= current_date <= end_date:
    st.success(f"**📅 Data Period (Active)**: {period_text}")
else:
    st.error(f"**📅 Data Period (Expired)**: {period_text}")

# Rate validation section - outside collapsible panel for visibility
st.markdown("---")
st.markdown("### 🔍 Rate Validation: App vs Official Ofgem Published Rates")

# Validate app rates against official Ofgem data (using current/status quo scenario)
validation_result, error = validate_app_rates_against_ofgem(
    current_electricity_tariff,
    current_gas_tariff,
    data_info['validation_rates']
)

if validation_result:
    st.markdown(f"**Comparison with [official Ofgem rates]({validation_result['validation_data']['source_url']})**: {validation_result['validation_data']['period']} ({validation_result['validation_data']['payment_method']})")

    # Display comparison table with individual RAG status
    st.dataframe(validation_result['comparison_table'], use_container_width=True, hide_index=True)

    st.caption(f"**Legend:** 🟢 Excellent (<0.25%) | 🟡 Acceptable (<1%) | 🔴 Issues (>1%)")

    # Add explanation for denominator differences
    with st.expander("ℹ️ **Why do app rates differ slightly from official Ofgem rates?**", expanded=False):
        st.markdown("""
        **Expected small differences due to methodological choices:**

        1. **Different denominators**: App uses DESNZ domestic consumption data (2023) for internal consistency, while Ofgem uses their own supply volumes and customer counts

        2. **Rebalancing to denominators**: App calls `rebalance_to_denominators()` to ensure all levies use consistent baseline data, which adjusts rates slightly from Ofgem published values

        3. **Data processing variations**: Different rounding, scaling factors, or calculation sequencing

        4. **Purpose**: These adjustments enable accurate **relative comparisons** between scenarios while maintaining revenue neutrality

        **Key Quote**: *"This is mitigated by rebalancing to the analysis denominators, but means that the base case will be slightly different to that published by ofgem."* - ASF Levies Model documentation
        """)

    st.caption(f"*Validation data verified {validation_result['validation_data']['verified_date']}.*")
else:
    st.info(f"💡 Rate validation not available: {error}")
    st.caption("*Rate validation requires manual updates to validation_rates section in base.yaml config file*")

st.markdown("---")

st.markdown(
    f"<p style='color:black; font-size: 20px;'><b>All Consumer Archetypes Analysis</b></p>",
    unsafe_allow_html=True,
)

# Helper function to calculate tariff rates for display
def get_tariff_rates(elec_tariff, gas_tariff):
    """Calculate unit rates and standing charges (inc VAT) for display"""
    # Electricity
    elec_total_1_mwh = elec_tariff.calculate_total_consumption(1, vat=True)
    elec_standing = elec_tariff.calculate_nil_consumption() * 1.05
    elec_unit_rate = ((elec_total_1_mwh - elec_standing) / 1000) * 100  # p/kWh
    elec_standing_charge = (elec_standing / 365) * 100  # p/day

    # Gas
    gas_total_1_mwh = gas_tariff.calculate_total_consumption(1, vat=True)
    gas_standing = gas_tariff.calculate_nil_consumption() * 1.05
    gas_unit_rate = ((gas_total_1_mwh - gas_standing) / 1000) * 100  # p/kWh
    gas_standing_charge = (gas_standing / 365) * 100  # p/day

    return {
        'elec_unit_rate': elec_unit_rate,
        'elec_standing_charge': elec_standing_charge,
        'gas_unit_rate': gas_unit_rate,
        'gas_standing_charge': gas_standing_charge
    }

# Calculate rates for all scenarios
current_rates = get_tariff_rates(current_electricity_tariff, current_gas_tariff)
complete_rates = get_tariff_rates(complete_electricity_tariff, complete_gas_tariff)
targeted_rates = get_tariff_rates(targeted_electricity_tariff, targeted_gas_tariff)

# Detailed tariff comparison for all scenarios
st.markdown("<h4>📊 Detailed Tariff Rate Comparison: All Scenarios</h4>", unsafe_allow_html=True)
st.info("ℹ️ **All tariff rates shown include VAT at 5%** - matching published Ofgem price cap rates")

# 3-scenario detailed comparison
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### 📊 Status Quo")

    st.markdown("**Electricity**")
    st.metric("Unit Rate", f"{current_rates['elec_unit_rate']:.2f} p/kWh")
    st.metric("Standing Charge", f"{current_rates['elec_standing_charge']:.2f} p/day")

    st.markdown("**Gas**")
    st.metric("Unit Rate", f"{current_rates['gas_unit_rate']:.2f} p/kWh")
    st.metric("Standing Charge", f"{current_rates['gas_standing_charge']:.2f} p/day")

    st.markdown("**Ratio**")
    current_ratio_calc = current_rates['elec_unit_rate'] / current_rates['gas_unit_rate']
    st.metric("Elec/Gas Ratio", f"{current_ratio_calc:.2f}", help="Electricity ÷ Gas unit rate")

with col2:
    st.markdown("#### ⚖️ Complete Rebalancing")

    st.markdown("**Electricity**")
    elec_unit_change = complete_rates['elec_unit_rate'] - current_rates['elec_unit_rate']
    elec_standing_change = complete_rates['elec_standing_charge'] - current_rates['elec_standing_charge']
    st.metric("Unit Rate", f"{complete_rates['elec_unit_rate']:.2f} p/kWh", f"{elec_unit_change:+.2f}")
    st.metric("Standing Charge", f"{complete_rates['elec_standing_charge']:.2f} p/day", f"{elec_standing_change:+.2f}")

    st.markdown("**Gas**")
    gas_unit_change = complete_rates['gas_unit_rate'] - current_rates['gas_unit_rate']
    gas_standing_change = complete_rates['gas_standing_charge'] - current_rates['gas_standing_charge']
    st.metric("Unit Rate", f"{complete_rates['gas_unit_rate']:.2f} p/kWh", f"{gas_unit_change:+.2f}")
    st.metric("Standing Charge", f"{complete_rates['gas_standing_charge']:.2f} p/day", f"{gas_standing_change:+.2f}")

    st.markdown("**Ratio**")
    complete_ratio_calc = complete_rates['elec_unit_rate'] / complete_rates['gas_unit_rate']
    ratio_change = current_ratio_calc - complete_ratio_calc
    st.metric("Elec/Gas Ratio", f"{complete_ratio_calc:.2f}", f"{-ratio_change:+.2f}")

with col3:
    st.markdown("#### 🎯 Targeted Rebalancing")

    st.markdown("**Electricity**")
    elec_unit_change_t = targeted_rates['elec_unit_rate'] - current_rates['elec_unit_rate']
    elec_standing_change_t = targeted_rates['elec_standing_charge'] - current_rates['elec_standing_charge']
    st.metric("Unit Rate", f"{targeted_rates['elec_unit_rate']:.2f} p/kWh", f"{elec_unit_change_t:+.2f}")
    st.metric("Standing Charge", f"{targeted_rates['elec_standing_charge']:.2f} p/day", f"{elec_standing_change_t:+.2f}")

    st.markdown("**Gas**")
    gas_unit_change_t = targeted_rates['gas_unit_rate'] - current_rates['gas_unit_rate']
    gas_standing_change_t = targeted_rates['gas_standing_charge'] - current_rates['gas_standing_charge']
    st.metric("Unit Rate", f"{targeted_rates['gas_unit_rate']:.2f} p/kWh", f"{gas_unit_change_t:+.2f}")
    st.metric("Standing Charge", f"{targeted_rates['gas_standing_charge']:.2f} p/day", f"{gas_standing_change_t:+.2f}")

    st.markdown("**Ratio**")
    targeted_ratio_calc = targeted_rates['elec_unit_rate'] / targeted_rates['gas_unit_rate']
    ratio_change_t = current_ratio_calc - targeted_ratio_calc
    st.metric("Elec/Gas Ratio", f"{targeted_ratio_calc:.2f}", f"{-ratio_change_t:+.2f}")

st.markdown("---")

# All archetypes XY chart with reference table
st.markdown("<h4>🏠 Energy Cost Analysis: Gas Consumer Archetypes</h4>", unsafe_allow_html=True)
st.caption("Gas cost (x-axis) vs Electricity cost (y-axis) for gas-heated consumer archetypes only. **All costs include VAT at 5%.** Bubble size represents number of households. Non-gas archetypes are hidden from chart but shown greyed out in reference table below.")

# Full-width chart (showing current vs complete rebalancing)
xy_chart = make_all_archetypes_xy_chart(
    baseline_consumers=current_consumers,
    rebalanced_consumers=complete_consumers,
    ofgem_archetypes_df=ofgem_archetypes_df,
    chart_width=900
)

if xy_chart:
    st.altair_chart(xy_chart, use_container_width=True)
else:
    st.error("Unable to create chart")

# Archetype reference table below chart
st.markdown("---")
st.markdown("<h5>📋 Archetype Reference</h5>", unsafe_allow_html=True)
st.caption("🔵 = Shown in chart | ⚫ = Hidden (non-gas consumers)")

ref_table = create_archetype_reference_table(ofgem_archetypes_df)

# Apply styling: grey out non-gas archetypes as mentioned in caption
def highlight_non_gas(row):
    if row['Heating'] != 'Gas':
        return ['color: #888888; opacity: 0.6'] * len(row)
    return [''] * len(row)

styled_table = ref_table.style.apply(highlight_non_gas, axis=1).set_properties(**{'text-align': 'left'})

# Display styled dataframe - full width below chart
st.dataframe(
    styled_table,
    use_container_width=True,
    height=400,
    hide_index=True
)

# Heat pump economics analysis section
st.markdown("---")
st.markdown("<h4>🏠 Heat Pump Retrofit Analysis: The Purpose of Levy Rebalancing</h4>", unsafe_allow_html=True)
st.caption("Analysis of how levy rebalancing affects the economics of switching from gas boilers to electric heat pumps")

# Perform heat pump analysis (comparing current vs complete rebalancing)
hp_analysis = analyze_heat_pump_economics(
    current_consumers, complete_consumers,
    current_electricity_tariff, complete_electricity_tariff,
    current_gas_tariff, complete_gas_tariff
)

# Key metrics display
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Electricity/Gas Ratio",
        value=f"{hp_analysis['rebalanced_ratio']:.2f}",
        delta=f"{hp_analysis['rebalanced_ratio'] - hp_analysis['baseline_ratio']:+.2f}"
    )
    ratio_status = "✅ Competitive" if hp_analysis['rebalanced_ratio'] < hp_analysis['heat_pump_spf'] else "❌ Not competitive"
    st.caption(f"Heat pump threshold: {hp_analysis['heat_pump_spf']:.1f}")
    st.caption(ratio_status)

with col2:
    st.metric(
        label="Archetypes Benefiting",
        value=f"{hp_analysis['rebalanced_winners']}",
        delta=f"{hp_analysis['rebalanced_winners'] - hp_analysis['baseline_winners']:+d}"
    )
    st.caption(f"Out of {hp_analysis['total_gas_archetypes']} gas archetypes")

with col3:
    st.metric(
        label="Average Improvement",
        value=f"£{hp_analysis['avg_improvement']:+,.0f}",
        delta=None
    )
    st.caption("Annual savings per household")

with col4:
    # Policy assessment for complete rebalancing scenario
    if hp_analysis['rebalanced_ratio'] < hp_analysis['heat_pump_spf']:
        st.success("🎯 **POLICY SUCCESS**")
        st.caption("Heat pumps now competitive")
    else:
        st.warning("⚠️ **PARTIAL PROGRESS**")
        st.caption("Further rebalancing needed")

# Heat pump analysis table
st.markdown("### 📊 Heat Pump Economics by Archetype")

# Format display table with proper formatting
display_data = hp_analysis['analysis_data'].copy()

# Format MWh to 3 decimal places
display_data['gas_formatted'] = display_data['gas_consumption_mwh'].apply(lambda x: f"{x:.3f}")
display_data['hp_elec_formatted'] = display_data['hp_elec_demand_mwh'].apply(lambda x: f"{x:.3f}")

# Format currency values
display_data['baseline_saving_formatted'] = display_data['baseline_saving'].apply(lambda x: f"£{x:+,.0f}")
display_data['rebalanced_saving_formatted'] = display_data['rebalanced_saving'].apply(lambda x: f"£{x:+,.0f}")
display_data['improvement_formatted'] = display_data['improvement'].apply(lambda x: f"£{x:+,.0f}")

# Add competitiveness indicators
display_data['baseline_status'] = display_data['baseline_competitive'].apply(lambda x: "✅" if x else "❌")
display_data['rebalanced_status'] = display_data['rebalanced_competitive'].apply(lambda x: "✅" if x else "❌")

# Select columns for display
table_display = display_data[[
    'archetype', 'gas_formatted', 'hp_elec_formatted',
    'baseline_saving_formatted', 'baseline_status',
    'rebalanced_saving_formatted', 'rebalanced_status',
    'improvement_formatted'
]].copy()

table_display.columns = [
    'Archetype', 'Gas (MWh)', 'HP Elec (MWh)',
    'Baseline Saving', 'Baseline', 'Rebalanced Saving', 'Rebalanced', 'Improvement'
]

# Apply styling for alignment
styled_hp_table = table_display.style.set_properties(
    subset=['Gas (MWh)', 'HP Elec (MWh)', 'Baseline Saving', 'Rebalanced Saving', 'Improvement'],
    **{'text-align': 'right'}
).set_properties(
    subset=['Baseline', 'Rebalanced'],
    **{'text-align': 'center'}
)

st.dataframe(styled_hp_table, use_container_width=True, hide_index=True)

# Policy insights
st.markdown("### 🎯 Policy Impact Summary")

# Policy impact summary (comparing current vs complete rebalancing)
col1, col2 = st.columns(2)

with col1:
    st.info(f"**📊 Current State**: Electricity-to-gas ratio is {hp_analysis['baseline_ratio']:.2f}, above heat pump competitiveness threshold of {hp_analysis['heat_pump_spf']:.1f}")
    st.metric(
        label="Current Heat Pump Competitive Archetypes",
        value=f"{hp_analysis['baseline_winners']}/{hp_analysis['total_gas_archetypes']}"
    )

with col2:
    st.info(f"**⚖️ Complete Rebalancing**: Electricity-to-gas ratio is {hp_analysis['rebalanced_ratio']:.2f}, {'below' if hp_analysis['rebalanced_ratio'] < hp_analysis['heat_pump_spf'] else 'above'} heat pump competitiveness threshold")
    improvement = hp_analysis['rebalanced_winners'] - hp_analysis['baseline_winners']
    st.metric(
        label="Additional Competitive Archetypes",
        value=f"+{improvement}",
        delta=f"{hp_analysis['rebalanced_winners']}/{hp_analysis['total_gas_archetypes']} total"
    )

# Overall policy assessment
if hp_analysis['rebalanced_ratio'] < hp_analysis['heat_pump_spf']:
    st.success(f"**🏆 Policy Success**: Heat pump competitiveness achieved through levy rebalancing")
else:
    st.warning(f"**⚠️ Partial Progress**: Ratio improved from {hp_analysis['baseline_ratio']:.2f} to {hp_analysis['rebalanced_ratio']:.2f}, but still above heat pump threshold")

# Economic impact
if hp_analysis['avg_improvement'] > 0:
    st.success(f"**💰 Economic Benefit**: Average £{hp_analysis['avg_improvement']:,.0f}/year improvement in heat pump economics per household")
else:
    st.warning(f"**💸 Economic Impact**: Average £{abs(hp_analysis['avg_improvement']):,.0f}/year cost increase per household")

st.markdown("---")

# Result: Distribution impacts dot chart (using current vs complete rebalancing)
baseline_summary_table = tidy_to_pivot_summary(
    get_tidy_summary(current_consumers, "Current")
)
rebalanced_summary_table = tidy_to_pivot_summary(
    get_tidy_summary(complete_consumers, "Complete Rebalancing")
)
# Add bill change column
rebalanced_summary_table["bill_change"] = (
    rebalanced_summary_table["combined_fuel_bill"]
    - baseline_summary_table["combined_fuel_bill"]
)

# Add archetype sizes

archetype_sizes = data.ofgem_archetypes_data()[
    ["AnnualConsumptionProfile", "ArchetypeSize"]
]
archetype_sizes = archetype_sizes.rename(
    columns={
        "AnnualConsumptionProfile": "Name",
    }
)
rebalanced_summary_table = rebalanced_summary_table.merge(
    archetype_sizes, on="Name", how="left"
)

st.markdown(
    f"<p style='color:black; font-size: 20px;'><b>Distributional impacts: Effect on energy bills</b></p>",
    unsafe_allow_html=True,
)
col1, col2 = st.columns(2)
with col2:
    st.info(
        f"**Typical household bill: £{complete_price_cap:,.2f}** *(Current: £{current_price_cap:,.2f})*"
    )

chart = make_archetype_bill_change_chart(rebalanced_summary_table, chart_width=1000)
st.altair_chart(chart)

# Option to view results table
if st.button("View distributional impacts results table"):
    # Show link to distributional effects summary dataframe for download
    @st.cache_data
    def convert_df(df):
        return df.to_csv(index=False).encode("utf-8")

    csv = convert_df(rebalanced_summary_table)

    st.download_button(
        "Download table",
        csv,
        "rebalanced_scenario_distributional_effect.csv",
        "text/csv",
        key="download-csv",
    )

    st.write(rebalanced_summary_table)
