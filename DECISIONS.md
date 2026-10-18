# DECISIONS — BobTV

Settled calls are recorded inline in `docs/status.md`. Highlights:
- Stdlib HTTP servers, loopback by default; non-loopback needs `BOBTV_PASSWORD` (9/21).
- TV wake only after the VPN region is verified; CEC failures never block a launch (9/28).
- Remote power key toggles the TV, never the computer (9/28).
- Home closes the show; one show at a time (9/28).
