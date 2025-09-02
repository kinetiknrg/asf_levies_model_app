import streamlit as st
import pandas as pd
import altair as alt

from typing import List, Dict

import asf_levies_model.getters.load_data as data

import asf_levies_model.levies as levies
import asf_levies_model.tariffs as tariffs

from asf_levies_model.levies import Levy, LevyCollection

from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment

from asf_levies_model.consumers import Consumer, ConsumerCollection

from asf_levies_model.summary import create_scenario_weights_dict

import numpy as np
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s')


def instantiate_levies(
    fileobject_annex_4,
    supply_elec: float = 96_517_461.0,  # MWh
    supply_gas: float = 266_505_188.0,  # MWh
    customers_elec: int = 29_239_936,
    customers_gas: int = 24_605_467,
) -> LevyCollection:

    denominator_values = {
        "supply_elec": supply_elec,
        "supply_gas": supply_gas,
        "customers_gas": customers_gas,
        "customers_elec": customers_elec,
    }

    # Scaling factor for estimating domestic share of FIT revenue
    total_supply_elec = (
        249_044_438  # DESNZ GB total electricity consumption - all meters (2023)
    )
    exempt_eii_supply = (
        10_529_633  # Apr-Jun2025 period, Annex 4, New FIT methodology tab
    )
    fit_scaling_factor = supply_elec / (total_supply_elec - exempt_eii_supply)

    # Scaling factor for estimating domestic share of NCC revenue
    ncc_eligible_supply = (
        119_380_310.7  # Mar-Jun2025 period, Annex 4, NCC methodology tab
    )
    ncc_scaling_factor = supply_elec / ncc_eligible_supply

    # Instantiate status quo levies with Annex 4 data
    list_levies = [
        levies.RO.from_dataframe(
            data.process_data_RO(fileobject_annex_4), denominator=supply_elec
        ),
        levies.AAHEDC.from_dataframe(
            data.process_data_AAHEDC(fileobject_annex_4), denominator=supply_elec
        ),
        levies.GGL.from_dataframe(
            data.process_data_GGL(fileobject_annex_4), denominator=customers_gas
        ),
        levies.WHD.from_dataframe(
            data.process_data_WHD(fileobject_annex_4),
            customers_gas=customers_gas,
            customers_elec=customers_elec,
        ),
        levies.ECO4.from_dataframe(data.process_data_ECO(fileobject_annex_4)),
        levies.GBIS.from_dataframe(data.process_data_ECO(fileobject_annex_4)),
        levies.FIT.from_dataframe(
            data.process_data_FIT(fileobject_annex_4),
            scaling_factor=fit_scaling_factor,
        ),
        levies.NCC.from_dataframe(
            data.process_data_NCC(fileobject_annex_4), scaling_factor=ncc_scaling_factor
        ),
    ]

    pc = levies.LevyCollection("Policy Costs", "pc", list_levies, denominator_values)

    # Rebalance baseline levies to reflect denominators
    pc = pc.rebalance_to_denominators()

    return pc


