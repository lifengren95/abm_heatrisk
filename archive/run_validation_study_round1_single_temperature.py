#!/usr/bin/env python3
"""
Simple runner script for the Heat Risk Validation Study
Usage: python run_validation_study.py
"""

import os
import sys
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Import the validation model runner
from heat_risk_validation_model import ValidationModelRunner

def main():
    """Run the heat risk validation study"""
    
    print("🌡️  Hennepin County Heat Risk Validation Study")
    print("=" * 60)
    print("🎯 Tracking visits to validated cooling centers")
    print("🌡️  Temperature levels: 94.73°F and 82.56°F")
    print("=" * 60)
    
    # Check for configuration file in config folder
    config_path = current_dir / "config" / "config_validation.yaml"
    
    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        print("\n📝 Please ensure config_validation.yaml exists in your config directory")
        return
    
    try:
        print(f"📋 Loading configuration from: {config_path}")
        
        # Create and run the validation model
        print("\n🚀 Starting heat risk validation study...")
        model_runner = ValidationModelRunner(str(config_path))
        
        # Run the complete validation study
        visit_summary = model_runner.run_complete_validation_study()
        
        if visit_summary is not None:
            print("\n✅ Validation study completed successfully!")
            print(f"📊 Generated visit summary with {len(visit_summary)} records")
            print("\n📁 Check the following files:")
            print(f"   - Validation output: {model_runner.config['paths']['validation_output_dir']}")
            print(f"   - Visit summary: {model_runner.config['output']['cooling_center_visits']}")
        else:
            print("\n❌ Validation study failed - no results generated")
            print("Please check the error messages above for details")
        
    except KeyboardInterrupt:
        print("\n⏸️  Validation study interrupted by user")
    except Exception as e:
        print(f"\n❌ Error running validation study: {e}")
        print("\n🔍 For detailed error information:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()