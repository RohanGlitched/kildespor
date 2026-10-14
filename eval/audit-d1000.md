# Kildespor d1000 precision audit

Independent check of published identity claims in `out/d1000/envelopes.jsonl` (run kildespor-20261014T120105Z), audited 2026-10-14. Every site was fetched again (home page plus contact/about/privacy pages, robots.txt respected, at most 4 requests in flight) and compared with the Brønnøysund record (enheter, roller, underenheter).

## Scope

- **Websites:** all 117 `official_website` claims in scope (discovered_via = name_derived, or identity_proof containing legal_name / registry_declared, or only name_address), plus a random 30 (seed 42) of the other 57. Total 147 websites at 144 companies.
- **Social:** all 232 `social/company_profile` claims of those companies.
- **Contact:** all 487 `contact/email` and `contact/phone` claims of those companies.
- **Jobs:** the run contains only 9 `job_posting` claims (fewer than the 20 requested), so all 9 were checked.

## Summary

| claim type | n | CORRECT | RELATED | WRONG | UNCLEAR |
|---|---|---|---|---|---|
| official_website | 147 | 129 | 13 | 3 | 2 |
| social company_profile | 232 | 175 | 34 | 19 | 4 |
| contact email/phone | 487 | 389 | 69 | 26 | 3 |
| job_posting | 9 | 9 | 0 | 0 | 0 |

All three WRONG_ENTITY websites and 13 RELATED_ENTITY websites were published with relationship `exact`. Under the Signalpost rule, each WRONG_ENTITY item is a material wrong-company publication, and so is any RELATED_ENTITY item published as `exact`.

**Websites by sample bucket**

| group | n | CORRECT | RELATED_ENTITY | WRONG_ENTITY | UNCLEAR |
|---|---|---|---|---|---|
| scope | 117 | 103 | 9 | 3 | 2 |
| random | 30 | 26 | 4 | 0 | 0 |

**Websites by discovery origin (value.discovered_via)**

| group | n | CORRECT | RELATED_ENTITY | WRONG_ENTITY | UNCLEAR |
|---|---|---|---|---|---|
| name_derived | 100 | 96 | 2 | 1 | 1 |
| registry_website | 32 | 21 | 8 | 2 | 1 |
| registry_email | 9 | 7 | 2 | 0 | 0 |
| subunit_email | 6 | 5 | 1 | 0 | 0 |

**Websites by identity proof (value.identity_proof)**

| group | n | CORRECT | RELATED_ENTITY | WRONG_ENTITY | UNCLEAR |
|---|---|---|---|---|---|
| name_address+orgnr | 37 | 37 | 0 | 0 | 0 |
| name_address | 34 | 33 | 1 | 0 | 0 |
| orgnr | 14 | 14 | 0 | 0 | 0 |
| registry_declared | 12 | 2 | 7 | 2 | 1 |
| legal_name | 12 | 9 | 1 | 1 | 1 |
| email+phone | 8 | 5 | 3 | 0 | 0 |
| name_address+orgnr+phone | 6 | 6 | 0 | 0 | 0 |
| name_address+phone | 6 | 6 | 0 | 0 | 0 |
| phone | 4 | 4 | 0 | 0 | 0 |
| email+name_address+phone | 4 | 4 | 0 | 0 | 0 |
| email+name_address+orgnr+phone | 4 | 4 | 0 | 0 | 0 |
| email+name_address | 2 | 1 | 1 | 0 | 0 |
| orgnr+phone | 1 | 1 | 0 | 0 | 0 |
| email+name_address+orgnr | 1 | 1 | 0 | 0 | 0 |
| email+orgnr | 1 | 1 | 0 | 0 | 0 |
| email | 1 | 1 | 0 | 0 | 0 |

