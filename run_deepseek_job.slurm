#!/bin/bash
#SBATCH --job-name=DEEPSEEK
#SBATCH --output=/work/barcomb_lab/Mahdi/COSETO/logs/job_output_%j.log
#SBATCH --error=/work/barcomb_lab/Mahdi/COSETO/logs/job_error_%j.log
#SBATCH --time=1-00:00:00  # 7 days
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem=16G  # Adjust memory as needed
#SBATCH --partition=cpu2023

####### Set environment variables ###############
module load python/3.12.5

# Set up virtual environment
VENV_DIR="/work/barcomb_lab/Mahdi/COSETO/senv"
if [ ! -d "$VENV_DIR" ]; then
    python -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip
    pip install -r /work/barcomb_lab/Mahdi/COSETO/requirements.txt
else
    source "$VENV_DIR/bin/activate"
fi

####### Cleanup Old Logs #########################
LOG_DIR="/work/barcomb_lab/Mahdi/COSETO/logs"

# Delete logs older than 7 days
find "$LOG_DIR" -type f -name "job_*.log" -mtime +7 -exec rm {} \;
find "$LOG_DIR" -type f -name "job_error_*.log" -mtime +7 -exec rm {} \;

echo "✅ Old logs cleaned up successfully!"

####### Run your script #########################
python /work/barcomb_lab/Mahdi/COSETO/01_deepseek.py
