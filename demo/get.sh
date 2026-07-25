#!/bin/sh
# FSME Logic - the secure_plant demo, fetched and run.
#
# You are about to pipe a script from the internet into a shell, which you
# should be suspicious of. It is 30 lines and you can read all of it above
# before you run it. All it does is:
#   1. check you have stratum installed
#   2. download two .st source files into ./stratum-demo
#   3. run one of them
# Nothing else. No sudo, no install, no writes outside this folder.

set -e
BASE="https://fsmelogic.ca/demo"
DIR="stratum-demo"

if ! command -v stratum >/dev/null 2>&1; then
  echo "stratum is not installed. Get it first:"
  echo "    pip install stratum-lang"
  exit 1
fi

echo "Fetching the demo into ./$DIR ..."
mkdir -p "$DIR/showcase"
curl -sSL "$BASE/secure_plant.st"           -o "$DIR/secure_plant.st"
curl -sSL "$BASE/showcase/dosing_vendor.st" -o "$DIR/showcase/dosing_vendor.st"

echo ""
echo "Running. Watch for three things:"
echo "  1. the vendor module runs under an empty capability ceiling"
echo "  2. sabotage inside the valid range gets caught anyway"
echo "  3. the plant quarantines itself and drops the flood"
echo ""

cd "$DIR"
stratum --grant console,entropic,randomness,self_heal,concurrency secure_plant.st

echo ""
echo "The source you just ran is in ./$DIR. Read it."
echo "What this proves, and how to measure it yourself: https://fsmelogic.ca/lab.html"