def get_approach_weights(levies: List, approach_name: str) -> Dict:

    logging.info(f"get_approach_weights called with approach_name: '{approach_name}'")

    # "Current"
    baseline_weights = create_scenario_weights_dict(levies)
    logging.info("Successfully created baseline_weights.")

    # "Rebalance all levies on electricity to gas"
    all_gas_weights = create_scenario_weights_dict(levies)
    for levy in [levy for levy in levies if levy.electricity_weight > 0]:
        all_gas_weights[levy.short_name] = {
            "new_electricity_weight": 0.0,
            "new_gas_weight": 1.0,
            "new_tax_weight": 0.0,
            "new_variable_weight_elec": 0.0,
            "new_fixed_weight_elec": 0.0,
            "new_variable_weight_gas": levy.electricity_variable_weight,
            "new_fixed_weight_gas": levy.electricity_fixed_weight,
        }
    logging.info("Successfully created all_gas_weights.")

    # "Rebalance RO and FIT levies from electricity to gas"
    rebalance_ro_fit_weights = create_scenario_weights_dict(levies)
    for levy in [levy for levy in levies if levy.short_name in ["ro", "fit"]]:
        rebalance_ro_fit_weights[levy.short_name] = {
            "new_electricity_weight": 0.0,
            "new_gas_weight": 1.0,
            "new_tax_weight": 0.0,
            "new_variable_weight_elec": 0.0,
            "new_fixed_weight_elec": 0.0,
            "new_variable_weight_gas": levy.electricity_variable_weight,
            "new_fixed_weight_gas": levy.electricity_fixed_weight,
        }
    logging.info("Successfully created rebalance_ro_fit_weights.")

    # "Remove all levies on electricity to taxation"
    sq_electricity_removal_weights = create_scenario_weights_dict(levies)
    for levy in [levy.short_name for levy in levies if levy.electricity_weight > 0]:
        sq_electricity_removal_weights[levy]["new_tax_weight"] = (
            sq_electricity_removal_weights[levy]["new_electricity_weight"]
        )

        for weight_type in [
            "new_electricity_weight",
            "new_variable_weight_elec",
            "new_fixed_weight_elec",
        ]:
            sq_electricity_removal_weights[levy][weight_type] = 0.0
    logging.info("Successfully created sq_electricity_removal_weights.")

    # "Remove RO and FIT levies from electricity to taxation"
    remove_ro_fit_weights = create_scenario_weights_dict(levies)
    for levy in ["ro", "fit"]:
        remove_ro_fit_weights[levy]["new_tax_weight"] = remove_ro_fit_weights[levy][
            "new_electricity_weight"
        ]

        for weight_type in [
            "new_electricity_weight",
            "new_variable_weight_elec",
            "new_fixed_weight_elec",
        ]:
            remove_ro_fit_weights[levy][weight_type] = 0.0
    logging.info("Successfully created remove_ro_fit_weights.")

    # Create lookup dictionary for weights of each approach
    approach_weights = {
        "Current": baseline_weights,
        "Rebalance all levies on electricity to gas": all_gas_weights,
        "Rebalance RO and FIT levies from electricity to gas": rebalance_ro_fit_weights,
        "Remove all levies on electricity to taxation": sq_electricity_removal_weights,
        "Remove RO and FIT levies from electricity to taxation": remove_ro_fit_weights,
    }

    if approach_name not in approach_weights.keys():
        raise ValueError("Rebalancing approach name not recognised.")

    logging.info(f"Successfully retrieved weights for '{approach_name}'.")
    return approach_weights[approach_name]


def instantiate_tariffs(
    fileobject_annex_9, payment_method: str = "Other Payment"
) -> Dict:

    # Load tariff tables from Annex 9
    # Other payment
    elec_other_payment_nil = data.process_tariff_elec_other_payment_nil(
        fileobject_annex_9
    )
    elec_other_payment_typical = data.process_tariff_elec_other_payment_typical(
        fileobject_annex_9
    )
    gas_other_payment_nil = data.process_tariff_gas_other_payment_nil(
        fileobject_annex_9
    )
    gas_other_payment_typical = data.process_tariff_gas_other_payment_typical(
        fileobject_annex_9
    )
    # Prepayment meter
    elec_ppm_nil = data.process_tariff_elec_ppm_nil(fileobject_annex_9)
    elec_ppm_typical = data.process_tariff_elec_ppm_typical(fileobject_annex_9)
    gas_ppm_nil = data.process_tariff_gas_ppm_nil(fileobject_annex_9)
    gas_ppm_typical = data.process_tariff_gas_ppm_typical(fileobject_annex_9)
    # Standard Credit
    elec_standard_credit_nil = data.process_tariff_elec_standard_credit_nil(
        fileobject_annex_9
    )
    elec_standard_credit_typical = data.process_tariff_elec_standard_credit_typical(
        fileobject_annex_9
    )
    gas_standard_credit_nil = data.process_tariff_gas_standard_credit_nil(
        fileobject_annex_9
    )
    gas_standard_credit_typical = data.process_tariff_gas_standard_credit_typical(
        fileobject_annex_9
    )

    # Instantiate Tariff objects
    if payment_method == "Other Payment":
        electricity_tariff = ElectricityOtherPayment.from_dataframe(
            elec_other_payment_nil, elec_other_payment_typical
        )
        gas_tariff = GasOtherPayment.from_dataframe(
            gas_other_payment_nil, gas_other_payment_typical
        )
    elif payment_method == "PPM":
        electricity_tariff = ElectricityOtherPayment.from_dataframe(
            elec_ppm_nil, elec_ppm_typical
        )
        gas_tariff = GasOtherPayment.from_dataframe(gas_ppm_nil, gas_ppm_typical)
    elif payment_method == "Standard Credit":
        electricity_tariff = ElectricityOtherPayment.from_dataframe(
            elec_standard_credit_nil, elec_standard_credit_typical
        )
        gas_tariff = GasOtherPayment.from_dataframe(
            gas_standard_credit_nil, gas_standard_credit_typical
        )
    else:
        raise ValueError("Payment method not recognised.")

    return {"electricity": electricity_tariff, "gas": gas_tariff}


