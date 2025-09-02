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
)

from asf_levies_model.summary import (
    set_common_denominators,
    create_scenario_weights_dict,
)
import asf_levies_model.levies as levies
import asf_levies_model.getters.load_data as data
import copy
import traceback
from datetime import datetime
import numpy as np
import yaml

st.set_page_config(
    page_title="NESTA Levies Rebalancing Model + Heat Pump Analysis", page_icon="🏠", layout="wide"
)

st.title("Ofgem Levies Rebalancing & Heat Pump Analysis App💡")
st.markdown("**Based on original work by the [A Sustainable Future](https://www.nesta.org.uk/sustainable-future/) team at Nesta**")

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

levies = load_levies()

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

# Initialise session state variables

if "approach" not in st.session_state:
    st.session_state.approach = "Current"

if "rebalancing_weights" not in st.session_state:
    st.session_state.rebalancing_weights = {}

if "levy_modes" not in st.session_state:
    st.session_state.levy_modes = {}

if (
    st.session_state.approach == "Create my own"
    and not st.session_state.rebalancing_weights
):
    st.session_state.rebalancing_weights = create_scenario_weights_dict(levies)


# Show selectors for levy reform scenario in side bar
with st.sidebar:
    st.info(
        "**Test a levy reform scenario** by adjusting the settings below. *Note: You can hide or adjust the width of this sidebar.*"
    )

    internal_to_display_map = {
        "Current": "Status Quo",
        "Rebalance all levies on electricity to gas": "Rebalancing ⚖️ all levies to gas",
        "Rebalance RO and FIT levies from electricity to gas": "Rebalancing ⚖️ RO+FIT levies to gas",
        "Remove all levies on electricity to taxation": "Taxation 👑 all levies to taxation",
        "Remove RO and FIT levies from electricity to taxation": "Taxation 👑 RO+FIT levies to taxation",
        "Create my own": "Create my own",
    }
    selected_display = internal_to_display_map.get(
        st.session_state.approach, st.session_state.approach
    )
    st.success(f"**Selected:** {selected_display}")

    def set_status_quo():
        st.session_state.approach = "Current"

    st.button(
        "⚖️ Status Quo",
        use_container_width=True,
        type="primary" if st.session_state.approach == "Current" else "secondary",
        on_click=set_status_quo,
        key="button_status_quo"
    )

    st.markdown("---")

    st.subheader("Rebalancing ⚖️")
    st.caption("From electricity :zap: to gas :fire:")
    def set_rebalance_all():
        st.session_state.approach = "Rebalance all levies on electricity to gas"

    col1, col2 = st.columns(2)
    with col1:
        st.button(
            "All levies",
            key="rebalance_all",
            use_container_width=True,
            type="primary"
            if st.session_state.approach == "Rebalance all levies on electricity to gas"
            else "secondary",
            on_click=set_rebalance_all
        )
    def set_rebalance_ro_fit():
        st.session_state.approach = "Rebalance RO and FIT levies from electricity to gas"

    with col2:
        st.button(
            "RO + FIT only",
            help="Renewables Obligation and Feed-in Tariff",
            key="rebalance_ro_fit",
            use_container_width=True,
            type="primary"
            if st.session_state.approach
            == "Rebalance RO and FIT levies from electricity to gas"
            else "secondary",
            on_click=set_rebalance_ro_fit
        )

    st.subheader("Taxation 👑")
    st.caption("From electricity :zap: to general taxation")
    def set_taxation_all():
        st.session_state.approach = "Remove all levies on electricity to taxation"

    col1, col2 = st.columns(2)
    with col1:
        st.button(
            "All levies",
            key="taxation_all",
            use_container_width=True,
            type="primary"
            if st.session_state.approach
            == "Remove all levies on electricity to taxation"
            else "secondary",
            on_click=set_taxation_all
        )
    def set_taxation_ro_fit():
        st.session_state.approach = "Remove RO and FIT levies from electricity to taxation"

    with col2:
        st.button(
            "RO + FIT only",
            help="Renewables Obligation and Feed-in Tariff",
            key="taxation_ro_fit",
            use_container_width=True,
            type="primary"
            if st.session_state.approach
            == "Remove RO and FIT levies from electricity to taxation"
            else "secondary",
            on_click=set_taxation_ro_fit
        )

    st.markdown("---")

    def set_create_own():
        st.session_state.approach = "Create my own"

    st.button(
        "✍️ Create my own",
        use_container_width=True,
        type="primary" if st.session_state.approach == "Create my own" else "secondary",
        on_click=set_create_own,
        key="button_create_own"
    )

    st.markdown("---")

    if st.session_state.approach == "Create my own":
        st.session_state.rebalancing_weights = create_scenario_weights_dict(levies)

        for levy in levies:

            st.markdown("---")

            # Radio button for levy mode (rebalance or move to tax)
            if levy.short_name not in st.session_state.levy_modes:
                st.session_state.levy_modes[levy.short_name] = (
                    "Rebalance between electricity and gas"
                )

            st.session_state.levy_modes[levy.short_name] = st.radio(
                f"**{levy.name}**",
                [
                    "Rebalance between electricity and gas",
                    "Remove off bills to general taxation",
                ],
                index=[
                    "Rebalance between electricity and gas",
                    "Remove off bills to general taxation",
                ].index(st.session_state.levy_modes[levy.short_name]),
                key=f"{levy.short_name}_radio",
            )

            # Rebalancing weights: Fuel
            if (
                st.session_state.levy_modes[levy.short_name]
                == "Rebalance between electricity and gas"
            ):
                st.session_state.rebalancing_weights[levy.short_name][
                    "new_tax_weight"
                ] = 0.0
                st.session_state.rebalancing_weights[levy.short_name][
                    "new_gas_weight"
                ] = (
                    st.slider(
                        "Electricity (0) <-> Gas (100)",
                        value=(
                            st.session_state.rebalancing_weights[levy.short_name][
                                "new_gas_weight"
                            ]
                        )
                        * 100.0,
                        min_value=0.0,
                        max_value=100.0,
                        step=1.0,
                        key=f"{levy.short_name}_rebalancing_slider",
                    )
                    / 100.0
                )
                st.session_state.rebalancing_weights[levy.short_name][
                    "new_electricity_weight"
                ] = 1.0 - (
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_gas_weight"
                    ]
                )

            # Rebalancing weights: To general taxation
            else:
                st.session_state.rebalancing_weights[levy.short_name][
                    "new_tax_weight"
                ] = 1.0
                st.session_state.rebalancing_weights[levy.short_name][
                    "new_gas_weight"
                ] = 0.0
                st.session_state.rebalancing_weights[levy.short_name][
                    "new_electricity_weight"
                ] = 0.0

            # Rebalancing weights: Unit costs vs standing charge

            # Check for electricity levy rebalancing
            if (
                st.session_state.rebalancing_weights[levy.short_name][
                    "new_electricity_weight"
                ]
                != 0.0
            ):
                # Set initial mode based on weights
                if (
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_variable_weight_elec"
                    ]
                    == 1.0
                ):
                    elec_index = 0  # Variable weight mode
                elif (
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_fixed_weight_elec"
                    ]
                    != 0.0
                ):
                    elec_index = 1  # Fixed weight mode
                else:
                    # Default to either variable or fixed based on gas weight setting
                    elec_index = (
                        0
                        if st.session_state.rebalancing_weights[levy.short_name][
                            "new_variable_weight_gas"
                        ]
                        else 1
                    )

                # Display the radio button for levy mode on electricity
                elec_mode = st.radio(
                    "Mode of levy on electricity:",
                    ["Unit cost", "Standing charge"],
                    index=elec_index,
                    key=f"{levy.short_name}_elec_mode",
                )

                # Update weights based on the selected mode
                if elec_mode == "Unit cost":
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_variable_weight_elec"
                    ] = 1.0
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_fixed_weight_elec"
                    ] = 0.0
                else:
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_variable_weight_elec"
                    ] = 0.0
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_fixed_weight_elec"
                    ] = 1.0

            # Check for gas levy rebalancing
            if (
                st.session_state.rebalancing_weights[levy.short_name]["new_gas_weight"]
                != 0.0
            ):
                # Set initial mode based on weights
                if (
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_variable_weight_gas"
                    ]
                    == 1.0
                ):
                    gas_index = 0  # Variable weight mode
                elif (
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_fixed_weight_gas"
                    ]
                    != 0.0
                ):
                    gas_index = 1  # Fixed weight mode
                else:
                    # Default to either variable or fixed based on gas weight setting
                    gas_index = (
                        0
                        if st.session_state.rebalancing_weights[levy.short_name][
                            "new_variable_weight_elec"
                        ]
                        else 1
                    )

                # Display the radio button for levy mode on gas
                gas_mode = st.radio(
                    "Mode of levy on gas:",
                    ["Unit cost", "Standing charge"],
                    index=gas_index,
                    key=f"{levy.short_name}_gas_mode",
                )

                # Update weights based on the selected mode
                if gas_mode == "Unit cost":
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_variable_weight_gas"
                    ] = 1.0
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_fixed_weight_gas"
                    ] = 0.0
                else:
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_variable_weight_gas"
                    ] = 0.0
                    st.session_state.rebalancing_weights[levy.short_name][
                        "new_fixed_weight_gas"
                    ] = 1.0

    else:
        # Create a deep copy of the cached levies to prevent mutation errors on re-runs
        levies_copy = copy.deepcopy(levies)
        st.session_state.rebalancing_weights = get_approach_weights(
            levies_copy, st.session_state.approach
        )


