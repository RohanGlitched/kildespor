/* Kildespor viewer: find, compare and verify company facts.
   Opens straight from disk (file://): the run index and each profile are plain scripts, no server or network needed. */
(function () {
  "use strict";
  const KS = window.KS || { families: [], index: [], run: {} };
  KS.index = KS.index || [];
  KS.run = KS.run || {};
  const FAM = KS.families || [];
  const FAMKEYS = FAM.map((f) => f[0]);
  const FAML = Object.fromEntries(FAM);
  const SHORT = { identity: "Identity", financials: "Accounts", people: "Leadership", locations: "Workplaces", website: "Website", contact: "Contact",
    social: "Profiles", jobs: "Hiring", activity: "Activity", reviews: "Ratings", description: "Description" };
  const famShort = (f) => SHORT[f] || FAML[f] || f;
  const SEC_OF = { identity: "identity", description: "identity", financials: "accounts", people: "leadership", locations: "leadership",
    website: "online", social: "online", contact: "online", jobs: "activity", activity: "activity", reviews: "activity" };

  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ESC[c]);
  const fold = (v) => String(v == null ? "" : v).toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "")
    .replace(/æ/g, "ae").replace(/ø/g, "o").replace(/å/g, "a");
  const nf = new Intl.NumberFormat("en-GB");
  const collator = new Intl.Collator("nb", { sensitivity: "base" });
  const plural = (n, w, p) => nf.format(n) + " " + (n === 1 ? w : p || w + "s");
  const cap = (s) => String(s || "").charAt(0).toUpperCase() + String(s || "").slice(1);
  const reduced = () => window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  const narrow = () => window.matchMedia && matchMedia("(max-width: 899px)").matches;

  /* ---------- vocabulary ---------- */
  const STATE = {
    available: { w: "Found", d: "Facts found and tied to this organisation number." },
    not_available: { w: "Not found", d: "Checked; nothing was there for this entity." },
    ambiguous: { w: "Unconfirmed", d: "Candidates were found, but none was proven to be this exact entity, so nothing is shown." },
    blocked: { w: "Blocked", d: "The source refused automated access (robots.txt or HTTP 401/403)." },
    failed: { w: "Source failed", d: "The source broke during this run; nothing is inferred from its silence." },
    not_applicable: { w: "Not applicable", d: "This kind of information does not apply to this entity." },
  };
  const ST_ORDER = ["available", "ambiguous", "blocked", "failed", "not_available", "not_applicable"];
  const DEFAULT_NOTE = "Checked; nothing found for this entity";
  const CLASS = { official_registry: "Official register", company_owned: "Company's own website", public_job_board: "Public job board",
    open_knowledge_base: "Open knowledge base", public_directory: "Public directory", platform_feed: "Platform feed" };
  const METHOD = {
    registry_field: "Field in the register record", registry_field_date: "Date field in the register record",
    registry_accounts: "Figure in the filed annual accounts", registry_accounts_copies: "List of filed annual-account copies",
    registry_update_log: "Register update log", registry_roles: "Role register", registry_roles_date: "Role register (date of change)",
    registry_subunits: "Sub-unit register (workplaces)", state_aid_register_exact_orgnr: "State-aid register row naming this org.nr",
    page_text_or_mailto: "Text or e-mail link on the company site", page_text_or_tel: "Text or phone link on the company site",
    address_pattern: "Address printed on the company site", outbound_link: "Link on the company site", meta_description: "Site description tag",
    jsonld: "Structured data (JSON-LD) on the site", jsonld_sameAs: "JSON-LD sameAs link on the site",
    jsonld_identifier_orgnr: "JSON-LD identifier carrying this org.nr", rss_item: "Item in the site's news feed", html_title: "Page title",
    news_listing_date: "Dated item on the site's news page", careers_page: "Careers page on the company site",
    smilefjes_csv_orgnr: "Mattilsynet inspection row naming this org.nr", finanstilsynet_licence: "Finanstilsynet licence register",
    finanstilsynet_exact_orgnr: "Finanstilsynet register row naming this org.nr", ted_winner_identifier: "EU award notice naming this org.nr as winner",
    wikidata_sparql_p2333: "Wikidata item carrying this org.nr (P2333)", arbeidstilsynet_register_orgnr: "Arbeidstilsynet register row naming this org.nr",
    nav_feed_employer_orgnr: "NAV job ad naming this org.nr as employer",
  };
  const PROOF = {
    orgnr: ["Org.nr on the site", "the site prints this organisation number"],
    phone: ["Registered phone", "the site shows the phone number registered for this company"],
    email: ["Registered e-mail", "the site shows the e-mail address registered for this company"],
    name_address: ["Name and address", "the site shows the exact legal name together with the registered street address"],
    legal_name: ["Legal name", "the site shows the exact legal name"],
    legal_name_town: ["Name and town", "the site shows the exact legal name next to the registered town"],
    role_holder_and_name: ["Role holder and name", "the site names a registered role holder together with the company name"],
    registry_declared_name: ["Declared in the register", "the register lists this site and its home page carries the company name"],
    name_domain_town: ["Domain and town", "the domain spells the full legal name and the site names the registered town"],
  };
  const VIA = { registry_website: "the website field in the register", name_derived: "a domain derived from the company name",
    email_domain: "the domain of the registered e-mail address", subunit_website: "a workplace's website field in the register",
    wikidata: "Wikidata", registry_email_domain: "the domain of the registered e-mail address" };
  const ROLE_EN = { DAGL: "Managing director", LEDE: "Chair of the board", NEST: "Deputy chair", MEDL: "Board member", VARA: "Deputy board member",
    KONT: "Contact person", REVI: "Auditor", REGN: "Accountant", INNH: "Proprietor", DTPR: "Partner (shared liability)", DTSO: "Partner (full liability)",
    KOMP: "General partner", BEST: "Managing shipowner", "FFØR": "Business manager", REPR: "Norwegian representative", HFOR: "Home-country details",
    SAM: "Co-owner", OBS: "Observer" };
  const ROLE_ORDER = ["DAGL", "INNH", "LEDE", "NEST", "MEDL", "VARA", "DTSO", "DTPR", "KOMP", "BEST", "FFØR", "KONT", "REPR", "HFOR", "OBS", "REVI", "REGN"];
  const REL = { exact: "This exact organisation number", registered_subunit: "A registered workplace (sub-unit) of this company",
    group_member: "Another entity in the same group, linked by the register or Wikidata" };
  const TOPIC = { identity: "Identity", what_it_does: "What it does", financials: "Accounts", people: "Leadership", locations: "Workplaces",
    online: "Online", hiring: "Hiring", reviews: "Ratings", activity: "Activity", changes: "Changes",
    profile: "Profile", assessment: "Assessment", risk: "Register warning", recent_changes: "Last 12 months" };
  const CHANGE = { new_filing: "New filing", removed: "No longer listed", new_role: "New role holder", role_removed: "Role ended",
    changed: "Value changed", added: "New fact", new_posting: "New job posting", posting_closed: "Job posting closed", new_website: "Website verified",
    website_changed: "Website changed", renamed: "Renamed", address_changed: "Address changed" };
  const ROUTINE = new Set(["registry_update"]);
  const ID_ORDER = ["legal_name", "organisation_number", "legal_form", "industry", "founded", "registered", "municipality", "registered_business_address",
    "postal_address", "registered_employees", "share_capital", "registry_flags", "public_brand", "former_name", "site_title", "registered_website",
    "parent_organisation", "wikidata_item", "inception", "lei_code", "financial_licence", "financial_supervision", "public_approval"];
  const FIN_ROWS = [["revenue", "Operating revenue"], ["operating_result", "Operating result"], ["profit_before_tax", "Result before tax"],
    ["annual_result", "Annual result"], ["payroll_cost", "Payroll costs"], ["total_assets", "Total assets"], ["equity", "Equity"],
    ["total_debt", "Total debt"], ["cash", "Bank deposits and cash"]];
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const ICON = {
    chev: '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="m9 6 6 6-6 6"/></svg>',
    ext: '<svg class="ic ext" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5h5v5M19 5l-8 8M17 14v5H5V7h5"/></svg>',
    check: '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
    cross: '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7 7 17"/></svg>',
    pick: '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><rect class="bx" x="4" y="4" width="16" height="16" rx="3"/><path class="tk" d="m8 12.5 3 3 5-6"/><path class="pl" d="M12 8v8M8 12h8"/></svg>',
    back: '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="m15 6-6 6 6 6"/></svg>',
  };

  /* ---------- formatting ---------- */
  function compact(v) {
    if (v == null || isNaN(v)) return "—";
    const a = Math.abs(v), s = v < 0 ? "−" : "";
    const t = (x, d) => x.toFixed(d).replace(/\.0$/, "");
    if (a >= 1e9) return s + t(a / 1e9, a >= 1e11 ? 0 : 1) + " bn";
    if (a >= 1e6) return s + t(a / 1e6, a >= 1e8 ? 0 : 1) + " m";
    if (a >= 1e3) return s + Math.round(a / 1e3) + " k";
    return s + nf.format(Math.round(a));
  }
  const money = (v, cur) => (v == null || isNaN(v) ? "—" : (v < 0 ? "−" : "") + ((cur && cur !== "NOK") ? cur : "NOK") + " " + compact(Math.abs(v)));
  const fullMoney = (v, cur) => (v == null ? "—" : (cur || "NOK") + " " + nf.format(v));
  const orgFmt = (o) => String(o || "").replace(/^(\d{3})(\d{3})(\d{3})$/, "$1 $2 $3");
  const phone = (v) => String(v).replace(/^(\d{2})(\d{2})(\d{2})(\d{2})$/, "$1 $2 $3 $4");
  function fdate(d) {
    const m = String(d || "").match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m ? +m[3] + " " + MON[+m[2] - 1] + " " + m[1] : esc(d || "");
  }
  function fdt(iso) {
    const m = String(iso || "").match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
    return m ? fdate(iso) + ", " + m[4] + ":" + m[5] + (/Z$|\+00:?00$/.test(iso) ? " UTC" : "") : fdate(iso);
  }
  function fperiod(p) {
    const m = String(p || "").match(/^(\d{4})(?:-(\d{2})-(\d{2}))?\.\.(\d{4})(?:-(\d{2})-(\d{2}))?$/);
    if (!m) return esc(p || "");
    if (!m[2]) return m[1] === m[4] ? "Financial year " + m[1] : m[1] + " – " + m[4];
    return fdate(m[1] + "-" + m[2] + "-" + m[3]) + " – " + fdate(m[4] + "-" + m[5] + "-" + m[6]);
  }
  function dur(sec) {
    if (sec == null) return "—";
    sec = Math.round(sec);
    if (sec < 90) return sec + " s";
    const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    return (h ? h + " h " : "") + (m ? m + " min" : "") + (!h && s ? " " + s + " s" : "");
  }
  const isUrl = (u) => /^https?:\/\//i.test(String(u || ""));
  const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch (e) { return String(u || ""); } };
  const link = (u, text, cls) => isUrl(u)
    ? '<a href="' + esc(u) + '" target="_blank" rel="noopener noreferrer"' + (cls ? ' class="' + cls + '"' : "") + ">" + esc(text == null ? u : text) + "</a>"
    : esc(text == null ? u : text);
  function srcShort(e) {
    if (!e) return "Source";
    const n = e.source_name || host(e.source_url);
    return ({ "Brønnøysundregistrene": "Brønnøysund", "TED (EU Publications Office)": "TED", "NAV arbeidsplassen": "NAV" })[n] || String(n).replace(/^www\./, "");
  }
  function methodLabel(m) {
    if (!m) return "—";
    if (METHOD[m]) return METHOD[m];
    const p = m.match(/^identity_proof_(.+)$/);
    if (p) return "Identity proof on the company site: " + (PROOF[p[1]] ? PROOF[p[1]][1] : p[1].replace(/_/g, " "));
    return cap(m.replace(/_/g, " "));
  }
  function pageKind(u) {
    let p = "";
    try { p = decodeURIComponent(new URL(u).pathname).toLowerCase(); } catch (e) { return "a page of the site"; }
    if (p === "/" || p === "" || /^\/(index|home|hjem|forside)(\.\w+)?$/.test(p)) return "the home page";
    if (/kontakt|contact/.test(p)) return "the contact page";
    if (/om-?oss|about|om_oss|hvem-er-vi|firma|selskap/.test(p)) return "the about page";
    if (/personvern|privacy|cookie/.test(p)) return "the privacy page";
    if (/vilkar|vilkår|terms|betingelser/.test(p)) return "the terms page";
    if (/impressum|kundeservice/.test(p)) return "the company-details page";
    return "the page " + p;
  }
  const hide = (o, k, v) => Object.defineProperty(o, k, { value: v, enumerable: false, configurable: true, writable: true });

  /* ---------- data loading ---------- */
  const cache = {};
  const waiting = {};
  KS.put = function (env) {
    // websites and profiles carry a plain URL as the value and their structure in "details"
    (env.claims || []).forEach((c) => { if (c.details && typeof c.details === "object") c.value = c.details; });
    cache[env.organisation_number] = env;
    (waiting[env.organisation_number] || []).forEach((f) => f[0](env));
    delete waiting[env.organisation_number];
  };
  function load(org) {
    if (cache[org]) return Promise.resolve(prep(cache[org]));
    return new Promise((resolve, reject) => {
      if (waiting[org]) { waiting[org].push([resolve, reject]); return; }
      waiting[org] = [[resolve, reject]];
      const s = document.createElement("script");
      s.src = "data/c/" + org + ".js";
      s.onerror = () => { (waiting[org] || []).forEach((f) => f[1](new Error("The profile file data/c/" + org + ".js is missing."))); delete waiting[org]; s.remove(); };
      document.head.appendChild(s);
    }).then(prep);
  }
  function prep(env) {
    if (env._k) return env;
    hide(env, "_ev", Object.fromEntries((env.evidence || []).map((e) => [e.id, e])));
    hide(env, "_k", Object.fromEntries((env.claims || []).map((c) => [c.key, c])));
    const f = {};
    FAMKEYS.forEach((k) => (f[k] = []));
    (env.claims || []).forEach((c) => (f[c.family] || (f[c.family] = [])).push(c));
    hide(env, "_f", f);
    hide(env, "_s", Object.fromEntries((env.field_states || []).map((s) => [s.family, s])));
    return env;
  }
  const claimsOf = (env, fam, field) => (env._f[fam] || []).filter((c) => !field || c.field === field);
  const one = (env, fam, field) => (env._f[fam] || []).find((c) => c.field === field);
  const stOf = (env, fam) => env._s[fam] || { family: fam, state: (env._f[fam] || []).length ? "available" : "not_available", claims: 0 };
  function finOf(env) {
    return claimsOf(env, "financials").filter((c) => c.value && typeof c.value === "object" && c.value.amount != null && c.value.year);
  }
  function latestFin(env, field) {
    const r = finOf(env).filter((c) => c.field === field).sort((a, b) => String(b.value.year).localeCompare(String(a.value.year)));
    return r[0] || null;
  }
  function finIn(env, field, year) { return finOf(env).find((c) => c.field === field && String(c.value.year) === String(year)) || null; }
  function rolesOf(env) {
    return claimsOf(env, "people", "registered_role").filter((c) => c.value && typeof c.value === "object").sort((a, b) => {
      const ia = ROLE_ORDER.indexOf(a.value.role_code), ib = ROLE_ORDER.indexOf(b.value.role_code);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
  }
  function datedActivity(env, routine) {
    const items = (env.claims || []).filter((c) => (c.family === "activity" || c.field === "job_posting") && c.effective_date && (routine || !ROUTINE.has(c.field)));
    const seen = new Set();
    return items.sort((a, b) => String(b.effective_date).localeCompare(String(a.effective_date))).filter((c) => {
      const k = String(c.effective_date).slice(0, 10) + "|" + valText(c);
      if (seen.has(k)) return false;
      seen.add(k);
      return true;
    });
  }

  /* ---------- values ---------- */
  function valText(c) {
    const v = c.value;
    if (v == null) return "—";
    if (typeof v !== "object") {
      if (/phone|mobile/.test(c.field)) return phone(v);
      if (c.field === "founded" || c.field === "registered" || c.field === "inception") return fdate(v);
      if (c.field === "municipality") return String(v).charAt(0) + String(v).slice(1).toLowerCase();
      return String(v);
    }
    if (Array.isArray(v)) return v.join(", ");
    if ("amount" in v && "year" in v) return money(v.amount, v.currency) + " (" + v.year + ")";
    if (v.title && "amount" in v) return v.title + (v.amount != null ? " · " + money(v.amount, v.currency) : "");
    if ("amount" in v) return money(v.amount, v.currency) + (v.shares ? " · " + nf.format(v.shares) + " shares" : "");
    if (v.rating != null) return Math.round(v.rating * 10) / 10 + " / " + (v.best || 5) + (v.count ? " from " + nf.format(v.count) + " ratings" : "");
    if (v.year && v.format) return "Annual accounts " + v.year + " (" + String(v.format).toUpperCase() + ")";
    if (v.domain) return v.domain;
    if (v.platform) return cap(v.platform) + (v.handle ? " · " + v.handle : "");
    if (v.name && v.role) return v.name;
    if (v.title) return v.title;
    if (v.name) return v.name + (v.address ? ", " + v.address : "");
    if (v.address) return v.address;
    if (v.label) return v.label + (v.id ? " (" + v.id + ")" : "");
    if (v.url) return v.url;
    return JSON.stringify(v);
  }
  function fmtValue(c) {
    const v = c.value;
    if (v == null) return "—";
    if (typeof v !== "object") {
      if (c.field === "registered_website" || c.field === "website_listed_in_wikidata" || isUrl(v)) return link(isUrl(v) ? v : "https://" + v, String(v).replace(/^https?:\/\//, ""));
      if (c.field === "email" || c.field === "registered_email") return '<a href="mailto:' + esc(v) + '">' + esc(v) + "</a>";
      if (/phone|mobile/.test(c.field)) return '<a href="tel:' + esc(String(v).replace(/\s/g, "")) + '">' + esc(phone(v)) + "</a>";
      if (c.field === "opening_hours") return esc(String(v).length > 160 ? String(v).slice(0, 160) + "…" : v);
      return esc(valText(c));
    }
    if (Array.isArray(v)) return esc(v.join(", "));
    if ("amount" in v && "year" in v) return '<span title="' + esc(fullMoney(v.amount, v.currency)) + '">' + esc(money(v.amount, v.currency)) + "</span>";
    if (v.title && "amount" in v) return link(v.url, v.title) + (v.amount != null ? ' <span class="muted">' + esc(money(v.amount, v.currency)) + "</span>" : "");
    if ("amount" in v) return esc(money(v.amount, v.currency)) + (v.shares ? ' <span class="muted">' + nf.format(v.shares) + " shares</span>" : "");
    if (v.rating != null) return link(v.url, Math.round(v.rating * 10) / 10 + " / " + (v.best || 5)) + (v.count ? ' <span class="muted">' + nf.format(v.count) + " ratings · " + esc(v.platform || "") + "</span>" : "");
    if (v.year && v.format) return link(v.url, "Annual accounts " + v.year + " (" + String(v.format).toUpperCase() + ")");
    if (v.id && v.url && v.label) return link(v.url, v.label) + ' <span class="muted mono">' + esc(v.id) + "</span>";
    if (v.domain) return link(v.url, v.domain);
    if (v.platform) return link(v.url, cap(v.platform)) + (v.handle ? ' <span class="muted">' + esc(v.handle) + "</span>" : "");
    if (v.name && v.role) return esc(v.name) + (v.kind === "organisation" ? ' <span class="muted">organisation' + (v.organisation_number ? " " + orgLink(v.organisation_number) : "") + "</span>" : "");
    if (v.title) return link(v.url, v.title) + (v.status ? ' <span class="tag' + (v.status === "closed" ? " off" : "") + '">' + esc(v.status) + "</span>" : "") + (v.location ? ' <span class="muted">' + esc(v.location) + "</span>" : "");
    if (v.organisation_number && v.name) return esc(v.name) + '<span class="muted block">' + esc(v.address || "") + (v.registered_employees != null ? " · " + plural(v.registered_employees, "registered employee") : "") + "</span>";
    if (v.address) return esc(v.address);
    if (v.label) return esc(v.label);
    if (v.url) return link(v.url);
    return esc(JSON.stringify(v));
  }
  function orgLink(o) {
    return IDX[o] ? '<a href="#/c/' + esc(o) + '">' + esc(orgFmt(o)) + "</a>" : link("https://virksomhet.brreg.no/nb/oppslag/enheter/" + o, orgFmt(o));
  }
  function objText(v) {
    if (v == null) return "—";
    if (typeof v !== "object") return String(v);
    if (v.year && v.format) return "Annual accounts " + v.year + " (" + String(v.format).toUpperCase() + ")";
    if ("amount" in v && "year" in v) return money(v.amount, v.currency) + " (" + v.year + ")";
    return v.title || (v.name ? v.name + (v.role ? ", " + v.role : "") : "") || v.domain || v.address || v.url || JSON.stringify(v);
  }
  function srcBtn(env, c, label) {
    const e = env._ev[(c.evidence_ids || [])[0]];
    const n = (c.evidence_ids || []).length;
    return '<button type="button" class="src" data-target="f:' + esc(c.key) + '" aria-label="Evidence for ' + esc(c.label || c.field) + (e ? ", from " + esc(srcShort(e)) : "") + '">' +
      '<span class="src-n">' + esc(label || srcShort(e)) + "</span>" + (n > 1 ? '<span class="src-c">' + n + "</span>" : "") + ICON.chev + "</button>";
  }
  const stChip = (st, text) => '<span class="st st-' + esc(st) + '"><i aria-hidden="true"></i>' + esc(text || (STATE[st] || { w: st }).w) + "</span>";

  /* ---------- index ---------- */
  const IDX = {};
  KS.index.forEach((x, i) => {
    x._i = i;
    x.ribbon = x.ribbon || [];
    x._found = x.ribbon.filter((s) => s === "available").length;
    x._h = fold([x.name, x.org, x.domain, x.muni, x.industry, x.nace, x.lead].join(" "));
    x._n = fold(x.name);
    IDX[x.org] = x;
  });

  /* ---------- list (find) ---------- */
  const F = { q: "", site: false, jobs: false, social: false, changed: false, fam: "", st: "", sort: "facts" };
  const PAGE = 120;
  let view = [], shown = 0, terms = [], currentOrg = null;
  const rowsEl = $("#rows");
  const nullLast = (k) => (a, b) => (a[k] == null) - (b[k] == null) || (b[k] || 0) - (a[k] || 0) || a._i - b._i;
  const SORTS = {
    facts: (a, b) => b.facts - a.facts || a._i - b._i,
    revenue: nullLast("revenue"),
    result: nullLast("result"),
    name: (a, b) => collator.compare(a.name, b.name),
    recent: (a, b) => String(b.last || "").localeCompare(String(a.last || "")) || a._i - b._i,
    changes: (a, b) => b.changes - a.changes || b.facts - a.facts,
  };
  function filtered() {
    const q = fold(F.q).trim();
    const digits = q.replace(/\s+/g, "");
    terms = /^\d{3,9}$/.test(digits) ? [digits] : q.split(/\s+/).filter(Boolean);
    const fi = F.fam ? FAMKEYS.indexOf(F.fam) : -1;
    const r = KS.index.filter((x) => (!terms.length || terms.every((t) => x._h.includes(t) || x.org.includes(t))) &&
      (!F.site || x.domain) && (!F.jobs || x.jobs > 0) && (!F.social || x.social > 0) && (!F.changed || x.changes > 0) &&
      (!F.st || (fi >= 0 ? x.ribbon[fi] === F.st : x.ribbon.includes(F.st))));
    const sorter = SORTS[F.sort] || SORTS.facts;
    if (terms.length && F.sort === "facts") {
      const score = (x) => (x.org === digits ? 0 : x._n.startsWith(terms[0]) ? 1 : x._n.includes(terms[0]) ? 2 : 3);
      r.forEach((x) => (x._sc = score(x)));
      return r.sort((a, b) => a._sc - b._sc || sorter(a, b));
    }
    return r.sort(sorter);
  }
  function hl(text, ts) {
    text = String(text || "");
    if (!ts.length) return esc(text);
    const chars = Array.from(text);
    let f = "";
    const map = [];
    chars.forEach((ch, i) => { const fc = fold(ch); for (let k = 0; k < fc.length; k++) map.push(i); f += fc; });
    const mark = new Array(chars.length).fill(false);
    ts.forEach((t) => { let p = f.indexOf(t); while (t && p !== -1) { for (let k = p; k < p + t.length; k++) mark[map[k]] = true; p = f.indexOf(t, p + t.length); } });
    let out = "", on = false;
    chars.forEach((ch, i) => {
      if (mark[i] && !on) { out += "<mark>"; on = true; }
      if (!mark[i] && on) { out += "</mark>"; on = false; }
      out += esc(ch);
    });
    return out + (on ? "</mark>" : "");
  }
  function miniRibbon(states) {
    return '<span class="rib" aria-hidden="true">' + FAMKEYS.map((f, i) => '<i class="s-' + esc(states[i] || "not_available") + '"></i>').join("") + "</span>";
  }
  function rowHtml(x) {
    const cur = x.org === currentOrg;
    const picked = compare.includes(x.org);
    const sub = [x.org, x.muni, x.industry].filter(Boolean).join(" · ");
    const badges = (x.status === "failed" ? '<span class="bd bad">Not in register</span>' : "") +
      (x.domain ? '<span class="bd web" title="Verified website">' + ICON.check + hl(x.domain, terms) + "</span>" : "") +
      (x.jobs ? '<span class="bd job">Hiring · ' + x.jobs + "</span>" : "") +
      (x.changes ? '<span class="bd chg">' + plural(x.changes, "change") + "</span>" : "");
    return '<li class="row' + (cur ? " cur" : "") + '" data-org="' + x.org + '">' +
      '<a class="rl" href="#/c/' + x.org + '"' + (cur ? ' aria-current="page"' : "") + '><span class="nm">' + hl(x.name, terms) + '</span><span class="sub">' + hl(sub, terms) + "</span></a>" +
      '<span class="rv">' + (x.revenue != null ? esc(money(x.revenue)) + "<small>revenue " + esc(x.ry || "") + "</small>" : "<small>no revenue filed</small>") + "</span>" +
      '<span class="rb">' + miniRibbon(x.ribbon) + '<span class="sr">' + x._found + " of " + FAMKEYS.length + " information types found.</span>" + badges + "</span>" +
      '<button type="button" class="pick" data-pick="' + x.org + '" aria-pressed="' + picked + '" aria-label="Compare ' + esc(x.name) + '" title="Add to compare">' + ICON.pick + "</button></li>";
  }
  let io = null;
  function more() {
    const s = $("#sentinel");
    if (s) { if (io) io.unobserve(s); s.remove(); }
    const next = view.slice(shown, shown + PAGE);
    shown += next.length;
    let html = next.map(rowHtml).join("");
    if (shown < view.length) html += '<li id="sentinel" class="sentinel"><button type="button" class="linkbtn" data-more>Show ' + Math.min(PAGE, view.length - shown) + " more (" + nf.format(view.length - shown) + " left)</button></li>";
    if (!view.length) html = '<li class="none"><p><b>No company matches.</b> Search by name, organisation number, website, municipality or industry.</p><button type="button" class="btn ghost" data-reset>Clear search and filters</button></li>';
    rowsEl.insertAdjacentHTML("beforeend", html);
    const ns = $("#sentinel");
    if (ns && io) io.observe(ns);
  }
  if ("IntersectionObserver" in window) io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) more(); }, { rootMargin: "600px 0px" });
  function renderList() {
    view = filtered();
    shown = 0;
    rowsEl.innerHTML = "";
    more();
    const n = KS.index.length;
    $("#count").textContent = view.length === n ? plural(n, "company", "companies") : nf.format(view.length) + " of " + plural(n, "company", "companies");
    const active = F.q || F.site || F.jobs || F.social || F.changed || F.st;
    $("#reset").hidden = !active;
    $("#mfon").textContent = F.st ? "· " + (F.fam ? famShort(F.fam) : "Any type") + ": " + STATE[F.st].w : "";
    $$(".chip[data-f]").forEach((c) => c.setAttribute("aria-pressed", String(!!F[c.dataset.f])));
  }
  function markCurrent() {
    $$(".row", rowsEl).forEach((r) => {
      const on = r.dataset.org === currentOrg;
      r.classList.toggle("cur", on);
      const a = $(".rl", r);
      if (on) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
  }
  function resetFilters() {
    Object.assign(F, { q: "", site: false, jobs: false, social: false, changed: false, fam: "", st: "" });
    $("#q").value = "";
    $("#ffam").value = "";
    $("#fst").value = "";
    renderList();
  }
  function setStateFilter(fam, st) {
    Object.assign(F, { fam: fam || "", st: st || "" });
    $("#ffam").value = F.fam;
    $("#fst").value = F.st;
    $("#morefilters").open = true;
    renderList();
  }

  /* ---------- compare selection ---------- */
  let compare = [];
  try { compare = JSON.parse(localStorage.getItem("ks-compare") || "[]").filter((o) => IDX[o]).slice(0, 4); } catch (e) { compare = []; }
  function saveCompare() { try { localStorage.setItem("ks-compare", JSON.stringify(compare)); } catch (e) { /* storage unavailable */ } }
  function setCompare(list, quiet) {
    compare = list.filter((o, i) => IDX[o] && list.indexOf(o) === i).slice(0, 4);
    saveCompare();
    $$("[data-pick]").forEach((b) => {
      const on = compare.includes(b.dataset.pick);
      b.setAttribute("aria-pressed", String(on));
      if (b.dataset.lbl) b.querySelector(".bl").textContent = on ? "In compare" : "Add to compare";
    });
    renderTray();
    const h = location.hash.match(/^#\/compare\//);
    if (h && !quiet && compare.length >= 2) location.replace("#/compare/" + compare.join(","));
  }
  function togglePick(org) {
    if (compare.includes(org)) { setCompare(compare.filter((o) => o !== org)); return; }
    if (compare.length >= 4) { toast("Compare holds up to four companies. Remove one first."); return; }
    setCompare(compare.concat(org));
    if (compare.length === 1) toast("Added. Pick at least one more company to compare.");
  }
  function renderTray() {
    const tray = $("#tray");
    tray.hidden = !compare.length;
    document.body.classList.toggle("has-tray", !!compare.length);
    $("#trayitems").innerHTML = compare.map((o, i) => '<li><span class="lt" data-ci="' + i + '">' + "ABCD"[i] + '</span><span class="tn">' + esc((IDX[o] || {}).name || o) +
      '</span><button type="button" class="iconbtn sm" data-unpick="' + o + '" aria-label="Remove ' + esc((IDX[o] || {}).name || o) + ' from compare">' + ICON.cross + "</button></li>").join("");
    const go = $("#traygo");
    go.href = "#/compare/" + compare.join(",");
    go.textContent = compare.length < 2 ? "Pick one more" : "Compare " + compare.length;
    go.setAttribute("aria-disabled", String(compare.length < 2));
  }

  /* ---------- drawer (verify) ---------- */
  const drawer = $("#drawer");
  let lastFocus = null, drawerPushed = false;
  function openDrawer(eyebrow, title, html) {
    if (drawer.hidden) lastFocus = document.activeElement;
    $("#deyebrow").textContent = eyebrow;
    $("#dtitle").textContent = title;
    $("#dbody").innerHTML = html;
    drawer.hidden = false;
    document.documentElement.classList.add("lock");
    $("#dbody").scrollTop = 0;
    requestAnimationFrame(() => $(".panel", drawer).focus());
  }
  function hideDrawer() {
    if (drawer.hidden) return;
    drawer.hidden = true;
    document.documentElement.classList.remove("lock");
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
  }
  function closeDrawer() {
    if (/\/e\//.test(location.hash)) {
      if (drawerPushed) { drawerPushed = false; history.back(); return; }
      history.replaceState(null, "", location.hash.replace(/\/e\/.*$/, ""));
    }
    hideDrawer();
  }
  function evCard(e, c, tag) {
    if (!e) return "";
    return '<article class="evc">' +
      '<header class="evh">' + (tag ? '<span class="tag">' + esc(tag) + "</span>" : "") + '<span class="evs">' + esc(e.source_name || host(e.source_url)) + '</span><span class="pill">' + esc(CLASS[e.source_class] || cap(String(e.source_class || "").replace(/_/g, " "))) + "</span></header>" +
      (e.claim_span ? '<figure class="quote"><figcaption>Exact text the fact rests on</figcaption><blockquote><mark>' + esc(e.claim_span) + "</mark></blockquote></figure>" : "") +
      '<dl class="kv">' +
      "<dt>Source</dt><dd>" + link(e.source_url, e.source_url, "wrap") + "</dd>" +
      (e.final_url ? "<dt>Redirected to</dt><dd>" + link(e.final_url, e.final_url, "wrap") + "</dd>" : "") +
      "<dt>Retrieved</dt><dd>" + fdt(e.retrieved_at) + "</dd>" +
      (c && c.reporting_period ? "<dt>Reporting period</dt><dd>" + fperiod(c.reporting_period) + "</dd>" : "") +
      "<dt>Method</dt><dd>" + esc(methodLabel(e.extraction_method)) + ' <span class="muted mono sm">' + esc(e.extraction_method || "") + "</span></dd>" +
      (e.http_status ? "<dt>HTTP status</dt><dd>" + esc(e.http_status) + "</dd>" : "") +
      '<dt>Content hash</dt><dd><code class="hash">sha256:' + esc(e.content_sha256 || "—") + '</code> <button type="button" class="linkbtn sm" data-copy="' + esc(e.content_sha256 || "") + '">Copy</button></dd>' +
      '<dt>Evidence id</dt><dd class="mono sm">' + esc(e.id) + "</dd></dl></article>";
  }
  function proofBlock(env, c) {
    const v = c.value || {};
    const proofs = v.identity_proof || [];
    const evs = (c.evidence_ids || []).map((id) => env._ev[id]).filter(Boolean);
    const items = proofs.map((p) => {
      const e = evs.find((x) => x.extraction_method === "identity_proof_" + p);
      const d = PROOF[p] || [cap(p.replace(/_/g, " ")), p.replace(/_/g, " ")];
      return "<li>" + ICON.check + "<div><b>" + esc(d[0]) + "</b>: " + esc(d[1]) + (e ? ", on " + esc(pageKind(e.final_url || e.source_url)) + " (" + link(e.final_url || e.source_url, host(e.source_url) + (new URL(e.source_url, "http://x").pathname || "")) + ")" : "") + ".</div></li>";
    }).join("");
    return '<section class="proofs"><h3 class="dh">Why this is the company\'s own website</h3><ul class="prooflist">' + items + "</ul>" +
      '<p class="muted sm">Found through ' + esc(VIA[v.discovered_via] || String(v.discovered_via || "discovery").replace(/_/g, " ")) +
      ". A site is published only when it proves it belongs to organisation number " + esc(orgFmt(env.organisation_number)) + "; a site naming a different organisation number is rejected.</p></section>";
  }
  function factHtml(env, c) {
    const evs = (c.evidence_ids || []).map((id) => env._ev[id]).filter(Boolean);
    const rows = [["Company", esc(env.legal_name || "") + ' <span class="muted mono">' + esc(orgFmt(env.organisation_number)) + "</span>"],
      ["Information type", esc(FAML[c.family] || c.family)]];
    if (c.effective_date) rows.push(["Refers to", fdate(c.effective_date)]);
    if (c.reporting_period) rows.push(["Reporting period", fperiod(c.reporting_period)]);
    rows.push(["Applies to", esc(REL[c.relationship || "exact"] || c.relationship)]);
    if (c.confidence != null) rows.push(["Confidence", Math.round(c.confidence * 100) + "%"]);
    if (c.first_observed) rows.push(["First seen", fdt(c.first_observed)]);
    if (c.last_observed && c.last_observed !== c.first_observed) rows.push(["Last confirmed", fdt(c.last_observed)]);
    if (c.carried_forward) rows.push(["Note", "Kept from the previous run because its source failed or stopped listing it this time."]);
    return '<div class="dfact"><div class="dlabel">' + esc(c.label || c.field) + '</div><div class="dval">' + fmtValue(c) + "</div>" +
      '<dl class="kv">' + rows.map((r) => "<dt>" + r[0] + "</dt><dd>" + r[1] + "</dd>").join("") + "</dl></div>" +
      (c.field === "official_website" ? proofBlock(env, c) : "") +
      '<h3 class="dh">' + plural(evs.length, "evidence record") + "</h3>" + evs.map((e) => evCard(e, c)).join("") +
      '<div class="dfoot"><button type="button" class="btn ghost" data-copy-link>Copy link to this fact</button><span class="muted sm">Fact key <code>' + esc(c.key) + "</code></span>" +
      '<p class="muted sm">The content hash is SHA-256 of the exact bytes fetched. <code>python -m kildespor verify</code> re-checks every hash and quoted span against the archived responses.</p></div>';
  }
  function sentenceHtml(env, s) {
    const cs = (s.claim_keys || []).map((k) => env._k[k]).filter(Boolean);
    return '<blockquote class="sent">' + esc(s.text) + "</blockquote>" +
      '<p class="muted">This sentence was written only from the ' + plural(cs.length, "fact") + " below. Open one to see its source, retrieval time, hash and the exact quoted text.</p>" +
      cs.map((c, i) => '<details class="sfact"' + (i < 2 ? " open" : "") + "><summary><span class=\"dlabel\">" + esc(c.label || c.field) + '</span><span class="sv">' + esc(valText(c)) + "</span></summary>" +
        (c.reporting_period ? '<p class="muted sm">Reporting period: ' + fperiod(c.reporting_period) + "</p>" : "") +
        (c.field === "official_website" ? proofBlock(env, c) : "") +
        (c.evidence_ids || []).map((id) => evCard(env._ev[id], c)).join("") + "</details>").join("") +
      '<div class="dfoot"><button type="button" class="btn ghost" data-copy-link>Copy link to this sentence</button></div>';
  }
  function changeHtml(env, ch) {
    const evs = (list) => (list || []).map((e) => (typeof e === "string" ? env._ev[e] : e)).filter(Boolean);
    const prev = evs(ch.previous_evidence), cur = evs(ch.current_evidence);
    const rows = [["Change", esc(cap(ch.change || ""))], ["Materiality", esc(ch.materiality || "—")], ["Information type", esc(FAML[ch.family] || ch.family || "—")]];
    if (ch.previous !== undefined) rows.push(["Before", esc(objText(ch.previous))]);
    if (ch.current !== undefined) rows.push(["Now", esc(objText(ch.current))]);
    if (ch.last_observed) rows.push(["Last seen", fdt(ch.last_observed)]);
    if (ch.key) rows.push(["Fact key", "<code>" + esc(ch.key) + "</code>"]);
    const r = env.refresh || {};
    return '<div class="dfact"><dl class="kv">' + rows.map((x) => "<dt>" + x[0] + "</dt><dd>" + x[1] + "</dd>").join("") + "</dl>" +
      '<p class="muted sm">Compared with run ' + esc(r.previous_run_id || "—") + (r.previous_completed_at ? " (" + fdt(r.previous_completed_at) + ")" : "") + ".</p></div>" +
      (prev.length ? '<h3 class="dh">Evidence before</h3>' + prev.map((e) => evCard(e, null, "Previous run")).join("") : "") +
      (cur.length ? '<h3 class="dh">Evidence now</h3>' + cur.map((e) => evCard(e, null, "This run")).join("") : "");
  }
  function openTarget(env, t) {
    const m = String(t).match(/^([fsc]):(.*)$/);
    if (!m) return false;
    if (m[1] === "f") {
      const c = env._k[m[2]];
      if (!c) return false;
      openDrawer("Evidence · " + (env.legal_name || env.organisation_number), c.label || c.field, factHtml(env, c));
    } else if (m[1] === "s") {
      const s = ((env.summary || {}).sentences || [])[+m[2]];
      if (!s) return false;
      openDrawer("Summary sentence · " + (TOPIC[s.topic] || s.topic || ""), "What this sentence rests on", sentenceHtml(env, s));
    } else {
      const ch = (env.changes || [])[+m[2]];
      if (!ch) return false;
      openDrawer("Change since the previous run", CHANGE[ch.type] || cap(String(ch.type || "").replace(/_/g, " ")), changeHtml(env, ch));
    }
    return true;
  }

  /* ---------- company page ---------- */
  function section(id, num, title, state, body, note) {
    return '<section class="sec" id="s-' + id + '" aria-labelledby="h-' + id + '"><header class="sh"><span class="sn" aria-hidden="true">' + num + '</span><h2 id="h-' + id + '">' + esc(title) + "</h2>" +
      (state ? stChip(state.st, state.text) : "") + "</header>" + (note ? '<p class="snote">' + note + "</p>" : "") + body + "</section>";
  }
  function sub(title, st, text) { return '<h3 class="subh">' + esc(title) + (st ? stChip(st, text) : "") + "</h3>"; }
  function stateBox(env, fam, compact) {
    const st = stOf(env, fam);
    const note = st.note && st.note !== DEFAULT_NOTE ? st.note : (STATE[st.state] || {}).d;
    const checked = (st.checked_sources || []).filter(Boolean);
    return '<div class="stbox st-' + esc(st.state) + (compact ? " compact" : "") + '"><p><b>' + esc((STATE[st.state] || { w: st.state }).w) + ".</b> " + esc(note || "") + "</p>" +
      (checked.length ? '<p class="chk">Checked: ' + esc(checked.join(" · ")) + "</p>" : "") + "</div>";
  }
  function factLi(env, c, label) {
    let when = c.effective_date || "";
    if (typeof c.value === "string" && String(when).slice(0, 10) === c.value.slice(0, 10)) when = "";
    const rel = c.relationship && c.relationship !== "exact" ? ' <span class="tag" title="' + esc(REL[c.relationship] || "") + '">' + esc(c.relationship === "registered_subunit" ? "via workplace" : c.relationship.replace(/_/g, " ")) + "</span>" : "";
    return '<li class="fact"><span class="fl">' + (label || esc(c.label || c.field)) + rel + (c.carried_forward ? ' <span class="tag off">kept from previous run</span>' : "") + "</span>" +
      '<span class="fv">' + fmtValue(c) + "</span>" + (when ? '<span class="fd">' + fdate(when) + "</span>" : '<span class="fd"></span>') + srcBtn(env, c) + "</li>";
  }
  const factList = (env, cs) => (cs.length ? '<ul class="facts">' + cs.map((c) => factLi(env, c)).join("") + "</ul>" : "");

  function headHtml(env) {
    const org = env.organisation_number, x = IDX[org] || {};
    const form = one(env, "identity", "legal_form"), ind = one(env, "identity", "industry"), muni = one(env, "identity", "municipality"), fd = one(env, "identity", "founded");
    const picked = compare.includes(org);
    return '<header class="phead">' +
      '<a class="back" href="#/">' + ICON.back + "Companies</a>" +
      '<div class="over"><span class="mono">' + esc(orgFmt(org)) + '</span><button type="button" class="linkbtn sm" data-copy="' + esc(org) + '" aria-label="Copy organisation number">Copy</button>' +
      (form ? "<span>" + esc(form.value) + "</span>" : "") + (muni ? "<span>" + esc(valText(muni)) + "</span>" : "") + "</div>" +
      "<h1>" + esc(env.legal_name || x.name || org) + "</h1>" +
      '<p class="psub">' + esc(ind ? String(ind.value).replace(/^(\S+) (.*)$/, "$2 ($1)") : "Industry not registered") + (fd ? " · founded " + esc(String(fd.value).slice(0, 4)) : "") + "</p>" +
      '<div class="pact"><button type="button" class="btn" data-pick="' + org + '" data-lbl="1" aria-pressed="' + picked + '">' + ICON.pick + '<span class="bl">' + (picked ? "In compare" : "Add to compare") + "</span></button>" +
      '<a class="btn ghost" href="https://virksomhet.brreg.no/nb/oppslag/enheter/' + esc(org) + '" target="_blank" rel="noopener noreferrer">Brønnøysund record' + ICON.ext + "</a>" +
      '<button type="button" class="btn ghost" data-copy-link>Copy link</button>' +
      '<button type="button" class="btn ghost" data-download="' + esc(org) + '">Download JSON</button></div>' +
      '<p class="checked">Profile built ' + fdt((env.run || {}).completed_at) + " · run " + esc((env.run || {}).run_id || "") + "</p></header>";
  }
  function briefHtml(env) {
    const s = env.summary || {};
    const sents = (s.sentences || []).map((x, i) => {
      const n = (x.claim_keys || []).filter((k) => env._k[k]).length;
      return '<li><span class="topic">' + esc(TOPIC[x.topic] || cap(String(x.topic || "").replace(/_/g, " "))) + "</span><p>" + esc(x.text) +
        (x.method ? ' <span class="muted method">(' + esc(x.method) + ")</span>" : "") +
        (n ? ' <button type="button" class="cite" data-target="s:' + i + '" aria-label="Evidence for this sentence (' + plural(n, "fact") + ')">' + plural(n, "fact") + ICON.chev + "</button>" : ' <span class="cite none">run record</span>') + "</p></li>";
    }).join("");
    const unk = FAMKEYS.filter((f) => stOf(env, f).state !== "available");
    const unkHtml = unk.length ? '<div class="unk"><span class="topic">Unknown</span><ul>' + unk.map((f) => {
      const st = stOf(env, f);
      const note = st.note && st.note !== DEFAULT_NOTE ? st.note : "";
      return "<li><b>" + esc(famShort(f)) + "</b> " + stChip(st.state) + (note ? ' <span class="muted">' + esc(note) + "</span>" : "") + "</li>";
    }).join("") + "</ul></div>" : "";
    return '<section class="brief" aria-labelledby="h-brief"><h2 id="h-brief" class="eyebrow">Summary</h2><ol class="sents">' + (sents || "<li><p>No supported summary for this company.</p></li>") + "</ol>" + unkHtml + "</section>";
  }
  function kf(label, value, subText, claim, cls) {
    const inner = '<span class="kl">' + label + '</span><span class="kfv">' + value + "</span>" + (subText ? '<span class="ks">' + subText + "</span>" : "");
    return claim ? '<button type="button" class="kf ' + (cls || "") + '" data-target="f:' + esc(claim.key) + '">' + inner + "</button>" : '<div class="kf none ' + (cls || "") + '">' + inner + "</div>";
  }
  function keyFacts(env) {
    const rev = latestFin(env, "revenue"), res = latestFin(env, "annual_result"), eq = latestFin(env, "equity");
    const prev = rev ? finIn(env, "revenue", +rev.value.year - 1) : null;
    let delta = "";
    if (rev && prev && prev.value.amount) {
      const d = ((rev.value.amount - prev.value.amount) / Math.abs(prev.value.amount)) * 100;
      delta = (d >= 0 ? "▲ +" : "▼ −") + Math.abs(d).toFixed(Math.abs(d) < 10 ? 1 : 0) + "% on " + prev.value.year;
    }
    const emp = one(env, "identity", "registered_employees");
    const lead = rolesOf(env).find((c) => ["DAGL", "INNH"].includes(c.value.role_code)) || rolesOf(env).find((c) => c.value.role_code === "LEDE");
    const site = one(env, "website", "official_website");
    const wst = stOf(env, "website");
    const jobs = claimsOf(env, "jobs", "job_posting").filter((c) => (c.value || {}).status !== "closed");
    const careers = claimsOf(env, "jobs").find((c) => c.field === "careers_page" || c.field === "recruitment_channel");
    const jst = stOf(env, "jobs");
    const act = datedActivity(env, false)[0];
    const subs = claimsOf(env, "locations", "registered_subunit");
    return '<section class="kfs" aria-label="Key facts">' +
      kf("Revenue" + (rev ? " " + esc(rev.value.year) : ""), rev ? esc(money(rev.value.amount)) : "Not filed", esc(delta), rev) +
      kf("Annual result" + (res ? " " + esc(res.value.year) : ""), res ? esc(money(res.value.amount)) : "Not filed", "", res, res && res.value.amount < 0 ? "neg" : "") +
      kf("Equity" + (eq ? " " + esc(eq.value.year) : ""), eq ? esc(money(eq.value.amount)) : "Not filed", eq && eq.value.amount < 0 ? "negative equity" : "", eq, eq && eq.value.amount < 0 ? "neg" : "") +
      kf("Employees", emp ? esc(nf.format(emp.value)) : "Not registered", emp ? "registered" + (emp.effective_date ? ", " + fdate(emp.effective_date) : "") : "", emp) +
      kf(lead ? esc(ROLE_EN[lead.value.role_code] || lead.value.role) : "Leadership", lead ? esc(lead.value.name) : "No roles registered", subs.length ? plural(subs.length, "registered workplace") : "", lead) +
      kf("Website", site ? esc(site.value.domain) : esc(STATE[wst.state].w), site ? "verified: " + esc((site.value.identity_proof || []).map((p) => (PROOF[p] || [p])[0].toLowerCase()).join(", ")) : "", site, site ? "ok" : "st-" + wst.state) +
      kf("Hiring", jobs.length ? plural(jobs.length, "open posting") : careers ? "Careers page" : esc(STATE[jst.state].w), jobs.length ? "latest " + fdate(jobs.map((c) => c.effective_date || "").sort().pop()) : careers ? "no individual postings found" : "", jobs[0] || careers) +
      kf("Latest activity", act ? fdate(act.effective_date) : "None dated", act ? esc(clip(valText(act), 60)) : "", act) +
      "</section>";
  }
  const clip = (s, n) => (String(s).length > n ? String(s).slice(0, n - 1).replace(/\s+\S*$/, "") + "…" : String(s));
  function coverage(env) {
    return '<section class="cov" aria-labelledby="h-cov"><h2 id="h-cov" class="eyebrow">Coverage by information type</h2><ul class="covl">' + FAMKEYS.map((f) => {
      const st = stOf(env, f), n = (env._f[f] || []).length;
      return '<li><button type="button" class="covc s-' + esc(st.state) + '" data-jump="' + SEC_OF[f] + '" title="' + esc(FAML[f] + ": " + (st.note || STATE[st.state].d)) + '"><i aria-hidden="true"></i><span class="cn">' + esc(famShort(f)) +
        '</span><span class="cs">' + (st.state === "available" ? plural(n, "fact") : esc(STATE[st.state].w)) + "</span></button></li>";
    }).join("") + "</ul>" + legend() + "</section>";
  }
  function legend() {
    return '<div class="legend" aria-label="Legend">' + ["available", "not_available", "ambiguous", "blocked", "failed", "not_applicable"].map((s) => '<span><i class="s-' + s + '"></i>' + STATE[s].w + "</span>").join("") + "</div>";
  }
  function secNav() {
    const items = [["identity", "Identity"], ["accounts", "Accounts"], ["leadership", "Leadership"], ["online", "Website & profiles"], ["activity", "Hiring & activity"], ["evidence", "Evidence"], ["changes", "Changes"]];
    return '<nav class="secnav" aria-label="Sections of this profile"><ul>' + items.map((i) => '<li><button type="button" data-jump="' + i[0] + '">' + i[1] + "</button></li>").join("") + "</ul></nav>";
  }
  function secState(env, key) {
    const s = (env.sections || {})[key];
    return s ? { st: s.state } : null;
  }
  function identitySection(env) {
    const ids = claimsOf(env, "identity").slice().sort((a, b) => {
      const ia = ID_ORDER.indexOf(a.field), ib = ID_ORDER.indexOf(b.field);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
    const desc = claimsOf(env, "description");
    const descHtml = desc.length ? desc.map((c) => '<figure class="say"><figcaption>' + esc(c.label) + "</figcaption><blockquote>" + esc(valText(c)) + "</blockquote>" + srcBtn(env, c) + "</figure>").join("") : stateBox(env, "description", true);
    return section("identity", "01", "Identity & brand", secState(env, "legal_identity_and_brand"),
      '<div class="two"><div>' + sub("Register record") + factList(env, ids) + "</div><div>" + sub("What it does", stOf(env, "description").state === "available" ? null : stOf(env, "description").state) + descHtml + "</div></div>");
  }
  function barChart(title, pts, cls) {
    const W = 300, H = 156, padT = 20;
    const pos = Math.max(0, ...pts.map((d) => (d.v == null ? 0 : d.v)));
    const neg = Math.max(0, ...pts.map((d) => (d.v == null ? 0 : -d.v)));
    const padB = neg > 0 ? 36 : 24;
    const plotH = H - padT - padB, span = pos + neg || 1, zeroY = padT + plotH * (pos / span);
    const n = Math.max(1, pts.length), slot = (W - 8) / n, bw = Math.min(46, slot * 0.58);
    let g = '<line class="zero" x1="0" x2="' + W + '" y1="' + zeroY + '" y2="' + zeroY + '"/>';
    pts.forEach((d, i) => {
      const cx = 4 + i * slot + slot / 2, x = cx - bw / 2, last = i === n - 1;
      if (d.v == null) {
        g += '<text class="na" x="' + cx + '" y="' + (zeroY - 6) + '" text-anchor="middle">no figure</text>';
      } else {
        const h = Math.max(1, (Math.abs(d.v) / span) * plotH), y = d.v >= 0 ? zeroY - h : zeroY;
        g += '<rect class="' + (d.v < 0 ? "neg" : last ? "lat" : "bar") + '" x="' + x + '" y="' + y + '" width="' + bw + '" height="' + h + '" rx="1.5"><title>' + esc(title + " " + d.y + ": " + fullMoney(d.v)) + "</title></rect>";
        g += '<text class="vl" x="' + cx + '" y="' + (d.v >= 0 ? y - 5 : y + h + 13) + '" text-anchor="middle">' + esc(compact(d.v)) + "</text>";
      }
      g += '<text class="yr' + (last ? " lat" : "") + '" x="' + cx + '" y="' + (H - 6) + '" text-anchor="middle">' + esc(d.y) + "</text>";
    });
    return '<figure class="chart ' + (cls || "") + '"><figcaption>' + esc(title) + ' <span class="muted">NOK</span></figcaption><svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' +
      esc(title + ": " + pts.map((d) => d.y + " " + (d.v == null ? "no figure" : money(d.v))).join(", ")) + '">' + g + "</svg></figure>";
  }
  function accountsSection(env) {
    const fin = finOf(env);
    const pdfs = claimsOf(env, "financials", "annual_report_copy").filter((c) => c.value && c.value.year).sort((a, b) => String(b.value.year).localeCompare(String(a.value.year)));
    const st = secState(env, "annual_accounts");
    if (!fin.length && !pdfs.length) return section("accounts", "02", "Latest accounts", st, stateBox(env, "financials"));
    const years = [...new Set(fin.map((c) => String(c.value.year)))].sort();
    const get = (f, y) => fin.find((c) => c.field === f && String(c.value.year) === y);
    let body = "";
    if (years.length) {
      const pts = (f) => years.map((y) => { const c = get(f, y); return { y, v: c ? c.value.amount : null }; });
      const charts = [];
      if (fin.some((c) => c.field === "revenue")) charts.push(barChart("Operating revenue", pts("revenue")));
      if (fin.some((c) => c.field === "annual_result")) charts.push(barChart("Annual result", pts("annual_result"), "res"));
      const latest = years[years.length - 1];
      const periods = [...new Set(fin.filter((c) => String(c.value.year) === latest && c.reporting_period).map((c) => c.reporting_period))];
      body += '<div class="charts">' + charts.join("") + "</div>";
      body += '<div class="tblwrap"><table class="fin"><caption class="sr">Filed figures by year, NOK. Each figure opens its evidence.</caption><thead><tr><th scope="col">NOK</th>' +
        years.map((y) => '<th scope="col"' + (y === latest ? ' class="lat"' : "") + ">" + esc(y) + "</th>").join("") + "</tr></thead><tbody>" +
        FIN_ROWS.filter(([f]) => years.some((y) => get(f, y))).map(([f, label]) => '<tr><th scope="row">' + esc(label) + "</th>" + years.map((y) => {
          const c = get(f, y);
          return "<td" + (y === latest ? ' class="lat"' : "") + ">" + (c ? '<button type="button" class="num' + (c.value.amount < 0 ? " neg" : "") + '" data-target="f:' + esc(c.key) + '" title="' + esc(fullMoney(c.value.amount, c.value.currency)) + ' · open evidence">' + esc(compact(c.value.amount)) + "</button>" : '<span class="muted">—</span>') + "</td>";
        }).join("") + "</tr>").join("") + "</tbody></table></div>";
      body += '<p class="fnote">Figures as filed in the Register of Company Accounts (Regnskapsregisteret)' + (periods.length ? "; latest reporting period " + periods.map(fperiod).join(", ") : "") +
        ". Bars start at zero. A dash means no figure was filed for that year. Select a figure to see its source.</p>";
    } else {
      body += '<p class="fnote">No figures were filed in machine-readable form; the filed copies are listed below.</p>';
    }
    if (pdfs.length) {
      body += '<div class="pdfs"><span class="muted">Filed copies (PDF):</span> ' + pdfs.slice(0, 12).map((c) => link(c.value.url, c.value.year)).join(" ") + (pdfs.length > 12 ? ' <span class="muted">+ ' + (pdfs.length - 12) + " earlier</span>" : "") +
        " " + srcBtn(env, pdfs[0], "Evidence") + "</div>";
    }
    return section("accounts", "02", "Latest accounts", st, body);
  }
  function leadershipSection(env) {
    const roles = rolesOf(env);
    const pst = stOf(env, "people");
    const peopleHtml = roles.length ? '<ul class="facts people">' + roles.map((c) => {
      const v = c.value;
      return '<li class="fact"><span class="fl">' + esc(ROLE_EN[v.role_code] || v.role) + (ROLE_EN[v.role_code] ? ' <span class="muted">' + esc(v.role) + "</span>" : "") + "</span>" +
        '<span class="fv">' + fmtValue(c) + '</span><span class="fd">' + (c.effective_date ? fdate(c.effective_date) : "") + "</span>" + srcBtn(env, c) + "</li>";
    }).join("") + "</ul>" : stateBox(env, "people", true);
    const subs = claimsOf(env, "locations", "registered_subunit");
    const other = claimsOf(env, "locations").filter((c) => c.field !== "registered_subunit");
    const subLi = (c) => {
      const v = c.value || {};
      return '<li class="wp"><div class="wpn">' + esc(v.name || "Workplace") + ' <span class="muted mono sm">' + (v.organisation_number ? orgLink(v.organisation_number) : "") + "</span></div>" +
        '<div class="muted">' + esc([v.address, v.industry].filter(Boolean).join(" · ")) + "</div>" +
        '<div class="wpm">' + (v.registered_employees != null ? '<span class="tag">' + plural(v.registered_employees, "employee") + "</span>" : "") + (c.effective_date ? '<span class="muted sm">since ' + fdate(c.effective_date) + "</span>" : "") + srcBtn(env, c) + "</div></li>";
    };
    let wpHtml = subs.length ? '<ul class="wps">' + subs.slice(0, 6).map(subLi).join("") + "</ul>" + (subs.length > 6 ? '<details class="morelist"><summary>Show all ' + subs.length + " workplaces</summary><ul class=\"wps\">" + subs.slice(6).map(subLi).join("") + "</ul></details>" : "") : "";
    wpHtml += factList(env, other);
    if (!subs.length && !other.length) wpHtml = stateBox(env, "locations", true);
    return section("leadership", "03", "Leadership & workplaces", secState(env, "leadership_and_workplaces"),
      '<div class="two"><div>' + sub("Registered roles", pst.state === "available" ? null : pst.state) + peopleHtml + "</div><div>" + sub("Workplaces and addresses", subs.length ? "available" : null, subs.length ? plural(subs.length, "registered workplace") : "") + wpHtml + "</div></div>");
  }
  function onlineSection(env) {
    const site = one(env, "website", "official_website");
    const wst = stOf(env, "website");
    const regSite = one(env, "identity", "registered_website");
    let siteHtml;
    if (site) {
      const v = site.value || {};
      const evs = (site.evidence_ids || []).map((id) => env._ev[id]).filter(Boolean);
      siteHtml = '<div class="site"><div class="siteh">' + link(v.url, v.domain, "dom") + ICON.ext + stChip("available", "Verified") + "</div>" + (v.title ? '<div class="muted">' + esc(v.title) + "</div>" : "") +
        '<ul class="prooflist">' + (v.identity_proof || []).map((p) => {
          const e = evs.find((x) => x.extraction_method === "identity_proof_" + p);
          const d = PROOF[p] || [p, p.replace(/_/g, " ")];
          return "<li>" + ICON.check + "<div><b>" + esc(d[0]) + "</b> " + esc(e ? "on " + pageKind(e.final_url || e.source_url) : "") + (e && e.claim_span ? '<span class="qs"><mark>' + esc(clip(e.claim_span, 120)) + "</mark></span>" : "") + "</div></li>";
        }).join("") + "</ul>" + '<div class="siteact">' + srcBtn(env, site, "Proof and evidence") + "</div></div>";
      siteHtml += factList(env, claimsOf(env, "website").filter((c) => c !== site));
    } else {
      siteHtml = stateBox(env, "website");
      if (regSite) siteHtml += '<p class="fnote">The register lists ' + fmtValue(regSite) + ", but the site did not prove it belongs to this exact organisation number, so it is not treated as the official website. " + srcBtn(env, regSite, "Register field") + "</p>";
      siteHtml += factList(env, claimsOf(env, "website"));
    }
    const soc = claimsOf(env, "social"), sst = stOf(env, "social");
    const socHtml = soc.length ? factList(env, soc) + '<p class="fnote">Profiles count only when the verified site links to them, or Wikidata lists them on the item carrying this organisation number.</p>' : stateBox(env, "social", true);
    const con = claimsOf(env, "contact"), cst = stOf(env, "contact");
    const conHtml = con.length ? factList(env, con) : stateBox(env, "contact", true);
    return section("online", "04", "Website & profiles", secState(env, "website_and_profiles"),
      sub("Official website", site ? null : wst.state) + siteHtml + '<div class="two">' + "<div>" + sub("Company-owned profiles", sst.state, sst.state === "available" ? plural(soc.length, "profile") : null) + socHtml + "</div>" +
      "<div>" + sub("Contact details", cst.state, cst.state === "available" ? plural(con.length, "detail") : null) + conHtml + "</div></div>");
  }
  const tlState = { routine: false, all: false };
  function timelineHtml(env) {
    const all = datedActivity(env, true);
    const routineN = all.filter((c) => ROUTINE.has(c.field)).length;
    let list = tlState.routine ? all : all.filter((c) => !ROUTINE.has(c.field));
    const total = list.length;
    if (!tlState.all) list = list.slice(0, 12);
    if (!all.length) return stateBox(env, "activity", true);
    let year = "", html = '<ol class="tl">';
    list.forEach((c) => {
      const y = String(c.effective_date).slice(0, 4);
      if (y !== year) { year = y; html += '<li class="ty" aria-hidden="true">' + esc(y) + "</li>"; }
      const d = String(c.effective_date).slice(0, 10).match(/^(\d{4})-(\d{2})-(\d{2})$/);
      html += '<li class="ti' + (ROUTINE.has(c.field) ? " routine" : "") + '"><time datetime="' + esc(String(c.effective_date).slice(0, 10)) + '">' + (d ? +d[3] + " " + MON[+d[2] - 1] : esc(c.effective_date)) + '<span class="sr"> ' + y + "</span></time>" +
        '<div class="tb"><span class="tk">' + esc(c.label || c.field) + (c.relationship && c.relationship !== "exact" ? ' <span class="tag">via workplace</span>' : "") + '</span><span class="tt">' + fmtValue(c) + "</span></div>" + srcBtn(env, c) + "</li>";
    });
    html += "</ol>";
    html += '<div class="tlc">' + (routineN ? '<label class="tog"><input type="checkbox" data-tl="routine"' + (tlState.routine ? " checked" : "") + "> Include routine register updates (" + routineN + ")</label>" : "") +
      (total > 12 ? '<button type="button" class="linkbtn" data-tl="all">' + (tlState.all ? "Show the latest 12" : "Show all " + total + " dated items") + "</button>" : "") + "</div>";
    return html;
  }
  function activitySection(env) {
    const jobs = claimsOf(env, "jobs"), jst = stOf(env, "jobs");
    const open = jobs.filter((c) => c.field === "job_posting" && (c.value || {}).status !== "closed");
    const closed = jobs.filter((c) => c.field === "job_posting" && (c.value || {}).status === "closed");
    const otherJobs = jobs.filter((c) => c.field !== "job_posting");
    let jobsHtml = "";
    if (jobs.length) {
      jobsHtml = factList(env, open) + factList(env, otherJobs) + (closed.length ? '<details class="morelist"><summary>' + plural(closed.length, "closed posting") + "</summary>" + factList(env, closed) + "</details>" : "");
      if (!open.length) jobsHtml = '<p class="fnote">No open postings were found' + (jst.state === "failed" ? " (the job feed failed this run)" : "") + "; what was found is listed below.</p>" + jobsHtml;
    } else jobsHtml = stateBox(env, "jobs", true);
    const rev = claimsOf(env, "reviews"), rst = stOf(env, "reviews");
    const actN = datedActivity(env, false).length;
    return section("activity", "05", "Hiring & activity", secState(env, "hiring_and_activity"),
      '<div class="two"><div>' + sub("Hiring", jst.state, open.length ? plural(open.length, "open posting") : null) + jobsHtml + "</div><div>" + sub("Customer ratings", rst.state) + (rev.length ? factList(env, rev) : stateBox(env, "reviews", true)) + "</div></div>" +
      sub("Dated public activity", stOf(env, "activity").state, actN ? plural(actN, "dated item") : null) + '<div id="tl">' + timelineHtml(env) + "</div>");
  }
  function evidenceSection(env) {
    const rows = FAMKEYS.map((f) => {
      const st = stOf(env, f), n = (env._f[f] || []).length;
      const note = st.note && st.note !== DEFAULT_NOTE ? st.note : st.state === "available" ? "" : STATE[st.state].d;
      return '<tr><th scope="row">' + esc(FAML[f]) + "</th><td>" + stChip(st.state) + '</td><td class="n">' + (n ? nf.format(n) : "—") + "</td><td>" + (note ? esc(note) + "<br>" : "") +
        '<span class="muted sm">' + esc((st.checked_sources || []).filter(Boolean).join(" · ") || "") + "</span></td></tr>";
    }).join("");
    const by = {};
    (env.evidence || []).forEach((e) => { const k = e.source_name || host(e.source_url); (by[k] = by[k] || { n: 0, cls: e.source_class }).n++; });
    const srcs = Object.entries(by).sort((a, b) => b[1].n - a[1].n);
    const max = Math.max(1, ...srcs.map((s) => s[1].n));
    const times = (env.evidence || []).map((e) => e.retrieved_at).filter(Boolean).sort();
    const hashes = new Set((env.evidence || []).map((e) => e.content_sha256)).size;
    const errs = env.errors || [];
    const ops = env.operations || {};
    return section("evidence", "06", "Evidence & availability", { st: "available", text: plural((env.claims || []).length, "fact") },
      '<div class="tblwrap"><table class="avail"><thead><tr><th scope="col">Information type</th><th scope="col">State</th><th scope="col" class="n">Facts</th><th scope="col">Agent note and what was checked</th></tr></thead><tbody>' + rows + "</tbody></table></div>" +
      '<div class="two"><div>' + sub("Where the evidence comes from") + '<ul class="srcs">' + srcs.map(([k, v]) => '<li><span class="sl">' + esc(k) + ' <span class="muted sm">' + esc(CLASS[v.cls] || "") + '</span></span><span class="sb"><i style="width:' + Math.max(2, (v.n / max) * 100) + '%"></i></span><span class="n">' + nf.format(v.n) + "</span></li>").join("") + "</ul></div>" +
      "<div>" + sub("Run record") + '<dl class="kv">' +
      "<dt>Facts</dt><dd>" + nf.format((env.claims || []).length) + "</dd><dt>Evidence records</dt><dd>" + nf.format((env.evidence || []).length) + " (" + plural(hashes, "distinct fetched document") + ")</dd>" +
      (times.length ? "<dt>Fetched</dt><dd>" + fdt(times[0]) + (times[times.length - 1] !== times[0] ? " – " + fdt(times[times.length - 1]).replace(/^.*?, /, "") : "") + "</dd>" : "") +
      (ops.runtime_ms != null ? "<dt>Time spent</dt><dd>" + dur(ops.runtime_ms / 1000) + "</dd>" : "") +
      (ops.third_party_cost_usd != null ? "<dt>Third-party cost</dt><dd>$" + Number(ops.third_party_cost_usd).toFixed(2) + "</dd>" : "") +
      "<dt>Source errors</dt><dd>" + (errs.length ? '<ul class="errs">' + errs.map((e) => "<li><b>" + esc(e.source || "") + "</b>: " + esc(e.message || "") + "</li>").join("") + "</ul>" : "None recorded") + "</dd></dl></div></div>");
  }
  function changesSection(env) {
    const ch = env.changes || [], r = env.refresh || {};
    const carried = (env.claims || []).filter((c) => c.carried_forward);
    let body;
    if (!r.previous_run_id) {
      body = '<p class="fnote">First run for this company, so there is nothing to compare with yet. The next run compares every fact by its stable key and lists what was added, removed or changed, with evidence for both sides.</p>';
    } else {
      body = '<dl class="kv inline"><dt>Previous run</dt><dd>' + esc(r.previous_run_id) + (r.previous_completed_at ? ", " + fdt(r.previous_completed_at) : "") + "</dd>" + (r.compared_at ? "<dt>Compared</dt><dd>" + fdt(r.compared_at) + "</dd>" : "") +
        "<dt>Kept from previous run</dt><dd>" + plural(r.carried_forward || 0, "fact") + "</dd></dl>";
      body += ch.length ? '<ul class="chg">' + ch.map((e, i) => '<li><span class="tag ' + esc(e.change || "") + '">' + esc(cap(e.change || e.type)) + '</span><div class="cb"><b>' + esc(CHANGE[e.type] || cap(String(e.type).replace(/_/g, " "))) + "</b> " +
        '<span class="muted">' + esc(famShort(e.family)) + (e.materiality ? " · " + esc(e.materiality) + " materiality" : "") + "</span><div>" +
        (e.previous !== undefined ? "<s>" + esc(objText(e.previous)) + "</s> " : "") + (e.previous !== undefined && e.current !== undefined ? "→ " : "") + (e.current !== undefined ? esc(objText(e.current)) : "") + "</div></div>" +
        '<button type="button" class="src" data-target="c:' + i + '"><span class="src-n">Evidence</span>' + ICON.chev + "</button></li>").join("") + "</ul>"
        : '<p class="fnote">Every fact is unchanged since the previous run.</p>';
    }
    if (carried.length) body += sub("Kept from the previous run") + factList(env, carried);
    return section("changes", "07", "Changes since the last run", { st: ch.length ? "available" : "not_available", text: r.previous_run_id ? plural(ch.length, "change") : "First run" }, body);
  }
  function renderProfile(env) {
    const main = $("#main");
    if (env.status === "failed") {
      main.innerHTML = '<div class="page">' + headHtml(env) + '<div class="stbox st-failed"><p><b>Not found in the official register.</b> The organisation number could not be anchored in Brønnøysundregistrene, so no other source was trusted for it.</p></div>' + evidenceSection(env) + foot() + "</div>";
    } else {
      main.innerHTML = '<div class="page">' + headHtml(env) + briefHtml(env) + keyFacts(env) + coverage(env) + secNav() +
        identitySection(env) + accountsSection(env) + leadershipSection(env) + onlineSection(env) + activitySection(env) + evidenceSection(env) + changesSection(env) + foot() + "</div>";
    }
    document.title = (env.legal_name || env.organisation_number) + " · Kildespor";
    spy();
  }
  let spyIO = null;
  function spy() {
    if (spyIO) spyIO.disconnect();
    if (!("IntersectionObserver" in window)) return;
    const btns = $$(".secnav button");
    spyIO = new IntersectionObserver((es) => {
      es.forEach((e) => { if (e.isIntersecting) btns.forEach((b) => b.toggleAttribute("aria-current", b.dataset.jump === e.target.id.slice(2))); });
    }, { rootMargin: "-30% 0px -60% 0px" });
    $$(".sec").forEach((s) => spyIO.observe(s));
  }
  function foot() {
    const r = KS.run || {};
    return '<footer class="foot"><div><b>How a fact gets in.</b> The organisation number is the anchor. A website is published only when the site proves it belongs to this entity; social profiles only when the verified site or the matching Wikidata item links them; job ads only when the employer field names this organisation number or one of its workplaces. When the match is uncertain the fact is withheld and the profile says so. Missing values stay missing, never zero.</div>' +
      "<div><b>Sources.</b> Brønnøysundregistrene (Enhetsregisteret, Regnskapsregisteret, role and sub-unit registers, NLOD 2.0), the company's own website, NAV arbeidsplassen, Støtteregisteret, Mattilsynet, Finanstilsynet, TED, Wikidata (CC0).</div>" +
      '<div class="muted">Kildespor ' + esc(String(r.agent || "").replace(/^kildespor\s*/, "")) + " · run " + esc(r.run_id || "") + " · this viewer works offline from the run folder.</div></footer>";
  }

  /* ---------- compare ---------- */
  async function renderCompare(orgs) {
    const main = $("#main");
    main.innerHTML = '<div class="page"><p class="loading">Loading profiles…</p></div>';
    const envs = (await Promise.all(orgs.map((o) => load(o).catch(() => null)))).filter(Boolean);
    if (envs.length < 2) {
      main.innerHTML = '<div class="page"><a class="back" href="#/">' + ICON.back + 'Companies</a><h1 class="ph">Compare companies</h1><p>Pick two to four companies with the ' + ICON.pick + " button in the list or on a profile, then choose Compare. The link to a comparison can be shared.</p></div>";
      document.title = "Compare · Kildespor";
      return;
    }
    setCompare(envs.map((e) => e.organisation_number), true);
    const L = "ABCD";
    const cell = (env, c, text, extra) => (c ? '<button type="button" class="cv" data-target="f:' + esc(c.key) + '">' + (text != null ? text : esc(valText(c))) + "</button>" + (extra || "") : '<span class="muted">' + (text || "—") + "</span>");
    const fin = (field, delta) => (e) => {
      const c = latestFin(e, field);
      if (!c) return '<span class="muted">Not filed</span>';
      let d = "";
      if (delta) {
        const p = finIn(e, field, +c.value.year - 1);
        if (p && p.value.amount) { const x = ((c.value.amount - p.value.amount) / Math.abs(p.value.amount)) * 100; d = '<span class="dl">' + (x >= 0 ? "+" : "−") + Math.abs(x).toFixed(0) + "% on " + p.value.year + "</span>"; }
      }
      return cell(e, c, '<span class="' + (c.value.amount < 0 ? "neg" : "") + '">' + esc(money(c.value.amount)) + '</span> <span class="yr">' + esc(c.value.year) + "</span>") + d;
    };
    const allYears = [...new Set(envs.flatMap((e) => finOf(e).filter((c) => c.field === "revenue").map((c) => String(c.value.year))))].sort().slice(-5);
    const revMax = Math.max(1, ...envs.flatMap((e) => finOf(e).filter((c) => c.field === "revenue").map((c) => Math.abs(c.value.amount))));
    const spark = (e) => {
      if (!allYears.length) return '<span class="muted">—</span>';
      const W = 150, H = 44, n = allYears.length, slot = W / n, bw = Math.min(22, slot * 0.6);
      let g = '<line class="zero" x1="0" x2="' + W + '" y1="' + (H - 12) + '" y2="' + (H - 12) + '"/>';
      if (!allYears.some((y) => { const c = finIn(e, "revenue", y); return c && c.value.amount > 0; })) {
        return '<span class="muted">' + (allYears.some((y) => finIn(e, "revenue", y)) ? "Zero revenue in every filed year" : "No revenue figures filed") + "</span>";
      }
      allYears.forEach((y, i) => {
        const c = finIn(e, "revenue", y), cx = i * slot + slot / 2;
        if (c && c.value.amount > 0) { const h = Math.max(1, (c.value.amount / revMax) * (H - 16)); g += '<rect class="' + (i === n - 1 ? "lat" : "bar") + '" x="' + (cx - bw / 2) + '" y="' + (H - 12 - h) + '" width="' + bw + '" height="' + h + '"><title>' + esc(y + ": " + fullMoney(c.value.amount)) + "</title></rect>"; }
        g += '<text class="yr" x="' + cx + '" y="' + (H - 1) + '" text-anchor="middle">' + esc(y.slice(2)) + "</text>";
      });
      return '<svg class="spark" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Revenue by year, shared scale across compared companies">' + g + "</svg>";
    };
    const role = (codes) => (e) => {
      const r = rolesOf(e).filter((c) => codes.includes(c.value.role_code));
      return r.length ? r.slice(0, 3).map((c) => cell(e, c, esc(c.value.name))).join("") + (r.length > 3 ? '<span class="muted"> +' + (r.length - 3) + "</span>" : "") : '<span class="muted">None registered</span>';
    };
    const stateText = (e, f) => { const st = stOf(e, f); return stChip(st.state); };
    const groups = [
      ["Identity", [
        ["Industry", (e) => { const c = one(e, "identity", "industry"); return c ? cell(e, c, esc(String(c.value).replace(/^\S+ /, ""))) : '<span class="muted">—</span>'; }],
        ["Municipality", (e) => cell(e, one(e, "identity", "municipality"))],
        ["Legal form", (e) => cell(e, one(e, "identity", "legal_form"))],
        ["Founded", (e) => cell(e, one(e, "identity", "founded"))],
        ["Registered employees", (e) => cell(e, one(e, "identity", "registered_employees"), null) || ""],
        ["Registered workplaces", (e) => { const s = claimsOf(e, "locations", "registered_subunit"); return s.length ? cell(e, s[0], plural(s.length, "workplace")) : '<span class="muted">None registered</span>'; }],
      ]],
      ["Latest accounts", [
        ["Revenue", fin("revenue", true)], ["Revenue history", spark], ["Operating result", fin("operating_result")], ["Annual result", fin("annual_result")],
        ["Equity", fin("equity")], ["Total assets", fin("total_assets")], ["Payroll costs", fin("payroll_cost")],
      ]],
      ["Leadership", [
        ["Managing director", role(["DAGL", "INNH"])], ["Chair of the board", role(["LEDE"])],
        ["Board members", (e) => { const r = rolesOf(e).filter((c) => c.value.role_code === "MEDL"); return r.length ? cell(e, r[0], plural(r.length, "member")) : '<span class="muted">None registered</span>'; }],
        ["Auditor", role(["REVI"])],
      ]],
      ["Website & profiles", [
        ["Website", (e) => { const c = one(e, "website", "official_website"); return c ? cell(e, c, esc(c.value.domain)) + '<span class="dl">' + esc((c.value.identity_proof || []).map((p) => (PROOF[p] || [p])[0]).join(", ")) + "</span>" : stateText(e, "website"); }],
        ["Profiles", (e) => { const s = claimsOf(e, "social"); return s.length ? s.slice(0, 4).map((c) => cell(e, c, esc(cap(c.value.platform)))).join("") : stateText(e, "social"); }],
        ["Contact details", (e) => { const s = claimsOf(e, "contact"); return s.length ? cell(e, s[0], plural(s.length, "detail") + " published") : stateText(e, "contact"); }],
      ]],
      ["Hiring & activity", [
        ["Open job postings", (e) => { const j = claimsOf(e, "jobs", "job_posting").filter((c) => (c.value || {}).status !== "closed"); return j.length ? cell(e, j[0], plural(j.length, "posting")) : stateText(e, "jobs"); }],
        ["Careers page", (e) => { const c = claimsOf(e, "jobs").find((x) => x.field === "careers_page" || x.field === "recruitment_channel"); return c ? cell(e, c, "Yes") : '<span class="muted">None found</span>'; }],
        ["Latest dated activity", (e) => { const a = datedActivity(e, false)[0]; return a ? cell(e, a, '<span class="yr">' + fdate(a.effective_date) + "</span> " + esc(clip(valText(a), 70))) : '<span class="muted">None</span>'; }],
        ["Dated items, last 12 months", (e) => {
          const cut = new Date(Date.parse((e.run || {}).completed_at || new Date().toISOString()) - 365 * 864e5).toISOString().slice(0, 10);
          return nf.format(datedActivity(e, false).filter((c) => String(c.effective_date) >= cut).length);
        }],
        ["Customer rating", (e) => { const c = one(e, "reviews", "customer_rating"); return c ? cell(e, c) : stateText(e, "reviews"); }],
      ]],
      ["Evidence & coverage", [
        ["Coverage", (e) => miniRibbon(FAMKEYS.map((f) => stOf(e, f).state)) + '<span class="dl">' + FAMKEYS.filter((f) => stOf(e, f).state === "available").length + " of " + FAMKEYS.length + " types found</span>"],
        ["Not found or withheld", (e) => { const u = FAMKEYS.filter((f) => stOf(e, f).state !== "available"); return u.length ? '<ul class="ul">' + u.map((f) => "<li>" + esc(famShort(f)) + " " + stChip(stOf(e, f).state) + "</li>").join("") + "</ul>" : "Nothing"; }],
        ["Facts and evidence", (e) => plural((e.claims || []).length, "fact") + ' <span class="muted">· ' + plural((e.evidence || []).length, "record") + "</span>"],
        ["Changes since last run", (e) => ((e.refresh || {}).previous_run_id ? plural((e.changes || []).length, "change") : '<span class="muted">First run</span>')],
      ]],
    ];
    const head = envs.map((e, i) => '<th scope="col" data-ci="' + i + '"><div class="ch"><span class="lt" data-ci="' + i + '">' + L[i] + '</span><div><a href="#/c/' + e.organisation_number + '">' + esc(e.legal_name || e.organisation_number) + '</a><span class="muted mono sm">' + orgFmt(e.organisation_number) +
      '</span></div><button type="button" class="iconbtn sm" data-unpick="' + e.organisation_number + '" aria-label="Remove ' + esc(e.legal_name) + ' from compare">' + ICON.cross + "</button></div></th>").join("");
    const body = groups.map(([g, rows]) => '<tbody><tr class="grp"><th scope="colgroup" colspan="' + (envs.length + 1) + '">' + esc(g) + "</th></tr>" +
      rows.map(([label, fn]) => '<tr><th scope="row">' + esc(label) + "</th>" + envs.map((e, i) => '<td data-org="' + e.organisation_number + '" data-ci="' + i + '"><span class="lt" data-ci="' + i + '" aria-hidden="true">' + L[i] + "</span><div class=\"cc\">" + (fn(e) || '<span class="muted">—</span>') + "</div></td>").join("") + "</tr>").join("") + "</tbody>").join("");
    const legendList = '<ol class="cmplegend">' + envs.map((e, i) => '<li><span class="lt" data-ci="' + i + '">' + L[i] + '</span><a href="#/c/' + e.organisation_number + '">' + esc(e.legal_name) + '</a><span class="muted mono sm">' + orgFmt(e.organisation_number) + "</span></li>").join("") + "</ol>";
    main.innerHTML = '<div class="page wide"><a class="back" href="#/">' + ICON.back + "Companies</a>" +
      '<header class="cmph"><div><div class="eyebrow">Compare</div><h1 class="ph">' + plural(envs.length, "company", "companies") + " side by side</h1><p class=\"muted\">Every value is a fact from the profile. Select one to see its source, retrieval time and hash.</p></div>" +
      '<div class="pact"><button type="button" class="btn ghost" data-copy-link>Copy link to this comparison</button></div></header>' + legendList +
      '<div class="cmpwrap"><table class="cmp n' + envs.length + '"><caption class="sr">Side-by-side comparison</caption><thead><tr><th scope="col"><span class="sr">Field</span></th>' + head + "</tr></thead>" + body + "</table></div>" + foot() + "</div>";
    document.title = "Compare " + envs.map((e) => e.legal_name).join(" / ") + " · Kildespor";
  }

  /* ---------- run overview ---------- */
  function renderOverview() {
    const r = KS.run || {}, n = KS.index.length, ops = r.operations || {};
    const counts = FAMKEYS.map((f, i) => { const c = {}; KS.index.forEach((x) => { const s = x.ribbon[i] || "not_available"; c[s] = (c[s] || 0) + 1; }); return c; });
    const val = r.validation || {};
    const checks = Object.entries(val.checks || {});
    const changed = KS.index.filter((x) => x.changes > 0);
    const stat = (label, v, s) => '<div class="stat"><dt>' + label + "</dt><dd>" + v + (s ? "<small>" + s + "</small>" : "") + "</dd></div>";
    const covRows = FAMKEYS.map((f, i) => {
      const c = counts[i], found = c.available || 0;
      return '<li class="covrow"><span class="cl">' + esc(famShort(f)) + '<span class="muted sm">' + esc(FAML[f]) + '</span></span><span class="segs">' + ST_ORDER.filter((s) => c[s]).map((s) =>
        '<button type="button" class="seg s-' + s + '" style="flex-grow:' + c[s] + '" data-ff="' + f + '" data-fs="' + s + '" title="' + esc(famShort(f) + ": " + c[s] + " " + STATE[s].w.toLowerCase() + ". Show these companies") + '" aria-label="' +
        esc(famShort(f) + ": " + c[s] + " companies " + STATE[s].w.toLowerCase() + ". Show them in the list") + '">' + (c[s] / n >= 0.08 ? nf.format(c[s]) : "") + "</button>").join("") +
        '</span><span class="cp"><b>' + Math.round((found / Math.max(1, n)) * 100) + "%</b> found</span></li>";
    }).join("");
    const bySrc = Object.entries(ops.by_source || {}).sort((a, b) => b[1] - a[1]);
    const srcMax = Math.max(1, ...bySrc.map((s) => s[1]));
    const top = (arr, fmt) => arr.length ? '<ol class="tops">' + arr.map((x) => '<li><a href="#/c/' + x.org + '">' + esc(x.name) + '</a><span class="muted">' + fmt(x) + "</span></li>").join("") + "</ol>" : '<p class="muted">None in this run.</p>';
    const biggest = KS.index.filter((x) => x.revenue != null).sort((a, b) => b.revenue - a.revenue).slice(0, 6);
    const hiring = KS.index.filter((x) => x.jobs > 0).sort((a, b) => b.jobs - a.jobs).slice(0, 6);
    const sites = KS.index.filter((x) => x.domain).length;
    $("#main").innerHTML = '<div class="page">' +
      '<header class="ovh"><div class="eyebrow">Run overview</div><h1 class="ph">' + plural(n, "company", "companies") + ", every fact sourced</h1>" +
      '<p class="muted">Run <span class="mono">' + esc(r.run_id || "—") + "</span>" + (r.started_at ? " · " + fdt(r.started_at) + " – " + fdt(r.completed_at).replace(/^.*?, /, "") : "") + (r.agent ? " · " + esc(r.agent) : "") + "</p></header>" +
      '<dl class="stats">' + stat("Companies", nf.format(r.companies || n)) + stat("Facts", nf.format(r.claims || 0), "each with evidence") + stat("Evidence records", nf.format(r.evidence_records || 0), "source, time, hash, quote") +
      stat("Runtime", dur(r.runtime_seconds), ops.p50_company_ms ? "p50 " + dur(ops.p50_company_ms / 1000) + " per company" : "") + stat("Requests", nf.format(ops.requests || 0)) +
      stat("Third-party cost", "$" + Number(ops.third_party_cost_usd || 0).toFixed(2)) + "</dl>" +
      '<section class="ovs"><h2 class="h2">Validation <span class="st st-' + (val.passed ? "available" : "failed") + '"><i></i>' + (val.passed ? "Passed" : val.passed === false ? "Failed" : "Not recorded") + "</span></h2>" +
      '<ul class="checks">' + checks.map(([k, v]) => '<li class="' + (v ? "ok" : "bad") + '">' + (v ? ICON.check : ICON.cross) + "<span>" + esc(cap(k.replace(/_/g, " "))) + "</span></li>").join("") + "</ul></section>" +
      '<section class="ovs"><h2 class="h2">Coverage by information type</h2><p class="muted">How many companies have facts of each type, and why the rest do not. Select a segment to list those companies.</p><ul class="covrows">' + covRows + "</ul>" + legend() + "</section>" +
      '<div class="two">' +
      '<section class="ovs"><h2 class="h2">Largest by latest revenue</h2>' + top(biggest, (x) => money(x.revenue) + " · " + x.ry) + "</section>" +
      '<section class="ovs"><h2 class="h2">Hiring now</h2>' + top(hiring, (x) => plural(x.jobs, "open posting")) + "</section>" +
      '<section class="ovs"><h2 class="h2">Changed since the last run</h2>' + (changed.length ? '<p><b>' + plural(changed.length, "company", "companies") + "</b> with " + plural(changed.reduce((s, x) => s + x.changes, 0), "change") + '. <button type="button" class="linkbtn" data-quick="changed">Show them</button></p>' + top(changed.slice().sort((a, b) => b.changes - a.changes).slice(0, 5), (x) => plural(x.changes, "change")) : '<p class="muted">No changes recorded: either the first run, or nothing moved since the previous one.</p>') + "</section>" +
      '<section class="ovs"><h2 class="h2">Verified websites</h2><p><b>' + plural(sites, "company", "companies") + "</b> have a website that proved it belongs to the organisation number. " + '<button type="button" class="linkbtn" data-quick="site">Show them</button></p><p class="muted sm">The rest are listed as not found, unconfirmed (candidates without proof) or blocked; nothing is guessed.</p></section>' +
      "</div>" +
      (bySrc.length ? '<section class="ovs"><h2 class="h2">Requests by source</h2><ul class="srcs">' + bySrc.map(([k, v]) => '<li><span class="sl">' + esc(k.replace(/_/g, " ")) + '</span><span class="sb"><i style="width:' + Math.max(1, (v / srcMax) * 100) + '%"></i></span><span class="n">' + nf.format(v) + "</span></li>").join("") + "</ul></section>" : "") +
      '<section class="ovs"><h2 class="h2">How to read a profile</h2><ol class="howto"><li><b>Summary first.</b> Each sentence is written only from facts; open its evidence to see exactly which.</li><li><b>Every value opens its evidence:</b> source and URL, retrieval time, reporting period, content hash and the exact quoted text.</li><li><b>Unknowns are explicit.</b> Not found, unconfirmed, blocked, failed and not applicable are different states, each with the agent\'s note.</li><li><b>Compare</b> up to four companies; the link can be shared.</li></ol></section>' +
      foot() + "</div>";
    document.title = "Run overview · Kildespor";
  }

  /* ---------- routing ---------- */
  let rendered = "", lastView = "home", listScroll = 0;
  function setView(v) {
    if (narrow() && lastView === "home" && v !== "home") listScroll = window.scrollY;
    document.body.dataset.view = v;
    lastView = v;
  }
  async function route() {
    const h = location.hash.slice(1) || "/";
    const m = h.match(/^\/c\/(\d{9})(?:\/e\/(.+))?$/);
    const cm = h.match(/^\/compare\/([\d,]*)/);
    $$(".topnav a").forEach((a) => a.removeAttribute("aria-current"));
    if (m) {
      setView("page");
      currentOrg = m[1];
      markCurrent();
      let env = null;
      if (rendered !== "c/" + m[1]) {
        hideDrawer();
        tlState.routine = false; tlState.all = false;
        $("#main").innerHTML = '<div class="page"><p class="loading">Loading profile…</p></div>';
        try { env = await load(m[1]); } catch (e) {
          $("#main").innerHTML = '<div class="page"><a class="back" href="#/">' + ICON.back + 'Companies</a><div class="stbox st-failed"><p><b>Profile not available.</b> ' + esc(e.message) + "</p></div></div>";
          rendered = ""; return;
        }
        if (currentOrg !== m[1]) return;
        renderProfile(env);
        rendered = "c/" + m[1];
        window.scrollTo(0, 0);
        if (!m[2]) $("#main").focus({ preventScroll: true });
      } else env = cache[m[1]];
      if (m[2]) { if (!openTarget(env, decodeURIComponent(m[2]))) history.replaceState(null, "", "#/c/" + m[1]); }
      else { drawerPushed = false; hideDrawer(); }
      return;
    }
    hideDrawer();
    currentOrg = null;
    markCurrent();
    if (cm) {
      setView("page");
      rendered = h;
      await renderCompare(cm[1].split(",").filter((o) => /^\d{9}$/.test(o)).slice(0, 4));
      window.scrollTo(0, 0);
      $("#main").focus({ preventScroll: true });
    } else if (h === "/run") {
      setView("page");
      rendered = h;
      $('.topnav a[data-nav="run"]').setAttribute("aria-current", "page");
      renderOverview();
      window.scrollTo(0, 0);
      $("#main").focus({ preventScroll: true });
    } else {
      setView("home");
      $('.topnav a[data-nav="list"]').setAttribute("aria-current", "page");
      if (rendered !== "home") { rendered = "home"; renderOverview(); }
      document.title = "Kildespor · " + plural(KS.index.length, "company", "companies");
      if (narrow()) window.scrollTo(0, listScroll);
    }
  }

  /* ---------- utilities ---------- */
  let toastT = 0;
  function toast(msg) {
    const t = $("#toast");
    t.textContent = msg;
    t.classList.add("on");
    clearTimeout(toastT);
    toastT = setTimeout(() => t.classList.remove("on"), 2600);
  }
  async function copy(text, msg) {
    try { await navigator.clipboard.writeText(text); toast(msg || "Copied"); return; } catch (e) { /* fall back below */ }
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.cssText = "position:fixed;opacity:0;top:0;left:0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); toast(msg || "Copied"); } catch (e) { toast("Copy is not available here; select the text instead."); }
    ta.remove();
  }
  function download(org) {
    const env = cache[org];
    if (!env) return;
    const blob = new Blob([JSON.stringify(env, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = org + ".json";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  function jump(id) {
    const t = document.getElementById("s-" + id);
    if (!t) return;
    t.scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "start" });
    t.setAttribute("tabindex", "-1");
    t.focus({ preventScroll: true });
  }

  /* ---------- events ---------- */
  document.addEventListener("click", (ev) => {
    const t = ev.target;
    const pick = t.closest("[data-pick]");
    if (pick) { ev.preventDefault(); togglePick(pick.dataset.pick); return; }
    const un = t.closest("[data-unpick]");
    if (un) { setCompare(compare.filter((o) => o !== un.dataset.unpick)); return; }
    const tg = t.closest("[data-target]");
    if (tg) {
      const holder = tg.closest("[data-org]");
      if (holder && /^#\/compare\//.test(location.hash)) { load(holder.dataset.org).then((env) => openTarget(env, tg.dataset.target)); return; }
      if (currentOrg) { drawerPushed = true; location.hash = "#/c/" + currentOrg + "/e/" + encodeURIComponent(tg.dataset.target); }
      return;
    }
    if (t.closest("[data-close]")) { closeDrawer(); return; }
    const j = t.closest("[data-jump]");
    if (j) { jump(j.dataset.jump); return; }
    const cp = t.closest("[data-copy]");
    if (cp) { copy(cp.dataset.copy); return; }
    if (t.closest("[data-copy-link]")) { copy(location.href, "Link copied"); return; }
    const dl = t.closest("[data-download]");
    if (dl) { download(dl.dataset.download); return; }
    if (t.closest("[data-more]")) { more(); return; }
    if (t.closest("[data-reset]") || t.id === "reset") { resetFilters(); $("#q").focus(); return; }
    const chip = t.closest(".chip[data-f]");
    if (chip) { F[chip.dataset.f] = !F[chip.dataset.f]; renderList(); return; }
    const seg = t.closest("[data-ff]");
    if (seg) {
      F.q = ""; $("#q").value = "";
      setStateFilter(seg.dataset.ff, seg.dataset.fs);
      toast(nf.format(view.length) + " " + (view.length === 1 ? "company" : "companies") + ": " + famShort(seg.dataset.ff) + " " + STATE[seg.dataset.fs].w.toLowerCase());
      if (narrow()) { listScroll = 0; location.hash = "#/"; } else if ($(".rows .rl")) $(".rows .rl").focus();
      return;
    }
    const q = t.closest("[data-quick]");
    if (q) {
      resetFilters();
      F[q.dataset.quick] = true;
      renderList();
      if (narrow()) { listScroll = 0; location.hash = "#/"; } else if ($(".rows .rl")) $(".rows .rl").focus();
      return;
    }
    const tl = t.closest("button[data-tl]");
    if (tl) { tlState.all = !tlState.all; const env = cache[currentOrg]; if (env) $("#tl").innerHTML = timelineHtml(env); return; }
    if (t.id === "trayclear") { setCompare([]); return; }
    const go = t.closest("#traygo");
    if (go && compare.length < 2) { ev.preventDefault(); toast("Pick at least two companies to compare."); }
  });
  document.addEventListener("change", (ev) => {
    const t = ev.target;
    if (t.id === "sort") { F.sort = t.value; renderList(); }
    if (t.id === "ffam" || t.id === "fst") { F.fam = $("#ffam").value; F.st = $("#fst").value; renderList(); }
    if (t.matches("input[data-tl='routine']")) { tlState.routine = t.checked; const env = cache[currentOrg]; if (env) { $("#tl").innerHTML = timelineHtml(env); const c = $("input[data-tl='routine']"); if (c) c.focus(); } }
  });
  let qT = 0;
  $("#q").addEventListener("input", (ev) => {
    clearTimeout(qT);
    const v = ev.target.value;
    qT = setTimeout(() => { F.q = v; renderList(); if (narrow() && document.body.dataset.view !== "home") location.hash = "#/"; }, KS.index.length > 400 ? 60 : 0);
  });
  $("#q").addEventListener("keydown", (ev) => {
    if (ev.key === "ArrowDown") { const a = $(".rows .rl"); if (a) { ev.preventDefault(); a.focus(); } }
    if (ev.key === "Enter") { const a = $(".rows .rl"); if (a) { ev.preventDefault(); location.hash = a.getAttribute("href"); } }
    if (ev.key === "Escape" && ev.target.value) { ev.preventDefault(); ev.stopPropagation(); ev.target.value = ""; F.q = ""; renderList(); }
  });
  rowsEl.addEventListener("keydown", (ev) => {
    if (!ev.target.classList.contains("rl")) return;
    const links = $$(".rl", rowsEl), i = links.indexOf(ev.target);
    let n = -1;
    if (ev.key === "ArrowDown") n = Math.min(links.length - 1, i + 1);
    if (ev.key === "ArrowUp") { if (i === 0) { ev.preventDefault(); $("#q").focus(); return; } n = i - 1; }
    if (ev.key === "Home") n = 0;
    if (ev.key === "End") n = links.length - 1;
    if (ev.key === " " || ev.key === "c") { ev.preventDefault(); togglePick(ev.target.closest(".row").dataset.org); return; }
    if (n >= 0) { ev.preventDefault(); links[n].focus(); if (n >= links.length - 3 && shown < view.length) more(); }
  });
  document.addEventListener("keydown", (ev) => {
    if (!drawer.hidden) {
      if (ev.key === "Escape") { ev.preventDefault(); closeDrawer(); return; }
      if (ev.key === "Tab") {
        const f = $$('a[href], button:not([disabled]), input, select, summary, [tabindex="-1"].panel', drawer).filter((x) => x.offsetParent !== null || x.classList.contains("panel"));
        const first = f[0], last = f[f.length - 1];
        if (ev.shiftKey && (document.activeElement === first || document.activeElement === $(".panel", drawer))) { ev.preventDefault(); last.focus(); }
        else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
      }
      return;
    }
    const ae = document.activeElement;
    const typing = (ae.tagName === "INPUT" && /^(text|search)$/.test(ae.type)) || ae.tagName === "TEXTAREA" || ae.isContentEditable;
    if (ev.key === "/" && !typing && !ev.ctrlKey && !ev.metaKey) {
      ev.preventDefault();
      if (narrow() && document.body.dataset.view !== "home") location.hash = "#/";
      $("#q").focus();
      $("#q").select();
    }
  });
  $("#theme").addEventListener("click", () => {
    const cur = document.documentElement.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    const next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("ks-theme", next); } catch (e) { /* storage unavailable */ }
    toast(next === "dark" ? "Dark theme" : "Light theme");
  });

  /* ---------- start ---------- */
  $("#ffam").innerHTML = '<option value="">Any type</option>' + FAM.map(([k, l]) => '<option value="' + esc(k) + '">' + esc(famShort(k)) + " · " + esc(l) + "</option>").join("");
  $("#fst").innerHTML = '<option value="">Any state</option>' + ST_ORDER.map((s) => '<option value="' + s + '">' + STATE[s].w + "</option>").join("");
  $("#sort").value = F.sort;
  if (!KS.index.some((x) => x.changes > 0)) $('.chip[data-f="changed"]').title = "No company changed since the previous run";
  renderList();
  renderTray();
  window.addEventListener("hashchange", route);
  route();
})();
