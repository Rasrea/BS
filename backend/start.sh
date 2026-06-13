#!/bin/bash
source /home/sd317/miniconda3_new/etc/profile.d/conda.sh
conda activate torchtest
cd /home/sd317/cad/backend
nohup python main.py > /tmp/cad_backend.log 2>&1 &
echo "PID: $!"
