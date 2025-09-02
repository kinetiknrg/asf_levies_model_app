import sys
import pandas as pd

# Add the model directory to the path to import its modules
sys.path.append("../asf_levies_model")
from asf_levies_model.getters import load_data as data
from asf_levies_model_app.utils.app_utils import (
    instantiate_levies,
    get_approach_weights,
)

def debug_mutation_in_cached_object():
    """
    Diagnose if the cached 'levies' object is mutated in-place.
    """
    print("--- Starting Mutation Diagnosis ---")
    try:
        # 1. Simulate loading the cached levies object
        fileobject = data.download_annex_4(as_fileobject=True)
        levies = instantiate_levies(fileobject)
        fileobject.close()

        # 2. Select a specific levy and log its "before" state
        # The Renewables Obligation (RO) is a good candidate as it's 100% on electricity
        ro_levy = next((levy for levy in levies if levy.short_name == 'ro'), None)
        if not ro_levy:
            print("ERROR: Could not find the 'RO' levy for the test.")
            return

        print(f"\nBEFORE mutation:")
        print(f"  RO levy object ID: {id(ro_levy)}")
        print(f"  RO levy electricity_weight: {ro_levy.electricity_weight}")
        print(f"  RO levy gas_weight: {ro_levy.gas_weight}")

        # 3. Simulate a user selecting a scenario that will cause mutation
        approach = "Rebalance all levies on electricity to gas"
        rebalancing_weights = get_approach_weights(levies, approach)

        # 4. Call the function suspected of mutating the object
        rebalanced_levies = levies.rebalance_levies(rebalancing_weights)

        # 5. Log the "after" state of the ORIGINAL levy object
        print(f"\nAFTER mutation:")
        print(f"  RO levy object ID: {id(ro_levy)}")
        print(f"  RO levy electricity_weight: {ro_levy.electricity_weight}")
        print(f"  RO levy gas_weight: {ro_levy.gas_weight}")

        # 6. Conclusive check
        print("\n--- Conclusion ---")
        if ro_levy.electricity_weight == 0.0:
            print("CONFIRMED: The original 'levies' object was mutated in-place.")
        else:
            print("NOT CONFIRMED: The original 'levies' object was not mutated.")

    except Exception as e:
        import traceback
        print(f"An error occurred: {e}")
        traceback.print_exc()
    finally:
        print("\n--- End of a deliberate diagnostic process ---")

if __name__ == "__main__":
    debug_mutation_in_cached_object()