def update_electricity_tariff_policy_cost(tariff, levies):
    tariff.pc_nil = sum([levy.calculate_levy(0, 0, True, False) for levy in levies])
    tariff.pc = sum([levy.calculate_levy(1, 0, False, False) for levy in levies])
    return tariff


def update_gas_tariff_policy_cost(tariff, levies):
    tariff.pc_nil = sum([levy.calculate_levy(0, 0, False, True) for levy in levies])
    tariff.pc = sum([levy.calculate_levy(0, 1, False, False) for levy in levies])
    return tariff


def instantiate_archetype_consumers(
    ofgem_archetypes_df: pd.DataFrame,
    gas_tariff: tariffs.Tariff,
    electricity_tariff: tariffs.Tariff,
):

    # Create list of Consumers (Average Ofgem archetypes only, n=24)
    consumers = [
        Consumer.consumer_from_dataframe(
            df=ofgem_archetypes_df,
            row=row,
            name_col="AnnualConsumptionProfile",
            archetype_col="AnnualConsumptionProfile",
            net_annual_income_col="NetAnnualHouseholdIncome",
            main_heating_fuel_col="ArchetypeHeatingFuel",
            gas_consumption_col="GaskWh",
            electricity_consumption_col="ElectricitySingleRatekWh",
            gas_tariff=gas_tariff,
            electricity_tariff=electricity_tariff,
            unit_converter=1_000,
        )
        for row in range(1, 25)
    ]

    return consumers


def instantiate_archetype_consumers_with_eligibility(
    ofgem_archetypes_df: pd.DataFrame,
    gas_tariff: tariffs.Tariff,
    electricity_tariff: tariffs.Tariff,
):

    # Create list of eligible Consumers (Average Ofgem archetypes only, n=24)
    eligible_consumers = [
        Consumer(
            name=ofgem_archetypes_df.loc[row, "AnnualConsumptionProfile"],
            archetype=ofgem_archetypes_df.loc[row, "AnnualConsumptionProfile"],
            net_annual_income=ofgem_archetypes_df.loc[row, "NetAnnualHouseholdIncome"],
            net_income_decile=ofgem_archetypes_df.loc[row, "NetIncomeDecile"],
            main_heating_fuel=ofgem_archetypes_df.loc[row, "ArchetypeHeatingFuel"],
            gas_consumption=ofgem_archetypes_df.loc[row, "GaskWh"] / 1_000,
            electricity_consumption=ofgem_archetypes_df.loc[
                row, "ElectricitySingleRatekWh"
            ]
            / 1_000,
            gas_tariff=gas_tariff,
            electricity_tariff=electricity_tariff,
            scheme_eligible=True,
        )
        for row in range(1, 25)
    ]

    # Create list of ineligible Consumers (Average Ofgem archetypes only, n=24)
    ineligible_consumers = [
        Consumer(
            name=ofgem_archetypes_df.loc[row, "AnnualConsumptionProfile"],
            archetype=ofgem_archetypes_df.loc[row, "AnnualConsumptionProfile"],
            net_annual_income=ofgem_archetypes_df.loc[row, "NetAnnualHouseholdIncome"],
            net_income_decile=ofgem_archetypes_df.loc[row, "NetIncomeDecile"],
            main_heating_fuel=ofgem_archetypes_df.loc[row, "ArchetypeHeatingFuel"],
            gas_consumption=ofgem_archetypes_df.loc[row, "GaskWh"] / 1_000,
            electricity_consumption=ofgem_archetypes_df.loc[
                row, "ElectricitySingleRatekWh"
            ]
            / 1_000,
            gas_tariff=gas_tariff,
            electricity_tariff=electricity_tariff,
            scheme_eligible=True,
        )
        for row in range(1, 25)
    ]
    return eligible_consumers, ineligible_consumers


def calculate_unit_cost_ratio(electricity_tariff, gas_tariff):
    return electricity_tariff.calculate_variable_consumption(
        1
    ) / gas_tariff.calculate_variable_consumption(1)


