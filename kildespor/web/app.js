/* Kildespor viewer. Find, compare and verify company facts; every fact leads back to its source along a visible trail.
   Opens straight from disk (file://): the run index and each profile are plain scripts, no server or network needed. */
(function () {
  "use strict";
  const KS = window.KS || { families: [], index: [], run: {} };
  KS.index = KS.index || [];
  KS.run = KS.run || {};
  const BASE = typeof window.KS_BASE === "string" ? window.KS_BASE : "";
  const FAM = KS.families || [];
  const FAMKEYS = FAM.map((f) => f[0]);
  const FAML = Object.fromEntries(FAM);
  const SHORT = { identity: "Identity", financials: "Accounts", people: "Leadership", locations: "Workplaces", website: "Website", contact: "Contact",
    social: "Social profiles", jobs: "Hiring", activity: "Activity", reviews: "Ratings", description: "Description" };
  const famShort = (f) => SHORT[f] || FAML[f] || f;

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
  const docked = () => window.matchMedia && matchMedia("(min-width: 1280px)").matches;
  const clip = (s, n) => (String(s).length > n ? String(s).slice(0, n - 1).replace(/\s+\S*$/, "") + "…" : String(s));

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
    jsonld: "Structured data (JSON-LD) on the site", jsonld_sameAs: "JSON-LD sameAs link on the site", jsonld_jobposting: "JobPosting data on the company site",
    jsonld_identifier_orgnr: "JSON-LD identifier carrying this org.nr", rss_item: "Item in the site's news feed", html_title: "Page title",
    news_listing_date: "Dated item on the site's news page", careers_page: "Careers page on the company site",
    recruitment_link_on_verified_site: "Recruitment link on the verified company site",
    smilefjes_csv_orgnr: "Mattilsynet inspection row naming this org.nr", finanstilsynet_licence: "Finanstilsynet licence register",
    finanstilsynet_exact_orgnr: "Finanstilsynet register row naming this org.nr", ted_winner_identifier: "EU award notice naming this org.nr as winner",
    wikidata_sparql_p2333: "Wikidata item carrying this org.nr (P2333)", arbeidstilsynet_register_orgnr: "Arbeidstilsynet register row naming this org.nr",
    nav_feed_employer_orgnr: "NAV job ad naming this org.nr as employer",
    article_header_date: "Dated article header on the company site", article_jsonld_datePublished: "Article publish date (JSON-LD) on the company site",
    wordpress_rest_api: "Post in the company site's WordPress feed", sitemap_lastmod: "Dated page in the company site's sitemap",
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
  const PLAT = { facebook: ["f", "Facebook"], instagram: ["ig", "Instagram"], linkedin: ["in", "LinkedIn"], twitter: ["X", "X (Twitter)"], x: ["X", "X"],
    youtube: ["yt", "YouTube"], tiktok: ["tt", "TikTok"], pinterest: ["P", "Pinterest"], vimeo: ["v", "Vimeo"], github: ["gh", "GitHub"], threads: ["@", "Threads"] };
  const platName = (p) => (PLAT[String(p || "").toLowerCase()] || [0, cap(p || "Profile")])[1];
  const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const ICON = {
    ext: '<svg class="ic ext" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 5h5v5M19 5l-8 8M17 14v5H5V7h5"/></svg>',
    check: '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12.5 4.5 4.5L19 7.5"/></svg>',
    cross: '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 7l10 10M17 7 7 17"/></svg>',
    pick: '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><rect class="bx" x="4" y="4" width="16" height="16" rx="3"/><path class="tk" d="m8 12.5 3 3 5-6"/><path class="pl" d="M12 8v8M8 12h8"/></svg>',
    back: '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="m15 6-6 6 6 6"/></svg>',
    t: '<svg class="tmark" viewBox="0 0 24 20" aria-hidden="true"><rect width="24" height="20" rx="4"/><path d="M6 6h12M12 6v9"/></svg>',
  };

  /* ---------- formatting ---------- */
  function compact(v) {
    if (v == null || isNaN(v)) return "–";
    const a = Math.abs(v), s = v < 0 ? "−" : "";
    const t = (x, d) => x.toFixed(d).replace(/\.0$/, "");
    if (a >= 1e9) return s + t(a / 1e9, a >= 1e11 ? 0 : 1) + " bn";
    if (a >= 1e6) return s + t(a / 1e6, a >= 1e8 ? 0 : 1) + " m";
    if (a >= 1e3) return s + Math.round(a / 1e3) + " k";
    return s + nf.format(Math.round(a));
  }
  const money = (v, cur) => (v == null || isNaN(v) ? "–" : (v < 0 ? "−" : "") + ((cur && cur !== "NOK") ? cur : "NOK") + " " + compact(Math.abs(v)));
  const fullMoney = (v, cur) => (v == null ? "–" : (cur || "NOK") + " " + nf.format(v));
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
    if (!m[2]) return m[1] === m[4] ? "Financial year " + m[1] : m[1] + " to " + m[4];
    return fdate(m[1] + "-" + m[2] + "-" + m[3]) + " to " + fdate(m[4] + "-" + m[5] + "-" + m[6]);
  }
  function dur(sec) {
    if (sec == null) return "–";
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
    if (!m) return "–";
    if (METHOD[m]) return METHOD[m];
    const p = m.match(/^identity_proof_(.+)$/);
    if (p) return "Identity proof on the company site: " + (PROOF[p[1]] ? PROOF[p[1]][1] : p[1].replace(/_/g, " "));
    const l = m.match(/^(\w+)_listing$/);
    if (l) return "Listing on " + cap(l[1]);
    return cap(m.replace(/_/g, " "));
  }
  function pageKind(u) {
    let p = "";
    try { p = decodeURIComponent(new URL(u).pathname).toLowerCase(); } catch (e) { return "a page of the site"; }
    if (p === "/" || p === "" || /^\/(index|home|hjem|forside)(\.\w+)?$/.test(p)) return "the home page";
    if (/kontakt|contact/.test(p)) return "the contact page";
    if (/om-?oss|about|om_oss|hvem-er-vi|firma|selskap/.test(p)) return "the about page";
    if (/personvern|privacy|cookie/.test(p)) return "the privacy page";
    return "the page " + p;
  }
  const hide = (o, k, v) => Object.defineProperty(o, k, { value: v, enumerable: false, configurable: true, writable: true });

  /* ---------- data loading ---------- */
  const cache = {};
  const waiting = {};
  KS.put = function (env) {
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
      s.src = BASE + "data/c/" + org + ".js";
      s.onerror = () => { (waiting[org] || []).forEach((f) => f[1](new Error("The profile file " + BASE + "data/c/" + org + ".js is missing from the run folder."))); delete waiting[org]; s.remove(); };
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
  const finOf = (env) => claimsOf(env, "financials").filter((c) => c.value && typeof c.value === "object" && c.value.amount != null && c.value.year);
  const latestFin = (env, field) => finOf(env).filter((c) => c.field === field).sort((a, b) => String(b.value.year).localeCompare(String(a.value.year)))[0] || null;
  const finIn = (env, field, year) => finOf(env).find((c) => c.field === field && String(c.value.year) === String(year)) || null;
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
  const newsOf = (env) => claimsOf(env, "activity", "company_news").filter((c) => c.value && typeof c.value === "object")
    .sort((a, b) => String(b.effective_date || "").localeCompare(String(a.effective_date || "")));
  const openJobs = (env) => claimsOf(env, "jobs", "job_posting").filter((c) => c.value && typeof c.value === "object" && c.value.status !== "closed")
    .sort((a, b) => String(b.effective_date || "").localeCompare(String(a.effective_date || "")));
  function due(v) {
    const d = v.application_due || v.expires;
    if (d && /^\d{4}-\d{2}-\d{2}/.test(String(d))) return "apply by " + fdate(d);
    if (v.application_due_text) return "apply: " + v.application_due_text;
    return d && !/^\d{4}/.test(String(d)) ? "apply: " + d : "";
  }

  /* ---------- values ---------- */
  function valText(c) {
    const v = c.value;
    if (v == null) return "–";
    if (typeof v !== "object") {
      if (/phone|mobile/.test(c.field)) return phone(v);
      if (c.field === "founded" || c.field === "registered" || c.field === "inception") return fdate(v);
      if (c.field === "municipality") return String(v).charAt(0) + String(v).slice(1).toLowerCase();
      return String(v);
    }
    if (Array.isArray(v)) return v.join(", ");
    if ("amount" in v && "year" in v) return money(v.amount, v.currency) + " (" + v.year + ")";
    if (v.title && "amount" in v) return v.title + (v.amount != null ? ", " + money(v.amount, v.currency) : "");
    if ("amount" in v) return money(v.amount, v.currency) + (v.shares ? ", " + nf.format(v.shares) + " shares" : "");
    if (v.rating != null) return Math.round(v.rating * 10) / 10 + " / " + (v.best || 5) + (v.count ? " from " + nf.format(v.count) + " ratings" : "");
    if (v.year && v.format) return "Annual accounts " + v.year + " (" + String(v.format).toUpperCase() + ")";
    if (v.domain) return v.domain;
    if (v.platform && !v.title) return platName(v.platform) + (v.handle ? " " + v.handle : "");
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
    if (v == null) return "–";
    if (typeof v !== "object") {
      if (c.field === "registered_website" || c.field === "website_listed_in_wikidata" || isUrl(v)) return link(isUrl(v) ? v : "https://" + v, String(v).replace(/^https?:\/\//, ""));
      if (c.field === "email" || c.field === "registered_email") return '<a href="mailto:' + esc(v) + '">' + esc(v) + "</a>";
      if (/phone|mobile/.test(c.field)) return '<a href="tel:' + esc(String(v).replace(/\s/g, "")) + '">' + esc(phone(v)) + "</a>";
      if (c.field === "opening_hours") return esc(clip(v, 160));
      return esc(valText(c));
    }
    if (Array.isArray(v)) return esc(v.join(", "));
    if ("amount" in v && "year" in v) return '<span title="' + esc(fullMoney(v.amount, v.currency)) + '">' + esc(money(v.amount, v.currency)) + "</span>";
    if (v.title && "amount" in v) return link(v.url, v.title) + (v.amount != null ? ' <span class="mu">' + esc(money(v.amount, v.currency)) + "</span>" : "");
    if ("amount" in v) return esc(money(v.amount, v.currency)) + (v.shares ? ' <span class="mu">' + nf.format(v.shares) + " shares</span>" : "");
    if (v.rating != null) return link(v.url, Math.round(v.rating * 10) / 10 + " / " + (v.best || 5)) + (v.count ? ' <span class="mu">' + nf.format(v.count) + " ratings, " + esc(v.platform || "") + "</span>" : "");
    if (v.year && v.format) return link(v.url, "Annual accounts " + v.year + " (" + String(v.format).toUpperCase() + ")");
    if (v.id && v.url && v.label) return link(v.url, v.label) + ' <span class="mu">' + esc(v.id) + "</span>";
    if (v.domain) return link(v.url, v.domain);
    if (v.platform && !v.title) return link(v.url, platName(v.platform)) + (v.handle ? ' <span class="mu">' + esc(v.handle) + "</span>" : "");
    if (v.name && v.role) return esc(v.name) + (v.kind === "organisation" ? ' <span class="mu">organisation ' + (v.organisation_number ? orgLink(v.organisation_number) : "") + "</span>" : "");
    if (v.title) return link(v.url, v.title) + (v.status ? ' <span class="tag' + (v.status === "closed" ? " off" : "") + '">' + esc(v.status) + "</span>" : "") + (v.location ? ' <span class="mu">' + esc(v.location) + "</span>" : "");
    if (v.organisation_number && v.name) return esc(v.name) + '<span class="mu block">' + esc(v.address || "") + (v.registered_employees != null ? ", " + plural(v.registered_employees, "registered employee") : "") + "</span>";
    if (v.address) return esc(v.address);
    if (v.label) return esc(v.label);
    if (v.url) return link(v.url);
    return esc(JSON.stringify(v));
  }
  function orgLink(o) {
    return IDX[o] ? '<a href="#/c/' + esc(o) + '">' + esc(orgFmt(o)) + "</a>" : link("https://virksomhet.brreg.no/nb/oppslag/enheter/" + o, orgFmt(o));
  }
  function objText(v) {
    if (v == null) return "–";
    if (typeof v !== "object") return String(v);
    if (v.year && v.format) return "Annual accounts " + v.year + " (" + String(v.format).toUpperCase() + ")";
    if ("amount" in v && "year" in v) return money(v.amount, v.currency) + " (" + v.year + ")";
    return v.title || (v.name ? v.name + (v.role ? ", " + v.role : "") : "") || v.domain || v.address || v.url || JSON.stringify(v);
  }
  /* The trail mark: a red T, like the painted marks on Norwegian hiking trails. Every verifiable thing carries one. */
  function tBtn(target, label, n, extra) {
    return '<button type="button" class="tbtn' + (extra ? " " + extra : "") + '" data-target="' + esc(target) + '" aria-label="Follow the source trail: ' + esc(label) + '">' + ICON.t +
      (n != null ? '<span class="tn">' + esc(n) + "</span>" : "") + "</button>";
  }
  function srcBtn(env, c, text) {
    const e = env._ev[(c.evidence_ids || [])[0]];
    return '<button type="button" class="tsrc" data-target="f:' + esc(c.key) + '" aria-label="Follow the source trail for ' + esc(c.label || c.field) + (e ? ", from " + esc(srcShort(e)) : "") + '">' + ICON.t +
      '<span>' + esc(text || srcShort(e)) + "</span></button>";
  }
  const stChip = (st, text) => '<span class="st st-' + esc(st) + '"><i aria-hidden="true"></i>' + esc(text || (STATE[st] || { w: st }).w) + "</span>";

  /* ---------- index ---------- */
  const IDX = {};
  KS.index.forEach((x, i) => {
    x._i = i;
    x.ribbon = x.ribbon || [];
    x.news = x.news || 0;
    x._found = x.ribbon.filter((s) => s === "available").length;
    x._h = fold([x.name, x.org, x.domain, x.muni, x.place, x.industry, x.nace, x.lead, (x.platforms || []).join(" ")].join(" "));
    x._n = fold(x.name);
    IDX[x.org] = x;
  });
  const PLACES = (() => {
    const c = {};
    KS.index.forEach((x) => { if (x.muni) c[x.muni] = (c[x.muni] || 0) + 1; });
    return Object.entries(c).sort((a, b) => b[1] - a[1]).slice(0, 8);
  })();

  /* ---------- find ---------- */
  const F = { q: "", site: false, jobs: false, news: false, social: false, changed: false, place: "", fam: "", st: "", sort: "facts" };
  const TEST = { site: (x) => !!x.domain, jobs: (x) => x.jobs > 0 || !!x.careers, news: (x) => x.news > 0, social: (x) => x.social > 0, changed: (x) => x.changes > 0 };
  const PAGE = 100;
  let view = [], shown = 0, terms = [], currentOrg = null;
  const rowsEl = $("#rows");
  const nullLast = (k) => (a, b) => (a[k] == null) - (b[k] == null) || (b[k] || 0) - (a[k] || 0) || a._i - b._i;
  const SORTS = {
    facts: (a, b) => b.facts - a.facts || a._i - b._i,
    revenue: nullLast("revenue"),
    result: nullLast("result"),
    emp: nullLast("emp"),
    news: (a, b) => String(b.nd || "").localeCompare(String(a.nd || "")) || b.news - a.news || a._i - b._i,
    jobs: (a, b) => b.jobs - a.jobs || !!b.careers - !!a.careers || b.facts - a.facts,
    name: (a, b) => collator.compare(a.name, b.name),
    changes: (a, b) => b.changes - a.changes || b.facts - a.facts,
  };
  function filtered() {
    const q = fold(F.q).trim();
    const digits = q.replace(/\s+/g, "");
    terms = /^\d{3,9}$/.test(digits) ? [digits] : q.split(/\s+/).filter(Boolean);
    const fi = F.fam ? FAMKEYS.indexOf(F.fam) : -1;
    const r = KS.index.filter((x) => (!terms.length || terms.every((t) => x._h.includes(t) || x.org.includes(t))) &&
      Object.keys(TEST).every((k) => !F[k] || TEST[k](x)) && (!F.place || x.muni === F.place) &&
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
  function rowHtml(x) {
    const cur = x.org === currentOrg, picked = compare.includes(x.org);
    const sub = [orgFmt(x.org), x.muni, x.industry].filter(Boolean);
    const sig = (x.status === "failed" ? '<span class="bd bad">Not in the register</span>' : "") +
      (x.domain ? '<span class="bd web">' + ICON.check + hl(x.domain, terms) + "</span>" : "") +
      (x.jobs ? '<span class="bd job" title="' + esc(x.jt || "") + '">' + plural(x.jobs, "open job") + "</span>" : x.careers ? '<span class="bd job">Careers page</span>' : "") +
      (x.news ? '<span class="bd news" title="' + esc((x.nd ? fdate(x.nd) + ": " : "") + (x.nt || "")) + '">' + plural(x.news, "news item") + "</span>" : "") +
      (x.social ? '<span class="bd sc">' + esc((x.platforms || []).slice(0, 3).map(platName).join(", ") || plural(x.social, "profile")) + "</span>" : "") +
      (x.changes ? '<span class="bd chg">' + plural(x.changes, "change") + "</span>" : "");
    return '<li class="row' + (cur ? " cur" : "") + '" data-org="' + x.org + '">' +
      '<a class="rl" href="#/c/' + x.org + '"' + (cur ? ' aria-current="page"' : "") + '><span class="nm">' + hl(x.name, terms) + '</span><span class="sub">' + sub.map((s) => hl(s, terms)).join(", ") + "</span></a>" +
      '<span class="rv">' + (x.revenue != null ? esc(money(x.revenue)) + "<small>revenue " + esc(x.ry || "") + "</small>" : "<small>no revenue filed</small>") + "</span>" +
      (sig ? '<span class="rs">' + sig + "</span>" : "") +
      '<button type="button" class="pick" data-pick="' + x.org + '" aria-pressed="' + picked + '" aria-label="Compare ' + esc(x.name) + '" title="Add to compare">' + ICON.pick + "</button></li>";
  }
  let io = null;
  function more() {
    const s = $("#sentinel");
    if (s) { if (io) io.unobserve(s); s.remove(); }
    const next = view.slice(shown, shown + PAGE);
    shown += next.length;
    let html = next.map(rowHtml).join("");
    if (shown < view.length) html += '<li id="sentinel" class="sentinel"><button type="button" class="lb" data-more>Show ' + Math.min(PAGE, view.length - shown) + " more of " + nf.format(view.length - shown) + "</button></li>";
    if (!view.length) html = '<li class="none"><p><b>No company matches.</b> Try a name, an organisation number, a website, a place or an industry, or clear the filters.</p><button type="button" class="btn ghost" data-reset>Clear search and filters</button></li>';
    rowsEl.insertAdjacentHTML("beforeend", html);
    const ns = $("#sentinel");
    if (ns && io) io.observe(ns);
  }
  if ("IntersectionObserver" in window) io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) more(); }, { rootMargin: "600px 0px" });
  function renderPlaces() {
    $("#places").innerHTML = PLACES.length > 1 ? PLACES.map(([p, n]) => '<button type="button" class="place" data-place="' + esc(p) + '" aria-pressed="' + (F.place === p) + '">' + esc(p) + "<span>" + n + "</span></button>").join("") : "";
  }
  function renderList() {
    view = filtered();
    shown = 0;
    rowsEl.innerHTML = "";
    more();
    const n = KS.index.length;
    $("#count").textContent = view.length === n ? plural(n, "company", "companies") : nf.format(view.length) + " of " + plural(n, "company", "companies");
    $("#reset").hidden = !(F.q || F.place || F.st || Object.keys(TEST).some((k) => F[k]));
    $$(".chip[data-f]").forEach((c) => c.setAttribute("aria-pressed", String(!!F[c.dataset.f])));
    $$(".place").forEach((c) => c.setAttribute("aria-pressed", String(F.place === c.dataset.place)));
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
    Object.assign(F, { q: "", site: false, jobs: false, news: false, social: false, changed: false, place: "", fam: "", st: "" });
    $("#q").value = "";
    renderList();
  }

  /* ---------- compare selection ---------- */
  let compare = [];
  try { compare = JSON.parse(localStorage.getItem("ks-compare") || "[]").filter((o) => IDX[o]).slice(0, 4); } catch (e) { compare = []; }
  function setCompare(list, quiet) {
    compare = list.filter((o, i) => IDX[o] && list.indexOf(o) === i).slice(0, 4);
    try { localStorage.setItem("ks-compare", JSON.stringify(compare)); } catch (e) { /* storage unavailable */ }
    $$("[data-pick]").forEach((b) => {
      const on = compare.includes(b.dataset.pick);
      b.setAttribute("aria-pressed", String(on));
      const l = $(".bl", b);
      if (l) l.textContent = on ? "In compare" : "Compare";
    });
    renderBadge();
    if (!quiet && /^#\/compare\//.test(location.hash)) {
      const want = "#/compare/" + compare.join(",");
      if (compare.length < 2 && $("#cres")) { history.replaceState(null, "", want); rendered = want.slice(1); renderChosen(); pickResults(); }
      else if (location.hash !== want) location.replace(want); else route();
    }
  }
  function togglePick(org) {
    if (compare.includes(org)) { setCompare(compare.filter((o) => o !== org)); toast("Removed from compare"); return; }
    if (compare.length >= 4) { toast("Compare holds four companies. Remove one first."); return; }
    setCompare(compare.concat(org));
    if (!/^#\/compare\//.test(location.hash)) toast(compare.length === 1 ? "Added to compare. Choose one more." : "Added. Open Compare to see " + compare.length + " side by side.");
  }
  function renderBadge() {
    const nc = $("#ncmp");
    nc.textContent = compare.length ? String(compare.length) : "";
    nc.hidden = !compare.length;
    $('.tabs a[data-nav="compare"]').href = "#/compare/" + compare.join(",");
  }

  /* ---------- the source trail (verify) ---------- */
  const trailEl = $("#trail"), scrim = $("#scrim");
  let lastFocus = null, trailPushed = false, trailOrigin = null, trailTarget = "";
  function evNodes(e, c, compactMode) {
    if (!e) return "";
    const quote = e.claim_span ? '<li class="node n-quote"><span class="pin" aria-hidden="true"></span><div class="nb"><p class="nl">Quoted from the fetched document</p><blockquote><mark>' + esc(e.claim_span) + "</mark></blockquote></div></li>" : "";
    const doc = '<li class="node n-doc"><span class="pin" aria-hidden="true"></span><div class="nb"><p class="nl">Fetched document</p><p class="url">' + link(e.final_url || e.source_url, e.final_url || e.source_url, "wrap") + "</p>" +
      '<dl class="kv"><dt>Retrieved</dt><dd>' + fdt(e.retrieved_at) + "</dd>" +
      (e.final_url && e.final_url !== e.source_url ? "<dt>Requested</dt><dd>" + link(e.source_url, e.source_url, "wrap") + "</dd>" : "") +
      (e.http_status ? "<dt>HTTP status</dt><dd>" + esc(e.http_status) + "</dd>" : "") +
      '<dt>SHA-256</dt><dd><code class="hash">' + esc(e.content_sha256 || "–") + '</code> <button type="button" class="lb sm" data-copy="' + esc(e.content_sha256 || "") + '">Copy</button></dd></dl></div></li>';
    const src = '<li class="node n-src"><span class="pin" aria-hidden="true">' + ICON.t + '</span><div class="nb"><p class="nl">Source</p><p class="sname">' + esc(e.source_name || host(e.source_url)) +
      ' <span class="pill">' + esc(CLASS[e.source_class] || cap(String(e.source_class || "").replace(/_/g, " "))) + "</span></p>" +
      '<p class="mu">' + esc(methodLabel(e.extraction_method)) + "</p>" + (compactMode ? "" : '<p class="go">' + link(e.final_url || e.source_url, "Open the source", "btn ghost sm") + "</p>") + "</div></li>";
    return quote + doc + src;
  }
  function factNode(env, c, head) {
    const rows = [];
    if (c.effective_date) rows.push(["Refers to", fdate(c.effective_date)]);
    if (c.reporting_period) rows.push(["Reporting period", fperiod(c.reporting_period)]);
    if (c.relationship && c.relationship !== "exact") rows.push(["Applies to", esc(REL[c.relationship] || c.relationship)]);
    if (c.confidence != null && c.confidence < 1) rows.push(["Confidence", Math.round(c.confidence * 100) + "%"]);
    if (c.carried_forward) rows.push(["Note", "Kept from the previous run because its source failed or stopped listing it."]);
    return '<li class="node n-fact"><span class="pin" aria-hidden="true"></span><div class="nb"><p class="nl">' + esc(head || c.label || c.field) + '</p><p class="nv">' + fmtValue(c) + "</p>" +
      (rows.length ? '<dl class="kv">' + rows.map((r) => "<dt>" + r[0] + "</dt><dd>" + r[1] + "</dd>").join("") + "</dl>" : "") + "</div></li>";
  }
  function proofNode(env, c) {
    const v = c.value || {};
    const evs = (c.evidence_ids || []).map((id) => env._ev[id]).filter(Boolean);
    const items = (v.identity_proof || []).map((p) => {
      const e = evs.find((x) => x.extraction_method === "identity_proof_" + p);
      const d = PROOF[p] || [cap(p.replace(/_/g, " ")), p.replace(/_/g, " ")];
      return "<li>" + ICON.check + "<span><b>" + esc(d[0]) + "</b>: " + esc(d[1]) + (e ? ", on " + esc(pageKind(e.final_url || e.source_url)) : "") + ".</span></li>";
    }).join("");
    return '<li class="node n-proof"><span class="pin" aria-hidden="true"></span><div class="nb"><p class="nl">Why this is the company\'s own website</p><ul class="proofs">' + items + "</ul>" +
      '<p class="mu">Found through ' + esc(VIA[v.discovered_via] || String(v.discovered_via || "discovery").replace(/_/g, " ")) + ". A site naming a different organisation number is rejected.</p></div></li>";
  }
  function factTrail(env, c) {
    const evs = (c.evidence_ids || []).map((id) => env._ev[id]).filter(Boolean);
    let html = '<ol class="route">' + factNode(env, c) + (c.field === "official_website" ? proofNode(env, c) : "") + evNodes(evs[0], c) + "</ol>";
    evs.slice(1).forEach((e, i) => { html += '<details class="fork"' + (i < 1 ? " open" : "") + "><summary>Also backed by " + esc(srcShort(e)) + "</summary><ol class=\"route\">" + evNodes(e, c, true) + "</ol></details>"; });
    return html + trailFoot(c.key);
  }
  function trailFoot(key) {
    return '<div class="tfoot"><button type="button" class="btn ghost sm" data-copy-link>Copy a link to this trail</button>' +
      '<p class="mu">The SHA-256 is the hash of the exact bytes fetched. <code>python -m kildespor verify</code> re-checks every hash and quoted span against the archived responses.' + (key ? " Fact key <code>" + esc(key) + "</code>." : "") + "</p></div>";
  }
  function sentenceTrail(env, text, keys, sources) {
    const cs = (keys || []).map((k) => env._k[k]).filter(Boolean);
    const srcs = (sources || []).filter((x) => x && isUrl(x.url));
    let html = '<ol class="route"><li class="node n-sent"><span class="pin" aria-hidden="true"></span><div class="nb"><p class="nl">Sentence in the summary</p><blockquote class="sent">' + esc(text) + "</blockquote>" +
      (srcs.length ? '<p class="srcs">' + srcs.map((x) => link(x.url, x.name || host(x.url), "srcl")).join(" ") + "</p>" : "") +
      '<p class="mu">Written only from the ' + plural(cs.length, "fact") + " below. Each one continues to its fetched document.</p></div></li></ol>";
    html += cs.map((c, i) => {
      const e = env._ev[(c.evidence_ids || [])[0]];
      return '<details class="fork"' + (i < 3 ? " open" : "") + '><summary><span class="fl">' + esc(c.label || c.field) + '</span><span class="fv">' + esc(clip(valText(c), 90)) + "</span></summary>" +
        '<ol class="route">' + (c.field === "official_website" ? proofNode(env, c) : "") + evNodes(e, c, true) + "</ol></details>";
    }).join("");
    return html + trailFoot("");
  }
  function changeTrail(env, ch) {
    const evs = (list) => (list || []).map((e) => (typeof e === "string" ? env._ev[e] : e)).filter(Boolean);
    const prev = evs(ch.previous_evidence), cur = evs(ch.current_evidence);
    const r = env.refresh || {};
    let html = '<ol class="route"><li class="node n-fact"><span class="pin" aria-hidden="true"></span><div class="nb"><p class="nl">' + esc(CHANGE[ch.type] || cap(String(ch.type || "").replace(/_/g, " "))) + "</p>" +
      '<p class="nv">' + (ch.previous !== undefined ? "<s>" + esc(objText(ch.previous)) + "</s> " : "") + (ch.current !== undefined ? esc(objText(ch.current)) : "") + "</p>" +
      '<p class="mu">Compared with run ' + esc(r.previous_run_id || "–") + (r.previous_completed_at ? " of " + fdt(r.previous_completed_at) : "") + ".</p></div></li></ol>";
    if (prev.length) html += '<details class="fork" open><summary>Evidence in the previous run</summary><ol class="route">' + prev.map((e) => evNodes(e, null, true)).join("") + "</ol></details>";
    if (cur.length) html += '<details class="fork" open><summary>Evidence in this run</summary><ol class="route">' + cur.map((e) => evNodes(e, null, true)).join("") + "</ol></details>";
    return html;
  }
  function sentenceAt(env, i) { return ((env.summary || {}).sentences || [])[i]; }
  function openTarget(env, t, origin) {
    const m = String(t).match(/^([fscl]):?(.*)$/);
    if (!m) return false;
    const who = env.legal_name || env.organisation_number;
    if (m[1] === "f") {
      const c = env._k[m[2]];
      if (!c) return false;
      showTrail(famShort(c.family) + ", " + who, c.label || c.field, factTrail(env, c), origin, t);
    } else if (m[1] === "s") {
      const s = sentenceAt(env, +m[2]);
      if (!s) return false;
      showTrail("Summary, " + who, TOPIC[s.topic] || "Summary sentence", sentenceTrail(env, s.text, s.claim_keys, s.sources), origin, t);
    } else if (m[1] === "l") {
      const lf = (env.summary || {}).lead_fact;
      if (!lf) return false;
      showTrail("Summary, " + who, "The headline", sentenceTrail(env, (env.summary || {}).headline || lf.text, lf.claim_keys, lf.sources), origin, t);
    } else {
      const ch = (env.changes || [])[+m[2]];
      if (!ch) return false;
      showTrail("Change since the previous run, " + who, CHANGE[ch.type] || "Change", changeTrail(env, ch), origin, t);
    }
    return true;
  }
  function showTrail(kind, title, html, origin, target) {
    if (trailEl.hidden) lastFocus = document.activeElement;
    $("#tkind").textContent = kind;
    $("#ttitle").textContent = title;
    $("#tbody").innerHTML = html;
    $("#tbody").scrollTop = 0;
    trailTarget = target || "";
    trailOrigin = origin || (target ? $('[data-target="' + CSS.escape(target) + '"]', $("#main")) : null);
    $$(".tbtn.on, .tsrc.on, .on-trail").forEach((b) => b.classList.remove("on", "on-trail"));
    if (trailOrigin) { trailOrigin.classList.add("on"); const row = trailOrigin.closest(".fact, .kf, .si, .ls, .hline, tr, li"); if (row) row.classList.add("on-trail"); }
    trailEl.hidden = false;
    document.body.classList.add("trail-open");
    scrim.hidden = docked();
    if (!docked()) document.documentElement.classList.add("lock");
    trailEl.classList.remove("draw");
    void trailEl.offsetWidth;
    if (!reduced()) trailEl.classList.add("draw");
    thread();
    requestAnimationFrame(() => { $(".trail-in").focus({ preventScroll: true }); thread(); });
  }
  function hideTrail() {
    if (trailEl.hidden) return;
    trailEl.hidden = true;
    scrim.hidden = true;
    document.body.classList.remove("trail-open");
    document.documentElement.classList.remove("lock");
    $$(".tbtn.on, .tsrc.on, .on-trail").forEach((b) => b.classList.remove("on", "on-trail"));
    trailOrigin = null;
    thread();
    if (lastFocus && document.contains(lastFocus)) lastFocus.focus({ preventScroll: true });
  }
  function closeTrail() {
    if (/\/t\//.test(location.hash)) {
      if (trailPushed) { trailPushed = false; history.back(); return; }
      history.replaceState(null, "", location.hash.replace(/\/t\/.*$/, ""));
    }
    hideTrail();
  }
  /* The thread: a drawn line from the fact you followed to the first stop of its trail (wide screens, docked trail only). */
  const threadSvg = $("#thread"), threadP = $("#threadp");
  function thread() {
    if (trailEl.hidden || !docked() || !trailOrigin || !document.contains(trailOrigin)) { threadSvg.classList.remove("on"); return; }
    const a = trailOrigin.getBoundingClientRect();
    const pin = $(".route .pin", trailEl);
    if (!pin || a.bottom < 60 || a.top > innerHeight) { threadSvg.classList.remove("on"); return; }
    const b = pin.getBoundingClientRect(), tr = trailEl.getBoundingClientRect();
    const mk = $(".tmark", trailOrigin);
    const m0 = mk ? mk.getBoundingClientRect() : a;
    const x1 = Math.max(a.right, m0.right) + 3, y1 = m0.top + m0.height / 2, x2 = b.left - 2, y2 = b.top + b.height / 2;
    const gx = tr.left - 14, r = Math.min(14, Math.abs(y2 - y1) / 2), dy = y2 >= y1 ? 1 : -1;
    threadP.setAttribute("d", "M" + x1 + " " + y1 + " H" + (gx - r) + " Q" + gx + " " + y1 + " " + gx + " " + (y1 + dy * r) +
      " V" + (y2 - dy * r) + " Q" + gx + " " + y2 + " " + (gx + r) + " " + y2 + " H" + x2);
    threadSvg.classList.add("on");
  }
  window.addEventListener("scroll", thread, { passive: true });
  window.addEventListener("resize", () => { scrim.hidden = trailEl.hidden || docked(); requestAnimationFrame(thread); });
  $("#tbody").addEventListener("scroll", thread, { passive: true });

  /* ---------- summary: headline and plain-English brief first ---------- */
  const reEsc = (t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  function srcMap(env) {
    const m = {}, s = env.summary || {};
    const add = (x) => { if (x && x.name && isUrl(x.url) && !m[x.name]) m[x.name] = x.url; };
    (s.sources || []).forEach(add);
    if (s.lead_fact) (s.lead_fact.sources || []).forEach(add);
    (s.sentences || []).forEach((t) => (t.sources || []).forEach(add));
    return m;
  }
  function linkify(text, m) {
    text = String(text || "");
    const names = Object.keys(m).filter((n) => n.length > 2).sort((a, b) => b.length - a.length);
    const re = new RegExp(names.map(reEsc).concat(["https?://[^\\s)\\]]+"]).join("|"), "g");
    let out = "", last = 0, mt;
    while ((mt = re.exec(text))) {
      const w = mt[0].replace(/[.,;:]+$/, "") || mt[0];
      out += esc(text.slice(last, mt.index)) + (m[w] ? link(m[w], w, "srcl") : link(w, host(w), "srcl"));
      last = mt.index + w.length;
      re.lastIndex = Math.max(last, mt.index + 1);
    }
    return out + esc(text.slice(last));
  }
  const words = (t) => new Set(fold(t).replace(/\([^)]*\)/g, " ").split(/[^a-z0-9]+/).filter((w) => w.length > 2));
  function matchSentence(env, text) {
    const a = words(text);
    if (!a.size) return -1;
    let best = -1, bs = 0;
    ((env.summary || {}).sentences || []).forEach((s, i) => {
      const b = words(s.text);
      if (!b.size) return;
      let n = 0;
      a.forEach((w) => { if (b.has(w)) n++; });
      const sc = n / Math.min(a.size, b.size);
      if (sc > bs) { bs = sc; best = i; }
    });
    return bs >= 0.6 ? best : -1;
  }
  const nFacts = (env, keys) => (keys || []).filter((k) => env._k[k]).length;
  function sentT(env, i) {
    const s = sentenceAt(env, i);
    const n = s ? nFacts(env, s.claim_keys) : 0;
    return n ? tBtn("s:" + i, "summary sentence, " + plural(n, "fact"), n) : "";
  }
  function headlineT(env) {
    const s = env.summary || {};
    if (s.lead_fact && nFacts(env, s.lead_fact.claim_keys)) return tBtn("l:", "the headline, " + plural(nFacts(env, s.lead_fact.claim_keys), "fact"), nFacts(env, s.lead_fact.claim_keys));
    const i = s.headline ? matchSentence(env, s.headline) : -1;
    return i >= 0 ? sentT(env, i) : "";
  }
  /* Split the brief into sentences, never inside a quotation and never before a parenthesis. */
  function splitSentences(t) {
    t = String(t || "");
    const out = [];
    let depth = 0, start = 0;
    for (let i = 0; i < t.length; i++) {
      const ch = t[i];
      if (ch === "“" || ch === "«") depth++;
      else if ((ch === "”" || ch === "»") && depth > 0) depth--;
      else if (!depth && /[.!?]/.test(ch) && /\s/.test(t[i + 1] || "") && /[A-ZÆØÅ0-9“«"]/.test(t[i + 2] || "")) {
        out.push(t.slice(start, i + 1)); start = i + 2;
      }
    }
    out.push(t.slice(start));
    return out.map((x) => x.trim()).filter(Boolean);
  }
  function unknownsHtml(env) {
    const s = env.summary || {};
    const ex = Array.isArray(s.unknowns_explained) ? s.unknowns_explained : [];
    const unk = FAMKEYS.filter((f) => stOf(env, f).state !== "available");
    if (!unk.length) return "";
    const why = (f) => {
      const e = ex.find((x) => x.family === f);
      const st = stOf(env, f);
      return (e && e.text) || (st.note && st.note !== DEFAULT_NOTE ? st.note : STATE[st.state] ? STATE[st.state].d : "");
    };
    return '<section class="unk" aria-labelledby="h-unk"><h2 id="h-unk" class="h3">What we could not confirm</h2><ul>' +
      unk.map((f) => "<li>" + stChip(stOf(env, f).state, famShort(f)) + '<span class="mu">' + esc(cap(why(f))) + "</span></li>").join("") + "</ul></section>";
  }
  function briefHtml(env) {
    const s = env.summary || {};
    const sl = (s.sentences || []).map((x, i) => [x, i]);
    const m = srcMap(env);
    let html = "";
    if (s.headline) html += '<p class="hline">' + linkify(s.headline, m) + headlineT(env) + "</p>";
    if (s.text) {
      const used = new Set();
      const hl0 = fold(s.headline || "").trim();
      html += '<p class="ltext">' + splitSentences(s.text).filter((t) => fold(t).trim() !== hl0).map((t) => {
        const i = matchSentence(env, t);
        let c = i >= 0 && !used.has(i) ? (used.add(i), sentT(env, i)) : "";
        if (!c) {
          const ft = fold(t);
          const hit = newsOf(env).concat(openJobs(env)).find((x) => x.value.title && x.value.title.length > 6 && ft.includes(fold(x.value.title)));
          if (hit) c = tBtn("f:" + hit.key, clip(hit.value.title, 60));
        }
        return '<span class="ls">' + linkify(t, m) + c + "</span>";
      }).join(" ") + "</p>";
    }
    const list = (items) => '<ol class="sents">' + items.map(([x, i]) => '<li><span class="topic">' + esc(TOPIC[x.topic] || cap(String(x.topic || "").replace(/_/g, " "))) + "</span><p>" + linkify(x.text, m) +
      (x.method ? ' <span class="mu">(' + esc(x.method) + ")</span>" : "") + sentT(env, i) + "</p></li>").join("") + "</ol>";
    if (s.text) {
      if (sl.length) html += '<details class="more"><summary>Every summary sentence with its facts (' + sl.length + ")</summary>" + list(sl) + "</details>";
    } else {
      html += list(sl.slice(0, 4)) + (sl.length > 4 ? '<details class="more"><summary>' + plural(sl.length - 4, "more sentence") + "</summary>" + list(sl.slice(4)) + "</details>" : "");
    }
    return '<section class="brief" aria-label="Summary">' + html + "</section>";
  }

  /* ---------- company page ---------- */
  function peers(env, n) {
    const org = env.organisation_number, x = IDX[org] || {};
    const nace = String(x.nace || ""), lr = (v) => (v > 0 ? Math.log10(v) : 0);
    const score = (y) => {
      let s = 0;
      const yn = String(y.nace || "");
      if (nace && yn) s += yn === nace ? 6 : yn.slice(0, 4) === nace.slice(0, 4) ? 4 : yn.slice(0, 2) === nace.slice(0, 2) ? 3 : 0;
      if (x.revenue != null && y.revenue != null) s += Math.max(0, 2 - Math.abs(lr(x.revenue) - lr(y.revenue)));
      if (x.muni && y.muni === x.muni) s += 0.6;
      if (y.domain) s += 0.4;
      return s;
    };
    return KS.index.filter((y) => y.org !== org && y.status !== "failed").map((y) => [score(y), y]).sort((a, b) => b[0] - a[0] || b[1].facts - a[1].facts).slice(0, n || 3).map((p) => p[1]);
  }
  function headHtml(env) {
    const org = env.organisation_number, x = IDX[org] || {};
    const form = one(env, "identity", "legal_form"), ind = one(env, "identity", "industry"), muni = one(env, "identity", "municipality"), fd = one(env, "identity", "founded");
    const picked = compare.includes(org);
    const pe = env.status === "failed" ? [] : peers(env, 3);
    const facts = [form ? esc(String(form.value).replace(/\s*\(.*\)$/, "")) : "", muni ? esc(valText(muni)) : "", fd ? "founded " + esc(String(fd.value).slice(0, 4)) : ""].filter(Boolean);
    return '<header class="phead">' +
      '<a class="back" href="#/">' + ICON.back + "All companies</a>" +
      '<p class="porg"><span class="on">' + esc(orgFmt(org)) + '</span><button type="button" class="lb sm" data-copy="' + esc(org) + '" aria-label="Copy organisation number">Copy</button>' + facts.map((f) => "<span>" + f + "</span>").join("") + "</p>" +
      "<h1>" + esc(env.legal_name || x.name || org) + "</h1>" +
      '<p class="pind">' + esc(ind ? String(ind.value).replace(/^(\S+) (.*)$/, "$2 ($1)") : "Industry not registered") + "</p>" +
      '<div class="pact"><button type="button" class="btn" data-pick="' + org + '" aria-pressed="' + picked + '">' + ICON.pick + '<span class="bl">' + (picked ? "In compare" : "Compare") + "</span></button>" +
      '<a class="btn ghost" href="https://virksomhet.brreg.no/nb/oppslag/enheter/' + esc(org) + '" target="_blank" rel="noopener noreferrer">Brønnøysund' + ICON.ext + "</a>" +
      '<button type="button" class="btn ghost" data-copy-link>Copy link</button>' +
      '<button type="button" class="btn ghost" data-download="' + esc(org) + '">JSON</button></div>' +
      (pe.length ? '<div class="peers"><p>Side by side with</p><div class="pl">' + pe.map((y) => '<a class="peer" href="#/compare/' + org + "," + y.org + '"><b>' + esc(y.name) + "</b><span>" + esc([y.revenue != null ? money(y.revenue) : "", y.muni].filter(Boolean).join(", ")) + "</span></a>").join("") + "</div></div>" : "") +
      "</header>";
  }
  function kf(label, value, subText, claim, cls) {
    const inner = '<span class="kl">' + label + '</span><span class="kv2">' + value + "</span>" + (subText ? '<span class="ks">' + subText + "</span>" : "");
    return claim ? '<button type="button" class="kf ' + (cls || "") + '" data-target="f:' + esc(claim.key) + '">' + inner + ICON.t + "</button>" : '<div class="kf none ' + (cls || "") + '">' + inner + "</div>";
  }
  function figures(env) {
    const rev = latestFin(env, "revenue"), res = latestFin(env, "annual_result"), eq = latestFin(env, "equity");
    const prev = rev ? finIn(env, "revenue", +rev.value.year - 1) : null;
    let delta = "";
    if (rev && prev && prev.value.amount) {
      const d = ((rev.value.amount - prev.value.amount) / Math.abs(prev.value.amount)) * 100;
      delta = (d >= 0 ? "up " : "down ") + Math.abs(d).toFixed(Math.abs(d) < 10 ? 1 : 0) + "% on " + prev.value.year;
    }
    const emp = one(env, "identity", "registered_employees");
    const lead = rolesOf(env).find((c) => ["DAGL", "INNH"].includes(c.value.role_code)) || rolesOf(env).find((c) => c.value.role_code === "LEDE");
    const site = one(env, "website", "official_website"), wst = stOf(env, "website");
    return '<section class="kfs" aria-label="Key figures">' +
      kf("Revenue" + (rev ? " " + esc(rev.value.year) : ""), rev ? esc(money(rev.value.amount)) : "Not filed", esc(delta), rev, delta.startsWith("down") ? "dn" : "") +
      kf("Annual result" + (res ? " " + esc(res.value.year) : ""), res ? esc(money(res.value.amount)) : "Not filed", "", res, res && res.value.amount < 0 ? "neg" : "") +
      kf("Equity" + (eq ? " " + esc(eq.value.year) : ""), eq ? esc(money(eq.value.amount)) : "Not filed", eq && eq.value.amount < 0 ? "negative equity" : "", eq, eq && eq.value.amount < 0 ? "neg" : "") +
      kf("Employees", emp ? esc(nf.format(emp.value)) : "Not registered", emp ? "registered" + (emp.effective_date ? " " + fdate(emp.effective_date) : "") : "", emp) +
      kf(lead ? esc(ROLE_EN[lead.value.role_code] || lead.value.role) : "Leadership", lead ? esc(lead.value.name) : "None registered", "", lead) +
      kf("Website", site ? esc(site.value.domain) : esc(STATE[wst.state].w), site ? "proven: " + esc((site.value.identity_proof || []).map((p) => (PROOF[p] || [p])[0].toLowerCase()).join(", ")) : "", site, site ? "ok" : "") +
      "</section>";
  }
  function moreList(items, n, label) {
    if (items.length <= n) return items.join("");
    return items.slice(0, n).join("") + '<li class="mli"><details><summary>Show ' + (items.length - n) + " more " + label + '</summary><ul class="sl">' + items.slice(n).join("") + "</ul></details></li>";
  }
  function signalsHtml(env) {
    const site = one(env, "website", "official_website");
    const news = newsOf(env), jobs = openJobs(env), soc = claimsOf(env, "social");
    const careers = claimsOf(env, "jobs").filter((c) => (c.field === "careers_page" || c.field === "recruitment_channel") && c.value && c.value.url);
    const empty = (txt) => '<p class="empty">' + txt + "</p>";
    const item = (c, when, title, meta) => '<li class="si"><span class="sw">' + when + '</span><span class="stt">' + title + '</span><span class="sm">' + esc(meta) + "</span>" + tBtn("f:" + c.key, clip(valText(c), 60)) + "</li>";
    const newsLi = news.map((c) => item(c, c.effective_date ? fdate(c.effective_date) : "Undated", link(c.value.url, c.value.title || c.value.url), host(c.value.url)));
    const jobLi = jobs.map((c) => item(c, c.effective_date ? "Posted " + fdate(c.effective_date) : "Open now", link(c.value.url, c.value.title || c.value.url) + (c.relationship === "registered_subunit" ? ' <span class="tag">at a workplace</span>' : ""),
      [c.value.location, due(c.value), c.value.source || c.value.platform].filter(Boolean).join(", ")));
    const carLi = careers.map((c) => item(c, c.field === "careers_page" ? "Careers page" : "Recruitment page", link(c.value.url, host(c.value.url) + (new URL(c.value.url, "http://x").pathname.length > 1 ? new URL(c.value.url, "http://x").pathname : "")), c.value.platform || ""));
    const socLi = soc.map((c) => {
      const v = c.value || {};
      const p = PLAT[String(v.platform || "").toLowerCase()] || [String(v.platform || "?").slice(0, 2), cap(v.platform || "Profile")];
      return '<li class="sp"><a class="soc" href="' + esc(isUrl(v.url) ? v.url : "#") + '" target="_blank" rel="noopener noreferrer"><span class="sx" aria-hidden="true">' + esc(p[0]) + "</span><b>" + esc(p[1]) + "</b>" +
        (v.handle ? "<span>" + esc(v.handle) + "</span>" : "") + "</a>" + tBtn("f:" + c.key, p[1] + " profile") + "</li>";
    });
    const jst = stOf(env, "jobs"), sst = stOf(env, "social");
    const noSite = site ? "" : "no website was proven to belong to this organisation number, so nothing from a website is shown";
    const col = (id, title, n, body) => '<div class="sigc" id="sig-' + id + '"><h2 class="h3">' + esc(title) + (n ? "<b>" + n + "</b>" : "") + "</h2>" + body + "</div>";
    return '<section class="signals" aria-label="News, hiring and social profiles">' +
      col("news", "Company news", news.length, news.length ? '<ul class="sl">' + moreList(newsLi, 4, "news items") + "</ul>"
        : empty("No dated news" + (noSite ? ": " + noSite + "." : " posts found on " + link(site.value.url, site.value.domain) + "."))) +
      col("jobs", "Open jobs", jobs.length, (jobs.length ? '<ul class="sl">' + moreList(jobLi, 4, "postings") + "</ul>"
        : empty(jst.state === "failed" ? "The job sources failed this run; nothing is inferred from that." : "No open posting names this organisation number in NAV's feed" + (site ? " or on the recruitment pages its website links." : "."))) +
        (carLi.length ? '<ul class="sl car">' + carLi.join("") + "</ul>" : "")) +
      col("social", "Social profiles", soc.length, soc.length ? '<ul class="socs">' + socLi.join("") + "</ul>"
        : empty(sst.state === "ambiguous" ? "Candidate profiles were found but not proven to be this company's, so none are shown." : "None found" + (noSite ? ": " + noSite + "." : " linked from its website or its Wikidata item."))) +
      "</section>";
  }
  function section(id, title, state, body) {
    return '<section class="sec" id="s-' + id + '" aria-labelledby="h-' + id + '"><header class="sh"><h2 id="h-' + id + '">' + esc(title) + "</h2>" + (state ? stChip(state.st, state.text) : "") + "</header>" + body + "</section>";
  }
  const subh = (title, extra) => '<h3 class="subh">' + esc(title) + (extra || "") + "</h3>";
  function stateBox(env, fam) {
    const st = stOf(env, fam);
    const note = st.note && st.note !== DEFAULT_NOTE ? st.note : (STATE[st.state] || {}).d;
    const checked = (st.checked_sources || []).filter(Boolean);
    return '<div class="stbox st-' + esc(st.state) + '"><p><b>' + esc((STATE[st.state] || { w: st.state }).w) + ".</b> " + esc(note || "") + "</p>" + (checked.length ? '<p class="mu">Checked: ' + esc(checked.join(", ")) + "</p>" : "") + "</div>";
  }
  function factLi(env, c, label) {
    let when = c.effective_date || "";
    if (typeof c.value === "string" && String(when).slice(0, 10) === c.value.slice(0, 10)) when = "";
    const rel = c.relationship && c.relationship !== "exact" ? ' <span class="tag" title="' + esc(REL[c.relationship] || "") + '">' + (c.relationship === "registered_subunit" ? "at a workplace" : esc(c.relationship.replace(/_/g, " "))) + "</span>" : "";
    return '<li class="fact"><span class="fl">' + (label || esc(c.label || c.field)) + rel + (c.carried_forward ? ' <span class="tag off">kept from previous run</span>' : "") + "</span>" +
      '<span class="fv">' + fmtValue(c) + (when ? '<span class="fd">' + fdate(when) + "</span>" : "") + "</span>" + srcBtn(env, c) + "</li>";
  }
  const factList = (env, cs) => (cs.length ? '<ul class="facts">' + cs.map((c) => factLi(env, c)).join("") + "</ul>" : "");
  function barChart(title, pts, cls) {
    const W = 300, H = 150, padT = 20;
    const pos = Math.max(0, ...pts.map((d) => (d.v == null ? 0 : d.v)));
    const neg = Math.max(0, ...pts.map((d) => (d.v == null ? 0 : -d.v)));
    const padB = neg > 0 ? 34 : 22;
    const plotH = H - padT - padB, span = pos + neg || 1, zeroY = padT + plotH * (pos / span);
    const n = Math.max(1, pts.length), slot = (W - 8) / n, bw = Math.min(40, slot * 0.56);
    let g = '<line class="zero" x1="0" x2="' + W + '" y1="' + zeroY + '" y2="' + zeroY + '"/>';
    pts.forEach((d, i) => {
      const cx = 4 + i * slot + slot / 2, x = cx - bw / 2, last = i === n - 1;
      if (d.v == null) g += '<text class="na" x="' + cx + '" y="' + (zeroY - 6) + '" text-anchor="middle">none filed</text>';
      else {
        const h = Math.max(1, (Math.abs(d.v) / span) * plotH), y = d.v >= 0 ? zeroY - h : zeroY;
        g += '<rect class="' + (d.v < 0 ? "neg" : last ? "lat" : "bar") + '" x="' + x + '" y="' + y + '" width="' + bw + '" height="' + h + '" rx="1.5"><title>' + esc(title + " " + d.y + ": " + fullMoney(d.v)) + "</title></rect>";
        g += '<text class="vl" x="' + cx + '" y="' + (d.v >= 0 ? y - 5 : y + h + 13) + '" text-anchor="middle">' + esc(compact(d.v)) + "</text>";
      }
      g += '<text class="yr' + (last ? " lat" : "") + '" x="' + cx + '" y="' + (H - 5) + '" text-anchor="middle">' + esc(d.y) + "</text>";
    });
    return '<figure class="chart ' + (cls || "") + '"><figcaption>' + esc(title) + '</figcaption><svg viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="' +
      esc(title + ": " + pts.map((d) => d.y + " " + (d.v == null ? "none filed" : money(d.v))).join(", ")) + '">' + g + "</svg></figure>";
  }
  function accountsSection(env) {
    const fin = finOf(env);
    const pdfs = claimsOf(env, "financials", "annual_report_copy").filter((c) => c.value && c.value.year).sort((a, b) => String(b.value.year).localeCompare(String(a.value.year)));
    const st = { st: stOf(env, "financials").state };
    if (!fin.length && !pdfs.length) return section("accounts", "Accounts", st, stateBox(env, "financials"));
    const years = [...new Set(fin.map((c) => String(c.value.year)))].sort();
    const get = (f, y) => fin.find((c) => c.field === f && String(c.value.year) === y);
    let body = "";
    if (years.length) {
      const pts = (f) => years.map((y) => { const c = get(f, y); return { y, v: c ? c.value.amount : null }; });
      const charts = [];
      if (fin.some((c) => c.field === "revenue")) charts.push(barChart("Operating revenue, NOK", pts("revenue")));
      if (fin.some((c) => c.field === "annual_result")) charts.push(barChart("Annual result, NOK", pts("annual_result"), "res"));
      const latest = years[years.length - 1];
      body += '<div class="charts">' + charts.join("") + "</div>";
      body += '<div class="tw"><table class="fin"><caption class="sr">Filed figures by year in NOK. Each figure opens its source trail.</caption><thead><tr><th scope="col">NOK</th>' +
        years.map((y) => '<th scope="col"' + (y === latest ? ' class="lat"' : "") + ">" + esc(y) + "</th>").join("") + "</tr></thead><tbody>" +
        FIN_ROWS.filter(([f]) => years.some((y) => get(f, y))).map(([f, label]) => '<tr><th scope="row">' + esc(label) + "</th>" + years.map((y) => {
          const c = get(f, y);
          return "<td" + (y === latest ? ' class="lat"' : "") + ">" + (c ? '<button type="button" class="num' + (c.value.amount < 0 ? " neg" : "") + '" data-target="f:' + esc(c.key) + '" title="' + esc(fullMoney(c.value.amount, c.value.currency)) + '">' + esc(compact(c.value.amount)) + "</button>" : '<span class="mu">–</span>') + "</td>";
        }).join("") + "</tr>").join("") + "</tbody></table></div>";
      body += '<p class="note">As filed in the Register of Company Accounts. A dash means nothing was filed for that year. Select a figure to follow it to the filing.</p>';
    }
    if (pdfs.length) body += '<p class="pdfs"><span class="mu">Filed copies:</span> ' + pdfs.slice(0, 12).map((c) => link(c.value.url, c.value.year)).join(" ") + " " + srcBtn(env, pdfs[0], "Source") + "</p>";
    return section("accounts", "Accounts", st, body);
  }
  function peopleSection(env) {
    const roles = rolesOf(env);
    const peopleHtml = roles.length ? '<ul class="facts">' + roles.map((c) => {
      const v = c.value;
      return '<li class="fact"><span class="fl">' + esc(ROLE_EN[v.role_code] || v.role) + "</span><span class=\"fv\">" + fmtValue(c) + (c.effective_date ? '<span class="fd">since ' + fdate(c.effective_date) + "</span>" : "") + "</span>" + srcBtn(env, c) + "</li>";
    }).join("") + "</ul>" : stateBox(env, "people");
    const subs = claimsOf(env, "locations", "registered_subunit");
    const other = claimsOf(env, "locations").filter((c) => c.field !== "registered_subunit");
    const subLi = (c) => {
      const v = c.value || {};
      return '<li class="fact"><span class="fl">' + esc(v.name || "Workplace") + "</span><span class=\"fv\">" + esc([v.address, v.industry].filter(Boolean).join(", ")) +
        '<span class="fd">' + (v.registered_employees != null ? plural(v.registered_employees, "employee") : "") + (v.organisation_number ? " " + orgLink(v.organisation_number) : "") + "</span></span>" + srcBtn(env, c) + "</li>";
    };
    let wp = subs.length ? '<ul class="facts">' + subs.slice(0, 6).map(subLi).join("") + "</ul>" + (subs.length > 6 ? '<details class="more"><summary>All ' + subs.length + ' workplaces</summary><ul class="facts">' + subs.slice(6).map(subLi).join("") + "</ul></details>" : "") : "";
    wp += factList(env, other);
    if (!subs.length && !other.length) wp = stateBox(env, "locations");
    return section("people", "Leadership and workplaces", { st: stOf(env, "people").state }, '<div class="two"><div>' + subh("Registered roles") + peopleHtml + "</div><div>" + subh("Workplaces and addresses") + wp + "</div></div>");
  }
  function registerSection(env) {
    const ids = claimsOf(env, "identity").slice().sort((a, b) => {
      const ia = ID_ORDER.indexOf(a.field), ib = ID_ORDER.indexOf(b.field);
      return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
    });
    const desc = claimsOf(env, "description");
    const site = one(env, "website", "official_website");
    const regSite = one(env, "identity", "registered_website");
    let online = "";
    if (site) online = factList(env, claimsOf(env, "website"));
    else online = stateBox(env, "website") + (regSite ? '<p class="note">The register lists ' + fmtValue(regSite) + ", but that site did not prove it belongs to this organisation number, so it is not treated as the company's website.</p>" : "");
    const con = claimsOf(env, "contact");
    const descHtml = desc.length ? desc.map((c) => '<figure class="say"><figcaption>' + esc(c.label) + "</figcaption><blockquote>" + esc(valText(c)) + "</blockquote>" + srcBtn(env, c) + "</figure>").join("") : stateBox(env, "description");
    return section("register", "Register record and website", { st: stOf(env, "identity").state }, '<div class="two"><div>' + subh("Register record") + factList(env, ids) + "</div><div>" +
      subh("What it does") + descHtml + subh("Website") + online + subh("Contact details") + (con.length ? factList(env, con) : stateBox(env, "contact")) + "</div></div>");
  }
  const tl = { routine: false, all: false };
  function timelineHtml(env) {
    const all = datedActivity(env, true);
    const routineN = all.filter((c) => ROUTINE.has(c.field)).length;
    let list = tl.routine ? all : all.filter((c) => !ROUTINE.has(c.field));
    const total = list.length;
    if (!tl.all) list = list.slice(0, 12);
    if (!all.length) return stateBox(env, "activity");
    let year = "", html = '<ol class="tl">';
    list.forEach((c) => {
      const y = String(c.effective_date).slice(0, 4);
      if (y !== year) { year = y; html += '<li class="ty" aria-hidden="true">' + esc(y) + "</li>"; }
      const d = String(c.effective_date).slice(0, 10).match(/^(\d{4})-(\d{2})-(\d{2})$/);
      html += '<li class="ti' + (ROUTINE.has(c.field) ? " routine" : "") + '"><time datetime="' + esc(String(c.effective_date).slice(0, 10)) + '">' + (d ? +d[3] + " " + MON[+d[2] - 1] : esc(c.effective_date)) + '<span class="sr"> ' + y + "</span></time>" +
        '<div class="tb"><span class="tk">' + esc(c.label || c.field) + '</span><span class="tt">' + fmtValue(c) + "</span></div>" + srcBtn(env, c) + "</li>";
    });
    html += "</ol>";
    html += '<div class="tlc">' + (routineN ? '<label class="tog"><input type="checkbox" data-tl="routine"' + (tl.routine ? " checked" : "") + "> Include routine register updates (" + routineN + ")</label>" : "") +
      (total > 12 ? '<button type="button" class="lb" data-tl="all">' + (tl.all ? "Show the latest 12" : "Show all " + total + " dated items") + "</button>" : "") + "</div>";
    return html;
  }
  function activitySection(env) {
    const rev = claimsOf(env, "reviews");
    const closed = claimsOf(env, "jobs", "job_posting").filter((c) => (c.value || {}).status === "closed");
    return section("activity", "Dated activity", { st: stOf(env, "activity").state }, '<div id="tl">' + timelineHtml(env) + "</div>" +
      '<div class="two"><div>' + subh("Customer ratings") + (rev.length ? factList(env, rev) : stateBox(env, "reviews")) + "</div><div>" +
      (closed.length ? subh("Closed job postings") + factList(env, closed) : "") + "</div></div>");
  }
  function availabilitySection(env) {
    const rows = FAMKEYS.map((f) => {
      const st = stOf(env, f), n = (env._f[f] || []).length;
      const note = st.note && st.note !== DEFAULT_NOTE ? st.note : st.state === "available" ? "" : STATE[st.state].d;
      return '<tr><th scope="row">' + esc(FAML[f]) + "</th><td>" + stChip(st.state) + '</td><td class="n">' + (n ? nf.format(n) : "–") + "</td><td>" + esc(note || "") +
        ((st.checked_sources || []).length ? '<span class="mu block">Checked: ' + esc(st.checked_sources.filter(Boolean).join(", ")) + "</span>" : "") + "</td></tr>";
    }).join("");
    const by = {};
    (env.evidence || []).forEach((e) => { const k = e.source_name || host(e.source_url); by[k] = (by[k] || 0) + 1; });
    const srcs = Object.entries(by).sort((a, b) => b[1] - a[1]);
    const errs = env.errors || [];
    return section("evidence", "Sources and availability", null,
      '<div class="tw"><table class="avail"><thead><tr><th scope="col">Information type</th><th scope="col">State</th><th scope="col" class="n">Facts</th><th scope="col">What was checked</th></tr></thead><tbody>' + rows + "</tbody></table></div>" +
      '<p class="note">' + plural((env.claims || []).length, "fact") + " from " + plural((env.evidence || []).length, "evidence record") + ": " + srcs.map(([k, n]) => esc(k) + " " + n).join(", ") + "." +
      (errs.length ? " Source errors: " + errs.map((e) => esc(e.source || "") + " (" + esc(e.message || "") + ")").join("; ") + "." : " No source errors.") + "</p>");
  }
  function changesSection(env) {
    const ch = env.changes || [], r = env.refresh || {};
    if (!r.previous_run_id) return section("changes", "Changes since the last run", { st: "not_applicable", text: "First run" }, '<p class="note">First run for this company. The next run compares every fact by its stable key and lists what was added, removed or changed, with evidence for both sides.</p>');
    const body = ch.length ? '<ul class="chg">' + ch.map((e, i) => '<li><span class="tag ' + esc(e.change || "") + '">' + esc(cap(e.change || e.type)) + '</span><div><b>' + esc(CHANGE[e.type] || cap(String(e.type).replace(/_/g, " "))) + "</b> " +
      '<span class="mu">' + esc(famShort(e.family)) + "</span><div>" + (e.previous !== undefined ? "<s>" + esc(objText(e.previous)) + "</s> " : "") + (e.current !== undefined ? esc(objText(e.current)) : "") + "</div></div>" + tBtn("c:" + i, "change evidence") + "</li>").join("") + "</ul>"
      : '<p class="note">Every fact is unchanged since run ' + esc(r.previous_run_id) + ".</p>";
    return section("changes", "Changes since the last run", { st: ch.length ? "available" : "not_available", text: plural(ch.length, "change") }, body);
  }
  function secNav() {
    const items = [["accounts", "Accounts"], ["people", "People"], ["register", "Register"], ["activity", "Activity"], ["evidence", "Sources"], ["changes", "Changes"]];
    return '<nav class="secnav" aria-label="Sections"><ul>' + items.map((i) => '<li><a href="#s-' + i[0] + '" data-jump="' + i[0] + '">' + i[1] + "</a></li>").join("") + "</ul></nav>";
  }
  function renderProfile(env) {
    const main = $("#main");
    if (env.status === "failed") {
      main.innerHTML = '<div class="page">' + headHtml(env) + '<div class="stbox st-failed"><p><b>Not found in the official register.</b> The organisation number could not be anchored in Brønnøysundregistrene, so no other source was trusted for it.</p></div>' + availabilitySection(env) + foot() + "</div>";
    } else {
      main.innerHTML = '<div class="page">' + headHtml(env) + briefHtml(env) + figures(env) + signalsHtml(env) + unknownsHtml(env) + secNav() +
        accountsSection(env) + peopleSection(env) + registerSection(env) + activitySection(env) + availabilitySection(env) + changesSection(env) + foot() + "</div>";
    }
    document.title = (env.legal_name || env.organisation_number) + ", Kildespor";
  }
  function foot() {
    const r = KS.run || {};
    return '<footer class="foot"><p><b>How a fact gets in.</b> The organisation number is the anchor. A website is published only when the site proves it belongs to this entity; social profiles only when that website or the matching Wikidata item links them; job ads only when the employer field names this organisation number or one of its workplaces. When a match is uncertain the fact is withheld and the page says so. Missing values stay missing, never zero.</p>' +
      "<p><b>Sources.</b> Brønnøysundregistrene (NLOD 2.0), the company's own website, NAV arbeidsplassen, Støtteregisteret, Mattilsynet, Finanstilsynet, TED, Wikidata (CC0).</p>" +
      '<p class="mu">Kildespor ' + esc(String(r.agent || "").replace(/^kildespor\s*/, "")) + ", run " + esc(r.run_id || "") + ". This viewer works offline from the run folder.</p></footer>";
  }

  /* ---------- compare ---------- */
  function suggestedPairs() {
    const ok = KS.index.filter((x) => x.status !== "failed");
    const top2 = (arr) => (arr.length >= 2 ? [arr[0], arr[1]] : null);
    const out = [];
    const rev = ok.filter((x) => x.revenue != null).sort((a, b) => b.revenue - a.revenue);
    const p = (label, pair) => { if (pair) out.push([label, pair]); };
    p("The two largest by revenue", top2(rev));
    p("Two companies hiring now", top2(ok.filter((x) => x.jobs > 0).sort((a, b) => b.jobs - a.jobs)));
    p("Two with recent company news", top2(ok.filter((x) => x.news > 0).sort((a, b) => String(b.nd).localeCompare(String(a.nd)))));
    const by = {};
    rev.forEach((x) => { if (x.nace) (by[x.nace] = by[x.nace] || []).push(x); });
    const ind = Object.values(by).filter((a) => a.length >= 2).sort((a, b) => b.length - a.length || b[0].revenue - a[0].revenue)[0];
    if (ind) p("Same industry: " + (ind[0].industry || ind[0].nace), [ind[0], ind[1]]);
    p("Two with proven websites", top2(ok.filter((x) => x.domain && x.revenue != null).sort((a, b) => b.facts - a.facts)));
    const seen = new Set();
    return out.filter(([, q]) => { const k = [q[0].org, q[1].org].sort().join(); if (seen.has(k)) return false; seen.add(k); return true; });
  }
  function pickRow(x) {
    const on = compare.includes(x.org);
    return '<li class="cr"><div><a href="#/c/' + x.org + '">' + esc(x.name) + '</a><span class="mu">' + esc([orgFmt(x.org), x.muni, x.revenue != null ? money(x.revenue) + " revenue" : ""].filter(Boolean).join(", ")) + "</span></div>" +
      '<button type="button" class="btn sm' + (on ? "" : " ghost") + '" data-pick="' + x.org + '" aria-pressed="' + on + '">' + ICON.pick + '<span class="bl">' + (on ? "In compare" : "Compare") + "</span></button></li>";
  }
  function pickResults() {
    const el = $("#cres");
    if (!el) return;
    const ts = fold(($("#cq") || {}).value || "").trim().split(/\s+/).filter(Boolean);
    const hits = (ts.length ? KS.index.filter((x) => ts.every((t) => x._h.includes(t))) : KS.index.slice().sort((a, b) => b.facts - a.facts)).slice(0, 8);
    el.innerHTML = hits.length ? hits.map(pickRow).join("") : '<li class="none">No company matches. Try a name, an organisation number or a place.</li>';
  }
  function chosenHtml() {
    const L = "ABCD";
    const items = compare.map((o, i) => '<li><span class="lt" data-ci="' + i + '">' + L[i] + "</span>" + esc((IDX[o] || {}).name || o) + '<button type="button" class="iconbtn sm" data-unpick="' + o + '" aria-label="Remove ' + esc((IDX[o] || {}).name || o) + '">' + ICON.cross + "</button></li>").join("");
    return items ? '<ol class="chosen">' + items + "</ol>" + (compare.length === 1 ? '<p class="mu">Choose one more.</p>' : "") : '<p class="mu">Nothing chosen yet.</p>';
  }
  function renderChosen() { const el = $("#chosen"); if (el) el.innerHTML = chosenHtml(); }
  function renderPicker() {
    const pairs = suggestedPairs();
    $("#main").innerHTML = '<div class="page"><h1 class="ph">Compare companies</h1><p class="lede">Choose two to four companies to see accounts, size, website, hiring, news and what is unknown side by side. Every value keeps its trail to the source.</p>' +
      (pairs.length ? '<section class="blk"><h2 class="h3">Start from a pair</h2><ul class="pairs">' + pairs.map(([label, q]) => '<li><a class="pair" href="#/compare/' + q[0].org + "," + q[1].org + '"><span>' + esc(label) + "</span><b>" + esc(q[0].name) + "</b><b>" + esc(q[1].name) + "</b></a></li>").join("") + "</ul></section>" : "") +
      '<section class="blk"><h2 class="h3">Or choose your own</h2><div id="chosen">' + chosenHtml() + "</div>" +
      '<div class="sbox"><label class="sr" for="cq">Find a company to compare</label><svg class="sic" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="6.5"/><path d="m16 16 4.5 4.5"/></svg>' +
      '<input id="cq" type="search" placeholder="Name, org.nr, website, place or industry" autocomplete="off" spellcheck="false"></div><ul class="cres" id="cres"></ul></section>' + foot() + "</div>";
    pickResults();
    document.title = "Compare, Kildespor";
  }
  async function renderCompare(orgs) {
    const main = $("#main");
    main.innerHTML = '<div class="page"><p class="loading">Loading profiles…</p></div>';
    const envs = (await Promise.all(orgs.map((o) => load(o).catch(() => null)))).filter(Boolean);
    if (envs.length < 2) {
      setCompare(envs.map((e) => e.organisation_number).concat(compare).filter((o, i, a) => a.indexOf(o) === i), true);
      renderPicker();
      return;
    }
    setCompare(envs.map((e) => e.organisation_number), true);
    const L = "ABCD";
    const cell = (env, c, text, extra) => (c ? '<button type="button" class="cv" data-target="f:' + esc(c.key) + '">' + (text != null ? text : esc(valText(c))) + ICON.t + "</button>" + (extra || "") : '<span class="mu">' + (text || "–") + "</span>");
    const fin = (field, delta) => (e) => {
      const c = latestFin(e, field);
      if (!c) return '<span class="mu">Not filed</span>';
      let d = "";
      if (delta) {
        const p = finIn(e, field, +c.value.year - 1);
        if (p && p.value.amount) { const x = ((c.value.amount - p.value.amount) / Math.abs(p.value.amount)) * 100; d = '<span class="dl">' + (x >= 0 ? "up " : "down ") + Math.abs(x).toFixed(0) + "% on " + p.value.year + "</span>"; }
      }
      return cell(e, c, '<span class="' + (c.value.amount < 0 ? "neg" : "") + '">' + esc(money(c.value.amount)) + '</span> <span class="yr">' + esc(c.value.year) + "</span>") + d;
    };
    const allYears = [...new Set(envs.flatMap((e) => finOf(e).filter((c) => c.field === "revenue").map((c) => String(c.value.year))))].sort().slice(-5);
    const revMax = Math.max(1, ...envs.flatMap((e) => finOf(e).filter((c) => c.field === "revenue").map((c) => Math.abs(c.value.amount))));
    const spark = (e) => {
      if (!allYears.length || !allYears.some((y) => { const c = finIn(e, "revenue", y); return c && c.value.amount > 0; })) return '<span class="mu">No positive revenue filed</span>';
      const W = 150, H = 44, n = allYears.length, slot = W / n, bw = Math.min(20, slot * 0.6);
      let g = '<line class="zero" x1="0" x2="' + W + '" y1="' + (H - 12) + '" y2="' + (H - 12) + '"/>';
      allYears.forEach((y, i) => {
        const c = finIn(e, "revenue", y), cx = i * slot + slot / 2;
        if (c && c.value.amount > 0) { const h = Math.max(1, (c.value.amount / revMax) * (H - 16)); g += '<rect class="' + (i === n - 1 ? "lat" : "bar") + '" x="' + (cx - bw / 2) + '" y="' + (H - 12 - h) + '" width="' + bw + '" height="' + h + '"><title>' + esc(y + ": " + fullMoney(c.value.amount)) + "</title></rect>"; }
        g += '<text x="' + cx + '" y="' + (H - 1) + '" text-anchor="middle">' + esc(y.slice(2)) + "</text>";
      });
      return '<svg class="spark" viewBox="0 0 ' + W + " " + H + '" role="img" aria-label="Revenue by year, on one scale for all compared companies">' + g + "</svg>";
    };
    const role = (codes) => (e) => {
      const r = rolesOf(e).filter((c) => codes.includes(c.value.role_code));
      return r.length ? r.slice(0, 2).map((c) => cell(e, c, esc(c.value.name))).join("") + (r.length > 2 ? '<span class="mu"> and ' + (r.length - 2) + " more</span>" : "") : '<span class="mu">None registered</span>';
    };
    const stateText = (e, f) => stChip(stOf(e, f).state);
    const groups = [
      ["In one line", [
        ["Summary", (e) => { const s = e.summary || {}; if (!s.headline) return '<span class="mu">–</span>'; return '<span class="chl">' + linkify(s.headline, srcMap(e)) + "</span>" + headlineT(e); }],
      ]],
      ["Size and accounts", [
        ["Revenue", fin("revenue", true)], ["Revenue by year", spark], ["Operating result", fin("operating_result")], ["Annual result", fin("annual_result")],
        ["Equity", fin("equity")], ["Total assets", fin("total_assets")],
        ["Employees", (e) => cell(e, one(e, "identity", "registered_employees"), null) || ""],
        ["Workplaces", (e) => { const s = claimsOf(e, "locations", "registered_subunit"); return s.length ? cell(e, s[0], plural(s.length, "workplace")) : '<span class="mu">None registered</span>'; }],
      ]],
      ["Online", [
        ["Website", (e) => { const c = one(e, "website", "official_website"); return c ? cell(e, c, esc(c.value.domain)) + '<span class="dl">proven by ' + esc((c.value.identity_proof || []).map((p) => (PROOF[p] || [p])[0].toLowerCase()).join(", ")) + "</span>" : stateText(e, "website"); }],
        ["Social profiles", (e) => { const s = claimsOf(e, "social"); return s.length ? s.slice(0, 5).map((c) => cell(e, c, esc(platName(c.value.platform)))).join("") : stateText(e, "social"); }],
        ["Contact details", (e) => { const s = claimsOf(e, "contact"); return s.length ? cell(e, s[0], plural(s.length, "detail") + " published") : stateText(e, "contact"); }],
      ]],
      ["Hiring and news", [
        ["Open jobs", (e) => { const j = openJobs(e); return j.length ? '<ul class="ul">' + j.slice(0, 3).map((c) => "<li>" + cell(e, c, esc(clip(c.value.title || "Posting", 64))) + (due(c.value) ? '<span class="dl">' + esc(due(c.value)) + "</span>" : "") + "</li>").join("") + "</ul>" + (j.length > 3 ? '<span class="mu">and ' + (j.length - 3) + " more</span>" : "") : stOf(e, "jobs").state === "available" ? '<span class="mu">No open postings</span>' : stateText(e, "jobs"); }],
        ["Company news", (e) => { const n = newsOf(e); return n.length ? '<ul class="ul">' + n.slice(0, 3).map((c) => "<li>" + cell(e, c, '<span class="yr">' + fdate(c.effective_date) + "</span> " + esc(clip(c.value.title || "", 64))) + "</li>").join("") + "</ul>" : '<span class="mu">None found</span>'; }],
        ["Latest dated activity", (e) => { const a = datedActivity(e, false)[0]; return a ? cell(e, a, '<span class="yr">' + fdate(a.effective_date) + "</span> " + esc(clip(valText(a), 64))) : '<span class="mu">None</span>'; }],
      ]],
      ["Leadership", [["Managing director", role(["DAGL", "INNH"])], ["Chair of the board", role(["LEDE"])], ["Auditor", role(["REVI"])]]],
      ["Identity", [
        ["Industry", (e) => { const c = one(e, "identity", "industry"); return c ? cell(e, c, esc(String(c.value).replace(/^\S+ /, ""))) : '<span class="mu">–</span>'; }],
        ["Municipality", (e) => cell(e, one(e, "identity", "municipality"))],
        ["Legal form", (e) => cell(e, one(e, "identity", "legal_form"))],
        ["Founded", (e) => cell(e, one(e, "identity", "founded"))],
      ]],
      ["What is unknown", [
        ["Not found or withheld", (e) => { const u = FAMKEYS.filter((f) => stOf(e, f).state !== "available"); return u.length ? '<ul class="ul">' + u.map((f) => "<li>" + stChip(stOf(e, f).state, famShort(f)) + "</li>").join("") + "</ul>" : "Nothing"; }],
        ["Facts and evidence", (e) => plural((e.claims || []).length, "fact") + ', <span class="mu">' + plural((e.evidence || []).length, "evidence record") + "</span>"],
      ]],
    ];
    const head = envs.map((e, i) => '<th scope="col" data-ci="' + i + '"><div class="ch"><span class="lt" data-ci="' + i + '">' + L[i] + '</span><div><a href="#/c/' + e.organisation_number + '">' + esc(e.legal_name || e.organisation_number) + '</a><span class="mu">' + orgFmt(e.organisation_number) +
      '</span></div><button type="button" class="iconbtn sm" data-unpick="' + e.organisation_number + '" aria-label="Remove ' + esc(e.legal_name) + ' from compare">' + ICON.cross + "</button></div></th>").join("");
    const body = groups.map(([g, rows]) => '<tbody><tr class="grp"><th scope="colgroup" colspan="' + (envs.length + 1) + '">' + esc(g) + "</th></tr>" +
      rows.map(([label, fn]) => '<tr><th scope="row">' + esc(label) + "</th>" + envs.map((e, i) => '<td data-org="' + e.organisation_number + '" data-ci="' + i + '"><span class="lt" data-ci="' + i + '" aria-hidden="true">' + L[i] + '</span><div class="cc">' + (fn(e) || '<span class="mu">–</span>') + "</div></td>").join("") + "</tr>").join("") + "</tbody>").join("");
    const legend = '<ol class="cleg">' + envs.map((e, i) => '<li><span class="lt" data-ci="' + i + '">' + L[i] + '</span><a href="#/c/' + e.organisation_number + '">' + esc(e.legal_name) + '</a><button type="button" class="iconbtn sm" data-unpick="' + e.organisation_number + '" aria-label="Remove ' + esc(e.legal_name) + '">' + ICON.cross + "</button></li>").join("") + "</ol>";
    main.innerHTML = '<div class="page wide"><header class="cmph"><div><h1 class="ph">' + envs.map((e) => esc(e.legal_name)).join('<span class="vs"> and </span>') + "</h1>" +
      '<p class="mu">Every value is a fact with a trail. Select one to follow it to its source.</p></div><div class="pact"><a class="btn ghost" href="#/compare/">Change companies</a><button type="button" class="btn ghost" data-copy-link>Copy link</button></div></header>' + legend +
      '<div class="cw"><table class="cmp n' + envs.length + '"><caption class="sr">Side-by-side comparison</caption><thead><tr><th scope="col"><span class="sr">Field</span></th>' + head + "</tr></thead>" + body + "</table></div>" + foot() + "</div>";
    document.title = "Compare " + envs.map((e) => e.legal_name).join(" and ") + ", Kildespor";
  }

  /* ---------- start (home) and run overview ---------- */
  function featured() {
    return KS.index.filter((x) => x.status !== "failed").sort((a, b) => (!!b.domain && b.news > 0) - (!!a.domain && a.news > 0) || (b.social > 0) - (a.social > 0) || (b.revenue || 0) - (a.revenue || 0))[0];
  }
  function renderHome() {
    const n = KS.index.length, f = featured(), pair = suggestedPairs()[0];
    const cnt = (k) => KS.index.filter(TEST[k]).length;
    const news = KS.index.filter((x) => x.news > 0 && x.nd).sort((a, b) => String(b.nd).localeCompare(String(a.nd))).slice(0, 6);
    const jobs = KS.index.filter((x) => x.jobs > 0 && x.jt).sort((a, b) => b.jobs - a.jobs).slice(0, 6);
    $("#main").innerHTML = '<div class="page home">' +
      '<section class="hero"><h1>' + plural(n, "Norwegian company", "Norwegian companies") + ". Every fact leads back to its source.</h1>" +
      '<p class="lede">Each value below carries a red trail mark ' + ICON.t + ". Select it to follow the fact to the exact document it came from: when it was fetched, the hash of the bytes and the words it rests on.</p>" +
      '<div class="demo" id="demo">' + (f ? '<p class="loading">Loading an example…</p>' : "") + "</div></section>" +
      '<section class="ways"><div><h2 class="h3">Find</h2><p>Type a name, organisation number, website, place or industry in the search on the left' + (narrow() ? "" : " (press /)") + ". Filter to companies with " +
      '<button type="button" class="lb" data-quick="site">a website (' + cnt("site") + ')</button>, <button type="button" class="lb" data-quick="jobs">hiring (' + cnt("jobs") + ')</button> or <button type="button" class="lb" data-quick="news">company news (' + cnt("news") + ")</button>.</p></div>" +
      '<div><h2 class="h3">Compare</h2><p>Tick two to four companies, or start from a pair.</p>' + (pair ? '<p><a class="btn sm" href="#/compare/' + pair[1][0].org + "," + pair[1][1].org + '">' + esc(clip(pair[1][0].name, 26)) + " and " + esc(clip(pair[1][1].name, 26)) + "</a></p>" : "") + "</div>" +
      '<div><h2 class="h3">Verify</h2><p>Every sentence, figure, news item, job and profile has a trail. Unknowns say why they are unknown.</p>' + (f ? '<p><a class="btn sm ghost" href="#/c/' + f.org + '">Open ' + esc(clip(f.name, 30)) + "</a></p>" : "") + "</div></section>" +
      (news.length || jobs.length ? '<div class="two feeds"><section><h2 class="h3">Latest company news</h2>' + (news.length ? '<ul class="feed">' + news.map((x) => '<li><time datetime="' + esc(x.nd) + '">' + fdate(x.nd) + "</time><div>" + link(x.nu, x.nt || "News item") + '<a class="fco" href="#/c/' + x.org + '">' + esc(x.name) + "</a></div></li>").join("") + "</ul>" : '<p class="mu">None in this run.</p>') + "</section>" +
        '<section><h2 class="h3">Hiring now</h2>' + (jobs.length ? '<ul class="feed">' + jobs.map((x) => '<li><span class="fn">' + plural(x.jobs, "job") + "</span><div><span>" + esc(x.jt) + '</span><a class="fco" href="#/c/' + x.org + '">' + esc(x.name) + "</a></div></li>").join("") + "</ul>" : '<p class="mu">None in this run.</p>') + "</section></div>" : "") +
      foot() + "</div>";
    document.title = "Kildespor, " + plural(n, "company", "companies");
    if (f) load(f.org).then((env) => { const d = $("#demo"); if (d && rendered === "home") d.innerHTML = demoHtml(env); }).catch(() => { const d = $("#demo"); if (d) d.innerHTML = ""; });
  }
  function demoHtml(env) {
    const s = env.summary || {};
    const keys = (s.lead_fact && s.lead_fact.claim_keys) || [];
    const c = newsOf(env).find((x) => (x.evidence_ids || []).length) || keys.map((k) => env._k[k]).find((x) => x && (x.evidence_ids || []).length) || latestFin(env, "revenue") || (env.claims || [])[0];
    if (!c) return "";
    const e = env._ev[(c.evidence_ids || [])[0]];
    return '<div class="demo-in"><p class="dco"><a href="#/c/' + env.organisation_number + '">' + esc(env.legal_name) + "</a>, " + esc(c.label || c.field) + "</p>" +
      '<ol class="route static">' + factNode(env, c, "The fact") + evNodes(e, c, true) + "</ol>" +
      '<p><a class="lb" href="#/c/' + env.organisation_number + "/t/f:" + encodeURIComponent(c.key) + '">Open this trail on the company page</a></p></div>';
  }
  function renderRun() {
    const r = KS.run || {}, n = KS.index.length, ops = r.operations || {};
    const counts = FAMKEYS.map((f, i) => { const c = {}; KS.index.forEach((x) => { const s = x.ribbon[i] || "not_available"; c[s] = (c[s] || 0) + 1; }); return c; });
    const val = r.validation || {};
    const stat = (label, v, s) => '<div class="stat"><dt>' + label + "</dt><dd>" + v + (s ? "<small>" + s + "</small>" : "") + "</dd></div>";
    const covRows = FAMKEYS.map((f, i) => {
      const c = counts[i], found = c.available || 0;
      return '<li class="covrow"><span class="cl">' + esc(famShort(f)) + '</span><span class="segs">' + ST_ORDER.filter((s) => c[s]).map((s) =>
        '<button type="button" class="seg s-' + s + '" style="flex-grow:' + c[s] + '" data-ff="' + f + '" data-fs="' + s + '" title="' + esc(famShort(f) + ": " + c[s] + " " + STATE[s].w.toLowerCase()) + '" aria-label="' +
        esc(famShort(f) + ": " + c[s] + " companies " + STATE[s].w.toLowerCase() + ". List them") + '">' + (c[s] / n >= 0.08 ? nf.format(c[s]) : "") + "</button>").join("") +
        '</span><span class="cp"><b>' + Math.round((found / Math.max(1, n)) * 100) + "%</b> found</span></li>";
    }).join("");
    const bySrc = Object.entries(ops.by_source || {}).sort((a, b) => b[1] - a[1]);
    $("#main").innerHTML = '<div class="page">' +
      '<h1 class="ph">The run</h1><p class="mu">Run ' + esc(r.run_id || "–") + (r.started_at ? ", " + fdt(r.started_at) + " to " + fdt(r.completed_at).replace(/^.*?, /, "") : "") + (r.agent ? ", " + esc(r.agent) : "") + ".</p>" +
      '<dl class="stats">' + stat("Companies", nf.format(r.companies || n)) + stat("Facts", nf.format(r.claims || 0), "each with a trail") + stat("Evidence records", nf.format(r.evidence_records || 0), "URL, time, hash, quote") +
      stat("Runtime", dur(r.runtime_seconds), ops.p50_company_ms ? "median " + dur(ops.p50_company_ms / 1000) + " per company" : "") + stat("Requests", nf.format(ops.requests || 0)) + stat("Third-party cost", "$" + Number(ops.third_party_cost_usd || 0).toFixed(2)) + "</dl>" +
      '<section class="blk"><h2 class="h3">Validation ' + stChip(val.passed ? "available" : "failed", val.passed ? "Passed" : val.passed === false ? "Failed" : "Not recorded") + '</h2><ul class="checks">' +
      Object.entries(val.checks || {}).map(([k, v]) => '<li class="' + (v ? "ok" : "bad") + '">' + (v ? ICON.check : ICON.cross) + "<span>" + esc(cap(k.replace(/_/g, " "))) + "</span></li>").join("") + "</ul></section>" +
      '<section class="blk"><h2 class="h3">Coverage by information type</h2><p class="mu">How many companies have facts of each type, and why the rest do not. Select a segment to list those companies.</p><ul class="covrows">' + covRows + "</ul>" +
      '<p class="legend">' + ST_ORDER.map((s) => '<span><i class="s-' + s + '"></i>' + STATE[s].w + "</span>").join("") + "</p></section>" +
      (bySrc.length ? '<section class="blk"><h2 class="h3">Requests by source</h2><p class="mu">' + bySrc.map(([k, v]) => esc(k.replace(/_/g, " ")) + " " + nf.format(v)).join(", ") + ".</p></section>" : "") +
      foot() + "</div>";
    document.title = "The run, Kildespor";
  }

  /* ---------- routing ---------- */
  let rendered = "", listScroll = 0;
  function setView(v) {
    if (narrow() && document.body.dataset.view === "home" && v !== "home") listScroll = window.scrollY;
    document.body.dataset.view = v;
  }
  function navOn(k) { $$(".tabs a").forEach((a) => (a.dataset.nav === k ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current"))); }
  async function route() {
    const h = location.hash.slice(1) || "/";
    const m = h.match(/^\/c\/(\d{9})(?:\/(?:t|e)\/(.+))?$/);
    const cm = h.match(/^\/compare\/([\d,]*)/);
    if (m) {
      setView("page");
      navOn("find");
      currentOrg = m[1];
      markCurrent();
      let env = null;
      if (rendered !== "c/" + m[1]) {
        hideTrail();
        tl.routine = false; tl.all = false;
        $("#main").innerHTML = '<div class="page"><p class="loading">Loading profile…</p></div>';
        try { env = await load(m[1]); } catch (e) {
          $("#main").innerHTML = '<div class="page"><a class="back" href="#/">' + ICON.back + 'All companies</a><div class="stbox st-failed"><p><b>Profile not available.</b> ' + esc(e.message) + "</p></div></div>";
          rendered = ""; return;
        }
        if (currentOrg !== m[1]) return;
        renderProfile(env);
        rendered = "c/" + m[1];
        window.scrollTo(0, 0);
        if (!m[2]) $("#main").focus({ preventScroll: true });
      } else env = cache[m[1]];
      if (m[2]) {
        const t = decodeURIComponent(m[2]);
        const o = $('[data-target="' + CSS.escape(t) + '"]', $("#main"));
        if (o && !trailPushed) { const rr = o.getBoundingClientRect(); if (rr.top < 120 || rr.bottom > innerHeight - 40) o.scrollIntoView({ block: "center" }); }
        const origin = trailOrigin && document.contains(trailOrigin) && trailOrigin.dataset.target === t ? trailOrigin : o;
        if (!openTarget(env, t, origin)) history.replaceState(null, "", "#/c/" + m[1]);
      } else { trailPushed = false; hideTrail(); }
      return;
    }
    hideTrail();
    currentOrg = null;
    markCurrent();
    if (cm) {
      setView("page");
      navOn("compare");
      rendered = h;
      const want = cm[1].split(",").filter((o) => /^\d{9}$/.test(o)).slice(0, 4);
      await renderCompare(want.length ? want : compare.slice());
      window.scrollTo(0, 0);
      $("#main").focus({ preventScroll: true });
    } else if (h === "/run") {
      setView("page");
      navOn("run");
      rendered = h;
      renderRun();
      window.scrollTo(0, 0);
      $("#main").focus({ preventScroll: true });
    } else {
      setView("home");
      navOn("find");
      if (rendered !== "home") { rendered = "home"; renderHome(); }
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
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([JSON.stringify(env, null, 2)], { type: "application/json" }));
    a.download = org + ".json";
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 500);
  }
  function goFind() { if (narrow()) { listScroll = 0; location.hash = "#/"; } else { const a = $(".rows .rl"); if (a) a.focus(); } }

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
      if (holder && /^#\/compare\//.test(location.hash)) { load(holder.dataset.org).then((env) => openTarget(env, tg.dataset.target, tg)); return; }
      if (currentOrg) {
        if (trailTarget === tg.dataset.target && !trailEl.hidden) { closeTrail(); return; }
        trailPushed = true;
        trailOrigin = tg;
        const base = "#/c/" + currentOrg;
        const next = base + "/t/" + encodeURIComponent(tg.dataset.target);
        if (/\/t\//.test(location.hash)) history.replaceState(null, "", next), route(); else location.hash = next;
      }
      return;
    }
    if (t.closest("[data-close]")) { closeTrail(); return; }
    const j = t.closest("[data-jump]");
    if (j) { ev.preventDefault(); const s = document.getElementById("s-" + j.dataset.jump); if (s) { s.scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "start" }); } return; }
    const cp = t.closest("[data-copy]");
    if (cp) { copy(cp.dataset.copy); return; }
    if (t.closest("[data-copy-link]")) { copy(location.href, "Link copied"); return; }
    const dl = t.closest("[data-download]");
    if (dl) { download(dl.dataset.download); return; }
    if (t.closest("[data-more]")) { more(); return; }
    if (t.closest("[data-reset]") || t.id === "reset") { resetFilters(); $("#q").focus(); return; }
    const chip = t.closest(".chip[data-f]");
    if (chip) { F[chip.dataset.f] = !F[chip.dataset.f]; renderList(); return; }
    const pl = t.closest("[data-place]");
    if (pl) { F.place = F.place === pl.dataset.place ? "" : pl.dataset.place; renderList(); return; }
    const seg = t.closest("[data-ff]");
    if (seg) { resetFilters(); F.fam = seg.dataset.ff; F.st = seg.dataset.fs; renderList(); toast(nf.format(view.length) + " " + (view.length === 1 ? "company" : "companies") + ": " + famShort(F.fam) + " " + STATE[F.st].w.toLowerCase()); goFind(); return; }
    const q = t.closest("[data-quick]");
    if (q) { resetFilters(); F[q.dataset.quick] = true; renderList(); goFind(); return; }
    const tlb = t.closest("button[data-tl]");
    if (tlb) { tl.all = !tl.all; const env = cache[currentOrg]; if (env) $("#tl").innerHTML = timelineHtml(env); }
  });
  document.addEventListener("change", (ev) => {
    const t = ev.target;
    if (t.id === "sort") { F.sort = t.value; renderList(); }
    if (t.matches("input[data-tl='routine']")) { tl.routine = t.checked; const env = cache[currentOrg]; if (env) { $("#tl").innerHTML = timelineHtml(env); const c = $("input[data-tl='routine']"); if (c) c.focus(); } }
  });
  document.addEventListener("input", (ev) => { if (ev.target.id === "cq") pickResults(); });
  let qT = 0;
  $("#q").addEventListener("input", (ev) => {
    clearTimeout(qT);
    const v = ev.target.value;
    qT = setTimeout(() => { F.q = v; renderList(); if (narrow() && document.body.dataset.view !== "home") location.hash = "#/"; }, KS.index.length > 400 ? 50 : 0);
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
    if (ev.target.id === "cq" && ev.key === "Enter") { const b = $("#cres [data-pick]"); if (b) { ev.preventDefault(); togglePick(b.dataset.pick); } return; }
    if (!trailEl.hidden && ev.key === "Escape") { ev.preventDefault(); closeTrail(); return; }
    if (!trailEl.hidden && !docked() && ev.key === "Tab") {
      const f = $$('a[href], button:not([disabled]), summary, input', trailEl).filter((x) => x.offsetParent !== null);
      const first = f[0], last = f[f.length - 1];
      if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
      else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
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
  $$(".chip[data-f]").forEach((c) => { const el = $("span", c); if (el) el.textContent = nf.format(KS.index.filter(TEST[c.dataset.f]).length); });
  $("#sort").value = F.sort;
  renderPlaces();
  renderList();
  renderBadge();
  window.addEventListener("hashchange", route);
  route();
})();
