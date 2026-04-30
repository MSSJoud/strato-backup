#!/usr/bin/env bash
set -euo pipefail

STACK_TYPE="${1:-sbas}"
PROJECT_DIR="/mnt/data/sbas_vs_ps_test_bologna"
CSV_FILE="${PROJECT_DIR}/configs/${STACK_TYPE}/valid_pairs.csv"
LOG_DIR="${PROJECT_DIR}/logs"
ISCE2_PLAYBOOK_DIR="/home/ubuntu/work/isce2-playbook"
REQUIRE_DENSE="${REQUIRE_DENSE:-1}"

if [[ "${STACK_TYPE}" != "sbas" && "${STACK_TYPE}" != "ps" ]]; then
  echo "Usage: $0 [sbas|ps]"
  exit 1
fi

if [[ ! -f "${CSV_FILE}" ]]; then
  echo "ERROR: missing CSV file: ${CSV_FILE}"
  exit 1
fi

mkdir -p "${LOG_DIR}"
RUN_TS="$(date +%Y%m%d_%H%M%S)"
RUN_LOG="${LOG_DIR}/${STACK_TYPE}_batch_${RUN_TS}.log"
ln -sfn "${RUN_LOG}" "${LOG_DIR}/${STACK_TYPE}_latest.log"

exec > >(tee -a "${RUN_LOG}") 2>&1

echo "============================================================"
echo "ISCE2 ${STACK_TYPE^^} batch started: $(date)"
echo "CSV: ${CSV_FILE}"
echo "Log: ${RUN_LOG}"
echo "============================================================"

TOTAL=$(($(wc -l < "${CSV_FILE}") - 1))
COUNT=0
SUCCESS=0
FAILED=0
SKIPPED=0

while IFS=',' read -r master slave master_date slave_date master_path slave_path xml_file; do
  if [[ "${master}" == "master" ]]; then
    continue
  fi

  COUNT=$((COUNT + 1))
  pair_dir="$(dirname "${xml_file}")"

  if [[ -f "${pair_dir}/merged/filt_topophase.unw.geo" ]]; then
    if [[ "${REQUIRE_DENSE}" == "1" ]]; then
      dense_count=$(find "${pair_dir}" -type f | grep -i dense | wc -l || true)
      if [[ "${dense_count}" -gt 0 ]]; then
        echo "[$COUNT/$TOTAL] SKIP ${master_date}_${slave_date} (unw.geo + dense outputs present)"
        SKIPPED=$((SKIPPED + 1))
        continue
      fi
      echo "[$COUNT/$TOTAL] RERUN ${master_date}_${slave_date} (unw.geo present but dense outputs missing)"
    else
      echo "[$COUNT/$TOTAL] SKIP ${master_date}_${slave_date} (already has merged/filt_topophase.unw.geo)"
      SKIPPED=$((SKIPPED + 1))
      continue
    fi
  fi

  echo "[$COUNT/$TOTAL] START ${master_date}_${slave_date}"
  echo "            XML: ${xml_file}"
  echo "            WORKDIR: ${pair_dir}"

  set +e
  (
    cd "${ISCE2_PLAYBOOK_DIR}"
    docker compose run --rm --workdir "${pair_dir}" isce2-insar topsApp.py "${xml_file}" < /dev/null
  )
  EXIT_CODE=$?
  set -e

  if [[ ${EXIT_CODE} -eq 0 ]]; then
    SUCCESS=$((SUCCESS + 1))
    echo "[$COUNT/$TOTAL] DONE ${master_date}_${slave_date}"
  else
    FAILED=$((FAILED + 1))
    echo "[$COUNT/$TOTAL] FAIL ${master_date}_${slave_date} (exit=${EXIT_CODE})"
  fi

  echo "------------------------------------------------------------"
done < "${CSV_FILE}"

echo "============================================================"
echo "ISCE2 ${STACK_TYPE^^} batch finished: $(date)"
echo "Total: ${TOTAL}, Success: ${SUCCESS}, Failed: ${FAILED}, Skipped: ${SKIPPED}"
echo "Log: ${RUN_LOG}"
echo "============================================================"
