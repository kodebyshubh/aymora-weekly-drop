"""Print the numbers quoted in WRITEUP.md. Usage: python -m scripts.run_sim"""
import numpy as np

from app.sim import SimParams, compare


def show(title, params):
    print(f"\n{title}")
    runs = compare(params)
    print(f"{'policy':<28}{'covered':>9}{'avg fit':>9}{'strong':>8}{'waited2+':>10}{'retained':>10}")
    for k, r in runs.items():
        cov = np.mean([x.covered for x in r.rows])
        sc = np.mean(r.all_scores) if r.all_scores else 0
        st = np.mean([x.strong_share for x in r.rows])
        print(f"{k:<28}{cov:>9.1%}{sc*100:>9.0f}{st:>8.0%}{r.rows[-1].waited_2plus:>10.1%}{r.retention:>10.0%}")


if __name__ == "__main__":
    base = dict(n=200, weeks=6, seed=11, pct_nonbinary=0.02)
    show("Four cities, 45% women (default)", SimParams(pct_women=0.45, **base))
    show("One city, 45% women", SimParams(pct_women=0.45, cities=[("Bengaluru", 1.0)], **base))
    show("One city, 50% women", SimParams(pct_women=0.50, cities=[("Bengaluru", 1.0)], **{**base, "pct_nonbinary": 0.0}))
    show("One city, 30% women", SimParams(pct_women=0.30, cities=[("Bengaluru", 1.0)], **{**base, "pct_nonbinary": 0.0}))

    from app import promise
    p = SimParams(pct_women=0.45, **base)
    h = promise.promise_report(p)["headline"]
    print("\nPromise:", {k: round(v, 3) for k, v in h.items()})
    for r in promise.redteam_report(p, 0.05).get("modes", []):
        print("Red team:", r)
    print("Closure:", promise.closure_report(p).get("rows", "see API"))
