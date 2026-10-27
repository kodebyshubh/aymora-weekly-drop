"use strict";
/* Engine room: can the promise be kept, who it works for, what it takes, scams, ghosting, policies.
   Needs h, s, api, pct, mean from app.js. */

const COL = { weekly_drop: "#E65C85", one_shot: "#BA8B2E", greedy: "#7090E4", ceiling: "#F7E9EE", blue: "#7090E4" };
const ORDER = ["weekly_drop", "one_shot", "greedy"];
const sim = { n: 200, weeks: 6, pct_women: 0.45, inflow_pct: 0.10, floor: 0.62, one_city: false, realistic: false, adv_pct: 0.05, seed: 11 };
let engineTimer = 0, engineRound = 0;
const sections = [];

/* ------------------------------------------------------------------ small building blocks */
function tbl(head, rows, opts = {}) {
  const t = h("table", { class: "cmp" }, opts.caption ? h("caption", { class: "sr" }, opts.caption) : null,
    h("thead", {}, h("tr", {}, head.map((c, i) => h("th", { scope: "col" }, c)))),
    h("tbody", {}, rows.map((r) => h("tr", {}, r.map((c, i) => (i === 0 ? h("th", { scope: "row" }, c) : h("td", { class: "num" + (r.best && r.best.includes(i) ? " best" : "") }, c)))))));
  return h("div", { class: "tblwrap" }, t);
}
const sw = (c) => h("span", { class: "sw", style: `background:${c}` });
const fix = (x, d = 1) => Number(x).toFixed(d);
function yrange(vals, pad = 0.05) {
  const lo = Math.max(0, Math.floor((Math.min(...vals) - pad) * 10) / 10), hi = Math.min(1, Math.ceil((Math.max(...vals) + pad) * 10) / 10);
  return { ymin: lo, ymax: hi > lo ? hi : lo + 0.1 };
}
const weeksBetween = (rate) => (rate >= 0.97 ? "every week" : rate > 0 ? `one every ${fix(1 / rate)} weeks` : "never");

