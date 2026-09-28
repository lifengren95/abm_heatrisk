# HeatRisk_ABM_Model

Agent-based model (ABM) for simulating heat risk and cooling center utilization in Hennepin County during extreme heat events (Summer 2025).

This codebase preserves the original `src` scripts while implementing new functionality through separate `run_` scripts, ensuring backward compatibility and modularity.

## Project Structure

- **`src/`** - Core model classes and utilities including the HeatEvent controller and Parcel agent implementation.
- **`oneoff/`** - Data processing and organization scripts for MSI results, including file reorganization and summary generation.
- **`docs/`** - Documentation files including model notes and MSI execution guides in Quarto markdown format.
- **`notebooks/`** - Jupyter notebooks for interactive model execution, data cleaning, and exploratory analysis.
- **`archive/`** - Previous versions of model scripts and deprecated code preserved for reference and reproducibility.
- **`validate/`** - Validation and analysis scripts including R code for statistical analysis of model results against real-world data.

## How to Run the Model

### Local Execution

For the most recent model (Summer 2025), execute: [`run_heat_risk_model_new_ac_data_parallel.py`](run_heat_risk_model_new_ac_data_parallel.py)

### MSI Cluster Execution

Submit the model to Minnesota Supercomputing Institute (MSI) using the `slurm_submit_heat_risk_model_07232025.slurm` script, which executes `run_heat_risk_model_msi_07232025.py` on the `msi_small` partition. Each simulation date runs 1,000 iterations and requires approximately 48 hours to complete (including queue time).

For detailed instructions, see: [`docs/running_on_msi.qmd`](docs/running_on_msi.qmd)

## Requirements

**Local Environment:**
```bash
mamba install geopandas numpy pandas matplotlib seaborn scipy scikit-learn rasterio shapely pyproj psycopg2 tqdm pillow jupyter jupyterlab ipython ipykernel ipywidgets notebook pandoc sqlalchemy postgresql
```

**MSI Environment:**
- See [`docs/running_on_msi.qmd`](docs/running_on_msi.qmd) for detailed setup instructions
- Complete package list: [`requirements_msi.txt`](requirements_msi.txt)

## Legacy Model

The previous model version can be executed by rendering: [`Model_final_LR_edit_adapt_from_ipynb.qmd`](Model_final_LR_edit_adapt_from_ipynb.qmd)

## Model Documentation

For comprehensive information about model functionality and features, refer to: [`docs/abm_model_2025Summer_notes.qmd`](docs/abm_model_2025Summer_notes.qmd)

This model extends the original implementation described in [`README_old.md`](README_old.md).



## Private configuration

See [PRIVACY_SETUP.md](PRIVACY_SETUP.md) before running the model. Credentials are supplied through environment variables; local dataset paths must be configured for your machine.
