#!/bin/bash

SCRIPT_PATH=$(dirname "$(realpath "$0")")
cd "$SCRIPT_PATH"

echo
echo "Opening report in LibreOffice..."

libreoffice ../output/combined_report.ods >/dev/null 2>&1 &