function lineChart(cfg) {
  const W = cfg.W || 560, H = cfg.H || 300, m = Object.assign({ l: 46, r: 120, t: 16, b: 36 }, cfg.m || {});
  const xs = cfg.xs, xmin = Math.min(...xs), xmax = Math.max(...xs);
  const X = (v) => m.l + ((v - xmin) / (xmax - xmin || 1)) * (W - m.l - m.r);
  const Y = (v) => m.t + (1 - (v - cfg.ymin) / (cfg.ymax - cfg.ymin || 1)) * (H - m.t - m.b);
  const svg = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": cfg.aria });
  for (let v = cfg.ymin; v <= cfg.ymax + 1e-9; v += cfg.ystep) svg.append(s("line", { class: "grid", x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v) }), s("text", { x: m.l - 8, y: Y(v) + 4, "text-anchor": "end" }, cfg.yfmt(v)));
  xs.forEach((x) => svg.append(s("text", { x: X(x), y: H - m.b + 20, "text-anchor": "middle" }, cfg.xfmt(x))));
  if (cfg.xtitle) svg.append(s("text", { x: (m.l + W - m.r) / 2, y: H - 2, "text-anchor": "middle" }, cfg.xtitle));
  if (cfg.hline) svg.append(s("line", { x1: m.l, x2: W - m.r, y1: Y(cfg.hline.y), y2: Y(cfg.hline.y), stroke: "#F7E9EE", "stroke-width": 1, "stroke-dasharray": "2 4" }), s("text", { x: W - m.r + 8, y: Y(cfg.hline.y) + 4, class: "lab" }, cfg.hline.label));
  const ends = [];
  [...cfg.series].reverse().forEach((se) => {
    const pts = xs.map((x, i) => [X(x), Y(se.values[i])]);
    svg.append(s("path", { d: pts.map((p, i) => (i ? "L" : "M") + p[0].toFixed(1) + " " + p[1].toFixed(1)).join(" "), fill: "none", stroke: se.color, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round", "stroke-dasharray": se.dash || "none" }));
    pts.forEach((p) => svg.append(s("circle", { cx: p[0], cy: p[1], r: 4, fill: se.color, stroke: "#22111B", "stroke-width": 2 })));
    ends.push([se.short || se.name, pts[pts.length - 1][1]]);
  });
  ends.sort((a, b) => a[1] - b[1]);
  for (let i = 1; i < ends.length; i++) if (ends[i][1] - ends[i - 1][1] < 15) ends[i][1] = ends[i - 1][1] + 15;
  ends.forEach(([t, y]) => svg.append(s("text", { class: "lab", x: W - m.r + 10, y: y + 4 }, t)));
  const tip = h("div", { class: "tip", hidden: true });
  const box = h("div", { class: "chartbox" }, svg, tip);
  xs.forEach((x, i) => {
    const bw = (W - m.l - m.r) / Math.max(1, xs.length - 1);
    const r = s("rect", { x: X(x) - bw / 2, y: m.t, width: bw, height: H - m.t - m.b, fill: "transparent" });
    const show = () => {
      tip.replaceChildren(h("b", {}, cfg.tipTitle(i)), ...cfg.series.map((se) => h("div", {}, sw(se.color), `${se.short || se.name} ${cfg.tipVal(se, se.values[i], i)}`)));
      tip.hidden = false; tip.style.left = (X(x) / W) * 100 + "%"; tip.style.top = "18%";
    };
    r.addEventListener("mousemove", show); r.addEventListener("mouseenter", show); r.addEventListener("mouseleave", () => { tip.hidden = true; });
    svg.append(r);
  });
  const legend = cfg.series.length > 1 ? h("div", { class: "legend" }, cfg.series.map((se) => h("span", {}, sw(se.color), se.name))) : null;
  const numbers = h("details", { class: "nums" }, h("summary", {}, "Show the numbers"),
    h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, cfg.xname || ""), cfg.series.map((se) => h("th", {}, se.short || se.name)))),
      h("tbody", {}, xs.map((x, i) => h("tr", {}, h("td", {}, cfg.xfmt(x)), cfg.series.map((se) => h("td", {}, cfg.tipVal(se, se.values[i], i))))))));
  return h("div", { class: "chart" }, h("h3", {}, cfg.title), cfg.sub ? h("p", { class: "sub" }, cfg.sub) : null, legend, box, numbers);
}

