# Extreme Heat Event Risk Model

## Overview
This agent-based model simulates how residents respond during extreme heat events in Hennepin County, MN. The model predicts whether individuals will stay home or move to cooling centers based on factors including surface temperature, age of household occupants, median household income, air conditioning access, and distance to cooling centers.

## Features
- **Spatially-explicit simulation**: Uses land surface temperature raster data
    - Can use static, county wide temperature value
- **Agent-based decision making**: Individuals make choices based on multiple factors
- **Ensemble approach**: Runs the model multiple times for robust results
- **Cooling center choice**: Predicts which cooling center a resident is likely to visit if decision is to move
- **GIS integration**: Imports from and exports to PostGIS database, exports shapefiles for use in GIS software

## Requirements
- Python 3.9+
- Dependencies: numpy, pandas, geopandas, matplotlib, seaborn, rasterio, psycopg2, sqlalchemy

## Usage
1. Configure database connection parameters in the notebook
2. Run the model using the Jupyter notebook: `Model_final.ipynb`
3. The model will:
   - Run 5 simulations with the same input data
   - Calculate average probability values across runs
   - Determine final decisions using majority voting
   - Generate visualizations of results
   - Export results to a PostGIS database

## Input Data
- Land surface temperature raster
- Hennepin County parcel dataset
- U.S. Census demographic data
- Market-based air conditioning data at census block level

## Output
- GeoDataFrame with averaged probabilities and decisions at parcel level
- Visualization of movement probability
- Visualization of cooling center choices
- Visualization of decision stability across runs
- PostGIS table with ensemble results

## Model Structure
- `src/`: Source code directory
  - `base.py`: Base classes for model entities
  - `event.py`: HeatEvent class and simulation controller
  - `utils.py`: Utility functions
