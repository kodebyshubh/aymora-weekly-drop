"use strict";
/* Weekly Drop front end. Plain JavaScript, no build step. All text goes in through textContent.
   app.js: shared helpers, the visitor's drop. engine.js: the engine room. */

const SVGNS = "http://www.w3.org/2000/svg";
const $ = (s, r = document) => r.querySelector(s);

function h(tag, attrs, ...kids) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === false || v == null) continue;
    if (k === "class") el.className = v;
    else if (k.startsWith("on")) el.addEventListener(k.slice(2), v);
    else if (v === true) el.setAttribute(k, "");
    else el.setAttribute(k, v);
  }
  for (const kid of kids.flat()) {
    if (kid == null || kid === false) continue;
    el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return el;
}
function s(tag, attrs, ...kids) {
  const el = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  for (const kid of kids.flat()) if (kid != null) el.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  return el;
}
const pct = (x, d = 0) => (x * 100).toFixed(d) + "%";
const mean = (a) => (a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0);

async function api(path, body) {
  const opt = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  let data = null;
  try { data = await r.json(); } catch (e) { /* not json */ }
  if (!r.ok) {
    const d = data && data.detail;
    const msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((x) => x.msg).join(". ") : "Something went wrong.";
    const err = new Error(msg);
    err.status = r.status;
    throw err;
  }
  return data;
}
function store(k, v) {
  try { if (v === undefined) return sessionStorage.getItem(k); if (v === null) sessionStorage.removeItem(k); else sessionStorage.setItem(k, v); } catch (e) { /* storage blocked */ }
  return null;
}

const HEART = () => s("svg", { viewBox: "0 0 32 32", "aria-hidden": "true" }, s("path", { d: "M16 28C6 20 3 15 3 10.5 3 7 5.6 4.5 9 4.5c2.8 0 5 1.6 7 4.3 2-2.7 4.2-4.3 7-4.3 3.4 0 6 2.5 6 6C29 15 26 20 16 28z" }));
const INTENTS = [[0, "Keeping it casual"], [1, "Open to something long term"], [2, "Looking for something serious"]];
const GROUP_NAME = { vibe: "Vibe", communication: "Communication", values_interests: "Values and interests", humor: "Humor" };
const GROUPS = ["vibe", "communication", "values_interests", "humor"];
const REASON_WORDS = { no_eligible: "No one fits your preferences yet", below_floor: "Nobody cleared the quality floor", outcompeted: "Better fits went to others" };
const CLOSE_REASONS = [["vibe", "Vibe"], ["communication", "Communication"], ["values_interests", "Values and interests"], ["humor", "Humor"], ["intent", "What we want"], ["distance", "Distance"], ["other", "Something else"]];
const REPORT_REASONS = ["Asked for money", "Pushed me to another app", "Felt unsafe", "Fake profile"];

const app = {
  Q: null,
  sid: store("sid"),
  data: null,
  step: -1,
  draft: { basics: { name: "", gender: "woman", seeking: ["man"], age: 24, age_min: 22, age_max: 30, city: "Bengaluru", open_distance: false, intent: 1, strict_intent: false, private: false, verified_only: false, campus: "" }, answers: {}, humor: [], interests: [], priorities: [], about: "" },
  fresh: false,
  ui: { rating: null, closing: false, reporting: false, levers: null },
};

