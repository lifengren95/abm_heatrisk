#!/usr/bin/env python3
import jupytext
from pathlib import Path

# Folder containing notebooks
folder_path = r"~\hennepin\code\hennepin_heat_abm\QAQC"

# Find all .ipynb files and convert to .qmd
folder = Path(folder_path)
for nb_file in folder.glob("*.ipynb"):
    qmd_file = nb_file.with_suffix('.qmd')
    
    notebook = jupytext.read(nb_file)
    jupytext.write(notebook, qmd_file, fmt='qmd')
    
    print(f"Converted: {nb_file.name} → {qmd_file.name}")

print("Done!")