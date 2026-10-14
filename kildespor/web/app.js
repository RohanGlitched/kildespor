/* Kildespor viewer: find, compare and verify company facts. Works from file:// (data loaded as scripts). */
(function () {
  "use strict";
  const KS = window.KS;
  const FAM = KS.families; // [[key,label],...]
  const $ = (s, r = document) => r.querySelector(s);
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fold = (v) => String(v ?? "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/æ/g, "ae").replace(/ø/g, "o").replace(/å/g, "a");
  const nf = new Intl.NumberFormat("en-GB");
  const STATE_WORD = { available: "Found", not_available: "Checked, nothing found", blocked: "Source refused access", ambiguous: "Could not confirm it is this company", failed: "Source failed this run", not_applicable: "Does not apply" };
  const cache = {};
  const loading = {};
  let compare = [];
  try { compare = JSON.parse(localStorage.getItem("ks-compare") || "[]"); } catch (e) { compare = []; }
  const filters = { q: "", site: false, jobs: false, changed: false, social: false, sort: "evidence" };

  KS.put = function (env) {
    cache[env.organisation_number] = env;
    (loading[env.organisation_number] || []).forEach((f) => f(env));
    delete loading[env.organisation_number];
  };
  function load(org) {
    if (cache[org]) return Promise.resolve(cache[org]);
    return new Promise((resolve, reject) => {
      if (loading[org]) { loading[org].push(resolve); return; }
      loading[org] = [resolve];
      const s = document.createElement("script");
      s.src = "data/c/" + org + ".js";
      s.onerror = () => { delete loading[org]; reject(new Error("Profile file missing for " + org)); };
      document.head.appendChild(s);
    });
  }

  function money(v, cur) {
    if (v == null) return "—";
    const a = Math.abs(v), s = v < 0 ? "−" : "";
    const c = cur && cur !== "NOK" ? " " + cur : "";
    if (a >= 1e9) return s + "NOK " + (a / 1e9).toFixed(1) + " bn" + c;
    if (a >= 1e6) return s + "NOK " + (a / 1e6).toFixed(1) + " m" + c;
    if (a >= 1e3) return s + "NOK " + Math.round(a / 1e3) + " k" + c;
    return s + "NOK " + nf.format(a) + c;
  }
  function ribbon(states, big) {
    if (!big) return '<span class="ribbon" aria-hidden="true">' + states.map((s) => '<i class="' + s + '"></i>').join("") + "</span>";
    return '<div class="ribbon big" role="list" aria-label="What was found, by information type">' + FAM.map(([k, label], i) =>
      '<div class="cell" role="listitem"><i class="' + states[i].state + '"></i><span><b>' + esc(label) + "</b><br>" +
      (states[i].state === "available" ? states[i].claims + " fact" + (states[i].claims === 1 ? "" : "s") : esc(STATE_WORD[states[i].state] || states[i].state)) + "</span></div>").join("") + "</div>";
  }

  /* ---------- list ---------- */
  function rows() {
    const q = fold(filters.q).trim();
    let r = KS.index.filter((x) => (!q || fold([x.name, x.org, x.muni, x.industry, x.domain].join(" ")).includes(q)) &&
      (!filters.site || x.domain) && (!filters.jobs || x.jobs > 0) && (!filters.changed || x.changes > 0) && (!filters.social || x.social > 0));
    const by = { evidence: (a, b) => b.facts - a.facts, name: (a, b) => a.name.localeCompare(b.name, "nb"), revenue: (a, b) => (b.revenue ?? -1e18) - (a.revenue ?? -1e18), changes: (a, b) => b.changes - a.changes };
    return r.sort(by[filters.sort] || by.evidence);
  }
  function renderList(current) {
    const r = rows();
    $("#count").textContent = r.length === KS.index.length ? nf.format(r.length) + " companies" : nf.format(r.length) + " of " + nf.format(KS.index.length);
    const html = r.slice(0, 600).map((x) =>
      '<button class="row" data-org="' + x.org + '"' + (x.org === current ? ' aria-current="true"' : "") + ">" +
      '<span class="nm">' + esc(x.name) + "</span>" +
      '<label class="cmp" onclick="event.stopPropagation()"><input type="checkbox" data-cmp="' + x.org + '"' + (compare.includes(x.org) ? " checked" : "") + ' aria-label="Compare ' + esc(x.name) + '"> compare</label>' +
      '<span class="sub">' + esc([x.org, x.muni, x.industry].filter(Boolean).join(" · ")) + "</span>" + ribbon(x.ribbon) + "</button>").join("");
    $("#rows").innerHTML = html || '<p class="empty">No company matches. Clear a filter or search by organisation number.</p>';
    renderCmpBar();
  }
  function renderCmpBar() {
    const bar = $("#cmpbar");
    if (!compare.length) { bar.hidden = true; return; }
    bar.hidden = false;
    $("#cmpn").textContent = compare.length + " selected";
    $("#cmpgo").disabled = compare.length < 2;
  }

  /* ---------- profile ---------- */
  function evHtml(env, ids) {
    const byId = env._ev || (env._ev = Object.fromEntries(env.evidence.map((e) => [e.id, e])));
    return ids.map((id) => byId[id]).filter(Boolean).map((e) =>
      '<div class="ev"><div><span class="span">' + esc(e.claim_span) + "</span></div>" +
      '<div><a href="' + esc(e.source_url) + '" target="_blank" rel="noreferrer noopener">' + esc(e.source_name || e.source_url) + "</a> · " + esc(e.source_url) + "</div>" +
      '<div class="meta"><span>Retrieved ' + esc(e.retrieved_at) + "</span><span>" + esc(e.source_class.replace(/_/g, " ")) + "</span><span>Method: " + esc(e.extraction_method) +
      '</span><span>SHA-256 <code title="' + esc(e.content_sha256) + '">' + esc(e.content_sha256.slice(0, 12)) + "…</code></span></div></div>").join("");
  }
  function fmtValue(c) {
    const v = c.value;
    if (v == null) return "—";
    if (typeof v !== "object") {
      if (c.field === "registered_website" || /^https?:/.test(String(v))) return '<a href="' + esc(/^https?:/.test(v) ? v : "https://" + v) + '" target="_blank" rel="noreferrer noopener">' + esc(v) + "</a>";
      if (c.field === "phone" || c.field.endsWith("phone") || c.field.endsWith("mobile")) return esc(String(v).replace(/^(\d{2})(\d{2})(\d{2})(\d{2})$/, "$1 $2 $3 $4"));
      return esc(Array.isArray(v) ? v.join(", ") : v);
    }
    if (Array.isArray(v)) return esc(v.join(", "));
    if (v.title && "amount" in v && !("year" in v)) return (v.url ? '<a href="' + esc(v.url) + '" target="_blank" rel="noreferrer noopener">' + esc(v.title) + "</a>" : esc(v.title)) + (v.amount != null ? ' <span class="lb">' + money(v.amount, v.currency) + "</span>" : "");
    if ("amount" in v && "year" in v) return money(v.amount, v.currency) + ' <span class="lb">' + esc(v.year) + "</span>";
    if ("amount" in v) return money(v.amount, v.currency) + (v.shares ? ' <span class="lb">' + nf.format(v.shares) + " shares</span>" : "");
    if (v.id && v.url && v.label) return '<a href="' + esc(v.url) + '" target="_blank" rel="noreferrer noopener">' + esc(v.label) + "</a> " + '<span class="lb">' + esc(v.id) + "</span>";
    if (v.url && (v.platform || v.domain)) return '<a href="' + esc(v.url) + '" target="_blank" rel="noreferrer noopener">' + esc(v.domain || v.url.replace(/^https?:\/\/(www\.)?/, "")) + "</a>" + (v.identity_proof ? '<span class="tag">proof: ' + esc(v.identity_proof.join(", ")) + "</span>" : "");
    if (v.year && v.format === "pdf") return '<a href="' + esc(v.url) + '" target="_blank" rel="noreferrer noopener">Annual accounts ' + esc(v.year) + " (PDF)</a>";
    if (v.title) return (v.url ? '<a href="' + esc(v.url) + '" target="_blank" rel="noreferrer noopener">' + esc(v.title) + "</a>" : esc(v.title)) +
      (v.status ? '<span class="tag ' + (v.status === "closed" ? "closed" : "") + '">' + esc(v.status) + "</span>" : "") +
      (v.location ? ' <span class="lb">' + esc(v.location) + "</span>" : "");
    if (v.name && v.role) return esc(v.name) + (v.kind === "organisation" ? ' <span class="lb">(organisation' + (v.organisation_number ? " " + esc(v.organisation_number) : "") + ")</span>" : "");
    if (v.organisation_number && v.address !== undefined) return esc(v.name || "") + '<br><span class="lb">' + esc(v.address) + (v.registered_employees != null ? " · " + esc(v.registered_employees) + " registered employees" : "") + "</span>";
    if (v.label) return esc(v.label);
    return esc(JSON.stringify(v));
  }
  function claimLi(env, c) {
    const id = "e" + Math.random().toString(36).slice(2, 9);
    let when = c.effective_date || c.reporting_period || "";
    if (typeof c.value === "string" && String(when).slice(0, 10) === c.value.slice(0, 10)) when = "";
    return '<li class="claim"><div><div class="lb">' + esc(c.label) + (c.relationship && c.relationship !== "exact" ? ' <span class="tag">' + esc(c.relationship.replace(/_/g, " ")) + "</span>" : "") +
      (c.carried_forward ? ' <span class="tag closed">kept from previous run</span>' : "") + '</div><div class="vl">' + fmtValue(c) + "</div></div>" +
      (when ? '<span class="when">' + esc(String(when).replace("..", " – ")) + "</span>" : "") +
      '<span class="src"><button class="srcbtn" aria-expanded="false" aria-controls="' + id + '" data-ev="' + esc(c.evidence_ids.join(",")) + '">Source</button></span>' +
      '<div id="' + id + '" hidden></div></li>';
  }
  function famSection(env, fam, title, body) {
    const st = env.field_states.find((s) => s.family === fam) || { state: "not_available" };
    const claims = env.claims.filter((c) => c.family === fam);
    let inner = body !== undefined ? body : claims.length ? '<ul class="claims">' + claims.map((c) => claimLi(env, c)).join("") + "</ul>" : "";
    if (!claims.length) inner = '<div class="empty"><b>' + esc(STATE_WORD[st.state] || st.state) + ".</b> " + esc(st.note || "") +
      (st.checked_sources && st.checked_sources.length ? '<div class="checked">Checked: ' + esc(st.checked_sources.join("; ")) + "</div>" : "") + "</div>";
    return '<section class="fam" id="f-' + fam + '"><header><h2>' + esc(title) + '</h2><span class="state ' + st.state + '">' + esc(st.state === "available" ? claims.length + " fact" + (claims.length === 1 ? "" : "s") : STATE_WORD[st.state] || st.state) + "</span></header>" + inner + "</section>";
  }
  function finSection(env) {
    const fin = env.claims.filter((c) => c.family === "financials" && c.value && "amount" in c.value);
    const pdfs = env.claims.filter((c) => c.field === "annual_report_copy").sort((a, b) => b.value.year.localeCompare(a.value.year));
    if (!fin.length && !pdfs.length) return famSection(env, "financials", "Annual accounts");
    const pdfHtml = pdfs.length ? '<div class="checked" style="padding:10px 0 4px">Filed copies (PDF): ' + pdfs.map((c) => '<a href="' + esc(c.value.url) + '" target="_blank" rel="noreferrer noopener">' + esc(c.value.year) + "</a>").join(" · ") + "</div>" : "";
    if (!fin.length) return '<section class="fam" id="f-financials"><header><h2>Annual accounts</h2><span class="state available">' + pdfs.length + ' filed copies</span></header><div class="fin">' + pdfHtml + "</div></section>";
    const years = [...new Set(fin.map((c) => c.value.year))].sort();
    const get = (f, y) => fin.find((c) => c.field === f && c.value.year === y);
    const rowsDef = [["revenue", "Operating revenue"], ["operating_result", "Operating result"], ["annual_result", "Annual result"], ["equity", "Equity"], ["total_assets", "Total assets"], ["total_debt", "Total debt"], ["payroll_cost", "Payroll costs"]];
    const rev = years.map((y) => (get("revenue", y) || {}).value?.amount ?? null);
    const res = years.map((y) => (get("annual_result", y) || {}).value?.amount ?? null);
    const maxv = Math.max(1, ...rev.filter((x) => x != null).map(Math.abs), ...res.filter((x) => x != null).map(Math.abs));
    const W = 520, H = 120, bw = Math.min(70, (W - 40) / years.length - 18);
    let svg = '<svg viewBox="0 0 ' + W + " " + (H + 26) + '" role="img" aria-label="Revenue and annual result by year">';
    svg += '<line x1="0" x2="' + W + '" y1="' + H / 2 + '" y2="' + H / 2 + '" stroke="var(--rule)"/>';
    years.forEach((y, i) => {
      const x = 20 + i * ((W - 40) / years.length);
      const r = rev[i], a = res[i];
      if (r != null) { const h = (Math.abs(r) / maxv) * (H / 2 - 6); svg += '<rect x="' + x + '" y="' + (r >= 0 ? H / 2 - h : H / 2) + '" width="' + bw + '" height="' + h + '" fill="var(--ink)" rx="1"><title>Revenue ' + y + ": " + money(r) + "</title></rect>"; }
      if (a != null) { const h = (Math.abs(a) / maxv) * (H / 2 - 6); svg += '<rect x="' + (x + bw + 4) + '" y="' + (a >= 0 ? H / 2 - h : H / 2) + '" width="' + bw / 2.5 + '" height="' + h + '" fill="' + (a >= 0 ? "var(--fjord)" : "var(--red)") + '" rx="1"><title>Annual result ' + y + ": " + money(a) + "</title></rect>"; }
      svg += '<text x="' + (x + bw / 2) + '" y="' + (H + 18) + '" font-size="12" fill="var(--ink-3)" text-anchor="middle">' + y + "</text>";
    });
    svg += "</svg>";
    let table = '<table><thead><tr><th>NOK</th>' + years.map((y) => "<th>" + y + "</th>").join("") + "<th></th></tr></thead><tbody>";
    rowsDef.forEach(([f, label]) => {
      const cells = years.map((y) => get(f, y));
      if (!cells.some(Boolean)) return;
      const ids = cells.filter(Boolean).flatMap((c) => c.evidence_ids);
      const id = "e" + Math.random().toString(36).slice(2, 9);
      table += "<tr><th>" + label + "</th>" + cells.map((c) => '<td class="' + (c && c.value.amount < 0 ? "neg" : "") + '">' + (c ? money(c.value.amount) : "—") + "</td>").join("") +
        '<td><button class="srcbtn" aria-expanded="false" aria-controls="' + id + '" data-ev="' + ids.join(",") + '">Source</button></td></tr><tr><td colspan="' + (years.length + 2) + '" style="padding:0;border:0"><div id="' + id + '" hidden></div></td></tr>';
    });
    table += "</tbody></table>" + pdfHtml;
    const st = env.field_states.find((s) => s.family === "financials");
    return '<section class="fam" id="f-financials"><header><h2>Annual accounts</h2><span class="state available">' + years.length + " year" + (years.length === 1 ? "" : "s") + ' filed</span></header><div class="fin">' + svg +
      '<div class="legend"><span><i class="available"></i>Operating revenue</span><span><i style="background:var(--fjord);border-color:var(--fjord)"></i>Annual result</span></div>' + table + "</div></section>";
  }
  function timeline(env) {
    const items = env.claims.filter((c) => (c.family === "activity" || c.field === "job_posting") && c.effective_date)
      .sort((a, b) => String(b.effective_date).localeCompare(String(a.effective_date)));
    const seen = new Set();
    const uniq = items.filter((c) => { const k = c.effective_date + (c.value && c.value.title); if (seen.has(k)) return false; seen.add(k); return true; });
    if (!uniq.length) return famSection(env, "activity", "Dated public activity");
    return '<section class="fam" id="f-activity"><header><h2>Dated public activity</h2><span class="state available">' + uniq.length + " dated item" + (uniq.length === 1 ? "" : "s") + '</span></header><ol class="tl">' +
      uniq.slice(0, 40).map((c) => { const id = "e" + Math.random().toString(36).slice(2, 9); return '<li><time datetime="' + esc(c.effective_date) + '">' + esc(c.effective_date) + '</time><div><span class="k">' + esc(c.label) + "</span>" + fmtValue(c) +
        '<div id="' + id + '" hidden></div></div><span class="srcwrap"><button class="srcbtn" aria-expanded="false" aria-controls="' + id + '" data-ev="' + esc(c.evidence_ids.join(",")) + '">Source</button></span></li>'; }).join("") + "</ol></section>";
  }
  function changesSection(env) {
    const ch = env.changes || [];
    const r = env.refresh || {};
    if (!r.previous_run_id) return '<section class="fam"><header><h2>Changes since the previous run</h2><span class="state">First run</span></header><div class="empty">This is the first run for this company. The next run will compare every fact against these and list what changed, with evidence for both sides.</div></section>';
    if (!ch.length) return '<section class="fam"><header><h2>Changes since the previous run</h2><span class="state available">No changes</span></header><div class="empty">Compared with run <b>' + esc(r.previous_run_id) + "</b> (" + esc(r.previous_completed_at || "") + "): every fact is unchanged." + (r.carried_forward ? " " + r.carried_forward + " fact(s) were kept from the previous run because their source failed or no longer lists them." : "") + "</div></section>";
    return '<section class="fam"><header><h2>Changes since the previous run</h2><span class="state available">' + ch.length + ' change(s)</span></header><ul class="claims">' + ch.map((e) =>
      '<li class="claim"><div><div class="lb">' + esc(e.type.replace(/_/g, " ")) + ' · <span class="tag">' + esc(e.materiality) + "</span></div><div class=\"vl\">" +
      (e.previous !== undefined ? "<s>" + esc(typeof e.previous === "object" ? (e.previous.title || e.previous.name || e.previous.url || JSON.stringify(e.previous)) : e.previous) + "</s> " : "") +
      (e.current !== undefined ? esc(typeof e.current === "object" ? (e.current.title || e.current.name || e.current.url || JSON.stringify(e.current)) : e.current) : "") + "</div></div></li>").join("") + "</ul></section>";
  }
  function renderProfile(env) {
    const s = env.summary || {};
    const states = FAM.map(([k]) => env.field_states.find((x) => x.family === k) || { state: "not_available", claims: 0 });
    const id = (f) => env.claims.find((c) => c.family === "identity" && c.field === f);
    const keyIdx = {};
    env.claims.forEach((c, i) => (keyIdx[c.key] = c));
    const famLabel = Object.fromEntries(FAM);
    const brief = (s.sentences || []).map((x) => {
      const fams = [...new Set((x.claim_keys || []).map((k) => keyIdx[k] && keyIdx[k].family).filter(Boolean))];
      return "<p>" + esc(x.text) + fams.map((f) => '<button class="cite" data-jump="' + esc(f) + '" title="Go to the sources: ' + esc(famLabel[f]) + '">↗ sources</button>').join("") + "</p>";
    }).join("");
    const unknown = (s.unknowns || []).map((f) => (FAM.find((x) => x[0] === f) || [f, f])[1].toLowerCase());
    const html =
      '<button class="back" data-back>← All companies</button>' +
      '<div class="hdr"><h1>' + esc(env.legal_name || env.organisation_number) + "</h1>" +
      '<div class="ids"><span>Org.nr <code>' + esc(env.organisation_number) + "</code></span>" + (id("legal_form") ? "<span>" + esc(id("legal_form").value) + "</span>" : "") +
      (id("municipality") ? "<span>" + esc(String(id("municipality").value)) + "</span>" : "") +
      '<span><a href="https://virksomhet.brreg.no/nb/oppslag/enheter/' + esc(env.organisation_number) + '" target="_blank" rel="noreferrer noopener">Brønnøysund record</a></span>' +
      '<span>Checked ' + esc((env.run || {}).completed_at || "") + "</span></div>" + ribbon(states, true) +
      '<div class="legend"><span><i class="available"></i>found</span><span><i class="not_available"></i>checked, nothing found</span><span><i class="ambiguous"></i>uncertain match, withheld</span><span><i class="blocked"></i>source refused</span><span><i class="failed"></i>source failed</span></div></div>' +
      '<div class="brief" aria-label="Summary">' + (brief || "<p>No supported summary.</p>") + (unknown.length ? '<p class="unknowns">Not found: ' + esc(unknown.join(", ")) + ".</p>" : "") + "</div>" +
      '<div class="grid">' +
      famSection(env, "identity", "Legal identity and brand") + finSection(env) + famSection(env, "people", "Leadership and board") +
      famSection(env, "locations", "Workplaces and addresses") + famSection(env, "website", "Verified website") + famSection(env, "social", "Company-owned profiles") +
      famSection(env, "contact", "Contact details") + famSection(env, "jobs", "Hiring") + timeline(env) + famSection(env, "description", "What it does") + changesSection(env) +
      "</div>" + foot();
    $("#main").innerHTML = html;
    document.title = (env.legal_name || env.organisation_number) + " · Kildespor";
  }
  function foot() {
    return '<footer class="foot">Every fact links to the page or record it came from, with the time we fetched it and a hash of what we saw. Facts we could not tie to this exact organisation number are withheld, not guessed. Sources: Brønnøysundregistrene (NLOD 2.0), the company\'s own website, NAV arbeidsplassen, Wikidata (CC0).</footer>';
  }

  /* ---------- compare ---------- */
  async function renderCompare(orgs) {
    const envs = await Promise.all(orgs.map((o) => load(o).catch(() => null)));
    const ok = envs.filter(Boolean);
    const pick = (e, fam, field) => e.claims.filter((c) => c.family === fam && (!field || c.field === field));
    const latest = (e, f) => { const c = pick(e, "financials", f).sort((a, b) => b.value.year.localeCompare(a.value.year))[0]; return c ? money(c.value.amount) + ' <span class="lb">' + c.value.year + "</span>" : "—"; };
    const rowsDef = [
      ["Industry", (e) => esc((pick(e, "identity", "industry")[0] || {}).value || "—")],
      ["Municipality", (e) => esc((pick(e, "identity", "municipality")[0] || {}).value || "—")],
      ["Founded", (e) => esc((pick(e, "identity", "founded")[0] || {}).value || "—")],
      ["Revenue", (e) => latest(e, "revenue")],
      ["Annual result", (e) => latest(e, "annual_result")],
      ["Equity", (e) => latest(e, "equity")],
      ["Daily manager", (e) => esc(pick(e, "people", "registered_role").filter((c) => c.value.role_code === "DAGL").map((c) => c.value.name).join(", ") || "—")],
      ["Chair", (e) => esc(pick(e, "people", "registered_role").filter((c) => c.value.role_code === "LEDE").map((c) => c.value.name).join(", ") || "—")],
      ["Workplaces", (e) => String(pick(e, "locations", "registered_subunit").length)],
      ["Website", (e) => { const c = pick(e, "website", "official_website")[0]; return c ? '<a href="' + esc(c.value.url) + '" target="_blank" rel="noreferrer noopener">' + esc(c.value.domain) + "</a>" : "—"; }],
      ["Profiles", (e) => esc([...new Set(pick(e, "social").map((c) => c.value.platform))].join(", ") || "—")],
      ["Open job ads", (e) => String(pick(e, "jobs", "job_posting").filter((c) => c.value.status !== "closed").length)],
      ["Latest dated activity", (e) => { const c = e.claims.filter((x) => x.family === "activity" && x.effective_date).sort((a, b) => b.effective_date.localeCompare(a.effective_date))[0]; return c ? esc(c.effective_date) + " · " + esc((c.value && c.value.title) || c.label) : "—"; }],
      ["Facts found", (e) => String(e.claims.length)],
    ];
    $("#main").innerHTML = '<button class="back" data-back>← All companies</button><div class="hdr"><h1>Compare ' + ok.length + " companies</h1><div class=\"ids\"><span>Every value is the same fact you can open on each profile, with its source.</span></div></div>" +
      '<div class="compare" style="margin-top:18px"><table><thead><tr><th></th>' + ok.map((e) => '<th><a href="#/c/' + e.organisation_number + '">' + esc(e.legal_name) + '</a><div class="lb">' + e.organisation_number + "</div></th>").join("") + "</tr></thead><tbody>" +
      rowsDef.map(([label, f]) => "<tr><th>" + label + "</th>" + ok.map((e) => "<td>" + f(e) + "</td>").join("") + "</tr>").join("") + "</tbody></table></div>" + foot();
    document.title = "Compare · Kildespor";
  }

  /* ---------- run overview ---------- */
  function renderAbout() {
    const r = KS.run;
    const n = r.companies || KS.index.length;
    const fam = FAM.map(([k, label]) => { const v = (r.companies_with_claims_by_family || {})[k] || 0; return '<div class="stat"><b>' + nf.format(v) + '</b><span>' + esc(label) + " · " + Math.round((v / n) * 100) + '% of companies</span><div class="bar"><i style="width:' + (v / n) * 100 + '%"></i></div></div>'; }).join("");
    $("#main").innerHTML = '<div class="about"><div class="hdr"><h1>Run ' + esc(r.run_id) + '</h1><div class="ids"><span>' + nf.format(n) + " companies</span><span>" + nf.format(r.claims || 0) + " facts</span><span>" + nf.format(r.evidence_records || 0) + " evidence records</span><span>" + esc(r.runtime_seconds) + " s</span><span>" + nf.format((r.operations || {}).requests || 0) + " requests</span><span>Third-party cost $" + ((r.operations || {}).third_party_cost_usd || 0) + "</span></div></div>" +
      "<h2>How many companies have facts of each type</h2><div class=\"statgrid\">" + fam + "</div>" +
      "<h2>How a fact gets in</h2><p>The organisation number is the anchor. Official records come from Brønnøysundregistrene. A website is published only when the site itself proves it belongs to this entity: it shows the organisation number, the phone or e-mail registered for the entity, or the exact legal name together with the registered street address. A site that names a different organisation number is rejected. Social profiles count only when the verified site links to them, or Wikidata lists them on the item carrying this organisation number. Job ads count only when NAV's record names this organisation number, or one of its registered workplaces, as the employer.</p>" +
      "<p>When the match is uncertain the fact is withheld and the profile says so. Missing information stays missing: nothing is turned into a zero.</p>" +
      '<h2>Validation</h2><ul>' + Object.entries((r.validation || {}).checks || {}).map(([k, v]) => "<li>" + (v ? "✓ " : "✗ ") + esc(k.replace(/_/g, " ")) + "</li>").join("") + "</ul></div>" + foot();
    document.title = "Run overview · Kildespor";
  }

  /* ---------- routing ---------- */
  async function route() {
    const h = location.hash.slice(1) || "/";
    const app = $("#app");
    const m = h.match(/^\/c\/(\d{9})/);
    const cm = h.match(/^\/compare\/([\d,]+)/);
    if (m) {
      app.classList.add("profile-open");
      renderList(m[1]);
      $("#main").innerHTML = '<p class="empty">Loading…</p>';
      try { renderProfile(await load(m[1])); } catch (e) { $("#main").innerHTML = '<p class="empty"><b>Profile not available.</b> ' + esc(e.message) + "</p>"; }
      $("#main").focus({ preventScroll: true });
      window.scrollTo({ top: 0 });
    } else if (cm) {
      app.classList.add("profile-open");
      renderList();
      await renderCompare(cm[1].split(",").slice(0, 4));
    } else {
      app.classList.remove("profile-open");
      renderList();
      renderAbout();
    }
  }

  document.addEventListener("click", (ev) => {
    const row = ev.target.closest(".row");
    if (row && !ev.target.closest(".cmp")) { location.hash = "#/c/" + row.dataset.org; return; }
    const b = ev.target.closest(".srcbtn");
    if (b) {
      const box = document.getElementById(b.getAttribute("aria-controls"));
      const open = b.getAttribute("aria-expanded") === "true";
      if (!open && !box.innerHTML) box.innerHTML = evHtml(cache[(location.hash.match(/\d{9}/) || [])[0]], b.dataset.ev.split(","));
      box.hidden = open;
      b.setAttribute("aria-expanded", String(!open));
      return;
    }
    const cite = ev.target.closest(".cite");
    if (cite) { const t = document.getElementById("f-" + cite.dataset.jump); if (t) t.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" }); return; }
    if (ev.target.closest("[data-back]")) { location.hash = "#/"; return; }
    const chip = ev.target.closest(".chip[data-f]");
    if (chip) { const f = chip.dataset.f; filters[f] = !filters[f]; chip.setAttribute("aria-pressed", String(filters[f])); renderList((location.hash.match(/\d{9}/) || [])[0]); return; }
    if (ev.target.id === "cmpgo") { location.hash = "#/compare/" + compare.join(","); return; }
    if (ev.target.id === "cmpclear") { compare = []; save(); renderList((location.hash.match(/\d{9}/) || [])[0]); }
  });
  document.addEventListener("change", (ev) => {
    const c = ev.target.closest("[data-cmp]");
    if (c) {
      const o = c.dataset.cmp;
      compare = c.checked ? [...new Set([...compare, o])].slice(-4) : compare.filter((x) => x !== o);
      save(); renderCmpBar();
    }
    if (ev.target.id === "sort") { filters.sort = ev.target.value; renderList((location.hash.match(/\d{9}/) || [])[0]); }
  });
  function save() { try { localStorage.setItem("ks-compare", JSON.stringify(compare)); } catch (e) { /* storage unavailable */ } }
  $("#q").addEventListener("input", (ev) => { filters.q = ev.target.value; renderList((location.hash.match(/\d{9}/) || [])[0]); });
  document.addEventListener("keydown", (ev) => { if (ev.key === "/" && document.activeElement !== $("#q")) { ev.preventDefault(); $("#q").focus(); } });
  $("#runlabel").innerHTML = '<a href="#/">Run <strong>' + esc(KS.run.run_id) + '</strong></a> <span class="long">· ' + nf.format(KS.index.length) + " companies · " + esc(KS.run.completed_at || "") + "</span>";
  window.addEventListener("hashchange", route);
  route();
})();