try:
    # Rebalance levies based on chosen approach
    rebalanced_levies = levies.rebalance_levies(
        st.session_state.rebalancing_weights,
        scenario_name="Rebalanced",
    )

    # Instantiate baseline and rebalanced tariffs
    @st.cache_data
    def load_tariffs():
        fileobject = data.download_annex_9(as_fileobject=True)
        baseline_tariffs = instantiate_tariffs(
            fileobject_annex_9=fileobject, payment_method="Other Payment"
        )
        rebalanced_tariffs = instantiate_tariffs(
            fileobject_annex_9=fileobject, payment_method="Other Payment"
        )
        fileobject.close()
        return baseline_tariffs, rebalanced_tariffs

    baseline_tariffs, rebalanced_tariffs = load_tariffs()

    baseline_electricity_tariff = update_electricity_tariff_policy_cost(
        baseline_tariffs["electricity"], levies
    )
    baseline_gas_tariff = update_gas_tariff_policy_cost(baseline_tariffs["gas"], levies)
    rebalanced_electricity_tariff = update_electricity_tariff_policy_cost(
        rebalanced_tariffs["electricity"], rebalanced_levies
    )
    rebalanced_gas_tariff = update_gas_tariff_policy_cost(
        rebalanced_tariffs["gas"], rebalanced_levies
    )

    # Create a list of Consumers (average Ofgem archetypes only, n=24) for baseline and rebalanced scenario
    @st.cache_data
    def load_archetypes():
        return data.ofgem_archetypes_data()

    ofgem_archetypes_df = load_archetypes()

    # Filter to primary archetypes only (first 24 rows) to exclude distributional data
    primary_archetypes_df = ofgem_archetypes_df.iloc[:24]

    baseline_consumers = instantiate_archetype_consumers(
        primary_archetypes_df, baseline_gas_tariff, baseline_electricity_tariff
    )
    rebalanced_consumers = instantiate_archetype_consumers(
        primary_archetypes_df, rebalanced_gas_tariff, rebalanced_electricity_tariff
    )

    # Result: Unit cost ratio
    baseline_ratio = calculate_unit_cost_ratio(
        baseline_electricity_tariff, baseline_gas_tariff
    )
    rebalanced_ratio = calculate_unit_cost_ratio(
        rebalanced_electricity_tariff, rebalanced_gas_tariff
    )

    # Result: Cost to taxpayers
    cost_to_tax = sum(
        st.session_state.rebalancing_weights[levy.short_name]["new_tax_weight"]
        * levy.revenue
        for levy in rebalanced_levies
    )

    # Result: Energy price cap (i.e. typical household bill)
    baseline_price_cap = baseline_electricity_tariff.calculate_total_consumption(
        2.7, vat=True
    ) + baseline_gas_tariff.calculate_total_consumption(11.5, vat=True)
    rebalanced_price_cap = rebalanced_electricity_tariff.calculate_total_consumption(
        2.7, vat=True
    ) + rebalanced_gas_tariff.calculate_total_consumption(11.5, vat=True)

    # Update data period status now that tariffs are loaded
    start = baseline_electricity_tariff.price_cap_period.left
    end = baseline_electricity_tariff.price_cap_period.right
    current_date = datetime.now().date()
    is_current = current_date <= end.date()  # Current or future data is valid
    status_icon = "✅" if is_current else "❌"
    period_text = f"{start.day} {start.strftime('%B')} - {end.day} {end.strftime('%B')} {end.year}"

    # Data sources transparency section (after tariffs loaded for dynamic period)
    data_info = get_data_sources_info()
    with st.expander("📊 **Data Sources**", expanded=True):

        # Config file management
        st.markdown("### 🔧 Configuration Management")
        st.markdown("**Config file contains links to Ofgem Annexes 4 and 9 used for calculation and must be updated manually to point to the latest versions.**")
        st.markdown("📁 [View config file on GitHub](https://github.com/kinetiknrg/asf_levies_model/blob/dev/asf_levies_model/config/base.yaml)")



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
            st.markdown(f"<div style='font-size: 16px'><b>Data Period Status</b><br>{status_icon} {period_text}</div>", unsafe_allow_html=True)

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

    col1, col2, col3 = st.columns(3)

    with col1:
        # Show data period status prominently with refined logic
        if current_date < start.date():
            st.success(f"**📅 Data Period (Future)**  \n{period_text}")
        elif start.date() <= current_date <= end.date():
            st.success(f"**📅 Data Period (Active)**  \n{period_text}")
        else:  # current_date > end.date()
            st.error(f"**📅 Data Period (Expired)**  \n{period_text}")

    with col2:
        st.warning(
            f"**Electricity-to-gas ratio: {rebalanced_ratio:.2f}** *(Current: {baseline_ratio:.2f})*"
        )
    with col3:
        st.error(
            f"**Additional cost to taxpayers: £{cost_to_tax/1_000_000_000:.2f} billion per year**"
        )

    # Rate validation section - outside collapsible panel for visibility
    st.markdown("---")
    st.markdown("### 🔍 Rate Validation: App vs Official Ofgem Published Rates")

    validation_result, error = validate_app_rates_against_ofgem(
        baseline_electricity_tariff,
        baseline_gas_tariff,
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

            **Bottom Line**: Small differences (<1%) confirm the app uses sophisticated methodology for policy analysis rather than simply replicating consumer-facing rates.
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

    # Calculate baseline and rebalanced tariff rates (inc VAT) for reference
    baseline_elec_total_1_mwh_inc_vat = baseline_electricity_tariff.calculate_total_consumption(1, vat=True)
    baseline_elec_standing_inc_vat = baseline_electricity_tariff.calculate_nil_consumption() * 1.05
    baseline_elec_unit_price_inc_vat = ((baseline_elec_total_1_mwh_inc_vat - baseline_elec_standing_inc_vat) / 1000) * 100
    baseline_elec_standing_charge_inc_vat = (baseline_elec_standing_inc_vat / 365) * 100

    baseline_gas_total_1_mwh_inc_vat = baseline_gas_tariff.calculate_total_consumption(1, vat=True)
    baseline_gas_standing_inc_vat = baseline_gas_tariff.calculate_nil_consumption() * 1.05
    baseline_gas_unit_price_inc_vat = ((baseline_gas_total_1_mwh_inc_vat - baseline_gas_standing_inc_vat) / 1000) * 100
    baseline_gas_standing_charge_inc_vat = (baseline_gas_standing_inc_vat / 365) * 100

    rebalanced_elec_total_1_mwh_inc_vat = rebalanced_electricity_tariff.calculate_total_consumption(1, vat=True)
    rebalanced_elec_standing_inc_vat = rebalanced_electricity_tariff.calculate_nil_consumption() * 1.05
    rebalanced_elec_unit_price_inc_vat = ((rebalanced_elec_total_1_mwh_inc_vat - rebalanced_elec_standing_inc_vat) / 1000) * 100
    rebalanced_elec_standing_charge_inc_vat = (rebalanced_elec_standing_inc_vat / 365) * 100

    rebalanced_gas_total_1_mwh_inc_vat = rebalanced_gas_tariff.calculate_total_consumption(1, vat=True)
    rebalanced_gas_standing_inc_vat = rebalanced_gas_tariff.calculate_nil_consumption() * 1.05
    rebalanced_gas_unit_price_inc_vat = ((rebalanced_gas_total_1_mwh_inc_vat - rebalanced_gas_standing_inc_vat) / 1000) * 100
    rebalanced_gas_standing_charge_inc_vat = (rebalanced_gas_standing_inc_vat / 365) * 100

    # Tariff comparison section
    st.markdown("<h4>📊 Tariff Rate Comparison: Baseline vs Rebalanced</h4>", unsafe_allow_html=True)
    st.info("ℹ️ **All tariff rates shown include VAT at 5%** - matching published Ofgem price cap rates")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown("<h6>Baseline Electricity</h6>", unsafe_allow_html=True)
        st.metric(
            label="Unit Rate (inc VAT)",
            value=f"{baseline_elec_unit_price_inc_vat:.2f} p/kWh"
        )
        st.metric(
            label="Standing Charge (inc VAT)",
            value=f"{baseline_elec_standing_charge_inc_vat:.2f} p/day"
        )

    with col2:
        st.markdown("<h6>Rebalanced Electricity</h6>", unsafe_allow_html=True)
        unit_rate_change = rebalanced_elec_unit_price_inc_vat - baseline_elec_unit_price_inc_vat
        standing_change = rebalanced_elec_standing_charge_inc_vat - baseline_elec_standing_charge_inc_vat
        st.metric(
            label="Unit Rate (inc VAT)",
            value=f"{rebalanced_elec_unit_price_inc_vat:.2f} p/kWh",
            delta=f"{unit_rate_change:+.2f} p/kWh"
        )
        st.metric(
            label="Standing Charge (inc VAT)",
            value=f"{rebalanced_elec_standing_charge_inc_vat:.2f} p/day",
            delta=f"{standing_change:+.2f} p/day"
        )

    with col3:
        st.markdown("<h6>Baseline Gas</h6>", unsafe_allow_html=True)
        st.metric(
            label="Unit Rate (inc VAT)",
            value=f"{baseline_gas_unit_price_inc_vat:.2f} p/kWh"
        )
        st.metric(
            label="Standing Charge (inc VAT)",
            value=f"{baseline_gas_standing_charge_inc_vat:.2f} p/day"
        )

    with col4:
        st.markdown("<h6>Rebalanced Gas</h6>", unsafe_allow_html=True)
        gas_unit_rate_change = rebalanced_gas_unit_price_inc_vat - baseline_gas_unit_price_inc_vat
        gas_standing_change = rebalanced_gas_standing_charge_inc_vat - baseline_gas_standing_charge_inc_vat
        st.metric(
            label="Unit Rate (inc VAT)",
            value=f"{rebalanced_gas_unit_price_inc_vat:.2f} p/kWh",
            delta=f"{gas_unit_rate_change:+.2f} p/kWh"
        )
        st.metric(
            label="Standing Charge (inc VAT)",
            value=f"{rebalanced_gas_standing_charge_inc_vat:.2f} p/day",
            delta=f"{gas_standing_change:+.2f} p/day"
        )

    st.markdown("---")

    # All archetypes XY chart with reference table
    st.markdown("<h4>🏠 Energy Cost Analysis: Gas Consumer Archetypes</h4>", unsafe_allow_html=True)
    st.caption("Gas cost (x-axis) vs Electricity cost (y-axis) for gas-heated consumer archetypes only. **All costs include VAT at 5%.** Bubble size represents number of households. Non-gas archetypes are hidden from chart but shown greyed out in reference table below.")

    # Full-width chart
    xy_chart = make_all_archetypes_xy_chart(
        baseline_consumers=baseline_consumers,
        rebalanced_consumers=rebalanced_consumers,
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
    # Apply basic styling for the reference table
    styled_table = ref_table.style.set_properties(**{'text-align': 'left'})

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

    # Perform heat pump analysis
    hp_analysis = analyze_heat_pump_economics(
        baseline_consumers, rebalanced_consumers,
        baseline_electricity_tariff, rebalanced_electricity_tariff,
        baseline_gas_tariff, rebalanced_gas_tariff
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
        # Only show policy assessment for rebalancing scenarios
        if st.session_state.approach == "Current":
            st.info("📊 **STATUS QUO**")
            st.caption("Current state analysis")
        else:
            # Rebalancing scenario assessment
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

    # Check if we're in Status Quo mode
    if st.session_state.approach == "Current":
        st.info(f"**📊 Current State Analysis**: Electricity-to-gas ratio is {hp_analysis['baseline_ratio']:.2f}, which is above the heat pump competitiveness threshold of {hp_analysis['heat_pump_spf']:.1f}")
        st.caption("ℹ️ Select a rebalancing scenario from the sidebar to see policy impact analysis")

        col1, col2 = st.columns(2)
        with col1:
            st.metric(
                label="Current Heat Pump Competitive Archetypes",
                value=f"{hp_analysis['baseline_winners']}/{hp_analysis['total_gas_archetypes']}"
            )
        with col2:
            if hp_analysis['baseline_ratio'] < hp_analysis['heat_pump_spf']:
                st.success("✅ **Heat pumps already competitive**")
            else:
                st.warning("⚠️ **Heat pumps not yet competitive**")
    else:
        # Rebalancing scenario analysis
        if hp_analysis['rebalanced_ratio'] < hp_analysis['heat_pump_spf']:
            st.success(f"**🏆 Heat Pump Competitiveness Achieved**: Electricity-to-gas ratio ({hp_analysis['rebalanced_ratio']:.2f}) is now below heat pump efficiency threshold ({hp_analysis['heat_pump_spf']:.1f})")
        else:
            st.warning(f"**⚠️ Partial Progress**: Electricity-to-gas ratio improved from {hp_analysis['baseline_ratio']:.2f} to {hp_analysis['rebalanced_ratio']:.2f}, but still above heat pump threshold ({hp_analysis['heat_pump_spf']:.1f})")

        col1, col2 = st.columns(2)
        with col1:
            st.info(f"**Household Impact**: {hp_analysis['rebalanced_winners'] - hp_analysis['baseline_winners']} additional archetypes would benefit from heat pump retrofits")
        with col2:
            if hp_analysis['avg_improvement'] > 0:
                st.success(f"**Economic Benefit**: Average £{hp_analysis['avg_improvement']:,.0f}/year improvement in heat pump economics")
            else:
                st.warning(f"**Economic Impact**: Average £{abs(hp_analysis['avg_improvement']):,.0f}/year cost increase")

except Exception as e:
    st.error(f"🚨 **Error**: {type(e).__name__}")
    st.error(f"**Message**: {str(e)}")

    with st.expander("🔍 **Error Details** (Click to expand)"):
        st.text(traceback.format_exc())
