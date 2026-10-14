# Kildespor d1000c precision audit

Independent re-check of identity claims in `out/d1000c/envelopes.jsonl`, audited 2026-10-14 after the rule tightening that followed `audit-d1000.md`. Each website was fetched again (home page plus up to five contact/about/privacy/terms pages, normal browser user agent, robots.txt respected, at most 4 requests in flight) and compared with the Brreg record (`enheter`, `/roller`, `underenheter`). Other organisation numbers found on a site were resolved in Brreg, and brand stems were name-searched in Brreg to find sister and parent entities.

## Scope

- **Websites:** all 87 `official_website` claims whose identity_proof has no `orgnr`, plus a random 15 (seed 11) of the 77 that do. Total 102 websites at 102 companies. Every claim in the run is published with relationship `exact`.
- **Social:** all 143 `social/company_profile` claims of those companies.
- **Contact:** all 256 `contact/email` and `contact/phone` claims of those companies.

## Summary

| claim type | n | CORRECT | RELATED | WRONG | UNCLEAR |
|---|---|---|---|---|---|
| official_website | 102 | 90 | 9 | 1 | 2 |
| social company_profile | 143 | 112 | 19 | 2 | 10 |
| contact email | 146 | 116 | 27 | 1 | 2 |
| contact phone | 110 | 93 | 9 | 4 | 4 |

