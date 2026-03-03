# pnio-validator

PNIO Validator is a PROFINET IO device validation tool that performs strict controller-level checks. It validates GSDML consistency, executes acyclic PNIO CM Read Implicit requests (e.g., 0xAFF0, 0xF841), and detects interoperability issues (I&M, slot/subslot, API, fragmentation, timeouts).

## Goals
- Discover devices via DCP (name, IP, MAC, vendor/device IDs)
- Run strict acyclic checks similar to Heidenhain IO-Controller behavior
- Validate key records:
  - 0xAFF0 (RealIdentificationData / I&M0)
  - 0xF841 (PDRRealData, large records ~24kB)
- Compare **Expected (GSDML)** vs **Real (device)** structure and report diffs
- Generate reproducible reports (JSON/HTML) for suppliers and commissioning

## Status
🚧 Work in progress (MVP: scan + Read Implicit 0xAFF0/0xF841 + timings)

## Planned CLI
```bash
pnio-validator scan --iface "Ethernet"
pnio-validator validate --device "em31-new" --mode heidenhain --timeout-ms 3000
pnio-validator report --out report.json