def instantiate_new_levy(
    new_levy_name,
    new_levy_revenue,
    new_levy_fuel,
    new_levy_type,
    supply_elec,
    customers_elec,
    supply_gas,
    customers_gas,
):

    electricity_fixed_weight = (
        1
        if (new_levy_fuel == "Electricity") & (new_levy_type == "Standing charge")
        else 0
    )
    electricity_variable_weight = (
        1 if (new_levy_fuel == "Electricity") & (new_levy_type == "Consumption") else 0
    )
    gas_variable_weight = (
        1 if (new_levy_fuel == "Gas") & (new_levy_type == "Consumption") else 0
    )
    gas_fixed_weight = (
        1 if (new_levy_fuel == "Gas") & (new_levy_type == "Standing charge") else 0
    )

    new_levy = Levy(
        name=new_levy_name,
        short_name=new_levy_name,
        electricity_weight=1 if new_levy_fuel == "Electricity" else 0,
        gas_weight=1 if new_levy_fuel == "Gas" else 0,
        tax_weight=0,
        electricity_variable_weight=electricity_variable_weight,
        electricity_fixed_weight=electricity_fixed_weight,
        gas_variable_weight=gas_variable_weight,
        gas_fixed_weight=gas_fixed_weight,
        electricity_variable_rate=(new_levy_revenue / supply_elec)
        * electricity_variable_weight,
        electricity_fixed_rate=(new_levy_revenue / customers_elec)
        * electricity_fixed_weight,
        gas_variable_rate=(new_levy_revenue / supply_gas) * gas_variable_weight,
        gas_fixed_rate=(new_levy_revenue / customers_gas) * gas_fixed_weight,
        general_taxation=0,
        revenue=new_levy_revenue,
        price_cap_period="LATEST",
    )

    return new_levy


def get_tidy_summary(consumers, scenario_name):
    tidy_summary = pd.concat([consumer.get_tidy_summary() for consumer in consumers])
    tidy_summary["Scenario"] = scenario_name
    return tidy_summary


def tidy_to_pivot_summary(tidy_summary):
    pivot_summary_table = tidy_summary.pivot_table(
        index=["Name", "Scenario"], columns="Attribute", values="Value", aggfunc="first"
    ).reset_index()

    # Define columns to be used and to be converted to numeric
    numeric_cols = [
        "electricity_bill",
        "gas_bill",
        "combined_fuel_bill",
        "fuel_poverty_gap",
    ]

    final_cols = [
        "Name",
        "Scenario",
        "main_heating_fuel",
    ] + numeric_cols

    pivot_summary_table = pivot_summary_table[final_cols].sort_values(
        by=["Scenario", "Name"]
    )

    # Convert object columns to numeric types to prevent charting errors
    for col in numeric_cols:
        pivot_summary_table[col] = pd.to_numeric(pivot_summary_table[col], errors='coerce')

    logging.info(f"DataFrame created with shape {pivot_summary_table.shape}. Dtypes: {pivot_summary_table.dtypes.to_dict()}")

    return pivot_summary_table


def make_archetype_bill_change_chart(rebalanced_summary_table, chart_width=1000):

    # Data validation to prevent charting errors
    # Ensure 'ArchetypeSize' is numeric and handle invalid values robustly
    rebalanced_summary_table["ArchetypeSize"] = pd.to_numeric(
        rebalanced_summary_table["ArchetypeSize"], errors="coerce"
    )
    rebalanced_summary_table["ArchetypeSize"] = rebalanced_summary_table[
        "ArchetypeSize"
    ].replace([np.inf, -np.inf], np.nan)
    rebalanced_summary_table["ArchetypeSize"] = rebalanced_summary_table[
        "ArchetypeSize"
    ].fillna(1)

    # Fuel colours
    cmap_2 = {
        "Electricity": "#15A38C",
        "Electricity/Other": "#d8d2ca",
        "Gas": "#0000ff",
        "Other": "#F6B0C0",
    }

    chart = alt.Chart(rebalanced_summary_table)
    # Dots
    points = chart.mark_point(opacity=1, filled=True).encode(
        x=alt.X(
            "bill_change:Q",
            axis=alt.Axis(grid=True),
            title="Bill change with respect to bill under status quo levies and social support (£)",
            scale=alt.Scale(domain=[-850, 450]),
        ),
        y=alt.Y(
            "Name:N",
            axis=alt.Axis(grid=True, labelLimit=500),
            sort=None,
            title="Energy consumer archetype (Lowest (A) to highest (J) income)",
        ),
        size=alt.Size(
            "ArchetypeSize:Q", title="No. of households", scale=alt.Scale(range=[10, 1000])
        ),
        color=alt.Color(
            "main_heating_fuel:N",
            scale=alt.Scale(domain=list(cmap_2.keys()), range=list(cmap_2.values())),
            title="Main heating fuel",
        ),
        tooltip=[
            alt.Tooltip("Name:N", title="Archetype"),
            alt.Tooltip("bill_change:Q", title="Bill Change (£)", format=".2f"),
            alt.Tooltip("main_heating_fuel:N", title="Main Heating Fuel"),
            alt.Tooltip("ArchetypeSize:Q", title="Households", format=","),
        ],
    )
    # x=0 base line
    rule = chart.mark_rule(strokeDash=[2, 2]).encode(x=alt.datum(0))
    # Layer dots and line
    chart = alt.layer(points, rule).properties(width=chart_width, height=alt.Step(15))
    chart = chart.configure_axis(
        labelColor="black", titleColor="black"
    ).configure_legend(labelColor="black", titleColor="black")

    return chart


