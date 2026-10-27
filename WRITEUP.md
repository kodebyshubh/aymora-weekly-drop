# Aymora Weekly Drop: what I would build first

## What

A working engine for Aymora's core promise, plus an honest answer to the question every founder should ask of it: **can Aymora keep that promise in India?** Live demo and code are in this repo.

Weekly Drop gives each person at most one introduction a week, chosen by matching the whole pool at once, with a quality floor that never moves below 0.55. Around it sit five additions built for an Indian launch:

1. **Promise report.** Measures delivered coverage against the best any policy could do and against people with nobody on the other side. Shows how coverage depends on the share of women, and which launch levers help (one city at a time, balanced admission).
2. **Attention inequality.** The Gini of weekly introductions per person, under each policy, next to an illustrated swipe feed.
3. **Safe reveal and scam red team.** Names and bio at a mutual yes, photos and numbers only when both tap, then a safety plan. Accounts get a risk score before matching. Four kinds of fake account are injected and the defences compared.
4. **Closure protocol.** After a mutual yes you can say talking, met, or close kindly with a reason. Silence for 72 hours closes the introduction, and repeat ghosting lowers priority.
5. **Boundaries.** Same intent only, family-privacy (hide me from my own campus circle), verified only, and a "why not more options?" panel that shows which setting costs how much.

## Why

A weekly guarantee is a supply problem before it is a taste problem. Public reports put women at roughly a quarter of Indian dating app users (Redseer, secondhand), and the Gini figures for swipe feeds I cite are also secondhand. So the demo does not stop at matching. It tells the team how many people the pool can serve, who is missing, and what launch policy keeps the promise.

## How

Python, FastAPI, numpy, networkx. Compatibility is scored both ways on vibe, communication, values and interests, and humor, weighted by Aymora's survey (73, 64, 48, 42); physical appearance (27%) is left out on purpose. Pair score is the geometric mean of both directions. Maximum weight matching picks the best pairs for the whole pool, waiting lowers a person's floor by 0.03 a week, and ghosting costs 0.05 priority. The ceiling is a maximum cardinality matching at the minimum floor. Plain JavaScript front end. 73 tests.

## What the simulator shows

200 synthetic people, 6 weeks, 10% new people a week, same people under every policy (`python -m scripts.run_sim`). Four cities, 45% women:

- **The promise.** Weekly Drop introduces 73% of people each week. The ceiling is 81%. 10% have nobody who fits their rules, so the engine is 8 points under the ceiling and the rest of the gap is supply.
- **First come, first served** introduces 66%, with 19% still waiting 2+ weeks. Weekly Drop: 10%.
- **Launch levers** (introduced each week): as launched 73%, balanced admission 76%, one city at a time 89%, both 92%. Density and balance matter more than the algorithm.
- **Attention.** Gini of weekly introductions per person: 0.23 under Weekly Drop, 0.29 first come first served. In an illustrated swipe feed it is 0.47.
- **Scams.** With 5% scam joiners, 18% of real people meet one within 6 weeks with no defence, 1% with a trust gate and reports. Raising the hold-back threshold from 0.5 to 0.6 held back 0 per 1,000 honest people and caught 78% of scam accounts (85% at 0.5, 1 per 1,000).
- **Closure.** After a mutual yes, 31% of introductions end in silence with no protocol, 18% with one; involvement of a repeat ghost falls from 9% to 3%.

## Limits

- Everyone is synthetic. Yes-probability, churn (6% per week waited), ghosting (10% chronic), the 40% close rate, and the 25% report rate are assumptions, not measurements.
- The swipe-feed numbers are an illustration of a popularity-ranked feed, not data from any real app.
- The closure drop in silence follows from the assumed 40% close rate. The drop in repeat-ghost exposure is emergent from the priority penalty.
- Balanced admission does not create supply, it decides who waits. Supply-curve points are noisy at this size.
- Verification, photos, numbers, and report review are mocked. The scam risk score is hand-set, not trained, and tuned on synthetic accounts.
- State is in memory and resets on restart.

## Next

Log real outcomes (second dates) and fit the weights. Real campus and ID verification. Human review for reports. Then the scale-out design: per-city sharded matching jobs, queues for the weekly run, and a waitlist service.
