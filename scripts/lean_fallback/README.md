# TL-001A LEAN synthetic historical probe

These TideLab-authored files use only three synthetic hourly values. They submit no orders and require no QuantConnect account, API token, or market-data download. They exercise the open-source LEAN Launcher directly, not the paid LEAN CLI.

Reproduce in an **isolated** LEAN source checkout at commit [`88bce0fc6fe282378ee73c54cef1090d0d7a73ee`](https://github.com/QuantConnect/Lean/commit/88bce0fc6fe282378ee73c54cef1090d0d7a73ee) with .NET SDK 10:

1. Copy `TideLabSyntheticProbeAlgorithm.cs` into LEAN's `Algorithm.CSharp/`.
2. Copy the three `fixtures/*.csv` files into LEAN's `Data/tidelab/`.
3. Build `Launcher/QuantConnect.Lean.Launcher.csproj` in `Release` mode.
4. In the **built copy** at `Launcher/bin/Release/config.json`, set `algorithm-type-name` to `TideLabSyntheticProbeAlgorithm`. Keep `environment` as `backtesting`, `algorithm-language` as `CSharp`, and `data-folder` pointing to LEAN's local `Data/` directory.
5. From `Launcher/bin/Release/`, run `dotnet QuantConnect.Lean.Launcher.dll`.

The expected log marker is `TL001A_LEAN_SYNTHETIC count=3 sum=306`, followed by analysis completion. A successful run establishes only local historical data delivery. It does not test TideLab's H1 strategy, order accounting, forward-paper operation, process-loss recovery, or LEAN adoption. See `docs/evidence/TL-001A-LEAN-FALLBACK-PREFLIGHT.md`.
