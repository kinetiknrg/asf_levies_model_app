import sys
import pandas as pd

# Add the model directory to the path to import its modules
sys.path.append("../asf_levies_model")
from asf_levies_model.getters import load_data as data
from asf_levies_model.consumers import Consumer
from asf_levies_model.tariffs import ElectricityOtherPayment, GasOtherPayment
from asf_levies_model_app.utils.app_utils import (
    instantiate_levies,
    instantiate_tariffs,
    update_electricity_tariff_policy_cost,
    update_gas_tariff_policy_cost,
    instantiate_archetype_consumers,
    get_tidy_summary,
    tidy_to_pivot_summary,
)


def debug_chart_data_pipeline():
    """
    Diagnose the final DataFrame passed to the chart renderer by replicating
    the full data pipeline from the main Streamlit script.
    """
    print("--- Starting Chart Data Pipeline Diagnosis ---")
    try:
        # Replicate the full data pipeline from run_rebalancing_scenario.py

        # 1. Load levies and tariffs
        fileobject_annex_4 = data.download_annex_4(as_fileobject=True)
        levies = instantiate_levies(fileobject_annex_4)
        fileobject_annex_4.close()

        fileobject_annex_9 = data.download_annex_9(as_fileobject=True)
        baseline_tariffs = instantiate_tariffs(fileobject_annex_9=fileobject_annex_9)
        fileobject_annex_9.close()

        baseline_electricity_tariff = update_electricity_tariff_policy_cost(
            baseline_tariffs["electricity"], levies
        )
        baseline_gas_tariff = update_gas_tariff_policy_cost(baseline_tariffs["gas"], levies)

        # 2. Load archetype data and create baseline consumers and summary
        ofgem_archetypes_df = data.ofgem_archetypes_data()

        baseline_consumers = instantiate_archetype_consumers(
            ofgem_archetypes_df, baseline_gas_tariff, baseline_electricity_tariff
        )

        baseline_summary_table = tidy_to_pivot_summary(
            get_tidy_summary(baseline_consumers, "Baseline")
        )

        # Assume a 'Current' scenario for the rebalanced table for this test
        rebalanced_summary_table = baseline_summary_table.copy()

        # 3. Calculate the bill_change column EXACTLY as in the script
        rebalanced_summary_table["bill_change"] = (
            rebalanced_summary_table["combined_fuel_bill"]
            - baseline_summary_table["combined_fuel_bill"]
        )

        # 4. Add ArchetypeSize EXACTLY as in the script
        archetype_sizes = data.ofgem_archetypes_data().loc[1:24][
            ["AnnualConsumptionProfile", "ArchetypeSize"]
        ]
        archetype_sizes = archetype_sizes.rename(
            columns={"AnnualConsumptionProfile": "Name"}
        )
        final_table_for_chart = rebalanced_summary_table.merge(
            archetype_sizes, on="Name", how="left"
        )

        # 5. Print the info of the final DataFrame
        print("\\n--- FINAL DATAFRAME SCHEMA FOR CHART ---")
        final_table_for_chart.info()

    except Exception as e:
        import traceback
        print(f"An error occurred: {e}")
        traceback.print_exc()
    finally:
        print("\\n--- End of a deliberate diagnostic process ---")


if __name__ == "__main__":
    debug_chart_data_pipeline()