/* ------------------------------------------------------------------ routing */
const VIEWS = ["drop", "engine", "how"];
function route() {
  const v = VIEWS.includes(location.hash.slice(1)) ? location.hash.slice(1) : "drop";
  for (const name of VIEWS) $("#view-" + name).hidden = name !== v;
  document.querySelectorAll("[data-nav]").forEach((a) => { if (a.dataset.nav === v) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
  if (v === "engine" && !$("#view-engine").dataset.ready) { $("#view-engine").dataset.ready = "1"; renderEngine(); }
  if (v === "how" && !$("#view-how").dataset.ready) { $("#view-how").dataset.ready = "1"; renderHow(); }
  window.scrollTo(0, 0);
}
window.addEventListener("hashchange", route);

async function boot() {
  try { app.Q = await api("/api/questionnaire"); } catch (e) { $("#view-drop").append(h("p", { class: "errtxt" }, "The demo server did not answer. Refresh to try again.")); return; }
  if (app.sid) {
    try { app.data = await api("/api/drop/" + app.sid); } catch (e) { app.sid = null; store("sid", null); }
  }
  renderDrop();
  route();
}

/* ------------------------------------------------------------------ drop view */
function renderDrop() {
  const root = $("#view-drop");
  root.replaceChildren();
  if (app.data) return root.append(dropView());
  if (app.step < 0) return root.append(landing());
  root.append(questionnaire());
}

function sampleNote() {
  const rows = [["Vibe", 0.86, 0.3], ["Communication", 0.78, 0.26], ["Values and interests", 0.64, 0.22], ["Humor", 0.9, 0.22]];
  return h("div", { class: "note tilt drop-in", "aria-label": "Example introduction" },
    h("div", { class: "kicker" }, h("span", {}, "Example drop, week 3"), h("b", {}, "Strong fit")),
    h("h2", { class: "name" }, "Meera, 25"),
    h("p", { class: "meta" }, "Bengaluru, sarcastic humor"),
    h("ul", { class: "chips" }, ["coffee", "trekking", "stand-up comedy"].map((t) => h("li", {}, t)), h("li", { class: "ok" }, "College verified")),
    h("div", { class: "scribble" }, "You both go quiet when you need space, then text first."),
    h("div", { class: "strip", role: "img", "aria-label": "Fit by area: vibe 86, communication 78, values 64, humor 90" },
      rows.map(([n, v, w]) => h("div", { class: "row" }, h("span", {}, n), h("div", { class: "track", style: `height:${6 + w * 36}px` }, h("div", { class: "fill", style: `width:${v * 100}%` })), h("span", { class: "val" }, Math.round(v * 100))))),
    h("p", { class: "strip-cap" }, "Bar length is the fit. Bar thickness is how much that area matters to you."));
}

function landing() {
  return h("div", {},
    h("div", { class: "hero" },
      h("div", {},
        h("h1", {}, "One introduction. Every week. Never a weak one."),
        h("p", { class: "lede" }, "Weekly Drop is the engine behind that promise. It decides the best set of pairings for the whole pool, puts people who missed out first in line, and tells the team honestly when the pool is too thin to keep the promise."),
        h("div", { class: "cta" },
          h("button", { class: "btn", onclick: () => { app.step = 0; renderDrop(); window.scrollTo(0, 0); } }, "Get your first drop"),
          h("a", { href: "#engine" }, "Can the promise be kept?"))),
      sampleNote()),
    h("div", { class: "promises" },
      h("div", {}, h("b", {}, "The whole pool decides"), h("p", {}, "Pairs are chosen together, so one popular person cannot use up everyone's best option. Nobody gets more than one introduction a week.")),
      h("div", {}, h("b", {}, "Safe by design"), h("p", {}, "Risky accounts are held back before matching. Names, photos and numbers open in stages, only when both of you agree.")),
      h("div", {}, h("b", {}, "Honest when it cannot"), h("p", {}, "When a city is too thin, the engine says which kind of person is missing, and what it would take to keep the promise."))),
    h("p", { class: "proto-note" }, "Takes about two minutes. You answer ten short scenarios, then meet a synthetic person chosen from a pool of 240."));
}

/* ------------------------------------------------------------------ questionnaire */
function stepCount() { return 2 + app.Q.scenarios.length + 4; }
function questionnaire() {
  const Q = app.Q, n = stepCount(), i = app.step;
  const wrap = h("div", { class: "qwrap" });
  wrap.append(h("div", { class: "progress", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": n, "aria-valuenow": i + 1, "aria-label": "Progress" }, h("i", { style: `width:${((i + 1) / n) * 100}%` })),
    h("div", { class: "qmeta" }, h("span", {}, `Step ${i + 1} of ${n}`), h("span", {}, i > 1 ? "No right answers" : "")));
  const back = () => { app.step = Math.max(0, app.step - 1); renderDrop(); focusPrompt(); };
  const next = () => { app.step += 1; renderDrop(); focusPrompt(); };
  const nav = (canNext, nextLabel, onNext) => h("div", { class: "qnav" },
    i > 0 ? h("button", { class: "linkbtn", onclick: back }, "Back") : h("button", { class: "linkbtn", onclick: () => { app.step = -1; renderDrop(); } }, "Cancel"),
    onNext ? h("button", { class: "btn", disabled: !canNext, onclick: onNext }, nextLabel) : null);

  if (i === 0) { wrap.append(basicsStep(next)); return wrap; }
  if (i === 1) { wrap.append(boundariesStep(next, back)); return wrap; }
  const sc = Q.scenarios[i - 2];
  if (sc) {
    wrap.append(h("h2", { class: "qprompt", tabindex: "-1" }, sc.prompt), h("p", { class: "qhelp" }, "Pick the one that sounds most like you. It moves on when you choose."));
    wrap.append(h("div", { class: "opts" }, sc.options.map((o) => h("button", { class: "opt", "aria-pressed": String(app.draft.answers[sc.id] === o.id), onclick: () => { app.draft.answers[sc.id] = o.id; setTimeout(next, 160); renderDrop(); } }, o.text))));
    wrap.append(nav(false));
    return wrap;
  }
  const k = i - 2 - Q.scenarios.length;
  if (k === 0) {
    wrap.append(h("h2", { class: "qprompt", tabindex: "-1" }, "What kind of funny are you?"), h("p", { class: "qhelp" }, "Choose one or two."));
    wrap.append(h("div", { class: "opts" }, Q.humor.map((o) => h("button", { class: "opt", "aria-pressed": String(app.draft.humor.includes(o.id)), onclick: () => { toggle(app.draft.humor, o.id, 2); renderDrop(); } }, o.label, h("small", {}, o.blurb)))));
    wrap.append(nav(app.draft.humor.length > 0, "Next", next));
  } else if (k === 1) {
    wrap.append(h("h2", { class: "qprompt", tabindex: "-1" }, "What fills your free time?"), h("p", { class: "qhelp" }, "Pick up to six. Rare shared interests count for more than common ones."));
    wrap.append(h("div", { class: "pillrow" }, Q.interests.map((t) => h("button", { class: "pill", "aria-pressed": String(app.draft.interests.includes(t)), onclick: () => { toggle(app.draft.interests, t, 6); renderDrop(); } }, t))));
    wrap.append(nav(true, "Next", next));
  } else if (k === 2) {
    wrap.append(h("h2", { class: "qprompt", tabindex: "-1" }, "What matters most in a match?"), h("p", { class: "qhelp" }, "Choose up to two. Their weight on your drop goes up by half."));
    wrap.append(h("div", { class: "opts" }, Q.priorities.map((o) => h("button", { class: "opt", "aria-pressed": String(app.draft.priorities.includes(o.id)), onclick: () => { toggle(app.draft.priorities, o.id, 2); renderDrop(); } }, o.label))));
    wrap.append(nav(true, "Next", next));
  } else {
    wrap.append(h("h2", { class: "qprompt", tabindex: "-1" }, "Anything else we should know?"), h("p", { class: "qhelp" }, "Optional. Write a line about a good Sunday. We pull interests out of it."));
    const ta = h("textarea", { rows: 4, maxlength: 400, "aria-label": "About you", placeholder: "A long trek, filter coffee, and then a movie." });
    ta.value = app.draft.about;
    ta.addEventListener("input", () => { app.draft.about = ta.value; });
    const box = h("div", { class: "field" }, ta);
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SR) {
      const mic = h("button", { class: "linkbtn", type: "button", style: "margin-top:8px" }, "Speak instead");
      mic.addEventListener("click", () => {
        const rec = new SR(); rec.lang = "en-IN"; mic.textContent = "Listening";
        rec.onresult = (e) => { ta.value = (ta.value + " " + e.results[0][0].transcript).trim(); app.draft.about = ta.value; };
        rec.onend = () => { mic.textContent = "Speak instead"; };
        try { rec.start(); } catch (e) { mic.textContent = "Speak instead"; }
      });
      box.append(mic);
    }
    wrap.append(box, nav(true, "Build my drop", submit));
  }
  return wrap;
}
function focusPrompt() { const p = $(".qprompt"); if (p) p.focus({ preventScroll: true }); window.scrollTo(0, 0); }
function toggle(arr, v, max) {
  const i = arr.indexOf(v);
  if (i >= 0) arr.splice(i, 1);
  else { if (arr.length >= max) arr.shift(); arr.push(v); }
}

function basicsStep(next) {
  const b = app.draft.basics, form = h("div", { class: "form" });
  const err = h("p", { class: "errtxt", role: "alert" });
  const text = (label, key) => { const i = h("input", { type: "text", maxlength: 40, id: "f-" + key, autocomplete: "given-name" }); i.value = b[key]; i.addEventListener("input", () => { b[key] = i.value; }); return h("div", { class: "field" }, h("label", { for: "f-" + key }, label), i); };
  const num = (key, label) => { const i = h("input", { type: "number", min: 18, max: 60, id: "f-" + key, "aria-label": label }); i.value = b[key]; i.addEventListener("input", () => { b[key] = parseInt(i.value, 10) || 0; }); return i; };
  const sel = (key, opts, label) => { const e = h("select", { id: "f-" + key }, opts.map(([v, t]) => h("option", { value: v }, t))); e.value = String(b[key]); e.addEventListener("change", () => { b[key] = typeof b[key] === "number" ? parseInt(e.value, 10) : e.value; }); return h("div", { class: "field" }, h("label", { for: "f-" + key }, label), e); };
  const seeking = h("div", { class: "field" }, h("span", { class: "lab" }, "You would like to meet"), h("div", { class: "pillrow" }, [["man", "Men"], ["woman", "Women"], ["nonbinary", "Non-binary people"]].map(([v, t]) => h("button", { class: "pill", type: "button", "aria-pressed": String(b.seeking.includes(v)), onclick: (e) => { toggle(b.seeking, v, 3); e.currentTarget.setAttribute("aria-pressed", String(b.seeking.includes(v))); } }, t))));
  form.append(
    h("h2", { class: "qprompt", tabindex: "-1" }, "First, the basics"),
    text("First name", "name"),
    sel("gender", [["woman", "Woman"], ["man", "Man"], ["nonbinary", "Non-binary"]], "You are a"),
    seeking,
    h("div", { class: "field" }, h("span", { class: "lab" }, "Your age and the range you want"), h("div", { class: "inline" }, num("age", "Your age"), h("span", {}, "looking for"), num("age_min", "Lowest age"), h("span", {}, "to"), num("age_max", "Highest age"))),
    sel("city", app.Q.cities.map((c) => [c, c]), "City"),
    (() => { const c = h("input", { type: "checkbox", id: "f-od" }); c.checked = b.open_distance; c.addEventListener("change", () => { b.open_distance = c.checked; }); return h("div", { class: "field" }, h("label", { class: "checkrow", for: "f-od" }, c, "Open to meeting people in other cities")); })(),
    sel("intent", INTENTS, "What are you looking for?"),
    err,
    h("div", { class: "qnav" }, h("button", { class: "linkbtn", onclick: () => { app.step = -1; renderDrop(); } }, "Cancel"),
      h("button", { class: "btn", onclick: () => {
        if (!b.name.trim()) return void (err.textContent = "Add your first name.");
        if (!b.seeking.length) return void (err.textContent = "Choose who you would like to meet.");
        if (b.age < 18 || b.age > 60) return void (err.textContent = "Age must be between 18 and 60.");
        if (b.age_min < 18 || b.age_max > 60 || b.age_min > b.age_max) return void (err.textContent = "Check your age range. It must sit between 18 and 60, lowest first.");
        next();
      } }, "Next")));
  return form;
}

function boundariesStep(next, back) {
  const b = app.draft.basics;
  const check = (key, label, hint) => { const c = h("input", { type: "checkbox", id: "b-" + key }); c.checked = b[key]; c.addEventListener("change", () => { b[key] = c.checked; }); return h("div", { class: "field" }, h("label", { class: "checkrow", for: "b-" + key }, c, label), h("p", { class: "hint", style: "margin:4px 0 0 30px" }, hint)); };
  const campus = h("select", { id: "b-campus" }, h("option", { value: "" }, "No college email"), app.Q.campuses.map((c) => h("option", { value: c }, c)));
  campus.value = b.campus; campus.addEventListener("change", () => { b.campus = campus.value; });
  return h("div", { class: "form" },
    h("h2", { class: "qprompt", tabindex: "-1" }, "Who can ever see you?"),
    h("p", { class: "qhelp" }, "Every boundary you set is a hard rule. More rules mean fewer people to match, and your drop will tell you what each one costs."),
    h("div", { class: "field" }, h("label", { for: "b-campus" }, "Your college ", h("span", { class: "hint" }, "(demo: no real email is checked)")), campus),
    check("strict_intent", "Only people looking for the same thing", "Skips anyone even one step apart on what they want."),
    check("private", "Family-privacy mode", "Never shown to people from your own college, so no one you know sees you. Needs a college above."),
    check("verified_only", "Only people with a verified college email", "Fewer people, fewer fake accounts."),
    h("div", { class: "qnav" }, h("button", { class: "linkbtn", onclick: back }, "Back"), h("button", { class: "btn", onclick: next }, "Next")));
}

async function submit() {
  const root = $("#view-drop");
  root.replaceChildren(h("div", { class: "working", role: "status" }, h("h2", {}, "Running this week's drop"), h("p", {}, "Matching you against the whole pool, not just the first person who fits."), h("div", { class: "dots", "aria-hidden": "true" }, h("i"), h("i"), h("i"))));
  try {
    const res = await api("/api/profile", { basics: app.draft.basics, answers: app.draft.answers, humor: app.draft.humor, interests: app.draft.interests, priorities: app.draft.priorities, about: app.draft.about });
    app.sid = res.sid; store("sid", res.sid);
    app.data = await api("/api/drop/" + res.sid);
    app.fresh = true;
    app.ui = { rating: null, closing: false, reporting: false, levers: null };
    renderDrop();
    window.scrollTo(0, 0);
  } catch (e) {
    app.step = 0; renderDrop();
    $("#view-drop").prepend(h("p", { class: "errtxt", role: "alert" }, e.message));
  }
}

/* ------------------------------------------------------------------ the drop */
async function act(fn, reset) {
  try {
    app.data = await fn(); app.fresh = false;
    if (reset) app.ui = { rating: null, closing: false, reporting: false, levers: null };
    renderDrop();
  } catch (e) {
    if (e.status === 404) { app.sid = null; app.data = null; app.step = -1; store("sid", null); renderDrop(); return; }
    const box = $(".actions") || $(".note"); if (box) box.append(h("p", { class: "errtxt", role: "alert" }, e.message));
  }
}
const post = (path, body) => () => api(`/api/drop/${app.sid}/${path}`, body || {});

function dropView() {
  const d = app.data;
  const grid = h("div", { class: "dropgrid" });
  grid.append(d.intro ? introNote(d) : emptyNote(d), sidePanel(d));
  return grid;
}

function emptyNote(d) {
  const u = d.unmatched || { text: "", reason: "no_eligible" };
  return h("div", { class: "note" + (app.fresh ? " drop-in" : "") },
    h("div", { class: "kicker" }, h("span", {}, "Week " + d.week), h("b", {}, "No drop this week")),
    h("h2", { class: "name" }, REASON_WORDS[u.reason] || "No introduction this week"),
    h("p", {}, u.text),
    h("div", { class: "scribble" }, d.waited > 0 ? `You have waited ${d.waited} ${d.waited === 1 ? "week" : "weeks"}. That counts in your favor.` : "Nothing was wrong with your profile."),
    h("p", {}, h("button", { class: "linkbtn", onclick: loadLevers }, "What would widen your options?")),
    leversBox(),
    h("p", { class: "privacy" }, `This week the pool had ${d.week_stats.pool} people and ${d.week_stats.intros} introductions went out.`));
}

function introNote(d) {
  const it = d.intro, o = it.other, ex = it.explain;
  const note = h("div", { class: "note" + (app.fresh ? " drop-in" : "") });
  note.append(h("div", { class: "kicker" }, h("span", {}, "Week " + d.week + (d.waited ? `, after ${d.waited} ${d.waited === 1 ? "week" : "weeks"} of waiting` : "")), h("b", {}, it.tier + " fit")));
  note.append(h("h2", { class: "name" }, (o.full_name || o.first_name) + ", " + o.age));
  note.append(h("p", { class: "meta" }, `${o.city}, ${o.humor} humor`));
  note.append(h("ul", { class: "chips" }, o.interests.map((t) => h("li", {}, t)),
    o.verified ? h("li", { class: "ok" }, o.campus ? "Verified: " + o.campus : "College verified") : h("li", { class: "dim" }, "Not verified"),
    o.new_account ? h("li", { class: "warn" }, "New account") : null));
  if (o.watch && o.watch.length) {
    note.append(h("div", { class: "caution", role: "alert" }, h("b", {}, "Take care with this one. "), `Our checks flagged: ${o.watch.join(", ")}. Keep chatting on Aymora, never send money, and report them if anything feels off.`));
  }
  note.append(h("div", { class: "score-line" }, h("span", { class: "big" }, Math.round(it.score * 100)), h("span", {}, `Mutual fit. You rate them ${Math.round(it.your_fit * 100)}, they rate you ${Math.round(it.their_fit * 100)}.`)));
  note.append(h("ul", { class: "why" }, ex.reasons.map((r) => h("li", {}, HEART(), h("span", {}, r)))));
  if (ex.watch_out) note.append(h("div", { class: "scribble" }, "Heads up: " + ex.watch_out));

  const wsum = GROUPS.reduce((a, g) => a + ex.weights[g], 0) || 1;
  note.append(h("div", { class: "strip", role: "img", "aria-label": "Fit by area: " + GROUPS.map((g) => `${GROUP_NAME[g]} ${Math.round(ex.groups[g] * 100)}`).join(", ") },
    GROUPS.map((g) => h("div", { class: "row" }, h("span", {}, GROUP_NAME[g]), h("div", { class: "track", style: `height:${6 + (ex.weights[g] / wsum) * 40}px` }, h("div", { class: "fill", style: `width:${ex.groups[g] * 100}%` })), h("span", { class: "val" }, Math.round(ex.groups[g] * 100))))));
  note.append(h("p", { class: "strip-cap" }, "Bar length is the fit. Bar thickness is how much that area matters to you."));
  note.append(h("div", { class: "two" }, h("div", {}, h("h3", {}, "A first line"), h("p", {}, ex.opener)), h("div", {}, h("h3", {}, "A first date"), h("p", {}, ex.date_idea))));

  if (it.reported) {
    note.append(h("div", { class: "reveal", style: "border-color:var(--ink-2)" }, h("h3", { style: "color:var(--ink)" }, "Reported"), h("p", {}, "They will never appear in your drops again. In this demo nobody reviews reports. In a real launch a person would, and you would see the result right here.")));
    return note;
  }
  const actions = h("div", { class: "actions" });
  if (it.status === "pending" && it.you === "pending") {
    actions.append(h("button", { class: "btn", onclick: () => act(post("respond", { action: "in" })) }, "I'm in"),
      h("button", { class: "btn ghost", onclick: () => act(post("respond", { action: "pass" })) }, "Pass"));
    note.append(actions, h("p", { class: "privacy" }, "Your answer stays private unless you both say yes. Photos and numbers open later, in stages."), reportBox(it));
  } else if (it.status === "mutual") {
    note.append(h("div", { class: "reveal" }, h("h3", {}, "It's mutual"), h("p", {}, `${o.full_name} said yes too.`), o.bio ? h("p", {}, o.bio) : null,
      h("div", { class: "opener-box" }, h("p", {}, ex.opener), h("button", { class: "btn ghost", onclick: (e) => copy(ex.opener, e.currentTarget) }, "Copy line"))));
    note.append(stages(it, o), closureBox(it), reportBox(it));
  } else {
    const youPassed = it.you === "pass";
    note.append(h("div", { class: "reveal", style: "border-color:var(--ink-2)" }, h("h3", { style: "color:var(--ink)" }, youPassed ? "You passed" : "They passed this time"),
      h("p", {}, youPassed ? "They are never told. Next week's drop starts fresh." : "They saw nothing about you beyond a name. Your next drop is already being built.")));
    note.append(feedback(d));
  }
  return note;
}

function copy(text, btn) {
  const done = () => { const t = btn.textContent; btn.textContent = "Copied"; setTimeout(() => { btn.textContent = t; }, 1400); };
  if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, done); else done();
}

/* staged reveal: names and bio, then photos, then numbers, each needs both people */
function stages(it, o) {
  const rv = it.reveal, box = h("div", { class: "stages" });
  const step = (label, state, body) => h("li", { class: "stage " + state }, h("div", { class: "stage-head" }, h("b", {}, label), h("span", { class: "stage-state" }, { done: "Open", now: "Up next", wait: "Locked" }[state])), body);
  const photosOpen = rv.photos === "open", numbersOpen = rv.numbers === "open";
  const photoBody = photosOpen
    ? h("div", { class: "photo-tile" }, h("span", { class: "initials", "aria-hidden": "true" }, o.full_name.split(" ").map((x) => x[0]).join("")), h("p", {}, "Photos would appear here. This prototype has none, on purpose: chemistry first."))
    : h("div", {}, h("p", {}, rv.photos === "declined" ? `${o.first_name} would like to wait a little longer. You can ask again.` : "Both of you agree before photos open."),
      h("button", { class: "btn ghost", onclick: () => act(post("reveal", { step: "photos" })) }, rv.photos === "declined" ? "Ask again" : "Share photos"));
  const numBody = numbersOpen
    ? h("p", {}, "Numbers are shared. In a real app they would appear here.")
    : photosOpen ? h("div", {}, h("p", {}, rv.numbers === "declined" ? `${o.first_name} is not ready to share a number yet.` : "Phone numbers only change hands when both of you tap."),
      h("button", { class: "btn ghost", onclick: () => act(post("reveal", { step: "numbers" })) }, rv.numbers === "declined" ? "Ask again" : "Share numbers"))
      : h("p", {}, "Opens after photos.");
  box.append(h("ol", {}, step("Names and bio", "done", h("p", {}, "Opened by your mutual yes.")), step("Photos", photosOpen ? "done" : "now", photoBody), step("Numbers", numbersOpen ? "done" : photosOpen ? "now" : "wait", numBody)));
  if (it.safety_plan) {
    const sp = it.safety_plan;
    box.append(h("div", { class: "plan" }, h("h3", {}, "Before you meet"), h("ul", {}, sp.tips.map((t) => h("li", {}, t))),
      h("div", { class: "opener-box" }, h("p", {}, sp.share_text), h("button", { class: "btn ghost", onclick: (e) => copy(sp.share_text, e.currentTarget) }, "Copy message to a friend"))));
  }
  return box;
}

/* closure protocol: a kind close beats a silent one */
function closureBox(it) {
  const oc = it.outcome, box = h("div", { class: "fb closure" });
  if (oc && oc.kind === "met") return box.appendChild(h("p", { class: "noted" }, app.data.note || "Glad you met. Your next drop will lean on what worked.")) && box;
  if (oc && oc.kind === "closed") return box.appendChild(h("p", { class: "noted" }, app.data.note || "Closed kindly. They hear a gentle goodbye, not silence.")) && box;
  box.append(h("h3", {}, "Where are things?"),
    h("p", { class: "hint" }, "If nobody replies for 72 hours the introduction closes itself, and a pattern of going quiet lowers your priority a little."),
    h("div", { class: "pillrow" },
      h("button", { class: "pill", "aria-pressed": String(oc && oc.kind === "talking"), onclick: () => act(post("outcome", { kind: "talking" })) }, "We're talking"),
      h("button", { class: "pill", onclick: () => act(post("outcome", { kind: "met" })) }, "We met"),
      h("button", { class: "pill", "aria-pressed": String(app.ui.closing), onclick: () => { app.ui.closing = !app.ui.closing; renderDrop(); } }, "Close kindly")));
  if (oc && oc.kind === "talking") box.append(h("p", { class: "noted" }, "Good. Tell us when you meet, or close it kindly if it fades."));
  if (app.ui.closing) {
    box.append(h("h3", { style: "margin-top:14px" }, "What was it?"), h("div", { class: "pillrow" }, CLOSE_REASONS.map(([v, t]) => h("button", { class: "pill", onclick: () => act(post("outcome", { kind: "closed", reason: v }), true) }, t))));
  }
  return box;
}

function reportBox(it) {
  const box = h("div", { class: "reportbox" });
  box.append(h("button", { class: "linkbtn", onclick: () => { app.ui.reporting = !app.ui.reporting; renderDrop(); } }, "Report this account"));
  if (app.ui.reporting) box.append(h("div", { class: "pillrow", style: "margin-top:10px" }, REPORT_REASONS.map((r) => h("button", { class: "pill", onclick: () => act(post("report", { reason: r }), true) }, r))));
  return box;
}

function feedback(d) {
  const box = h("div", { class: "fb" });
  if (d.intro.feedback_given) { box.append(h("p", { class: "noted" }, d.note || "Thanks. Your next drop will take that into account.")); return box; }
  box.append(h("h3", {}, "How was this introduction?"));
  const send = (rating, reason) => act(async () => { const v = await api(`/api/drop/${app.sid}/feedback`, { rating, reason }); app.ui.rating = null; return v; });
  box.append(h("div", { class: "pillrow" }, [["great", "Great"], ["fine", "Fine"], ["no", "Not for me"]].map(([v, t]) => h("button", { class: "pill", "aria-pressed": String(app.ui.rating === v), onclick: () => { if (v === "no") { app.ui.rating = "no"; renderDrop(); } else send(v, null); } }, t))));
  if (app.ui.rating === "no") {
    box.append(h("h3", { style: "margin-top:14px" }, "What was off?"), h("div", { class: "pillrow" }, GROUPS.map((g) => h("button", { class: "pill", onclick: () => send("no", g) }, GROUP_NAME[g])), h("button", { class: "pill", onclick: () => send("no", null) }, "Not sure")));
  }
  return box;
}

async function loadLevers() {
  try { app.ui.levers = (await api(`/api/drop/${app.sid}/levers`)).levers; } catch (e) { app.ui.levers = []; }
  renderDrop();
}
function leversBox() {
  const L = app.ui.levers;
  if (!L) return null;
  if (!L.length) return h("p", { class: "hint" }, "Nothing you could loosen would add people right now.");
  return h("ul", { class: "levers" }, L.map((l) => h("li", {}, h("b", {}, l.change), h("span", {}, l.viable_after > l.viable_before ? `People who clear the floor: ${l.viable_before} to ${l.viable_after}` : `No change: ${l.viable_before} people clear the floor`))));
}

function sidePanel(d) {
  const side = h("aside", { class: "side", "aria-label": "About this drop" });
  const prior = app.Q.survey.weights, tot = Object.values(prior).reduce((a, b) => a + b, 0);
  side.append(h("section", {}, h("h3", {}, "What your drop weighs"),
    h("p", {}, "Starts from what Aymora's own survey found people care about. Your priorities and your feedback move it. The tick marks the survey's starting point."),
    h("div", { class: "wts" }, GROUPS.map((g) => h("div", { class: "row" }, h("span", {}, GROUP_NAME[g]), h("div", { class: "track" }, h("div", { class: "fill", style: `width:${(d.weights[g] / 0.6) * 100}%` }), h("div", { class: "tick", style: `left:${(prior[g] / tot / 0.6) * 100}%` }))))),
    h("p", {}, "Physical appearance (27% in the survey) is left out on purpose. This engine only matches on what the survey calls compatibility."),
    d.notes.length ? h("p", { class: "noted" }, d.notes[d.notes.length - 1]) : null));

  const hb = d.held_back, pr = d.profile;
  const rules = [pr.strict_intent && "same intent only", pr.private && "family-privacy mode", pr.verified_only && "verified only", pr.open_distance && "open to other cities"].filter(Boolean);
  side.append(h("section", {}, h("h3", {}, "Safety this week"),
    h("p", {}, `${hb.this_week} ${hb.this_week === 1 ? "account was" : "accounts were"} held back before matching this week, ${hb.total} so far.` + (hb.top_reasons.length ? ` Typical signs: ${hb.top_reasons.join("; ")}.` : "")),
    h("p", {}, rules.length ? "Your rules: " + rules.join(", ") + "." : "You have not set any extra rules."),
    h("p", { style: "margin-bottom:8px" }, h("button", { class: "linkbtn", onclick: loadLevers }, "Why not more options?")), leversBox()));

  side.append(h("section", {}, h("h3", {}, "This week in the pool"),
    h("p", {}, `${d.pool} people are in the pool. ${d.week_stats.intros * 2} of the ${d.week_stats.pool} who were waiting got an introduction, ${pct(d.week_stats.covered)} of them.`)));
  side.append(h("section", {}, h("h3", {}, "Your weeks so far"),
    d.log.length ? h("ul", { class: "log" }, d.log.map((l) => h("li", {}, `Week ${l.week}: ` + logText(l)))) : h("p", {}, "This is your first week.")));
  side.append(h("section", {}, h("div", { class: "demo" }, h("h3", {}, "Demo controls"), h("p", {}, "Real weeks take seven days. Jump ahead to see waiting priority, closure and learning take effect."),
    h("div", { class: "pillrow" },
      h("button", { class: "btn ghost", disabled: d.week >= 12, onclick: () => act(post("next-week"), true) }, "Jump to next week"),
      h("button", { class: "btn ghost", onclick: () => act(post("demo-scam"), true) }, "Simulate a scam attempt")),
    h("p", { style: "margin:12px 0 0" }, h("button", { class: "linkbtn", onclick: () => { app.sid = null; app.data = null; app.step = -1; app.draft.answers = {}; app.draft.humor = []; app.draft.interests = []; app.draft.priorities = []; store("sid", null); renderDrop(); } }, "Start over with a new profile")))));
  return side;
}
function logText(l) {
  if (l.status === "none") return "no introduction (" + (REASON_WORDS[l.reason] || "none fit").toLowerCase() + ")";
  const w = {
    mutual: "mutual yes with " + l.name, closed: "did not go ahead with " + l.name, expired: "left " + l.name + " unanswered",
    quiet: "went quiet with " + l.name + ", closed after 72 hours", talking: "still talking with " + l.name, met: "met " + l.name,
    reported: "reported " + l.name,
  }[l.status] || l.status;
  return w + ", " + l.tier.toLowerCase();
}

/* ------------------------------------------------------------------ how it works */
function renderHow() {
  const root = $("#view-how");
  const step = (t, p) => h("li", {}, h("div", {}, h("h3", {}, t), h("p", {}, p)));
  root.append(h("div", { class: "how" },
    h("h2", {}, "How a drop is made"),
    h("ol", { class: "steps" },
      step("Who can be introduced", "Trust checks first: accounts that look like bots or scams are held back before matching, and borderline ones carry a caution banner. Then hard rules run both ways: gender, age range, city, relationship intent, your own boundaries, and nobody you have met before."),
      step("How well they fit", "Ten scenario answers become trait scores. Traits, humor and interests roll up into four areas: vibe, communication, values and interests, and humor. Each person weighs those areas their own way, starting from Aymora's survey (73, 64, 48 and 42) and shifted by what they say matters and what they tell us about past introductions. The pair's fit is the geometric mean of both views, so a lopsided pair scores low."),
      step("Who clears the bar", "A pair needs a mutual fit above the floor, 0.62 at the start. Each week someone has waited lowers their floor by 0.03, never below 0.55. A pattern of going quiet after a mutual yes costs a little priority."),
      step("Best set of pairs", "A maximum weight matching picks the set of pairs with the highest total value across the whole pool. Nobody gets more than one introduction a week, so nobody is flooded and nobody is skipped because someone else is popular."),
      step("Opens in stages", "A mutual yes opens names and a short bio. Photos open only when both tap. Numbers open only when both tap again, with a safety plan for the first meeting. Closing kindly, with a reason, beats going silent, and the reason teaches your own weights.")),
    h("div", { class: "cols" },
      h("div", {}, h("h3", {}, "What is real in this prototype"), h("ul", {}, h("li", {}, "The matching, the floor, the waiting rule and the simulator."), h("li", {}, "The ceiling calculation: the most any policy could deliver, so the promise report is not marking its own homework."), h("li", {}, "The trust score, with its precision and recall measured on synthetic accounts."), h("li", {}, "The learning loop. Your feedback and your closures change your own weights, within limits."), h("li", {}, "An optional language model layer that reads your free text and softens the explanations. It is off here, and the engine never depends on it."))),
      h("div", {}, h("h3", {}, "What is not"), h("ul", {}, h("li", {}, "Every person in the pool is synthetic, and their replies to you are drawn from a model."), h("li", {}, "College verification, photos, numbers and the report review are mocked. A real build checks .ac.in and .edu.in email domains and has a person review reports."), h("li", {}, "Rates of scams, reporting and ghosting in the engine room are assumptions you can change, not measurements."), h("li", {}, "No accounts or chat. State lives in memory and resets when the server restarts."))))));
}

boot();
