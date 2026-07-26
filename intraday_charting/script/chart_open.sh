#!/bin/bash

# 1. Target files and directories
CHART_DIR="/home/dev/stock/intraday_charting/charts"

# 2. Open the charts directory with a fast viewer instead of spamming windows
echo "Opening charts gallery..."
gthumb "$CHART_DIR" &

# 3. Add a pause
read -n 1 -s -r -p "Press any key to close..."

