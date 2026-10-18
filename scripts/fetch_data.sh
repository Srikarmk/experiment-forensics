#!/usr/bin/env bash
# Download the raw data into data/raw/ and verify checksums.
set -euo pipefail

cd "$(dirname "$0")/.."
mkdir -p data/raw

sha256() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | cut -d' ' -f1
  else
    shasum -a 256 "$1" | cut -d' ' -f1
  fi
}

fetch() {
  local url="$1" out="data/raw/$2" want="$3"
  if [[ -f "$out" && "$(sha256 "$out")" == "$want" ]]; then
    echo "ok (already present): $out"
    return
  fi
  echo "downloading $out"
  curl -fL --retry 3 -o "$out.part" "$url"
  local got
  got="$(sha256 "$out.part")"
  if [[ "$got" != "$want" ]]; then
    echo "checksum mismatch for $out: expected $want, got $got" >&2
    rm -f "$out.part"
    exit 1
  fi
  mv "$out.part" "$out"
  echo "ok: $out"
}

# Upworthy Research Archive (OSF), exploratory and confirmatory releases of 03.12.2020.
fetch "https://osf.io/download/3vqmp/" \
  "upworthy-archive-exploratory-packages-03.12.2020.csv" \
  "8368313b060f4015a0c6fb34e6d788163cee29554144aba9390b14922eb9d8ce"
fetch "https://osf.io/download/vy8mj/" \
  "upworthy-archive-confirmatory-packages-03.12.2020.csv" \
  "b2a88288c88f2b67d40413c9bdbebe79a1c0b5d9a9354180549f59f3bfff685f"

# Hillstrom MineThatData e-mail test (2008).
fetch "http://www.minethatdata.com/Kevin_Hillstrom_MineThatData_E-MailAnalytics_DataMiningChallenge_2008.03.20.csv" \
  "hillstrom.csv" \
  "0e5893329d8b93cefecc571777672028290ab69865718020c78c7284f291aece"