The pattern: **orgnr proof was 100% correct.** Every wrong or related match came from `registry_declared` (the register's own hjemmeside, which can point to a housing manager, chain, group or parent), from `legal_name` or `name_address` proofs alone, or from registry or sub-unit e-mail domains confirmed only by a shared phone or e-mail.

## Non-correct websites

| # | orgnr | legal name | published value | origin / proof | verdict | entity it belongs to | evidence seen | rule that would have prevented it |
|---|---|---|---|---|---|---|---|---|
| 1 | 912302792 | SAMEIET GJERDETUNET 1-11 | https://bate.no/ | registry_website / registry_declared | **WRONG_ENTITY** | BATE BOLIGBYGGELAG (952090275), the registered forretningsfører (FFØR) | "Som Bate-medlem får du rabatter, bonus og gode tilbud" - member portal of the housing manager; sameie not named | Before accepting any website for a borettslag/sameie (or any entity with an FFØR role), resolve the domain's own Brreg owner; reject when the domain belongs to the registered forretningsfører/REGN/REVI or a known manager domain (obos.no, bate.no, usbl.no, ...). Registry hjemmeside is not proof for housing co-ops. |
| 2 | 953188619 | AL TÅRNBO NORD BORETTSLAG | https://www.obos.no/ | registry_website / registry_declared | **WRONG_ENTITY** | OBOS (forretningsfører OBOS EIENDOMSFORVALTNING AS 934261585) | "Har du vurdert å bli OBOS-medlem" - national OBOS portal; borettslag not named | Before accepting any website for a borettslag/sameie (or any entity with an FFØR role), resolve the domain's own Brreg owner; reject when the domain belongs to the registered forretningsfører/REGN/REVI or a known manager domain (obos.no, bate.no, usbl.no, ...). Registry hjemmeside is not proof for housing co-ops. |
| 3 | 915903037 | NEMITEK AS | https://nemitek.com/ | name_derived / legal_name | **WRONG_ENTITY** | Unrelated software/game publisher 'Nemitek' (no orgnr, no Norwegian address); the real site nemitek.no (orgnr shown) is published too | "Nemitek — Software with a clear purpose"; legal_name proof came from "upload your game save to Nemitek as part of" | _exact_name_rx compiles with re.I so 'Nemitek as part' matched 'NEMITEK AS'. Match the legal-form suffix case-sensitively (AS/ASA/SA uppercase, or 'As' only before punctuation/end of line). Also: once an orgnr-proven site exists, drop extra name_derived domains that carry only legal_name proof. |
| 4 | 887813752 | BILVAREHUSENE SØR AS | https://bilxtra.no/ | registry_website / registry_declared | **RELATED_ENTITY** | BilXtra chain site; owned by BILXTRA AS (983032133); same hjemmeside also declared by BILVAREHUSENE NOR AS and BILXTRA ORKANGER AS | Chain web shop with "Velg butikk" store picker; no orgnr, address or phone of Bilvarehusene Sør | Reverse-lookup the registry hjemmeside: if Brreg lists the same hjemmeside for another entity (or several), publish only as relationship=group/shared, never exact, unless the site shows this orgnr. |
| 5 | 979488378 | SULLAND LILLEHAMMER AS | https://www.sulland.no/ | registry_website / registry_declared | **RELATED_ENTITY** | Sulland Gruppen AS (dealer group); hjemmeside also declared by SULLAND AMSRUDVEGEN AS | "Nettstedet www.sulland.no blir levert av Sulland Gruppen AS." | Parse operator statements on privacy/terms pages ('levert av', 'drives av', 'behandlingsansvarlig', '©'): if they name a different registered legal name, downgrade to related_entity. Reverse-lookup the registry hjemmeside: if Brreg lists the same hjemmeside for another entity (or several), publish only as relationship=group/shared, never exact, unless the site shows this orgnr. |
| 6 | 965092080 | PAULIG NORWAY AS | https://www.santamariaworld.com/en/select-market/ | registry_website / registry_declared | **RELATED_ENTITY** | Paulig group global brand site (Santa Maria); registry declared /no but the published URL is the global market picker | "Santa Maria World Choose your country Australia België ..." | Keep the declared path (/no); when the final URL is a country selector or a global group domain with no Norwegian orgnr/address, publish as relationship=parent_group. |
| 7 | 940193575 | WÄRTSILÄ NORWAY AS | https://www.wartsila.com/ | registry_website / registry_declared | **RELATED_ENTITY** | Wärtsilä Oyj Abp global parent site (Helsinki) | Contact block: "FI-00180 Helsinki Finland Tel. +358 10 709 0000"; no Wärtsilä Norway orgnr or address | Registry-declared global corporate domain with no Norwegian orgnr/address/phone on site -> relationship=parent_group, not exact. |
| 8 | 916164882 | ASSET BUYOUT PARTNERS INVEST AS | https://abpre.no/ | registry_website / registry_declared | **RELATED_ENTITY** | ASSET BUYOUT PARTNERS AS (915672795), sister/manager company | "Asset Buyout Partners AS, (organization number: 915 672 795) is responsible for the processing" | Extend ORGNR_LABEL_RE to English labels ('organization number', 'organisation no.', 'company no.', 'reg. no.'); the site's foreign orgnr was missed so the other_entity guard never fired. |
| 9 | 995366479 | ABERIA AS | https://www.aberia.no/ | name_derived / legal_name | **RELATED_ENTITY** | Aberia group site; Brreg declares aberia.no for ABERIA UNG AS (984331584); contact address is Aberia Ung's (Moss), not Aberia AS (Oslo) | "Aberia Ung er et landsdekkende, ideelt aksjeselskap"; "Ekholtveien 114, 1526 Moss" | legal_name-only proof ('© Aberia AS') must be rejected when the domain is declared in Brreg by a different entity and the site's address does not match the registry address. Reverse-lookup the registry hjemmeside: if Brreg lists the same hjemmeside for another entity (or several), publish only as relationship=group/shared, never exact, unless the site shows this orgnr. |
| 10 | 930468061 | SÆDALEN IDRETTSPARK AS | https://sedalenil.no/ | registry_website / registry_declared | **RELATED_ENTITY** | SÆDALEN IDRETTSLAG (990283710), the sports club that owns the park company; Brreg lists sedalenil.no for the club | Club site: "Klubben Visjon og verdier Styret og administrasjon Medlemskap og kontingent" | Reverse-lookup the registry hjemmeside: if Brreg lists the same hjemmeside for another entity (or several), publish only as relationship=group/shared, never exact, unless the site shows this orgnr. |
| 11 | 994916009 | NORRØN AS | https://norron.no/ | name_derived / name_address | **RELATED_ENTITY** | NORRØN GRUPPEN AS (997390237) / NORRØN BOLIG AS (830664602); Brreg lists norron.no for Norrøn Gruppen AS | "Norrøn Bolig: Din boligdrøm – vår jobb En del av Norrøn Gruppen"; "Velkommen til Norrøn Bolig!" | name_address proof via group's shared address: when the site's brand is a longer name that exists as its own Brreg entity at the same address (Norrøn Bolig / Norrøn Gruppen), downgrade to related. Reverse-lookup the registry hjemmeside: if Brreg lists the same hjemmeside for another entity (or several), publish only as relationship=group/shared, never exact, unless the site shows this orgnr. |
| 12 | 923804145 | JERNBANEVEIEN EIENDOM AS | https://fredensborgbolig.no/ | registry_website / registry_declared | **RELATED_ENTITY** | FREDENSBORG BOLIG AS (919998296), parent of the property SPV | "Fredensborg Bolig – Vi skaper bedre hjem"; SPV name absent | Registry-declared domain with zero token overlap with the legal name (fredensborgbolig vs Jernbaneveien Eiendom) and no orgnr -> parent_group, not exact. |
| 13 | 992059060 | VINKLGÅRDEN AS | https://vinkl.no/ | registry_website / email+phone | **RELATED_ENTITY** | VINKL AS (920700942), group company and data controller | "hvordan og hvorfor Vinkl AS («Vinkl») samler inn og behandler dine personopplysninger" | Parse operator statements on privacy/terms pages ('levert av', 'drives av', 'behandlingsansvarlig', '©'): if they name a different registered legal name, downgrade to related_entity. |
| 14 | 999292526 | LK EIENDOMSUTVIKLING AS | https://www.lk-arkitekter.no/ | registry_email / email+phone | **RELATED_ENTITY** | ARKITEKT LORENTZ KIELLAND (ENK 923882715), the owner's architect practice | "Arkitekt Lorentz Kielland – Verksted for arkitektur og prosjektutvikling"; LK Eiendomsutvikling not named | registry_email origin with only shared owner phone/e-mail as proof: require the legal name or orgnr on the site; a person's shared mobile is not entity proof. |
| 15 | 980402908 | BUGSERTJENESTE IV AS | https://ostensjo.no/ | subunit_email / email+phone | **RELATED_ENTITY** | ØSTENSJØ REDERI AS (980844072), parent shipowner of the vessel-owning SPV | "Endre joined Østensjø Rederi in 2021"; Bugsertjeneste IV not named | subunit_email / registry_email origin with only group switchboard phone and post@ e-mail: when the legal name is absent, publish as parent_group. |
| 16 | 998680360 | SUNNSAND AS | https://sunnsand.no/ | registry_email / email+name_address | **RELATED_ENTITY** | SUNNHORDLAND SANDBLÅSING AS (936481787), sister company at the same address; Brreg lists www.sunnsand.no for it | "© 2026 Sunnhordland Sandblåsing AS, https://sunnsand.no/. All rights reserved." | If the © or title names a different registered legal name, reject. Reverse-lookup the registry hjemmeside: if Brreg lists the same hjemmeside for another entity (or several), publish only as relationship=group/shared, never exact, unless the site shows this orgnr. |
| 17 | 989041800 | BIBELSKOLEN FJELLHAUG AS | http://fjellhaug.no/ | registry_website / registry_declared | **UNCLEAR** | Root page only advertises Fjellhaug Studentheim housing; school not named (campus domain shared with FJELLHAUG INTERNASJONALE HØGSKOLE AS 914086434) | "kan vi tilby hybler på Fjellhaug Studentheim" | Registry-declared domain whose pages name neither the entity nor its orgnr/phone/address: hold as unconfirmed instead of exact. |
| 18 | 984840551 | UNIVERSI AS | https://universi.no/ | name_derived / legal_name | **UNCLEAR** | Site prints a different orgnr (932 953 520, not in Brreg); DAGL's e-mail on site; Brreg hjemmeside is elektrokatalogen.no | "Universi AS · Org.nr. 932 953 520" | Any orgnr on the site that differs from ours (even one Brreg does not know) should block legal_name-only proof. |

## Non-correct social profiles

| orgnr | legal name | published value | verdict | evidence / reason |
|---|---|---|---|---|
| 828073052 | FORNEBU BILSKADESENTER AS | https://www.linkedin.com/company/enqvist-boligforvaltning | **WRONG** | a different company's LinkedIn (Enqvist Boligforvaltning) left in the template |
| 831712732 | FAKZ AS | https://www.facebook.com/gourmet.import | **WRONG** | client portfolio (Gourmet Import AS) |
| 831712732 | FAKZ AS | https://www.instagram.com/gourmetimportnorge | **WRONG** | client portfolio (Gourmet Import AS) |
| 831712732 | FAKZ AS | https://www.facebook.com/merete.mowinckel | **WRONG** | client portfolio (artist Merete Mowinckel) |
| 831712732 | FAKZ AS | https://www.instagram.com/meretemowinckel | **WRONG** | client portfolio (artist Merete Mowinckel) |
| 831712732 | FAKZ AS | https://www.instagram.com/mart1nthor | **WRONG** | client portfolio (Twitch streamer MartinThor) |
| 831712732 | FAKZ AS | https://www.facebook.com/profile.php?id=61575030142666 | **WRONG** | client portfolio (band Nowhere People) |
| 914876745 | FIDI VIDEO AS | https://www.facebook.com/p | **WRONG** | truncated from facebook.com/p/Sesong-61553316940008 (a café the page recommends) |
| 916164882 | ASSET BUYOUT PARTNERS INVEST AS | https://vimeo.com/privacy | **WRONG** | platform privacy page |
| 923938354 | FLEX1ONE AS | https://www.facebook.com/policies | **WRONG** | platform policy page |
| 925322830 | OTTADALEN ANLEGG AS | https://www.facebook.com/business | **WRONG** | platform page (Meta for Business) |
| 925831611 | SKOVENG TRANSPORT AS | https://www.facebook.com/p | **WRONG** | truncated facebook.com/p/... link |
| 926559443 | BIK SERVICE AS | https://www.facebook.com/pg | **WRONG** | truncated from m.facebook.com/pg/bikservice |
| 931133349 | CLEANBEE AS | https://www.linkedin.com/company/wix-com | **WRONG** | Wix platform's own LinkedIn from the site template |
| 934385128 | TECHSPACE SOLUTIONS AS | https://www.facebook.com/p | **WRONG** | truncated from facebook.com/p/Techspace-Solutions-61579309111363 |
| 953188619 | AL TÅRNBO NORD BORETTSLAG | https://www.facebook.com/obosmedlem | **WRONG** | OBOS (housing manager) |
| 953188619 | AL TÅRNBO NORD BORETTSLAG | https://www.instagram.com/obos | **WRONG** | OBOS |
| 953188619 | AL TÅRNBO NORD BORETTSLAG | https://www.tiktok.com/@obosnorge | **WRONG** | OBOS |
| 953188619 | AL TÅRNBO NORD BORETTSLAG | https://www.linkedin.com/company/obos | **WRONG** | OBOS |
| 851482652 | BRENNES AUTO AS | https://www.facebook.com/brennesautomoss | **RELATED** | sister company Brennes Auto Moss |
| 851482652 | BRENNES AUTO AS | https://www.instagram.com/brennesautomoss | **RELATED** | sister company Brennes Auto Moss |
| 851482652 | BRENNES AUTO AS | https://www.facebook.com/rabekken | **RELATED** | sister company Brennes Auto Fredrikstad (Rabekken) |
| 887813752 | BILVAREHUSENE SØR AS | https://www.facebook.com/BilXtra.no | **RELATED** | profile of the related entity whose site was published |
| 887813752 | BILVAREHUSENE SØR AS | https://www.tiktok.com/@bilxtra.no | **RELATED** | profile of the related entity whose site was published |
| 887813752 | BILVAREHUSENE SØR AS | https://www.instagram.com/bilxtra_no | **RELATED** | profile of the related entity whose site was published |
| 915903037 | NEMITEK AS | https://www.linkedin.com/company/skarland-press-as | **RELATED** | owner Skarland Press AS |
| 916164882 | ASSET BUYOUT PARTNERS INVEST AS | https://www.linkedin.com/company/10462793 | **RELATED** | profile of the related entity whose site was published |
| 923804145 | JERNBANEVEIEN EIENDOM AS | https://www.linkedin.com/company/fredensborg-bolig-as | **RELATED** | profile of the related entity whose site was published |
| 923804145 | JERNBANEVEIEN EIENDOM AS | https://www.facebook.com/fredensborgbolig | **RELATED** | profile of the related entity whose site was published |
| 923804145 | JERNBANEVEIEN EIENDOM AS | https://www.instagram.com/fredensborgbolig | **RELATED** | profile of the related entity whose site was published |
| 930468061 | SÆDALEN IDRETTSPARK AS | https://www.facebook.com/sedalenil | **RELATED** | profile of the related entity whose site was published |
| 930468061 | SÆDALEN IDRETTSPARK AS | https://www.instagram.com/sedalenil | **RELATED** | profile of the related entity whose site was published |
| 940193575 | WÄRTSILÄ NORWAY AS | https://www.facebook.com/wartsila | **RELATED** | profile of the related entity whose site was published |
| 940193575 | WÄRTSILÄ NORWAY AS | https://www.instagram.com/wartsilacorp | **RELATED** | profile of the related entity whose site was published |
| 940193575 | WÄRTSILÄ NORWAY AS | https://www.linkedin.com/company/166989 | **RELATED** | profile of the related entity whose site was published |
| 940193575 | WÄRTSILÄ NORWAY AS | https://x.com/wartsilacorp | **RELATED** | profile of the related entity whose site was published |
| 940193575 | WÄRTSILÄ NORWAY AS | https://www.youtube.com/user/wartsilacorp | **RELATED** | profile of the related entity whose site was published |
| 940193575 | WÄRTSILÄ NORWAY AS | https://www.linkedin.com/company/wartsila | **RELATED** | profile of the related entity whose site was published |
| 979488378 | SULLAND LILLEHAMMER AS | https://www.linkedin.com/company/sulland-gruppen | **RELATED** | profile of the related entity whose site was published |
| 979488378 | SULLAND LILLEHAMMER AS | https://www.instagram.com/sullandgruppen | **RELATED** | profile of the related entity whose site was published |
| 979488378 | SULLAND LILLEHAMMER AS | https://www.facebook.com/SullandGruppen | **RELATED** | profile of the related entity whose site was published |
| 980402908 | BUGSERTJENESTE IV AS | https://www.facebook.com/OstensjoRederi | **RELATED** | profile of the related entity whose site was published |
| 980402908 | BUGSERTJENESTE IV AS | https://www.linkedin.com/company/-stensj-rederi-as | **RELATED** | profile of the related entity whose site was published |
| 980402908 | BUGSERTJENESTE IV AS | https://www.facebook.com/ostensjolife | **RELATED** | profile of the related entity whose site was published |
| 992059060 | VINKLGÅRDEN AS | https://www.linkedin.com/company/vinkl-as | **RELATED** | profile of the related entity whose site was published |
| 992059060 | VINKLGÅRDEN AS | https://www.facebook.com/vinklski | **RELATED** | profile of the related entity whose site was published |
| 992059060 | VINKLGÅRDEN AS | https://www.instagram.com/vinklski | **RELATED** | profile of the related entity whose site was published |
| 994916009 | NORRØN AS | https://www.facebook.com/norronrehabilitering | **RELATED** | profile of the related entity whose site was published |
| 995366479 | ABERIA AS | https://www.facebook.com/aberia.no | **RELATED** | profile of the related entity whose site was published |
| 995366479 | ABERIA AS | https://www.instagram.com/aberianorge | **RELATED** | profile of the related entity whose site was published |
| 995366479 | ABERIA AS | https://www.tiktok.com/@aberianorge | **RELATED** | profile of the related entity whose site was published |
| 995366479 | ABERIA AS | https://www.linkedin.com/company/aberianorge | **RELATED** | profile of the related entity whose site was published |
| 995366479 | ABERIA AS | https://www.youtube.com/channel/UCwLKAi8TDaKGuE-n8PWenXg | **RELATED** | profile of the related entity whose site was published |
| 816689562 | CAMILLA PHOTOGRAPHY AS | https://www.instagram.com/millilill | **UNCLEAR** | personal Instagram of the photographer |
| 926906399 | ASTRIS AS | https://www.instagram.com/eleneriksen | **UNCLEAR** | personal Instagram of the board chair |
| 951065706 | NOVATEK AS | https://www.facebook.com/novatek.n | **UNCLEAR** | site's own href is truncated ('novatek.n') |
| 996808548 | NORSKE BÆRESYSTEMER AS | https://www.facebook.com/Vedalbygg | **UNCLEAR** | site header links a Facebook page named 'Vedalbygg', not Norske Bæresystemer |

Rules: (1) normalise facebook.com/p/<slug> and m.facebook.com/pg/<slug> to the full slug, and never publish a bare `/p` or `/pg`; (2) block platform paths (facebook.com/business, /policies, vimeo.com/privacy, linkedin.com/company/wix-com, squarespace, wordpress); (3) ignore social links inside portfolio/customer/team-member blocks (`wpr-team-member`, 'Våre kunder', 'kundegalleri', 'Se deres nettside') and inside commented-out template HTML; (4) require the handle or page name to share a token with the legal name, brand or domain, otherwise mark it unconfirmed (Vedalbygg, eleneriksen, millilill).

## Non-correct contact claims

| orgnr | legal name | field | published value | verdict | reason |
|---|---|---|---|---|---|
| 820014502 | BELTLAMP AS | phone | 62412424 | **WRONG** | retailer in the store list (Elverum) |
| 820014502 | BELTLAMP AS | phone | 51652299 | **WRONG** | retailer in the store list (Sola Optikeren) |
| 820014502 | BELTLAMP AS | phone | 38158155 | **WRONG** | retailer in the store list (Vennesla) |
| 820014502 | BELTLAMP AS | phone | 56510200 | **WRONG** | retailer in the store list (Voss) |
| 892873232 | WESTERN BULK CHARTERING AS | phone | 97154308 | **WRONG** | Dubai number '+97154 308 0020' truncated to 8 digits |
| 892873232 | WESTERN BULK CHARTERING AS | phone | 22937213 | **WRONG** | analyst at Arctic Securities ASA (another entity) |
| 892873232 | WESTERN BULK CHARTERING AS | phone | 24169188 | **WRONG** | analyst at DNB Markets (another entity) |
| 892873232 | WESTERN BULK CHARTERING AS | phone | 20252025 | **WRONG** | years from an investor-relations table |
| 912302792 | SAMEIET GJERDETUNET 1-11 | email | synnove.ronnestad@bate.no | **WRONG** | from the wrong entity's site |
| 912302792 | SAMEIET GJERDETUNET 1-11 | email | oskar.olsen@bate.no | **WRONG** | from the wrong entity's site |
| 912302792 | SAMEIET GJERDETUNET 1-11 | phone | 97652185 | **WRONG** | from the wrong entity's site |
| 912302792 | SAMEIET GJERDETUNET 1-11 | phone | 41365789 | **WRONG** | from the wrong entity's site |
| 912777944 | SANDHAALAND CAMPING - PANORAMAHYTTENE AS | phone | 47413458 | **WRONG** | '+ 47 41 34 58 32' parsed with the country code; real number is 41345832 |
| 914876745 | FIDI VIDEO AS | email | %20post@fidivideo.no | **WRONG** | malformed (URL-encoded space) duplicate of post@fidivideo.no |
| 915903037 | NEMITEK AS | email | support@nemitek.com | **WRONG** | from the namesake site nemitek.com |
| 922846235 | PROBOTIC AS | phone | 20222021 | **WRONG** | two years from a news timeline ('2022 2021') |
| 922846235 | PROBOTIC AS | phone | 20202019 | **WRONG** | two years from a news timeline ('2020 2019') |
| 923566597 | TRONDHEIM TORG AS | phone | 73890050 | **WRONG** | tenant shop (Telenor-butikken) in the mall |
| 923566597 | TRONDHEIM TORG AS | phone | 92405050 | **WRONG** | tenant shop (Telia) in the mall |
| 931342576 | LUNGESPESIALIST AS | phone | 22396900 | **WRONG** | Datatilsynet's phone from the privacy page |
| 940193575 | WÄRTSILÄ NORWAY AS | phone | 35810709 | **WRONG** | Finnish HQ '+358 10 709 0000' truncated |
| 980402908 | BUGSERTJENESTE IV AS | phone | 21228852 | **WRONG** | Malta number '+356 21 22 8852' (and part of RELATED site) |
| 980402908 | BUGSERTJENESTE IV AS | phone | 99011693 | **WRONG** | Malta mobile '+356 99 01 16 93' |
| 986018166 | ADVOKAT LARS R BERG | phone | 91595320 | **WRONG** | Advokat Geir Myhrvold (983078346) on the shared office site |
| 986018166 | ADVOKAT LARS R BERG | phone | 92254351 | **WRONG** | Advokat Gaute Nilsen AS (920364640) on the shared office site |
| 996808548 | NORSKE BÆRESYSTEMER AS | phone | 47221328 | **WRONG** | '47 22 13 28 80' parsed with the country code; real number 22132880 is also published |
| 851482652 | BRENNES AUTO AS | phone | 69330800 | **RELATED** | Brennes Auto Fredrikstad AS (sister) |
| 851482652 | BRENNES AUTO AS | phone | 69236500 | **RELATED** | Brennes Auto Moss (sister) |
| 887813752 | BILVAREHUSENE SØR AS | email | nettbutikk@bilxtra.no | **RELATED** | from the related entity's site |
| 916164882 | ASSET BUYOUT PARTNERS INVEST AS | email | contact@abpre.no | **RELATED** | from the related entity's site |
| 923804145 | JERNBANEVEIEN EIENDOM AS | email | post@fredensborgbolig.no | **RELATED** | from the related entity's site |
| 923804145 | JERNBANEVEIEN EIENDOM AS | phone | 40022878 | **RELATED** | from the related entity's site |
| 923804145 | JERNBANEVEIEN EIENDOM AS | email | aleksander.stenholen@fredensborgbolig.no | **RELATED** | from the related entity's site |
| 923804145 | JERNBANEVEIEN EIENDOM AS | email | annette.borgersen@fredensborgbolig.no | **RELATED** | from the related entity's site |
| 923804145 | JERNBANEVEIEN EIENDOM AS | email | bjorn-tore.olsen@fredensborgbolig.no | **RELATED** | from the related entity's site |
| 923804145 | JERNBANEVEIEN EIENDOM AS | email | camilla.eriksen@fredensborgbolig.no | **RELATED** | from the related entity's site |
| 923804145 | JERNBANEVEIEN EIENDOM AS | email | carl.fredrik.larsen@fredensborgbolig.no | **RELATED** | from the related entity's site |
| 923804145 | JERNBANEVEIEN EIENDOM AS | email | carl.soderstrom@fredensborgbolig.no | **RELATED** | from the related entity's site |
| 923804145 | JERNBANEVEIEN EIENDOM AS | phone | 45207580 | **RELATED** | from the related entity's site |
| 923804145 | JERNBANEVEIEN EIENDOM AS | phone | 97002687 | **RELATED** | from the related entity's site |
| 923804145 | JERNBANEVEIEN EIENDOM AS | phone | 41497006 | **RELATED** | from the related entity's site |
| 923804145 | JERNBANEVEIEN EIENDOM AS | phone | 97158758 | **RELATED** | from the related entity's site |
| 979488378 | SULLAND LILLEHAMMER AS | email | post@sulland.no | **RELATED** | from the related entity's site |
| 979488378 | SULLAND LILLEHAMMER AS | phone | 62519730 | **RELATED** | from the related entity's site |
| 979488378 | SULLAND LILLEHAMMER AS | email | innsyn@sulland.no | **RELATED** | from the related entity's site |
| 979488378 | SULLAND LILLEHAMMER AS | email | personvern@sulland.no | **RELATED** | from the related entity's site |
| 979488378 | SULLAND LILLEHAMMER AS | email | kjersti.berg@sulland.no | **RELATED** | from the related entity's site |
| 979488378 | SULLAND LILLEHAMMER AS | phone | 99739944 | **RELATED** | from the related entity's site |
| 980402908 | BUGSERTJENESTE IV AS | email | post@ostensjo.no | **RELATED** | from the related entity's site |
| 980402908 | BUGSERTJENESTE IV AS | phone | 52704545 | **RELATED** | from the related entity's site |
| 980402908 | BUGSERTJENESTE IV AS | email | bt.malta@ostensjo.no | **RELATED** | from the related entity's site |
| 980402908 | BUGSERTJENESTE IV AS | email | chartering@ostensjo.no | **RELATED** | from the related entity's site |
| 980402908 | BUGSERTJENESTE IV AS | phone | 90873689 | **RELATED** | from the related entity's site |
| 992059060 | VINKLGÅRDEN AS | email | epr@vinkl.no | **RELATED** | from the related entity's site |
| 992059060 | VINKLGÅRDEN AS | phone | 91788360 | **RELATED** | from the related entity's site |
| 992059060 | VINKLGÅRDEN AS | email | ep@vinkl.no | **RELATED** | from the related entity's site |
| 994916009 | NORRØN AS | email | tor.inge@norron.no | **RELATED** | from the related entity's site |
| 994916009 | NORRØN AS | email | dag.einar@norron.no | **RELATED** | from the related entity's site |
| 994916009 | NORRØN AS | email | post@norron.no | **RELATED** | from the related entity's site |
| 994916009 | NORRØN AS | phone | 90772650 | **RELATED** | from the related entity's site |
| 994916009 | NORRØN AS | phone | 51496500 | **RELATED** | from the related entity's site |
| 994916009 | NORRØN AS | phone | 93866130 | **RELATED** | from the related entity's site |
| 994916009 | NORRØN AS | email | hilde@norron.no | **RELATED** | from the related entity's site |
| 994916009 | NORRØN AS | email | bent.magne@norron.no | **RELATED** | from the related entity's site |
| 994916009 | NORRØN AS | email | christian@norron.no | **RELATED** | from the related entity's site |
| 994916009 | NORRØN AS | email | sturla@norron.no | **RELATED** | from the related entity's site |
| 994916009 | NORRØN AS | phone | 41412186 | **RELATED** | from the related entity's site |
| 994916009 | NORRØN AS | phone | 93278060 | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | phone | 45217339 | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | phone | 98243042 | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | phone | 40002060 | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | phone | 40000110 | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | email | post@aberia.no | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | email | trine.bakkeli@aberia.no | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | email | lene.lind@aberia.no | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | email | jonas@aberia.no | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | email | kristin.granne@aberia.no | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | email | hanne.stolevik@aberia.no | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | phone | 48228800 | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | phone | 91101814 | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | phone | 97958692 | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | phone | 99120964 | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | email | rekruttering@aberia.no | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | email | vibeke.fritzon@aberia.no | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | email | bjornar.aabel@aberia.no | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | email | stine-marie.lind@aberia.no | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | email | daniela.nicu@aberia.no | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | phone | 40003315 | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | phone | 93068196 | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | phone | 45488499 | **RELATED** | from the related entity's site |
| 995366479 | ABERIA AS | phone | 93226453 | **RELATED** | from the related entity's site |
| 998680360 | SUNNSAND AS | email | kjetil@sunnsand.no | **RELATED** | from the related entity's site |
| 998680360 | SUNNSAND AS | phone | 53457790 | **RELATED** | from the related entity's site |
| 999292526 | LK EIENDOMSUTVIKLING AS | email | lorentz@lk-arkitekter.no | **RELATED** | from the related entity's site |
| 999292526 | LK EIENDOMSUTVIKLING AS | phone | 41471817 | **RELATED** | from the related entity's site |
| 816717132 | ROMSDAL INNOVASJON AS | phone | 98883816 | **UNCLEAR** | daily manager of Nordveggen AS (the company's secretariat) |
| 984840551 | UNIVERSI AS | email | post@universi.no | **UNCLEAR** | from an unclear site |
| 997688821 | HAMMERFESTINGEN AS | phone | 32277045 | **UNCLEAR** | shared customer-service number (32 area code, not Hammerfest) |

Rules for contact claims: (1) PHONE_RE accepts any 8 digits after a non-+47 country code ('+971', '+358', '+356'). Reject a match when a `+` and a country code other than 47 come right before it, or when more digits follow after a space. (2) Strip a bare leading '47 ' only when 8 digits follow, and never keep '47'+6 digits. (3) Reject 8-digit strings that are two years (19xx/20xx 19xx/20xx). (4) Drop numbers and e-mails found in blocks that name another legal name or orgnr (shared office sites, store lists, IR analyst lists, mall tenant lists), and drop regulator contacts on privacy pages (Datatilsynet 22 39 69 00, postkasse@datatilsynet.no). (5) URL-decode and validate e-mails (`%20post@...`). (6) Contacts inherit the site verdict, so a related or wrong site leaks the other entity's staff into the profile (Aberia: 23, Norrøn: 12, Fredensborg: 12).

## Job postings (all 9 in the run)

| orgnr | legal name | posting | verdict | check |
|---|---|---|---|---|
| 934039254 | FINNFJORD AS | Prosessoperatør Produksjon (NAV 80c0b8a1) | CORRECT | feed employer 971686561 is a registered sub-unit |
| 928775305 | NORDLO VENNESLA AS | NAV ad, employer Mentor Partner AS | CORRECT | feed employer 972021059 is a registered sub-unit (sub-unit name differs from the parent) |
| 996963497 | LÆRINGSVERKSTEDET LILLEHAMMER IDRETTSBARNEHAGE AS | NAV ad | CORRECT | feed employer 997010329 is a registered sub-unit |
| 919789174 | MEDICALIS TØNSBERG AS | Helsesekretær 50% (NAV) | CORRECT | feed employer 919895489 is a registered sub-unit |
| 919789174 | MEDICALIS TØNSBERG AS | Helsesekretær 80% (NAV) | CORRECT | feed employer 919895489 is a registered sub-unit |
| 992797738 | ARKTIQ ASSURANSE AS | NAV ad | CORRECT | feed employer 992808578 is a registered sub-unit |
| 920322433 | OPCOM AS | 3 JobPosting entries on opcom.no/karriere | CORRECT | company site, orgnr 920 322 433 shown on the site |

## Top rule changes (in order of impact)

1. **Housing co-ops and the forretningsfører.** For BRL, ESEK and sameie entities, or any entity with an FFØR role, never accept the registry hjemmeside or a manager domain (obos.no, bate.no, usbl.no, boligbyggelag sites) as the official website unless the page names the co-op. This would have prevented 2 of the 3 WRONG_ENTITY items.
2. **Reverse hjemmeside lookup.** Query Brreg for other entities that declare the same hjemmeside or e-mail domain. If one exists, or the domain's ©, operator or data-controller line names another legal name, publish as `related_entity` (parent, group, chain, sister) and not `exact`. This covers 9 of the 13 RELATED items (BilXtra, Sulland, Aberia, Sædalen, Norrøn, Vinkl, Sunnsand, Asset Buyout, Fredensborg).
3. **English orgnr labels.** Extend `ORGNR_LABEL_RE` with 'organization number', 'organisation no.', 'company (reg.) no.'. The existing `other_entity` guard missed abpre.no ('organization number: 915 672 795') and westernbulk.com ('organisation no. 932 184 265').
4. **Case-sensitive legal form.** `_exact_name_rx` compiles with `re.I`, so the English word 'as' satisfied 'NEMITEK AS'. Make the legal-form suffix case-sensitive. Treat `legal_name` alone as weak: require a postcode or town from the register, and drop it when another orgnr-proven site already exists for the company.
5. **Group and global domains.** When a registry-declared or e-mail-derived domain shares no token with the legal name and the site has no orgnr, address or registered phone of the entity (wartsila.com, santamariaworld.com, fredensborgbolig.no, ostensjo.no, lk-arkitekter.no), publish it as `parent_group`, or hold it.
6. **Phone and social parsing hygiene.** Fix foreign-prefix truncation, the '47' prefix, year pairs, and regulator, tenant, retailer and analyst numbers. Fix truncated facebook `/p` and `/pg` links. Block platform paths and portfolio blocks. Together these produce 21 of the 26 WRONG contact claims and 15 of the WRONG social claims.
