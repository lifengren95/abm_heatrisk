# Local configuration

Set PGHOST, PGPORT, PGDATABASE, PGUSER, and PGPASSWORD in your process environment before running Python scripts or notebooks. Some SQLAlchemy export scripts use DATABASE_URL instead; supply a full connection URL with URL-encoded credentials. Set SYNOPTIC_API_TOKEN for the weather API notebook. `.env.example` lists the settings; neither it nor a local `.env` is loaded automatically. Do not put actual settings in tracked files.

Paths use relative data/, output/, and results/ locations. Run scripts from the repository root unless a script explicitly uses its own directory. Older scripts may still need dataset-specific path adjustments; local datasets are not included. HEAT_OUTPUT_DIR overrides the export folder where supported.

For Slurm, create logs/ before submission, set HEAT_VENV to your virtual environment directory, and submit from the repository root. Pass your allocation and email on the command line, for example: `sbatch --account=YOUR_ALLOCATION --mail-user=you@example.org slurm_submit_heat_risk_model_07232025.slurm`. Slurm directives do not expand shell environment variables.

Archived runners now update database settings in memory instead of writing passwords to src/utils.py. Configure all PG variables before importing the model.

Previously committed real credentials should be rotated in the original services. This copy does not revoke them or remove the old repository. Set a GitHub noreply commit email locally before future commits if desired. Clear notebook outputs again before publishing future changes.
