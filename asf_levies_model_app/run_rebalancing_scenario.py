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
    style_archetype_reference_table,
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

st.set_page_config(
    page_title="Nesta Levies Rebalancing Model", page_icon="🏠", layout="wide"
)

st.title("Ofgem Levies Rebalancing & Heat Pump Analysis App💡")
st.markdown(
    """
    **Based on original work by the [A Sustainable Future](https://www.nesta.org.uk/sustainable-future/) team at Nesta**

    🔗 [Original NESTA Streamlit app](https://nesta-levies-model.streamlit.app/)

    📚 [ASF Levies Model documentation](https://github.com/nesta-uk/asf-levies-model)
    """
)


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

    baseline_consumers = instantiate_archetype_consumers(
        ofgem_archetypes_df, baseline_gas_tariff, baseline_electricity_tariff
    )
    rebalanced_consumers = instantiate_archetype_consumers(
        ofgem_archetypes_df, rebalanced_gas_tariff, rebalanced_electricity_tariff
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

    col1, col2, col3 = st.columns(3)

    with col2:
        st.warning(
            f"**Electricity-to-gas ratio: {rebalanced_ratio:.2f}** *(Current: {baseline_ratio:.2f})*"
        )
    with col3:
        st.error(
            f"**Additional cost to taxpayers: £{cost_to_tax/1_000_000_000:.2f} billion per year**"
        )
        start = baseline_electricity_tariff.price_cap_period.left
        end = baseline_electricity_tariff.price_cap_period.right
        st.markdown(
            f"*Using price cap period: {start.day} {start.strftime('%B')} to {end.day} {end.strftime('%B')} {end.year}*"
        )


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
    styled_table = style_archetype_reference_table(ref_table)

    # Display styled dataframe - full width below chart
    st.dataframe(
        styled_table,
        use_container_width=True,
        height=400,
        hide_index=True
    )

except Exception as e:
    st.error(f"🚨 **Error**: {type(e).__name__}")
    st.error(f"**Message**: {str(e)}")

    with st.expander("🔍 **Error Details** (Click to expand)"):
        st.text(traceback.format_exc())
