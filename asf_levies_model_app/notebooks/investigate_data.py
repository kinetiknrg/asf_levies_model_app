import sys
import pandas as pd
# Add the model directory to the path to import its modules
sys.path.append("../asf_levies_model")
from asf_levies_model.getters import load_data as data

def investigate_archetype_data():
    """
    Loads the Ofgem archetype data and prints its shape and key column values
    to diagnose the data structure.
    """
    print("--- Loading Ofgem archetype data ---")
    try:
        df = data.ofgem_archetypes_data()
        print(f"Successfully loaded DataFrame. Shape: {df.shape}")
        print("\\n--- Head of 'AnnualConsumptionProfile' column ---")
        print(df["AnnualConsumptionProfile"].head())
        print("\\n--- Tail of 'AnnualConsumptionProfile' column ---")
        print(df["AnnualConsumptionProfile"].tail())
        print("\\n--- End of investigation ---")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    investigate_archetype_data()