def make_all_archetypes_xy_chart(baseline_consumers: List, rebalanced_consumers: List, ofgem_archetypes_df: pd.DataFrame, chart_width=800):
    """
    Create XY scatter chart showing gas cost (x-axis) vs electricity cost (y-axis)
    for all archetypes, with before and after rebalancing points.
    """

    # Create data for all archetypes
    chart_data = []

    for baseline_consumer, rebalanced_consumer in zip(baseline_consumers, rebalanced_consumers):
        # Get archetype description from the dataframe
        archetype_info = ofgem_archetypes_df[
            ofgem_archetypes_df["AnnualConsumptionProfile"] == baseline_consumer.name
        ]

        archetype_desc = archetype_info["ArchetypeNickname"].iloc[0] if len(archetype_info) > 0 else "Description not available"
        archetype_size = archetype_info["ArchetypeSize"].iloc[0] if len(archetype_info) > 0 else 0
        heating_fuel = baseline_consumer.main_heating_fuel

        # Baseline point
        chart_data.append({
            'gas_cost': baseline_consumer.gas_bill,
            'electricity_cost': baseline_consumer.electricity_bill,
            'scenario': 'Baseline',
            'archetype': baseline_consumer.name,
            'description': archetype_desc,
            'heating_fuel': heating_fuel,
            'total_bill': baseline_consumer.combined_fuel_bill,
            'archetype_size': archetype_size
        })

        # Rebalanced point
        chart_data.append({
            'gas_cost': rebalanced_consumer.gas_bill,
            'electricity_cost': rebalanced_consumer.electricity_bill,
            'scenario': 'Rebalanced',
            'archetype': rebalanced_consumer.name,
            'description': archetype_desc,
            'heating_fuel': heating_fuel,
            'total_bill': rebalanced_consumer.combined_fuel_bill,
            'archetype_size': archetype_size
                })

    # Convert list to DataFrame after all data is collected
    chart_data = pd.DataFrame(chart_data)

    # Filter to show only gas consumers in the chart
    chart_data = chart_data[chart_data['heating_fuel'] == 'Gas'].copy()

    # Color schemes
    scenario_colors = {
        'Baseline': '#1f77b4',      # Blue
        'Rebalanced': '#ff7f0e'     # Orange
    }

    # Heating fuel colors (matching existing app pattern)
    fuel_colors = {
        "Gas": "#0000ff",
        "Electricity": "#15A38C",
        "Oil": "#F6B0C0",
        "Other": "#d8d2ca"
    }

    # Create bubble chart for all archetypes
    points = alt.Chart(chart_data).mark_circle(
        opacity=0.8,
        stroke='white',
        strokeWidth=1
    ).encode(
                x=alt.X(
            'gas_cost:Q',
            title='Total Gas Cost (£, inc VAT)',
            axis=alt.Axis(grid=True, format=',.0f'),
            scale=alt.Scale(domainMin=600)
        ),
        y=alt.Y(
            'electricity_cost:Q',
            title='Total Electricity Cost (£, inc VAT)',
            axis=alt.Axis(grid=True, format=',.0f'),
            scale=alt.Scale(domainMin=600)
        ),
        color=alt.Color(
            'scenario:N',
            title='Scenario',
            scale=alt.Scale(
                domain=list(scenario_colors.keys()),
                range=list(scenario_colors.values())
            )
        ),
        shape=alt.Shape(
            'heating_fuel:N',
            title='Heating Fuel',
            scale=alt.Scale(range=['circle', 'square', 'triangle-up', 'diamond'])
        ),
        size=alt.Size(
            'archetype_size:Q',
            title='Number of Households',
            scale=alt.Scale(range=[50, 400])  # Min 50px, max 400px bubble size
        ),
        tooltip=[
            alt.Tooltip('archetype:N', title='Archetype'),
            alt.Tooltip('description:N', title='Profile'),
            alt.Tooltip('scenario:N', title='Scenario'),
            alt.Tooltip('heating_fuel:N', title='Heating Fuel'),
            alt.Tooltip('gas_cost:Q', title='Gas Cost (£)', format=',.0f'),
            alt.Tooltip('electricity_cost:Q', title='Electricity Cost (£)', format=',.0f'),
            alt.Tooltip('total_bill:Q', title='Total Bill (£)', format=',.0f'),
            alt.Tooltip('archetype_size:Q', title='Households', format=',')
        ]
    )

    # Add connecting lines between baseline and rebalanced points for each archetype
    lines = alt.Chart(chart_data).mark_line(
        strokeWidth=1,
        strokeDash=[3, 3],
        opacity=0.4,
        color='gray'
    ).encode(
        x='gas_cost:Q',
        y='electricity_cost:Q',
        detail='archetype:N'  # Group by archetype to connect pairs
    )

    # Combine points and lines
    chart = alt.layer(lines, points).resolve_scale(
        color='independent'
    ).properties(
        width=chart_width,
        height=chart_width * 0.8,
        title='Energy Costs Before vs After Rebalancing - Gas Consumer Archetypes Only (Bubble Size = Households)'
    ).configure_axis(
        labelColor='black',
        titleColor='black'
    ).configure_legend(
        labelColor='black',
        titleColor='black'
    ).configure_title(
        color='black'
    )

    return chart