/* ------------------------------------------------------------------ the sections */
function promiseSection(P) {
  const hd = P.headline, pr = P.params;
  const parts = [
    { v: hd.delivered, label: "Introduced", note: "Got this week's introduction.", color: "#E65C85" },
    { v: Math.max(0, hd.ceiling - hd.delivered), label: "Possible, not delivered", note: "Someone could have been paired with them, but the quality floor or a better global pairing said no.", color: "#F4B6C8" },
    { v: Math.max(0, 1 - hd.ceiling - hd.unreachable), label: "Not enough people on the other side", note: "They have options, but those options are taken. This is the supply gap.", color: "#8F6D80" },
    { v: hd.unreachable, label: "Nobody fits their rules", note: "Age range, city, intent and boundaries leave no one in the pool.", color: "url(#hatch)" },
  ];
  const W = 1000, H = 44;
  const bar = s("svg", { viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Where each week's pool ends up: " + parts.map((p) => `${p.label} ${pct(p.v)}`).join(", ") });
  bar.append(s("defs", {}, s("pattern", { id: "hatch", width: 8, height: 8, patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" }, s("rect", { width: 8, height: 8, fill: "#3A2431" }), s("line", { x1: 0, y1: 0, x2: 0, y2: 8, stroke: "#CDB6C1", "stroke-width": 2 }))));
  let x = 0;
  parts.forEach((p) => { const w = p.v * W; if (w > 0) bar.append(s("rect", { x: x + 1, y: 0, width: Math.max(0, w - 2), height: H, rx: 3, fill: p.color })); x += w; });
  const key = h("ul", { class: "partkey" }, parts.map((p) => h("li", {}, h("span", { class: "sw big", style: p.color.startsWith("url") ? "background:repeating-linear-gradient(45deg,#3A2431 0 3px,#CDB6C1 3px 5px)" : `background:${p.color}` }), h("div", {}, h("b", {}, `${pct(p.v)} ${p.label}`), h("small", {}, p.note)))));
  const rate = (g) => P.people[g] ? P.people[g].rate : 0;
  const cityTxt = pr.one_city ? "in one city" : "across four cities";
  const ceil = hd.ceiling;
  const nodes = [
    h("p", { class: "insight" }, `With ${pct(pr.pct_women)} women ${cityTxt}, Weekly Drop introduces ${pct(hd.delivered)} of people each week. The best any policy could do is ${pct(ceil)}, and ${pct(hd.unreachable)} have nobody who fits their rules. The engine sits ${fix(100 * hd.gap_to_ceiling, 0)} points under its ceiling. The rest of the gap is supply.`),
    h("div", { class: "bar" }, bar), key,
    lineChart({ title: "Delivered against the ceiling, by week", sub: "The ceiling is a maximum-cardinality matching at the loosest floor. No policy can beat it.", xs: P.weekly.map((r) => r.week), xfmt: (w) => "Week " + w, xname: "Week",
      series: [{ name: "Delivered", short: "Delivered", color: COL.weekly_drop, values: P.weekly.map((r) => r.delivered) }, { name: "Ceiling", short: "Ceiling", color: COL.ceiling, dash: "6 5", values: P.weekly.map((r) => r.ceiling) }],
      ...yrange(P.weekly.flatMap((r) => [r.delivered, r.ceiling]), 0.05), ystep: 0.1, yfmt: (v) => Math.round(v * 100) + "%", tipTitle: (i) => "Week " + P.weekly[i].week, tipVal: (se, v) => pct(v, 1), aria: "Delivered and ceiling coverage by week" }),
    h("div", { class: "callout" }, h("b", {}, "The promise this pool can support. "), `Women hear from Aymora ${weeksBetween(rate("woman"))}. Men ${weeksBetween(rate("man"))}. Saying "one introduction every week for everyone" here would be a promise the pool cannot keep, and the engine tells you before a customer finds out.`),
  ];
  return nodes;
}

function whoSection(P) {
  const L = P.labels, A = P.attention, f = P.swipe;
  const g = (k) => P.people[k] || { rate: 0, kept_once: 0, p95_drought: 0, gini: 0 };
  const t1 = tbl(["Weekly Drop", "Women", "Men"], [
    ["Introductions per week", fix(g("woman").rate, 2), fix(g("man").rate, 2)],
    ["Typical wait between introductions", weeksBetween(g("woman").rate), weeksBetween(g("man").rate)],
    ["Introduced at least once", pct(g("woman").kept_once), pct(g("man").kept_once)],
    ["Longest wait for 1 in 20 people", `${g("woman").p95_drought} weeks`, `${g("man").p95_drought} weeks`],
  ], { caption: "Weekly Drop by gender" });
  const rows = ORDER.map((k) => [L[k], fix(A[k].woman.rate, 2), fix(A[k].man.rate, 2), fix(A[k].woman.gini, 2), fix(A[k].man.gini, 2)]);
  const t2 = tbl(["Policy", "Women per week", "Men per week", "Inequality among women", "Inequality among men"], rows, { caption: "Attention by policy" });
  const wo = f.woman || {}, ma = f.man || {};
  const t3 = tbl(["Same people in a swipe feed", "Women", "Men"], [
    ["Typical likes received per week", fix(wo.mean_inbound || 0, 1), fix(ma.mean_inbound || 0, 1)],
    ["Top tenth receive", fix(wo.top_decile_inbound || 0, 1), fix(ma.top_decile_inbound || 0, 1)],
    ["Under half a like a week", pct(wo.invisible_share || 0), pct(ma.invisible_share || 0)],
    ["Inequality (Gini)", fix(wo.gini || 0, 2), fix(ma.gini || 0, 2)],
  ], { caption: "Swipe feed illustration" });
  return [
    h("p", { class: "insight" }, `Under Weekly Drop nobody is sent more than one introduction a week. In a swipe feed on the same people, the typical woman gets ${fix(wo.mean_inbound || 0, 0)} likes a week and the top tenth get ${fix(wo.top_decile_inbound || 0, 0)}, while the typical man gets ${fix(ma.mean_inbound || 0, 0)}. Attention that uneven is what burns people out, on both sides.`),
    t1, t2, t3,
    h("p", { class: "fine" }, "The swipe feed is an illustration: everyone sees the 15 most popular eligible people and likes them with the same probability model. Nothing in it is specific to any real app, so read the shape, not the number. Inequality is a Gini coefficient over weekly introductions per person (0 means perfectly even)."),
  ];
}

function whatItTakesSection(C, P) {
  const grid = C.grid;
  const wn = C.window;
  const txt = (w) => (w ? `${Math.round(w[0] * 100)}% to ${Math.round(w[1] * 100)}% women` : "no share of women");
  const nodes = [
    h("p", { class: "insight" }, `To keep the promise for ${pct(C.target)} of people each week, ${pr1(wn.current, txt)} ` + (wn.one_city ? `One city at a time gets there at ${txt(wn.one_city)}.` : "One city at a time does not get there in this range either.")),
    lineChart({ title: "Promise kept, by share of women", sub: "Weekly Drop, 4 weeks per point. Expect a few points of noise per dot: each is one simulated city.", xs: grid, xfmt: (v) => Math.round(v * 100) + "%", xname: "Women", xtitle: "Share of women in the pool",
      series: [{ name: "Four cities", short: "Four cities", color: COL.blue, values: C.current.map((p) => p.covered) }, { name: "One city", short: "One city", color: COL.weekly_drop, values: C.one_city.map((p) => p.covered) }],
      ...yrange([...C.current, ...C.one_city].map((p) => p.covered).concat([C.target]), 0.05), ystep: 0.1, yfmt: (v) => Math.round(v * 100) + "%", hline: { y: C.target, label: "Target" }, tipTitle: (i) => Math.round(grid[i] * 100) + "% women", tipVal: (se, v) => pct(v, 1), aria: "Share of people introduced each week against share of women, for four cities and for one city" }),
    h("p", { class: "fine" }, "Too many women breaks the promise too: the same engine cannot pair everyone when the other side runs short. Balance is the lever, and density multiplies it."),
  ];
  const lev = P.levers;
  nodes.push(h("h3", { class: "sub-h" }, "What the team can pull"), tbl(["Lever", "Introduced each week", "Everyone, incl. waitlisted", "Introduced at least once", "Average fit", "Still around"],
    lev.map((l) => [l.name, pct(l.covered, 1), pct(l.covered_all, 1), pct(l.kept_once), fix(l.avg_score * 100, 0), pct(l.retention)]), { caption: "Levers" }),
  h("p", { class: "fine" }, "Balanced admission waitlists the larger side per city, longest waiters first, and tells them so. It does not create supply. What it buys is honesty and a visible queue. Density is the lever that moves the numbers."));
  return nodes;
}
const pr1 = (w, txt) => (w ? `you need ${txt(w)} in this city mix.` : "this city mix never gets there at any share of women we tried.");

function scamSection(R) {
  const m = R.modes, b = R.benchmark, k = R.kinds;
  const rows = m.map((x) => [x.name, pct(x.exposed_rate, 1), pct(x.engaged_rate, 1), x.caught ? `${x.caught} of ${x.adversaries}` : "none", `${x.held_back_real}`]);
  const first = m[0], last = m[m.length - 1];
  return [
    h("p", { class: "insight" }, `With scam accounts making up ${pct(R.params.adv_pct)} of joiners, ${pct(first.exposed_rate, 0)} of real people meet one within ${R.params.weeks} weeks if nothing is done. With a trust gate and reports it drops to ${pct(last.exposed_rate, 0)}.`),
    tbl(["Defence", "Real people introduced to a scam account", "Said yes to one", "Scam accounts caught before matching", "Honest people held back"], rows, { caption: "Scam red team" }),
    h("p", { class: "fine" }, `Four kinds of fake account are injected: ${k.map((x) => `${x.label.toLowerCase()} (${x.caught} of ${x.count} caught)`).join(", ")}. Signals: account under a week old, bio copied across accounts, contact details or money talk in the bio, email domain that does not match the college, prior reports, photo seen elsewhere. A score of ${R.params.threshold} holds the account back before matching. Between ${0.35} and ${R.params.threshold} the other person sees a caution banner. About a quarter of people who meet a scammer report them (an assumption).`),
    h("h3", { class: "sub-h" }, "What the threshold costs"),
    tbl(["Hold back above", "Scam accounts caught", "Held-back accounts that are scams", "Honest people held back"],
      b.map((x) => [fix(x.threshold, 2), pct(x.recall), pct(x.precision), `${fix(x.honest_held_back * 1000, 0)} per 1,000`]), { caption: "Threshold sweep" }),
    h("p", { class: "fine" }, `Measured on ${b[0].honest.toLocaleString("en-IN")} synthetic honest accounts and ${b[0].scam} synthetic scam accounts. Honest people trip these signals too, since plenty put an Instagram handle in their bio, so a lower threshold starts to hold back real people.`),
  ];
}

function ghostSection(G) {
  const [off, on] = G.modes;
  return [
    h("p", { class: "insight" }, `After a mutual yes, ${pct(off.ghost_rate, 0)} of introductions end in silence with no protocol. With a kind close and a 72-hour expiry, ${pct(on.close_rate, 0)} of them end with a reason, and the share involving a repeat ghoster falls from ${pct(off.chronic_share, 0)} to ${pct(on.chronic_share, 0)}.`),
    tbl(["", off.name, on.name], [
      ["Introductions that end in silence", pct(off.ghost_rate, 1), pct(on.ghost_rate, 1)],
      ["Introductions that end with a kind close", pct(off.close_rate, 1), pct(on.close_rate, 1)],
      ["Reasons collected per 100 introductions", fix(off.reasons_per_100, 1), fix(on.reasons_per_100, 1)],
      ["Introductions involving a repeat ghoster", pct(off.chronic_share, 1), pct(on.chronic_share, 1)],
    ], { caption: "Ghosting" }),
    h("p", { class: "fine" }, "Two parts are assumptions: 10% of people often go quiet after a mutual yes, and 40% of would-be ghosts close kindly when the protocol nudges them. The drop in silence follows from that second number. The drop in repeat-ghoster exposure is the engine's own doing: ghosting costs priority, so repeat ghosters meet fewer people. The reasons feed each person's weights."),
  ];
}

function policySection(S, F) {
  const P = S.policies, L = S.labels;
  const stat = {};
  for (const k of ORDER) { const r = P[k].rows; stat[k] = { cov: mean(r.map((x) => x.covered)), score: P[k].avg_score, strong: mean(r.map((x) => x.strong_share)), mut: mean(r.map((x) => x.mutual_per_100)), wait: r[r.length - 1].waited_2plus, ret: P[k].retention, mis: mean(r.map((x) => x.intent_mismatch)) }; }
  const rowsDef = [["Introduced each week", "cov", (v) => pct(v, 1), 1], ["Average fit of an introduction", "score", (v) => fix(v * 100, 0), 1], ["Strong fits", "strong", (v) => pct(v), 1], ["Mutual yes per 100 people", "mut", (v) => fix(v, 1), 1], ["Waiting two weeks or more at the end", "wait", (v) => pct(v, 1), -1], ["Introductions that differ on intent", "mis", (v) => pct(v), -1], ["Still around at the end", "ret", (v) => pct(v), 1]];
  const rows = rowsDef.map(([name, key, f, dir]) => { const vals = ORDER.map((k) => stat[k][key]); const best = dir > 0 ? Math.max(...vals) : Math.min(...vals); const r = [name, ...ORDER.map((k) => f(stat[k][key]))]; r.best = ORDER.map((k, i) => (stat[k][key] === best ? i + 1 : 0)).filter(Boolean); return r; });
  const head = ["Measure", ...ORDER.map((k) => h("span", {}, sw(COL[k]), L[k]))];
  const gaps = P.weekly_drop.supply || [];
  const nodes = [
    h("p", { class: "insight" }, `Same people, three ways to run the week. Weekly Drop introduces ${pct(stat.weekly_drop.cov)} each week against ${pct(stat.greedy.cov)} for first come, first served, and ${pct(stat.weekly_drop.wait)} are still waiting two weeks or more at the end, against ${pct(stat.one_shot.wait)} when the matching has no memory.`),
    tbl(head, rows, { caption: "Policy comparison" }),
    h("div", { class: "charts" },
      lineChart({ title: "Share of the pool introduced, by week", sub: "Higher is better. Hover a week to compare.", xs: P.weekly_drop.rows.map((r) => r.week), xfmt: (w) => "Week " + w, xname: "Week",
        series: ORDER.map((k) => ({ name: L[k], short: { greedy: "First come", one_shot: "No memory", weekly_drop: "Weekly Drop" }[k], color: COL[k], values: P[k].rows.map((r) => r.covered) })),
        ...yrange(ORDER.flatMap((k) => P[k].rows.map((r) => r.covered)), 0.05), ystep: 0.1, yfmt: (v) => Math.round(v * 100) + "%", tipTitle: (i) => "Week " + P.weekly_drop.rows[i].week, tipVal: (se, v) => pct(v, 1), aria: "Share introduced by week and policy" }),
      lineChart({ title: "What a stricter floor costs", sub: "Weekly Drop only. A higher floor lifts average fit and shrinks the share introduced.", xs: F.map((p) => p.floor), xfmt: (v) => fix(v, 2), xname: "Floor", xtitle: "Quality floor", W: 480, m: { r: 24 },
        series: [{ name: "Introduced", short: "Introduced", color: COL.weekly_drop, values: F.map((p) => p.covered) }], ...yrange(F.map((p) => p.covered), 0.05), ystep: 0.1, yfmt: (v) => Math.round(v * 100) + "%",
        tipTitle: (i) => "Floor " + fix(F[i].floor, 2), tipVal: (se, v, i) => `${pct(v, 1)}, average fit ${fix(F[i].avg_score * 100, 0)}`, aria: "Share introduced against quality floor" })),
  ];
  const gbox = h("div", { class: "gaps" }, h("h3", {}, "Who is missing from the pool"), h("p", {}, "People who got nothing under Weekly Drop, grouped by the kind of person who would fix it. This is the list a growth team can act on."));
  if (gaps.length) gbox.append(h("ul", {}, gaps.slice(0, 4).map((x) => h("li", {}, `${x.people} people in ${x.city} looking for ${x.seeking.join(" or ")}`, h("small", {}, `Median age range ${x.age_range[0]} to ${x.age_range[1]}. ${x.no_eligible} had no one who fit their preferences, ${x.below_floor} had nobody above the floor, ${x.outcompeted} lost out to a stronger pairing.`)))));
  else gbox.append(h("p", {}, "No gaps in this run."));
  nodes.push(gbox);
  return nodes;
}

/* ------------------------------------------------------------------ page */
function renderEngine() {
  const root = $("#view-engine");
  const wrap = h("div", { class: "wrap" });
  wrap.append(h("h2", {}, "Can Aymora keep its promise?"),
    h("p", {}, "A weekly guarantee is a supply problem before it is a taste problem. This is the engine room: it measures how close Weekly Drop gets to the best any policy could do, who it works for, what it would take to keep the promise for everyone, and what scams and ghosting do to it. Everything runs on synthetic people. Move a slider and every section reruns."));
  const ctls = h("div", { class: "controls" });
  const slider = (key, label, min, max, step, fmt, note) => {
    const out = h("output", {}, fmt(sim[key]));
    const inp = h("input", { type: "range", min, max, step, id: "c-" + key, value: sim[key] });
    inp.addEventListener("input", () => { sim[key] = parseFloat(inp.value); out.textContent = fmt(sim[key]); schedule(); });
    return h("div", { class: "ctl" }, h("label", { for: "c-" + key }, label, out), inp, note ? h("small", {}, note) : null);
  };
  const check = (key, id, label, note) => { const c = h("input", { type: "checkbox", id }); c.checked = sim[key]; c.addEventListener("change", () => { sim[key] = c.checked; schedule(); }); return h("div", { class: "ctl" }, h("label", { class: "checkrow", for: id }, c, label), h("small", {}, note)); };
  ctls.append(slider("pct_women", "Share of women", 0.2, 0.8, 0.01, (v) => pct(v), "India's dating apps skew near 26% women"),
    slider("n", "People in the pool", 60, 400, 20, (v) => v, "Starting size"),
    slider("weeks", "Weeks simulated", 2, 10, 1, (v) => v),
    slider("inflow_pct", "New people each week", 0, 0.3, 0.02, (v) => pct(v)),
    slider("floor", "Quality floor", 0.55, 0.85, 0.01, (v) => v.toFixed(2), "Higher means fewer but stronger introductions"),
    slider("adv_pct", "Scam accounts among joiners", 0.01, 0.15, 0.01, (v) => pct(v), "Used by the scam red team"),
    check("one_city", "c-city", "Everyone in one city", "Four thin cities split the pool and lower coverage"),
    check("realistic", "c-real", "People have boundaries", "Some want the same intent only, hide from their own college, or verified only"));
  wrap.append(ctls);
  const defs = [
    { id: "promise", title: "The promise, measured", need: ["promise"], draw: (d) => promiseSection(d.promise) },
    { id: "who", title: "Who it works for", need: ["promise"], draw: (d) => whoSection(d.promise) },
    { id: "takes", title: "What it takes to keep it", need: ["curve", "promise"], draw: (d) => whatItTakesSection(d.curve, d.promise) },
    { id: "scams", title: "Scam red team", need: ["redteam"], draw: (d) => scamSection(d.redteam) },
    { id: "ghost", title: "Ghosting and closure", need: ["closure"], draw: (d) => ghostSection(d.closure) },
    { id: "policies", title: "Three ways to run the week", need: ["sim", "frontier"], draw: (d) => policySection(d.sim, d.frontier) },
  ];
  const nav = h("nav", { class: "subnav", "aria-label": "Engine room sections" }, defs.map((d) => h("button", { class: "linkbtn", onclick: () => { const el = $("#sec-" + d.id); if (el) el.scrollIntoView({ behavior: "smooth", block: "start" }); } }, d.title)));
  wrap.append(nav);
  sections.length = 0;
  defs.forEach((d) => {
    const body = h("div", { class: "secbody" });
    const el = h("section", { class: "eng", id: "sec-" + d.id }, h("h3", { class: "sec-title" }, d.title), body);
    wrap.append(el);
    sections.push({ ...d, el, body });
  });
  wrap.append(h("div", { class: "assume" }, h("b", {}, "What to keep in mind"),
    h("ul", {},
      h("li", {}, "People are synthetic, generated from seven personality archetypes. Real numbers will differ."),
      h("li", {}, "Whether someone says yes is a function of fit. People leave after waiting: 6% a week per week waited, capped at four weeks. Scam accounts report at 25% once introduced, 10% of people often go quiet after a mutual yes, and 40% of would-be ghosts close kindly when nudged. All of these are assumptions, not measurements."),
      h("li", {}, "The comparison holds the people constant. Only the policy changes."),
      h("li", {}, "Same settings always give the same numbers (seed 11)."))));
  root.append(wrap);
  schedule(0);
}

function schedule(ms = 600) {
  clearTimeout(engineTimer);
  sections.forEach((sec) => sec.el.classList.add("busy"));
  engineTimer = setTimeout(refresh, ms);
}

function refresh() {
  const round = ++engineRound;
  const body = JSON.parse(JSON.stringify(sim));
  const calls = {}, memo = {};
  const paths = { promise: "/api/promise", curve: "/api/promise/curve", redteam: "/api/redteam", closure: "/api/closure", sim: "/api/sim", frontier: "/api/frontier" };
  const get = (k) => { if (!memo[k]) memo[k] = api(paths[k], body).then((d) => (k === "frontier" ? d.points : d)); return memo[k]; };
  sections.forEach((sec) => {
    sec.body.classList.add("loading");
    if (!sec.body.childNodes.length) sec.body.append(h("p", { class: "fine" }, "Running the simulation. The first run takes about ten seconds."));
    Promise.all(sec.need.map(get)).then((vals) => {
      if (round !== engineRound) return;
      const d = {}; sec.need.forEach((k, i) => { d[k] = vals[i]; });
      sec.body.replaceChildren(...sec.draw(d));
      sec.body.classList.remove("loading");
      sec.el.classList.remove("busy");
    }).catch((e) => {
      if (round !== engineRound) return;
      sec.body.replaceChildren(h("div", { class: "errbox", role: "alert" }, e.message));
      sec.el.classList.remove("busy");
    });
  });
}
