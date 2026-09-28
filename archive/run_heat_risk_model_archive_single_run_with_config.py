#!/usr/bin/env python3
"""
Simple runner script for the Heat Risk ABM Model
Usage: python run_model.py
"""

import os
import sys
from pathlib import Path

# Add current directory to path
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Import the main model runner
from heat_risk_model import HeatRiskModelRunner

def main():
    """Run the heat risk model with default configuration"""
    
    print("🌡️  Hennepin County Heat Risk ABM Model")
    print("=" * 50)
    
    # Check for configuration file
    config_path = current_dir / "config" / "config.yaml"
    
    if not config_path.exists():
        print(f"❌ Configuration file not found: {config_path}")
        print("\n📝 Please create the configuration file first:")
        print("   1. Create a 'config' folder in your project directory")
        print("   2. Save the config.yaml file in that folder")
        print("   3. Update the paths in config.yaml to match your setup")
        return
    
    try:
        # Create and run the model
        print(f"📋 Loading configuration from: {config_path}")
        model_runner = HeatRiskModelRunner(str(config_path))
        
        print("\n🚀 Starting heat risk model analysis...")
        model_runner.run_complete_analysis()
        
        print("\n✅ Analysis completed successfully!")
        
    except KeyboardInterrupt:
        print("\n⏸️  Analysis interrupted by user")
    except Exception as e:
        print(f"\n❌ Error running analysis: {e}")
        print("\n🔍 For detailed error information:")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()