def create_archetype_reference_table(ofgem_archetypes_df: pd.DataFrame):
    """
    Create a reference table showing archetype codes with descriptions.
    Non-gas consumers are greyed out to indicate they're not shown in the chart.
    """
    # Filter for core archetypes (rows 1-24)
    ref_data = ofgem_archetypes_df.loc[1:24, [
        'AnnualConsumptionProfile',
        'ArchetypeNickname',
        'ArchetypeHeatingFuel',
        'ArchetypeSize',
        'NetAnnualHouseholdIncome'
    ]].copy()

    # Format for display
    ref_data = ref_data.rename(columns={
        'AnnualConsumptionProfile': 'Code',
        'ArchetypeNickname': 'Description',
        'ArchetypeHeatingFuel': 'Heating',
        'ArchetypeSize': 'Households',
        'NetAnnualHouseholdIncome': 'Income (£)'
    })

    # Format numbers nicely
    ref_data['Households'] = ref_data['Households'].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "")
    ref_data['Income (£)'] = ref_data['Income (£)'].apply(lambda x: f"£{x:,.0f}" if pd.notna(x) else "")

    # Add status column to indicate if shown in chart
    ref_data['Chart Status'] = ref_data['Heating'].apply(
        lambda x: '🔵 Shown' if x == 'Gas' else '⚫ Hidden'
    )

    return ref_data


def style_archetype_reference_table(df: pd.DataFrame):
    """
    Apply styling to the archetype reference table, greying out non-gas consumers.
    """
    def highlight_non_gas(row):
        if row['Heating'] != 'Gas':
            return ['color: #888888; font-style: italic'] * len(row)
        else:
            return [''] * len(row)

    return df.style.apply(highlight_non_gas, axis=1)


def get_data_sources_info():
    """
    Extract data source information from config and live data for transparency.
    Uses the asf_levies_model package config system.
    """
    from datetime import datetime
    import asf_levies_model

    try:
        # Use the package's built-in config system
        config = asf_levies_model.config

        if not config:
            return {
                'current_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
                'config_updated': 'Config not loaded',
                'days_since_update': 'Error',
                'ofgem_annex_4': 'Config not accessible',
                'ofgem_annex_9': 'Config not accessible',
                'validation_rates': {},
                'error': 'Package config not available'
            }

        # Get config file content to read update date from first line
        # Use the package's defined paths
        config_path = asf_levies_model.PROJECT_DIR / "asf_levies_model" / "config" / "base.yaml"
        with open(config_path, 'r') as f:
            config_content = f.read()

        # Extract update date from first line of config file
        first_line = config_content.split('\n')[0]
        if 'updated' in first_line:
            config_update_date = first_line.split('updated ')[1]
            # Calculate days since update
            try:
                config_date = datetime.strptime(config_update_date, '%d/%m/%Y %H:%M')
                days_since_update = (datetime.now() - config_date).days
            except:
                days_since_update = "Unknown"
        else:
            config_update_date = "Unknown"
            days_since_update = "Unknown"

        return {
            'current_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'config_updated': config_update_date,
            'days_since_update': days_since_update,
            'ofgem_annex_4': config['data_sources']['ofgem_annex_4'],
            'ofgem_annex_9': config['data_sources']['ofgem_annex_9'],
            'validation_rates': config.get('validation_rates', {})
        }
    except Exception as e:
        return {
            'current_date': datetime.now().strftime('%d/%m/%Y %H:%M'),
            'config_updated': 'Error reading config',
            'days_since_update': 'Error',
            'ofgem_annex_4': 'Error loading',
            'ofgem_annex_9': 'Error loading',
            'validation_rates': {},
            'error': str(e)
        }