**Material wrong-company publications remain.** One WRONG_ENTITY website (a housing manager's site published for a sameie) and 9 RELATED_ENTITY websites, all published as `exact`. Under the Signalpost rule each one blocks qualification. Of the previous audit's 16 WRONG/RELATED websites, 9 are gone and 7 are still published. 5 of those 7 are still RELATED, and 2 (Paulig, Aberia) are now judged CORRECT. The other 5 WRONG/RELATED sites are new: they are in companies the previous sample did not cover.

**Websites by sample bucket**

| group | n | CORRECT | RELATED_ENTITY | WRONG_ENTITY | UNCLEAR |
|---|---|---|---|---|---|
| scope | 87 | 75 | 9 | 1 | 2 |
| random | 15 | 15 | 0 | 0 | 0 |

**Websites by discovery origin (value.discovered_via)**

| group | n | CORRECT | RELATED_ENTITY | WRONG_ENTITY | UNCLEAR |
|---|---|---|---|---|---|
| name_derived | 61 | 57 | 2 | 0 | 2 |
| registry_website | 24 | 19 | 4 | 1 | 0 |
| registry_email | 10 | 8 | 2 | 0 | 0 |
| subunit_email | 6 | 5 | 1 | 0 | 0 |
| subunit_website | 1 | 1 | 0 | 0 | 0 |

**Websites by identity proof (value.identity_proof)**

| group | n | CORRECT | RELATED_ENTITY | WRONG_ENTITY | UNCLEAR |
|---|---|---|---|---|---|
| name_address | 33 | 31 | 2 | 0 | 0 |
| email+phone | 11 | 6 | 4 | 1 | 0 |
| phone | 10 | 7 | 2 | 0 | 1 |
| role_holder_and_name | 10 | 8 | 1 | 0 | 1 |
| name_address+phone | 7 | 7 | 0 | 0 | 0 |
| name_address+orgnr | 6 | 6 | 0 | 0 | 0 |
| email+name_address+phone | 5 | 5 | 0 | 0 | 0 |
| legal_name | 5 | 5 | 0 | 0 | 0 |
| name_address+orgnr+phone | 5 | 5 | 0 | 0 | 0 |
| email | 3 | 3 | 0 | 0 | 0 |
| orgnr | 3 | 3 | 0 | 0 | 0 |
| legal_name_town | 2 | 2 | 0 | 0 | 0 |
| email+name_address | 1 | 1 | 0 | 0 | 0 |
| email+orgnr+phone | 1 | 1 | 0 | 0 | 0 |

Pattern: **every orgnr-proven site was correct again (15/15).** All 12 non-correct sites came from proofs that never tie the page to this legal entity: phone or e-mail alone (a group switchboard, a person's mobile, a manager's number), `role_holder_and_name`, or `name_address` through a shared group address. In 6 of the 10 WRONG/RELATED cases the site itself said who runs it, in a ©, 'drevet av' or behandlingsansvarlig line naming another organisation, and the pipeline does not read those lines yet.

## Non-correct websites

| # | orgnr | legal name | published value | origin / proof | verdict | entity it belongs to | evidence (≤20 words) | rule change that prevents it |
|---|---|---|---|---|---|---|---|---|
| 1 | 993034231 | SAMEIET ECKERSBERGSGATE 51 | https://www.skeiendom.no | registry_website / email+phone | **WRONG_ENTITY** | SK EIENDOM AS (981135792), the registered forretningsfører | "SK Eiendom AS Vi er et autorisert regnskapsførerselskap som har spesialisert seg på forvaltning av eiendommer for andre" | For BRL/ESEK/sameie (or any FFØR role), reject a site whose title, © or contact block names a role-holder entity (FFØR/REGN/REVI legal name), not just a fixed manager-domain list. |
| 2 | 989747568 | TRAV 24 AS | https://trav24.no/ | registry_website / phone | **RELATED_ENTITY** | HESTESPORTMEDIER AS (821134072), sister company (same DAGL, LEDE and c/o address) | "Disse vilkårene gjelder mellom deg og Hestesportmedier AS (Org. nr. 821 134 072 MVA)" | Fetch kjøps-/abonnementsvilkår pages too and run the other-orgnr guard on them; Parse ©, 'drevet av', 'behandlingsansvarlig/datakontrollør' and terms pages; if they name any organisation other than the legal name (registered or a 'Gruppen' brand), publish as related, never exact. |
| 3 | 992059060 | VINKLGÅRDEN AS | https://vinkl.no/ | registry_website / email+phone | **RELATED_ENTITY** | VINKL AS (920700942), group company | "Vinkl, ved virksomhetens øverste leder, er behandlingsansvarlig for opplysninger som samles inn" | Brreg name search on the domain/brand stem: if another entity with that stem declares the same hjemmeside, shares the phone, or the site's brand equals that entity's name, publish as group/related. Parse ©, 'drevet av', 'behandlingsansvarlig/datakontrollør' and terms pages; if they name any organisation other than the legal name (registered or a 'Gruppen' brand), publish as related, never exact. |
| 4 | 927056712 | SKULLERUDBYEN AS | https://www.skullerudbyen.no/ | name_derived / name_address | **RELATED_ENTITY** | Opsahl Gruppen (developer group of the project SPV) | "nettsiden skullerudbyen.no, drevet av Opsahl Gruppen. Opsahl gruppen står som ansvarlig datakontrollør" | Parse ©, 'drevet av', 'behandlingsansvarlig/datakontrollør' and terms pages; if they name any organisation other than the legal name (registered or a 'Gruppen' brand), publish as related, never exact. |
| 5 | 993345911 | KLAVENESS FINANS AS | https://www.klaveness.com/ | registry_website / phone | **RELATED_ENTITY** | Torvald Klaveness group (hjemmeside also declared by REDERIAKSJESELSKAPET TORVALD KLAVENESS 932578247, KLAVENESS AS 997553667, AS KLAVENESS CHARTERING 913419472) | "© Torvald Klaveness 2024"; Klaveness Finans not named anywhere | Brreg name search on the domain/brand stem: if another entity with that stem declares the same hjemmeside, shares the phone, or the site's brand equals that entity's name, publish as group/related. Also: legal-name token 'Finans' absent. |
| 6 | 980402908 | BUGSERTJENESTE IV AS | https://ostensjo.no/ | subunit_email / email+phone | **RELATED_ENTITY** | ØSTENSJØ REDERI AS (980844072), parent shipowner | "Sonja has been a part of Østensjø Rederi since spring of 2014"; Bugsertjeneste IV not named | registry_email/subunit_email/registry_website with only phone/e-mail proof: require the legal name (or orgnr) on the site; a group switchboard or a person's mobile is not entity proof. |
| 7 | 917383545 | WULLUM HUS AS | https://wullumeiendom.no/ | registry_email / email+phone | **RELATED_ENTITY** | WULLUM EIENDOM AS (818807562), group operator; site lists 15 group companies | "Wullum Eiendom AS er behandlingsansvarlig for de personopplysningene som samles inn via nettsiden" | Parse ©, 'drevet av', 'behandlingsansvarlig/datakontrollør' and terms pages; if they name any organisation other than the legal name (registered or a 'Gruppen' brand), publish as related, never exact. (Lower severity: the invoice page lists Wullum Hus AS with its orgnr.) |
| 8 | 930468061 | SÆDALEN IDRETTSPARK AS | https://sedalenil.no/ | registry_website / role_holder_and_name | **RELATED_ENTITY** | SÆDALEN IDRETTSLAG (990283710), the owning sports club | "Sædalen IL er behandlingsansvarlig for den behandling av personopplysninger"; "Copyright Sædalen IL 2019" | role_holder_and_name must not override a ©/controller line naming another entity; Parse ©, 'drevet av', 'behandlingsansvarlig/datakontrollør' and terms pages; if they name any organisation other than the legal name (registered or a 'Gruppen' brand), publish as related, never exact. |
| 9 | 999292526 | LK EIENDOMSUTVIKLING AS | https://www.lk-arkitekter.no/ | registry_email / email+phone | **RELATED_ENTITY** | ARKITEKT LORENTZ KIELLAND (ENK 923882715), the owner's architect practice | "©2026 Arkitekt Lorentz Kielland"; LK Eiendomsutvikling not named | registry_email/subunit_email/registry_website with only phone/e-mail proof: require the legal name (or orgnr) on the site; a group switchboard or a person's mobile is not entity proof. |
| 10 | 994916009 | NORRØN AS | https://norron.no/ | name_derived / name_address | **RELATED_ENTITY** | NORRØN BOLIG AS (830664602) / Norrøn Gruppen | "© Norrøn Bolig AS"; "En del av Norrøn Gruppen" | name_address via a shared group address is not enough when © names a different registered legal name; Parse ©, 'drevet av', 'behandlingsansvarlig/datakontrollør' and terms pages; if they name any organisation other than the legal name (registered or a 'Gruppen' brand), publish as related, never exact. |
| 11 | 982100208 | VALLHALL FOTBALLHALL DRIFT AS | https://vallhall.no/ | name_derived / phone | **UNCLEAR** | Phone 23 24 78 40 is also registered for sister VALLHALL FOTBALLHALL AS (978703798); site names no legal entity | "Vallhall Arena – Oslo's største innendørs arena Kontakt +47 23 24 78 40" | Brreg name search on the domain/brand stem: if another entity with that stem declares the same hjemmeside, shares the phone, or the site's brand equals that entity's name, publish as group/related. Phone-only proof must be unique to the entity. |
| 12 | 984840551 | UNIVERSI AS | https://universi.no/ | name_derived / role_holder_and_name | **UNCLEAR** | Site prints an orgnr that fails the mod-11 check and is not in Brreg; Brreg hjemmeside is elektrokatalogen.no | "Universi AS · Org.nr. 932 953 520" | Any orgnr printed beside the legal name that differs from ours (valid or not) blocks name-only or role-holder proof; hold as unconfirmed. |

Correct, with notes:

- 995366479 ABERIA AS: Previous audit RELATED; now judged CORRECT: privacy page "Virksomhetens navn: Aberia AS" and "© Aberia AS" (group site run by this entity, Moss address).
- 965092080 PAULIG NORWAY AS: Previous audit RELATED (global selector); the published URL is now /no, whose footer reads "Paulig Norway AS ∙ Nils Hansens vei 13 ∙ 0667 Oslo ∙ Tel: 67555280".
- 915871372 RING AUTO SERVICE AS: Site returns 403 to scripted clients; a second fetch shows "Ring Auto Service", phone 32 17 98 80, 3511 Hønefoss.

## Previous audit websites: still published?

| orgnr | legal name | previous website | previous verdict | d1000c status |
|---|---|---|---|---|
| 912302792 | SAMEIET GJERDETUNET 1-11 | bate.no | WRONG | removed (no website published) |
| 953188619 | AL TÅRNBO NORD BORETTSLAG | obos.no | WRONG | removed |
| 915903037 | NEMITEK AS | nemitek.com | WRONG | removed; only nemitek.no (orgnr-proven, CORRECT) remains |
| 887813752 | BILVAREHUSENE SØR AS | bilxtra.no | RELATED | removed |
| 979488378 | SULLAND LILLEHAMMER AS | sulland.no | RELATED | removed |
| 965092080 | PAULIG NORWAY AS | santamariaworld.com/en/select-market/ | RELATED | **still published**, now as santamariaworld.com/no/. The /no footer names Paulig Norway AS with its address and phone, so CORRECT now |
| 940193575 | WÄRTSILÄ NORWAY AS | wartsila.com | RELATED | removed |
| 916164882 | ASSET BUYOUT PARTNERS INVEST AS | abpre.no | RELATED | removed |
| 995366479 | ABERIA AS | aberia.no | RELATED | **still published** (legal_name proof). Re-judged CORRECT: the privacy page names Aberia AS as the business |
| 930468061 | SÆDALEN IDRETTSPARK AS | sedalenil.no | RELATED | **still published** (proof changed to role_holder_and_name): still RELATED |
| 994916009 | NORRØN AS | norron.no | RELATED | **still published** (name_address): still RELATED |
| 923804145 | JERNBANEVEIEN EIENDOM AS | fredensborgbolig.no | RELATED | removed |
| 992059060 | VINKLGÅRDEN AS | vinkl.no | RELATED | **still published** (email+phone): still RELATED |
| 999292526 | LK EIENDOMSUTVIKLING AS | lk-arkitekter.no | RELATED | **still published** (email+phone): still RELATED |
| 980402908 | BUGSERTJENESTE IV AS | ostensjo.no | RELATED | **still published** (email+phone): still RELATED |
| 998680360 | SUNNSAND AS | sunnsand.no | RELATED | removed |
| 989041800 | BIBELSKOLEN FJELLHAUG AS | fjellhaug.no | UNCLEAR | removed |
| 984840551 | UNIVERSI AS | universi.no | UNCLEAR | **still published** (role_holder_and_name): still UNCLEAR |

From the previous social list, these are still published unchanged: the Enqvist LinkedIn on Fornebu Bilskadesenter (WRONG), `novatek.n`, `millilill` and `Vedalbygg` (now RELATED, because norbs.no says it is part of the Vedal group). The truncated `/p` and `/pg` Facebook links and the platform paths are gone. All 26 previous WRONG contact patterns are gone (years, the bare 47 prefix, +971/+358/+356 prefixes, retailer and tenant lists, Datatilsynet).

## Non-correct social profiles

| orgnr | legal name | published value | verdict | evidence / reason | rule change |
|---|---|---|---|---|---|
| 828073052 | FORNEBU BILSKADESENTER AS | https://www.linkedin.com/company/enqvist-boligforvaltning | **WRONG** | still published: JSON-LD sameAs of the web-agency template (Enqvist Boligforvaltning) | Drop JSON-LD sameAs whose handle shares no token with legal name, brand or domain. |
| 991319727 | AMUNDRØD STENINDUSTRI AS | https://www.instagram.com/hmgphotography | **WRONG** | photographer credit, not the company | Ignore links inside photo credits ("Foto:", "photography") and require a token overlap. |
| 917383545 | WULLUM HUS AS | https://www.facebook.com/profile.php?id=100094312151848 | **RELATED** | profile of the group site | Inherits site verdict. |
| 926956531 | AIRIUS NORGE AS | https://www.youtube.com/@AiriusEuropeLtd | **RELATED** | manufacturer Airius Europe Ltd (UK) | A handle naming a different legal form/entity (Ltd, Europe) is related, not exact. |
| 927056712 | SKULLERUDBYEN AS | https://www.instagram.com/skullerudbyen | **RELATED** | project profile of the Opsahl Gruppen site | Inherits site verdict. |
| 927056712 | SKULLERUDBYEN AS | https://www.instagram.com/skullerudbyen_ | **RELATED** | project profile of the Opsahl Gruppen site | Inherits site verdict. |
| 927056712 | SKULLERUDBYEN AS | https://www.facebook.com/people/Skullerud/61568067537204 | **RELATED** | project profile of the Opsahl Gruppen site | Inherits site verdict. |
| 930468061 | SÆDALEN IDRETTSPARK AS | https://www.facebook.com/sedalenil | **RELATED** | sports club Sædalen IL | Inherits site verdict. |
| 930468061 | SÆDALEN IDRETTSPARK AS | https://www.instagram.com/sedalenil | **RELATED** | sports club Sædalen IL | Inherits site verdict. |
| 980402908 | BUGSERTJENESTE IV AS | https://www.facebook.com/OstensjoRederi | **RELATED** | parent Østensjø Rederi | Inherits site verdict. |
| 980402908 | BUGSERTJENESTE IV AS | https://www.facebook.com/ostensjolife | **RELATED** | parent Østensjø Rederi | Inherits site verdict. |
| 980402908 | BUGSERTJENESTE IV AS | https://www.linkedin.com/company/-stensj-rederi-as | **RELATED** | parent Østensjø Rederi | Inherits site verdict. |
| 989747568 | TRAV 24 AS | https://www.facebook.com/trav24.no | **RELATED** | paper operated by Hestesportmedier AS | Inherits site verdict. |
| 989747568 | TRAV 24 AS | https://x.com/Trav24_no | **RELATED** | paper operated by Hestesportmedier AS | Inherits site verdict. |
| 992059060 | VINKLGÅRDEN AS | https://www.linkedin.com/company/vinkl-as | **RELATED** | Vinkl AS | Inherits site verdict. |
| 992059060 | VINKLGÅRDEN AS | https://www.facebook.com/vinklski | **RELATED** | Vinkl | Inherits site verdict. |
| 992059060 | VINKLGÅRDEN AS | https://www.instagram.com/vinklski | **RELATED** | Vinkl | Inherits site verdict. |
| 993345911 | KLAVENESS FINANS AS | https://www.linkedin.com/company/torvald-klaveness | **RELATED** | Torvald Klaveness group | Inherits site verdict. |
| 994916009 | NORRØN AS | https://www.facebook.com/norronrehabilitering | **RELATED** | sister NORRØN REHABILITERING AS (816529522) | Handle equal to another Brreg entity name -> related. |
| 996239721 | MILEPEL CAMPUS AS | https://www.facebook.com/milepel | **RELATED** | MILEPEL AS (993334073), separate Bergen entity | Handle equal to another Brreg entity name -> related. |
| 996808548 | NORSKE BÆRESYSTEMER AS | https://www.facebook.com/Vedalbygg | **RELATED** | parent Vedal-konsernet ("en del av Vedal-konsernet") | Handle equal to the parent named in "en del av" -> related. |
| 816689562 | CAMILLA PHOTOGRAPHY AS | https://www.instagram.com/millilill | **UNCLEAR** | personal Instagram (unchanged from previous audit) | Require token overlap or mark unconfirmed. |
| 925098787 | DIAGNOSTRIX AS | https://www.facebook.com/EndimetrixNo | **UNCLEAR** | 'Endimetrix' appears nowhere on the site or in Brreg | Require token overlap or mark unconfirmed. |
| 925098787 | DIAGNOSTRIX AS | https://www.instagram.com/endimetrix | **UNCLEAR** | 'Endimetrix' appears nowhere on the site or in Brreg | Require token overlap or mark unconfirmed. |
| 933682943 | SCOPE FILM AS | https://www.instagram.com/andresbratterud | **UNCLEAR** | owner's personal profile | Require token overlap or mark unconfirmed. |
| 933682943 | SCOPE FILM AS | https://www.facebook.com/Andressplease | **UNCLEAR** | owner's personal profile | Require token overlap or mark unconfirmed. |
| 933682943 | SCOPE FILM AS | https://vimeo.com/user2745471 | **UNCLEAR** | numeric personal Vimeo user | Require token overlap or mark unconfirmed. |
| 951065706 | NOVATEK AS | https://www.facebook.com/novatek.n | **UNCLEAR** | site's own href is truncated (unchanged) | Drop handles that are a strict prefix of the domain stem. |
| 965092080 | PAULIG NORWAY AS | https://www.linkedin.com/company/715845 | **UNCLEAR** | numeric LinkedIn id on a Paulig brand site; owner unverified | Numeric ids need a name check. |
| 982100208 | VALLHALL FOTBALLHALL DRIFT AS | https://www.facebook.com/Vallhall-Arena-282370260786 | **UNCLEAR** | inherits unclear site | Inherits site verdict. |
| 997750233 | KJØKKENHUSET BODØ AS | https://www.facebook.com/kjokkenhuset.no | **UNCLEAR** | handle of the Kjøkkenhuset name shared by 4 other Brreg entities; site calls itself Bodø Interiør | Require token overlap with the site brand. |

## Non-correct contact claims

Contacts on a RELATED site are marked RELATED. The exception is a phone that is also this entity's Brreg phone: those are CORRECT (Wullum 47025847, Klaveness 22526000, Vinklgården 91788360, LK 41471817, Trav 24 90193048, Vallhall 23247840).

| orgnr | legal name | field | published value | verdict | reason |
|---|---|---|---|---|---|
| 925322830 | OTTADALEN ANLEGG AS | phone | 61238995 | **WRONG** | a fax number ('Fax. 61 23 89 95') published as phone |
| 932089114 | NORGES GEOTEKNISKE INSTITUTT AS | phone | 65596499 | **WRONG** | Perth office '+61 8 6559 6499' truncated to 8 digits |
| 943310459 | DIA-TEAM AS | phone | 92116316 | **WRONG** | Dia-Team AB Sweden '+46 (0)921 16316' truncated |
| 993034231 | SAMEIET ECKERSBERGSGATE 51 | email | post@skeiendom.no | **WRONG** | housing manager SK Eiendom AS |
| 993034231 | SAMEIET ECKERSBERGSGATE 51 | phone | 23271133 | **WRONG** | SK Eiendom AS switchboard (also in Brreg as the sameie's phone, but it is the manager's) |
| 917383545 | WULLUM HUS AS | email | anders.solem@wullumeiendom.no | **RELATED** | from the Wullum Eiendom group site |
| 917383545 | WULLUM HUS AS | email | trond@wullumeiendom.no | **RELATED** | from the Wullum Eiendom group site |
| 917383545 | WULLUM HUS AS | email | henrik@wullumeiendom.no | **RELATED** | from the Wullum Eiendom group site |
| 917383545 | WULLUM HUS AS | phone | 47901109 | **RELATED** | from the Wullum Eiendom group site |
| 917383545 | WULLUM HUS AS | phone | 97426711 | **RELATED** | from the Wullum Eiendom group site |
| 927056712 | SKULLERUDBYEN AS | email | hei@skullerudbyen.no | **RELATED** | Opsahl Gruppen project contact |
| 927056712 | SKULLERUDBYEN AS | phone | 97149352 | **RELATED** | 'Kristian Kinn Daglig leder kristian@aoe.no' (not a Brreg role holder) |
| 943310459 | DIA-TEAM AS | email | post-se@diateam.no | **RELATED** | Swedish sister Dia-Team AB |
| 980402908 | BUGSERTJENESTE IV AS | email | post@ostensjo.no | **RELATED** | from the Østensjø Rederi site |
| 980402908 | BUGSERTJENESTE IV AS | phone | 52704545 | **RELATED** | from the Østensjø Rederi site |
| 980402908 | BUGSERTJENESTE IV AS | email | bt.malta@ostensjo.no | **RELATED** | from the Østensjø Rederi site |
| 980402908 | BUGSERTJENESTE IV AS | email | chartering@ostensjo.no | **RELATED** | from the Østensjø Rederi site |
| 980402908 | BUGSERTJENESTE IV AS | phone | 90873689 | **RELATED** | from the Østensjø Rederi site |
| 989747568 | TRAV 24 AS | phone | 91385977 | **RELATED** | tips line of the Hestesportmedier-run paper |
| 992059060 | VINKLGÅRDEN AS | email | epr@vinkl.no | **RELATED** | from the Vinkl site |
| 992059060 | VINKLGÅRDEN AS | email | ep@vinkl.no | **RELATED** | from the Vinkl site |
| 993345911 | KLAVENESS FINANS AS | email | administration@klaveness.com | **RELATED** | from the Torvald Klaveness group site |
| 993345911 | KLAVENESS FINANS AS | email | admin-dubai@klaveness.com | **RELATED** | from the Torvald Klaveness group site |
| 993345911 | KLAVENESS FINANS AS | email | admin-mnl@klaveness.com | **RELATED** | from the Torvald Klaveness group site |
| 993345911 | KLAVENESS FINANS AS | email | klavenessprivacy@klaveness.com | **RELATED** | from the Torvald Klaveness group site |
| 993345911 | KLAVENESS FINANS AS | email | legal@klaveness.com | **RELATED** | from the Torvald Klaveness group site |
| 993345911 | KLAVENESS FINANS AS | email | communications@klaveness.com | **RELATED** | from the Torvald Klaveness group site |
| 993345911 | KLAVENESS FINANS AS | email | cabu@klaveness.com | **RELATED** | from the Torvald Klaveness group site |
| 993345911 | KLAVENESS FINANS AS | email | cleanbu@klaveness.com | **RELATED** | from the Torvald Klaveness group site |
| 993345911 | KLAVENESS FINANS AS | email | contact-digital@klaveness.com | **RELATED** | from the Torvald Klaveness group site |
| 994916009 | NORRØN AS | email | tor.inge@norron.no | **RELATED** | from the Norrøn Bolig site |
| 994916009 | NORRØN AS | email | dag.einar@norron.no | **RELATED** | from the Norrøn Bolig site |
| 994916009 | NORRØN AS | email | post@norron.no | **RELATED** | from the Norrøn Bolig site |
| 994916009 | NORRØN AS | phone | 90772650 | **RELATED** | from the Norrøn Bolig site |
| 994916009 | NORRØN AS | phone | 93866130 | **RELATED** | from the Norrøn Bolig site |
| 994916009 | NORRØN AS | phone | 51496500 | **RELATED** | from the Norrøn Bolig site |
| 994916009 | NORRØN AS | email | hilde@norron.no | **RELATED** | from the Norrøn Bolig site |
| 994916009 | NORRØN AS | email | bent.magne@norron.no | **RELATED** | from the Norrøn Bolig site |
| 994916009 | NORRØN AS | email | christian@norron.no | **RELATED** | from the Norrøn Bolig site |
| 994916009 | NORRØN AS | email | sturla@norron.no | **RELATED** | from the Norrøn Bolig site |
| 999292526 | LK EIENDOMSUTVIKLING AS | email | lorentz@lk-arkitekter.no | **RELATED** | from the Arkitekt Lorentz Kielland site |
| 816717132 | ROMSDAL INNOVASJON AS | phone | 98883816 | **UNCLEAR** | daily manager of Nordveggen AS, the secretariat (unchanged) |
| 979124945 | HERJEDALSKJØKKEN AS | phone | 90022498 | **UNCLEAR** | 'HK Kjøkkenfornying i Østfold' office; no Østfold sub-unit in Brreg |
| 979124945 | HERJEDALSKJØKKEN AS | phone | 92069096 | **UNCLEAR** | 'HK Kjøkkenfornying i Telemark' office; no Telemark sub-unit in Brreg |
| 982100208 | VALLHALL FOTBALLHALL DRIFT AS | email | anders@vallhall.no | **UNCLEAR** | from an unclear site |
| 984840551 | UNIVERSI AS | email | post@universi.no | **UNCLEAR** | from an unclear site |
| 997688821 | HAMMERFESTINGEN AS | phone | 32277045 | **UNCLEAR** | shared newspaper customer-service number (unchanged) |

Contact rules: (1) the foreign-prefix guard looks only at the token right before the 8 digits. It misses '+61 8 6559 6499' and '+46 (0)921 16316'. Reject any match when a non-47 `+CC` occurs within the preceding 8 characters, allowing for an area code or '(0)'. (2) Skip numbers labelled 'Fax'/'Telefaks'. (3) For BRL/ESEK, drop contacts whose domain or number belongs to the FFØR entity. (4) Contacts inherit the site verdict; 35 of the 36 RELATED contacts come from 8 RELATED sites.

## Top rule changes (in order of impact)

1. **Read the site's own operator statements.** Parse ©, 'drevet av', 'levert av', 'behandlingsansvarlig', 'datakontrollør' and kjøps-/abonnementsvilkår pages. If they name any organisation other than the legal name, whether a registered entity or a 'Gruppen' brand, publish as `related_entity`, never `exact`. A `role_holder_and_name` or `name_address` proof must not override this. This prevents 6 of the 10 WRONG/RELATED sites: Skullerudbyen (Opsahl Gruppen), Norrøn (Norrøn Bolig AS), Sædalen (Sædalen IL), Vinklgården (Vinkl), Wullum Hus (Wullum Eiendom AS) and Trav 24 (Hestesportmedier AS, orgnr on the terms page).
2. **Weak proofs need the legal name.** When the only proof is phone and/or e-mail (registry_email, subunit_email or registry_website origin), require the legal name or orgnr on the site; otherwise hold the site. A group switchboard (Østensjø 52 70 45 45), a person's mobile and personal e-mail (LK), a group contact page (Wullum) or a phone registered to a sister (Vallhall) are not entity proof. This prevents Bugsertjeneste IV, LK Eiendomsutvikling and Wullum Hus, and holds Vallhall.
3. **Generalise the housing co-op rule.** For BRL/ESEK/sameie, or any entity with an FFØR role, compare the site's title, © and contact block with the legal names of the FFØR/REGN/REVI role holders, not only with a fixed manager-domain list. Do not count the Brreg phone as proof when it is the forretningsfører's switchboard. This prevents the only WRONG_ENTITY: skeiendom.no for Sameiet Eckersbergsgate 51.
4. **Brand-stem sibling lookup.** Name-search Brreg for the domain or brand stem. If another entity with that stem declares the same hjemmeside (Klaveness: 3 others), has the same phone (Vallhall Fotballhall AS), or its name equals the site brand (VINKL AS, NORRØN BOLIG AS), publish as group or related. Also require at least one distinctive legal-name token on the site ('Finans' never appears on klaveness.com).
5. **Any foreign orgnr blocks.** An orgnr printed beside the legal name that differs from ours blocks weak proof, even when it fails mod-11 or is not in Brreg (Universi: '932 953 520').
6. **Social and phone hygiene.** Drop social links inside photo credits (hmgphotography), JSON-LD `sameAs` with no token overlap (Enqvist LinkedIn), and handles equal to another Brreg entity name (milepel, norronrehabilitering, Vedalbygg, AiriusEuropeLtd). Fix the wider foreign-prefix window and the fax label described under contact rules.
