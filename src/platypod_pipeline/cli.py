"""`pp` — the single entrypoint of the image.

    pp generate [--check]     contracts -> DDL + dbt YAML (drift check for CI)
    pp lint                   validate every contract against ODCS
    pp migrate                apply migrations + generated DDL
    pp test [dataset ...]     contract tests against the live database
    pp run <pipeline>         run a pipeline (e.g. heartbeat)
"""

from __future__ import annotations

import argparse
import importlib
import logging
import sys

from datacontract.data_contract import DataContract

from . import contracts, telemetry
from .config import Settings
from .generate import generate
from .migrate import migrate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pp")
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate")
    g.add_argument("--check", action="store_true", help="exit 1 if generated files drifted")
    sub.add_parser("lint")
    sub.add_parser("migrate")
    t = sub.add_parser("test")
    t.add_argument("datasets", nargs="*")
    r = sub.add_parser("run")
    r.add_argument("pipeline")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    # The exporter warns on pass-through physical types (uuid, timestamptz) although it emits them correctly.
    logging.getLogger("datacontract.export.sql_type_converter").setLevel(logging.ERROR)
    settings = Settings()

    try:
        if args.cmd == "generate":
            drift = generate(settings, check=args.check)
            for p in drift:
                print(("DRIFT " if args.check else "wrote ") + str(p.relative_to(settings.root)))
            return 1 if (args.check and drift) else 0

        if args.cmd == "lint":
            bad = 0
            for path in contracts.contract_files(settings):
                run = DataContract(data_contract_file=str(path)).lint()
                ok = run.has_passed()
                print(("ok   " if ok else "FAIL ") + path.name)
                if not ok:
                    bad += 1
                    print(run.pretty())
            return 1 if bad else 0

        if args.cmd == "migrate":
            print("\n".join(migrate(settings)))
            return 0

        if args.cmd == "test":
            datasets = args.datasets or [contracts.dataset_of(p) for p in contracts.contract_files(settings)]
            failed = 0
            for ds in datasets:
                result = contracts.run_test(settings, ds)
                print(f"{'ok  ' if result.passed else 'FAIL'} {ds} ({len(result.checks)} checks)")
                for c in result.failures:
                    print(f"     - {c.name} [{c.field}]: {c.reason}")
                failed += not result.passed
            return 1 if failed else 0

        if args.cmd == "run":
            module = importlib.import_module(f"platypod_pipeline.pipelines.{args.pipeline}")
            module.run(settings)
            return 0
    finally:
        telemetry.shutdown()
    return 2


if __name__ == "__main__":
    sys.exit(main())