def validate_app_rates_against_ofgem(baseline_electricity_tariff, baseline_gas_tariff, validation_rates):
    """
    Compare app-calculated rates with official Ofgem published rates from config.
    """

    # Instead of current calendar quarter, check what validation data is available
    # and use the most appropriate one for the loaded data period
    if not validation_rates:
        return None, "No validation rates configured in base.yaml"

    # For now, use the first available validation data (could be enhanced to match periods)
    available_periods = list(validation_rates.keys())
    if not available_periods:
        return None, "No validation periods configured"

    validation_key = available_periods[0]  # Use first available (e.g., "2025-Q4")
    validation_data = validation_rates[validation_key]

    # Calculate app rates (VAT included)
    app_elec_total_1_mwh_inc_vat = baseline_electricity_tariff.calculate_total_consumption(1, vat=True)
    app_elec_standing_inc_vat = baseline_electricity_tariff.calculate_nil_consumption() * 1.05
    app_elec_unit_rate = ((app_elec_total_1_mwh_inc_vat - app_elec_standing_inc_vat) / 1000) * 100
    app_elec_standing_daily = (app_elec_standing_inc_vat / 365) * 100

    app_gas_total_1_mwh_inc_vat = baseline_gas_tariff.calculate_total_consumption(1, vat=True)
    app_gas_standing_inc_vat = baseline_gas_tariff.calculate_nil_consumption() * 1.05
    app_gas_unit_rate = ((app_gas_total_1_mwh_inc_vat - app_gas_standing_inc_vat) / 1000) * 100
    app_gas_standing_daily = (app_gas_standing_inc_vat / 365) * 100

    # Get official rates from config
    ofgem_elec_standing = validation_data['electricity_standing_pence_per_day']
    ofgem_elec_unit = validation_data['electricity_unit_pence_per_kwh']
    ofgem_gas_standing = validation_data['gas_standing_pence_per_day']
    ofgem_gas_unit = validation_data['gas_unit_pence_per_kwh']

        # Round values for comparison (same as display)
    app_elec_standing_rounded = round(app_elec_standing_daily, 2)
    app_elec_unit_rounded = round(app_elec_unit_rate, 2)
    app_gas_standing_rounded = round(app_gas_standing_daily, 2)
    app_gas_unit_rounded = round(app_gas_unit_rate, 2)

    # Calculate percentage differences on rounded values
    elec_standing_pct = abs((app_elec_standing_rounded - ofgem_elec_standing) / ofgem_elec_standing * 100)
    elec_unit_pct = abs((app_elec_unit_rounded - ofgem_elec_unit) / ofgem_elec_unit * 100)
    gas_standing_pct = abs((app_gas_standing_rounded - ofgem_gas_standing) / ofgem_gas_standing * 100)
    gas_unit_pct = abs((app_gas_unit_rounded - ofgem_gas_unit) / ofgem_gas_unit * 100)

    # RAG status function
    def get_rag_status(pct_diff):
        if pct_diff < 0.25:
            return "🟢 Excellent"
        elif pct_diff < 1.0:
            return "🟡 Acceptable"
        else:
            return "🔴 Issues"

    # Create comparison table with RAG status
    comparison_data = pd.DataFrame([
        {
            'Fuel': 'Electricity',
            'Rate Type': 'Standing Charge (p/day)',
            'Official Ofgem': f"{ofgem_elec_standing:.2f}",
            'App Calculated': f"{app_elec_standing_rounded:.2f}",
            'Difference (p)': f"{app_elec_standing_rounded - ofgem_elec_standing:+.2f}",
            'Difference (%)': f"{elec_standing_pct:+.2f}%",
            'Status': get_rag_status(elec_standing_pct)
        },
        {
            'Fuel': 'Electricity',
            'Rate Type': 'Unit Rate (p/kWh)',
            'Official Ofgem': f"{ofgem_elec_unit:.2f}",
            'App Calculated': f"{app_elec_unit_rounded:.2f}",
            'Difference (p)': f"{app_elec_unit_rounded - ofgem_elec_unit:+.2f}",
            'Difference (%)': f"{elec_unit_pct:+.2f}%",
            'Status': get_rag_status(elec_unit_pct)
        },
        {
            'Fuel': 'Gas',
            'Rate Type': 'Standing Charge (p/day)',
            'Official Ofgem': f"{ofgem_gas_standing:.2f}",
            'App Calculated': f"{app_gas_standing_rounded:.2f}",
            'Difference (p)': f"{app_gas_standing_rounded - ofgem_gas_standing:+.2f}",
            'Difference (%)': f"{gas_standing_pct:+.2f}%",
            'Status': get_rag_status(gas_standing_pct)
        },
        {
            'Fuel': 'Gas',
            'Rate Type': 'Unit Rate (p/kWh)',
            'Official Ofgem': f"{ofgem_gas_unit:.2f}",
            'App Calculated': f"{app_gas_unit_rounded:.2f}",
            'Difference (p)': f"{app_gas_unit_rounded - ofgem_gas_unit:+.2f}",
            'Difference (%)': f"{gas_unit_pct:+.2f}%",
            'Status': get_rag_status(gas_unit_pct)
        }
    ])

    # Overall validation status
    max_pct_diff = max(elec_standing_pct, elec_unit_pct, gas_standing_pct, gas_unit_pct)

    validation_status = {
        'comparison_table': comparison_data,
        'max_percentage_diff': max_pct_diff,
        'validation_data': validation_data
    }

    return validation_status, None


