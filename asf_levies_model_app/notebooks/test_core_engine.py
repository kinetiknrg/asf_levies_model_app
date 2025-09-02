#!/usr/bin/env python3
"""
CONSTITUTIONAL DIAGNOSTIC: Test core asf_levies_model engine independently
to isolate whether crash is in core computation vs Streamlit interface
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from asf_levies_model_app.utils.app_utils import (
    instantiate_levies,
    get_approach_weights,
)
import asf_levies_model.getters.load_data as data
import copy
from datetime import datetime

def test_core_rebalancing():
    """Test the exact rebalancing computation that crashes in Streamlit"""
    print("=== TESTING CORE ENGINE INDEPENDENTLY ===")
    print(f"Start time: {datetime.now()}")

    try:
        # 1. Load levies (same as Streamlit app)
        print("\n1. Loading levies...")
        fileobject = data.download_annex_4(as_fileobject=True)
        levies = instantiate_levies(fileobject)
        fileobject.close()
        print(f"   SUCCESS: Loaded {len(levies)} levies")

        # 2. Test "Current" approach (works in Streamlit)
        print("\n2. Testing 'Current' approach...")
        current_weights = get_approach_weights(copy.deepcopy(levies), "Current")
        current_rebalanced = levies.rebalance_levies(current_weights, scenario_name="Current")
        print(f"   SUCCESS: Current rebalancing completed")

        # 3. Test "Rebalance all levies" approach (crashes in Streamlit)
        print("\n3. Testing 'Rebalance all levies on electricity to gas' approach...")
        rebalance_weights = get_approach_weights(copy.deepcopy(levies), "Rebalance all levies on electricity to gas")
        rebalance_rebalanced = levies.rebalance_levies(rebalance_weights, scenario_name="Rebalanced")
        print(f"   SUCCESS: Rebalancing completed")

        # 4. Test tariff operations
        print("\n4. Testing tariff operations...")
        fileobject = data.download_annex_9(as_fileobject=True)
        from asf_levies_model_app.utils.app_utils import instantiate_tariffs, update_electricity_tariff_policy_cost, update_gas_tariff_policy_cost

        tariffs = instantiate_tariffs(fileobject_annex_9=fileobject, payment_method="Other Payment")
        fileobject.close()

        elec_tariff = update_electricity_tariff_policy_cost(tariffs["electricity"], rebalance_rebalanced)
        gas_tariff = update_gas_tariff_policy_cost(tariffs["gas"], rebalance_rebalanced)
        print(f"   SUCCESS: Tariff operations completed")

        # 5. Test consumer creation
        print("\n5. Testing consumer creation...")
        from asf_levies_model_app.utils.app_utils import instantiate_archetype_consumers

        ofgem_archetypes_df = data.ofgem_archetypes_data()
        consumers = instantiate_archetype_consumers(ofgem_archetypes_df, gas_tariff, elec_tariff)
        print(f"   SUCCESS: Created {len(consumers)} consumers")

        # 6. Test summary operations
        print("\n6. Testing summary operations...")
        from asf_levies_model_app.utils.app_utils import get_tidy_summary, tidy_to_pivot_summary

        tidy_summary = get_tidy_summary(consumers, "Test")
        pivot_summary = tidy_to_pivot_summary(tidy_summary)
        print(f"   SUCCESS: Summary operations completed - shape {pivot_summary.shape}")

        print(f"\n=== COMPLETE SUCCESS: All core operations work independently ===")
        print(f"End time: {datetime.now()}")
        return True

    except Exception as e:
        print(f"\n=== CORE ENGINE ERROR ===")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"End time: {datetime.now()}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_core_rebalancing()
    if success:
        print("\n🎯 DIAGNOSIS: Core engine works perfectly")
        print("   Crash must be in Streamlit interface or framework")
    else:
        print("\n🎯 DIAGNOSIS: Core engine has bugs")
        print("   Fix core engine before addressing Streamlit issues")


