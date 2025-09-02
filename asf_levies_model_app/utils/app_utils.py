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
        for row in range(0, 24)
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
        for row in range(0, 24)
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
        for row in range(0, 24)
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

    # Create scatter plot for all archetypes
    points = alt.Chart(chart_data).mark_circle(
        size=120,
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
        title='Energy Costs Before vs After Rebalancing - All Consumer Archetypes'
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

    return ref_data