def analyze_heat_pump_economics(baseline_consumers, rebalanced_consumers, baseline_elec_tariff, rebalanced_elec_tariff, baseline_gas_tariff, rebalanced_gas_tariff):
    """
    Analyze heat pump vs gas boiler economics for gas consumer archetypes.
    Based on analysis pattern from ro_fit_rate_breakdown.py.
    """

    # Heat pump assumptions
    BOILER_EFFICIENCY = 0.8  # 80% efficient gas boiler
    HEAT_PUMP_SPF = 3.0      # Seasonal Performance Factor

    # Calculate unit cost ratios
    baseline_elec_rate = baseline_elec_tariff.calculate_variable_consumption(1) * 1.05 / 10  # p/kWh inc VAT
    baseline_gas_rate = baseline_gas_tariff.calculate_variable_consumption(1) * 1.05 / 10
    rebalanced_elec_rate = rebalanced_elec_tariff.calculate_variable_consumption(1) * 1.05 / 10
    rebalanced_gas_rate = rebalanced_gas_tariff.calculate_variable_consumption(1) * 1.05 / 10

    baseline_ratio = baseline_elec_rate / baseline_gas_rate
    rebalanced_ratio = rebalanced_elec_rate / rebalanced_gas_rate

    # Filter for gas consumers only
    baseline_gas_consumers = [c for c in baseline_consumers if c.main_heating_fuel == 'Gas']
    rebalanced_gas_consumers = [c for c in rebalanced_consumers if c.main_heating_fuel == 'Gas']

    analysis_data = []

    for baseline_consumer, rebalanced_consumer in zip(baseline_gas_consumers, rebalanced_gas_consumers):
        # Heat pump electricity demand calculation
        gas_consumption = baseline_consumer.gas_consumption
        hp_elec_demand = gas_consumption * BOILER_EFFICIENCY / HEAT_PUMP_SPF

        # Baseline scenario costs
        baseline_boiler_cost = baseline_consumer.gas_bill
        baseline_hp_cost = baseline_elec_tariff.calculate_total_consumption(hp_elec_demand, vat=True)
        baseline_saving = baseline_boiler_cost - baseline_hp_cost

        # Rebalanced scenario costs
        rebalanced_boiler_cost = rebalanced_consumer.gas_bill
        rebalanced_hp_cost = rebalanced_elec_tariff.calculate_total_consumption(hp_elec_demand, vat=True)
        rebalanced_saving = rebalanced_boiler_cost - rebalanced_hp_cost

        # Improvement from rebalancing
        improvement = rebalanced_saving - baseline_saving

        analysis_data.append({
            'archetype': baseline_consumer.name,
            'gas_consumption_mwh': gas_consumption,
            'hp_elec_demand_mwh': hp_elec_demand,
            'baseline_boiler_cost': baseline_boiler_cost,
            'baseline_hp_cost': baseline_hp_cost,
            'baseline_saving': baseline_saving,
            'rebalanced_boiler_cost': rebalanced_boiler_cost,
            'rebalanced_hp_cost': rebalanced_hp_cost,
            'rebalanced_saving': rebalanced_saving,
            'improvement': improvement,
            'baseline_competitive': baseline_saving > 0,
            'rebalanced_competitive': rebalanced_saving > 0
        })

    analysis_df = pd.DataFrame(analysis_data)

    # Summary statistics
    baseline_winners = sum(analysis_df['baseline_competitive'])
    rebalanced_winners = sum(analysis_df['rebalanced_competitive'])
    avg_improvement = analysis_df['improvement'].mean()

    return {
        'analysis_data': analysis_df,
        'baseline_ratio': baseline_ratio,
        'rebalanced_ratio': rebalanced_ratio,
        'heat_pump_spf': HEAT_PUMP_SPF,
        'boiler_efficiency': BOILER_EFFICIENCY,
        'baseline_winners': baseline_winners,
        'rebalanced_winners': rebalanced_winners,
        'avg_improvement': avg_improvement,
        'total_gas_archetypes': len(baseline_gas_consumers)
    }
