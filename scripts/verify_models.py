"""Run the model verification suite from the command line and print the results.

    python scripts/verify_models.py
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from scientific_engine.validation import load_or_run  # noqa: E402

v = load_or_run(force=True)
print(f"Physics engine checks passed:    {v['physics_passed']}/{v['physics_total']}")
sim = v["similarity"]
print(f"Similarity engine checks passed: {sum(r['passed'] for r in sim)}/{len(sim)}")
for r in v["detector"]["rows"]:
    print(f"Detector [{r['scenario']}]: precision {r['precision']:.2f} recall {r['recall']:.2f} F1 {r['f1']:.2f}")
print(f"Physics throughput: {v['throughput']['evals_per_second']:.0f} wheel-soil solves/s")
print("Verification is not validation: no hardware or labelled real-terrain data were used.")
