# Kildespor d1000d precision audit

Independent re-check of identity claims in `out/d1000d/envelopes.jsonl` (run kildespor-20261014T130440Z), audited 2026-10-14 after the second rule tightening. Each website was fetched again: the home page plus up to six contact, about, privacy, cookie, terms or kjøps-/salgsbetingelser pages, with a normal browser user agent, robots.txt respected and at most 4 requests in flight. Each was compared with the Brreg record (`enheter`, `/roller`, `underenheter`). Three automated cross-checks were added this round:

- **Brand-stem sibling search.** Brreg name search on the domain stem and the first legal-name token, flagging any other active entity whose name equals the stem or which declares the same hjemmeside.
- **Printed legal names.** Every "X AS/ASA/SA/ANS/DA" printed on the fetched pages was resolved against Brreg, flagging registered entities other than ours.
- **Legal-name presence.** Checks whether the full legal name appears on the site at all.

## Scope

- **Websites:** all 73 `official_website` claims whose identity_proof has no `orgnr`, plus a random 10 (seed 5) of the 78 that do. That is 83 websites at 83 companies. All are published with relationship `exact`. 72 of the 73 scope sites were already in the d1000c sample with the same URL. Their earlier CORRECT verdicts were re-tested with the new cross-checks, not just copied.
- **Social / contact of audited companies:** all 98 `social/company_profile` claims, and all 106 `contact/email` and 86 `contact/phone` claims.
- **No-website companies:** a random 40 (seed 9) of the 849 companies without an `official_website` claim. None of them has a social claim; between them they have 28 registry-field contact claims (`registered_email` / `registered_phone` / `registered_mobile`). Only 2 no-website companies in the whole run have any social claim (both from Wikidata), so both were added in full. That makes 31 registry contact claims and 2 social claims.

## Summary by claim type

| claim type | n | CORRECT | RELATED | WRONG | UNCLEAR |
|---|---|---|---|---|---|
| official_website | 83 | 80 | 3 | 0 | 0 |
| social company_profile (audited sites) | 98 | 87 | 8 | 0 | 3 |
| contact email (audited sites) | 106 | 101 | 3 | 0 | 2 |
| contact phone (audited sites) | 86 | 81 | 1 | 1 | 3 |
| social company_profile (no-website, Wikidata) | 2 | 2 | 0 | 0 | 0 |
| contact registered_* (no-website, Brreg) | 31 | 30 | 1 | 0 | 0 |

**Material wrong-company publications remain: 3 RELATED_ENTITY websites, all published as `exact`.** There are no WRONG_ENTITY websites. Two of the three are new findings: **AviNeering Solutions AS → avineering.com** and **Carfreaks Media AS → carfreaks.no**. Both sites were judged CORRECT in d1000c, and the new sibling-stem cross-check exposed them. Each is the website of an older sister company at the same address, whose legal name is our name minus one token ("Solutions", "Media"). The third, Sædalen Idrettspark → sedalenil.no (the sports club's site), was flagged in d1000c and is still published. All 11 other d1000c WRONG/RELATED/UNCLEAR websites are gone. Under the Signalpost rule each of the three blocks qualification.

**Websites by sample bucket**

| group | n | CORRECT | RELATED_ENTITY | WRONG_ENTITY | UNCLEAR |
|---|---|---|---|---|---|
| scope | 73 | 70 | 3 | 0 | 0 |
| random | 10 | 10 | 0 | 0 | 0 |

**Websites by identity proof (value.identity_proof)**

| group | n | CORRECT | RELATED_ENTITY | WRONG_ENTITY | UNCLEAR |
|---|---|---|---|---|---|
| name_address | 32 | 30 | 2 | 0 | 0 |
| role_holder_and_name | 9 | 8 | 1 | 0 | 0 |
| phone | 7 | 7 | 0 | 0 | 0 |
| name_address+phone | 7 | 7 | 0 | 0 | 0 |
| name_address+orgnr | 6 | 6 | 0 | 0 | 0 |
| email+phone | 5 | 5 | 0 | 0 | 0 |
| email+name_address+phone | 5 | 5 | 0 | 0 | 0 |
| legal_name | 4 | 4 | 0 | 0 | 0 |
| email | 3 | 3 | 0 | 0 | 0 |
| email+name_address | 1 | 1 | 0 | 0 | 0 |
| email+orgnr | 1 | 1 | 0 | 0 | 0 |
| email+orgnr+phone | 1 | 1 | 0 | 0 | 0 |
| orgnr | 1 | 1 | 0 | 0 | 0 |
| email+name_address+orgnr+phone | 1 | 1 | 0 | 0 | 0 |

**Websites by discovery origin (value.discovered_via)**

| group | n | CORRECT | RELATED_ENTITY | WRONG_ENTITY | UNCLEAR |
|---|---|---|---|---|---|
| name_derived | 53 | 51 | 2 | 0 | 0 |
| registry_website | 17 | 16 | 1 | 0 | 0 |
| registry_email | 9 | 9 | 0 | 0 | 0 |
| subunit_email | 4 | 4 | 0 | 0 | 0 |

Pattern: every orgnr-proven site was correct (10/10 here, 15/15 in d1000c). All three non-correct sites have a weak proof:

- **Two `name_address` proofs on `name_derived` domains.** The pipeline built the domain by dropping a legal-name token (avineering.com from AVINEERING SOLUTIONS, carfreaks.no from CARFREAKS MEDIA). The address matched because the sister company sits at the same address. AviNeering's footer even prints the sister's legal name "AviNeering AS".
- **One `role_holder_and_name` proof on a registry-declared hjemmeside** (Sædalen). The owning club declares the same hjemmeside in Brreg.

## Non-correct websites

| # | orgnr | legal name | published value | origin / proof | verdict | entity it belongs to | evidence (≤20 words) | rule change that prevents it |
|---|---|---|---|---|---|---|---|---|
| 1 | 933907309 | AVINEERING SOLUTIONS AS | https://www.avineering.com/ | name_derived / name_address | **RELATED_ENTITY** | AVINEERING AS (918441514), the 2017 sister company (6 employees) at the same Tynset address; our entity was founded 2024 | "AviNeering AS Persvangveien 60, 2500 Tynset, Norway Contact: Info@avineering.com Copyright © AviNeering" | Sibling-stem guard: if the domain was derived by dropping a legal-name token (Solutions, Media) and Brreg has an active entity whose name equals the shorter stem, the site is that entity's; hold it or publish as related, never exact. name_address must find the full legal name (every distinctive token) beside the address; another 'X AS' printed with the same address (a sister at the same address) defeats the proof. |
| 2 | 930685402 | CARFREAKS MEDIA AS | https://carfreaks.no/ | name_derived / name_address | **RELATED_ENTITY** | CARFREAKS AS (924923911), the sister car dealership (NACE retail of motor vehicles) at the same Hamar address | "Biler med entusiastfaktor ... Alle våre biler gjennomgår tilstandsrapport hos BilXtra før utlevering" (Carfreaks Media is an ad agency) | Sibling-stem guard: if the domain was derived by dropping a legal-name token (Solutions, Media) and Brreg has an active entity whose name equals the shorter stem, the site is that entity's; hold it or publish as related, never exact. |
| 3 | 930468061 | SÆDALEN IDRETTSPARK AS | https://sedalenil.no/ | registry_website / role_holder_and_name | **RELATED_ENTITY** | SÆDALEN IDRETTSLAG (990283710), the owning sports club; unchanged since d1000c | "Sædalen IL er behandlingsansvarlig for den behandling av personopplysninger"; "Copyright Sædalen IL 2019" | A registry-declared hjemmeside is not proof when the ©/behandlingsansvarlig line names another entity that declares the same hjemmeside in Brreg (SÆDALEN IDRETTSLAG declares sedalenil.no too). |

Correct, with notes (checked because a sibling, a shared phone or a second legal name showed up):

- 979124945 HERJEDALSKJØKKEN AS: Brand is HK Kjøkkenfornying and sister HK KJØKKENFORNYING AS (994323237) shares the address, but the terms page says contracts are "mellom HerjedalsKjøkken AS og kunde".
- 923566597 TRONDHEIM TORG AS: Sisters TRONDHEIM TORG KONTOR AS and ...KJØPESENTER HJEMMEL AS exist, but the cookie page names "Trondheim Torg AS Solheimsgaten 7C 5058 BERGEN".
- 920465331 JV UTVIKLING AS: Site links to sister brands JV Eiendom/JV Anlegg, but its contact block reads "JV Utvikling AS Hevingen 2 1739 Borgenhaugen".
- 916556241 FITCAMP AS: Phone-only proof; 408 61 335 is also the registered phone of parent SPREK NORGE AS ("moren" on the site). Saved by the privacy page naming Fitcamp AS. Phone proof should be unique to the entity.
- 997796101 LINIMA AS: Published renovero.no: Brreg hjemmeside linima.no redirects there and the footer reads "© Linima AS".
- 997327888 MALERMESTRENE JUUHL & BRATFOSS AS: Cloudflare 403 today; the d1000c fetch of the same page shows the legal name, Hovfaret 8 and the role holders.
- 911873621 HOVELSRUDHAGEN AS: Farm site with garden and chicken sections; the orgnr is on the cookie page and the entity's NACE is meat wholesale, so kylling@ and @hovelsrudkylling belong to it.
- 932089114 NORGES GEOTEKNISKE INSTITUTT AS: Stiftelsen NGI (958254318) also declares ngi.no, but the invoice page gives this AS orgnr as the operating company.
- 930721921 IMPERO IT AS: Part of Serit-gruppen; IMPERO AS (926307819) is an unrelated Oslo name match; privacy page: "Impero IT AS er behandlingsansvarlig".

## Previous audits: still published?

| orgnr | legal name | previous website | previous verdict (audit) | d1000d status |
|---|---|---|---|---|
| 993034231 | SAMEIET ECKERSBERGSGATE 51 | skeiendom.no | WRONG (d1000c) | removed (no website published) |
| 989747568 | TRAV 24 AS | trav24.no | RELATED (d1000c) | removed (no website published) |
| 992059060 | VINKLGÅRDEN AS | vinkl.no | RELATED (d1000, d1000c) | removed (no website published) |
| 927056712 | SKULLERUDBYEN AS | skullerudbyen.no | RELATED (d1000c) | removed (no website published) |
| 993345911 | KLAVENESS FINANS AS | klaveness.com | RELATED (d1000c) | removed (no website published) |
| 980402908 | BUGSERTJENESTE IV AS | ostensjo.no | RELATED (d1000, d1000c) | removed (no website published) |
| 917383545 | WULLUM HUS AS | wullumeiendom.no | RELATED (d1000c) | removed (no website published) |
| 999292526 | LK EIENDOMSUTVIKLING AS | lk-arkitekter.no | RELATED (d1000, d1000c) | removed (no website published) |
| 994916009 | NORRØN AS | norron.no | RELATED (d1000, d1000c) | removed (no website published) |
| 982100208 | VALLHALL FOTBALLHALL DRIFT AS | vallhall.no | UNCLEAR (d1000c) | removed (no website published) |
| 984840551 | UNIVERSI AS | universi.no | UNCLEAR (d1000, d1000c) | removed (no website published) |
| 930468061 | SÆDALEN IDRETTSPARK AS | sedalenil.no | RELATED (d1000, d1000c) | **still published** (role_holder_and_name): still RELATED |
| 930685402 | CARFREAKS MEDIA AS | carfreaks.no | CORRECT (d1000c) | **re-judged RELATED** (sister CARFREAKS AS) |
| 933907309 | AVINEERING SOLUTIONS AS | avineering.com | CORRECT (d1000c) | **re-judged RELATED** (sister AVINEERING AS) |

The d1000 entries already removed by d1000c (Gjerdetunet, Tårnbo Nord, nemitek.com, Bilvarehusene, Sulland, Wärtsilä, ABP, Jernbaneveien, Sunnsand, Fjellhaug) are still absent. Paulig (/no) and Aberia remain CORRECT.

Previously flagged social/contact items:

- **Gone:** the Enqvist LinkedIn, hmgphotography, millilill, Endimetrix, the Paulig numeric LinkedIn, Vedalbygg, the Scope Film Vimeo, the NGI Perth truncated phone, the Dia-Team SE phone and every contact inherited from the removed sites.
- **Still published:** the Ottadalen fax (WRONG), Dia-Team post-se@ (RELATED), the Airius Europe YouTube and the milepel Facebook (RELATED), the two Scope Film personal profiles, the Kjøkkenhuset Facebook, the Romsdal/Nordveggen phone, the HK Telemark phone and the Hammerfestingen shared customer-service number (UNCLEAR).
- **Outside this sample:** `facebook.com/novatek.n` (Novatek, orgnr-proven site) is also still published.
- **Re-judged:** HK Østfold 90022498 is now judged CORRECT, because the om-oss team list gives it as "Ragnar Lund Kjøkkenekspert, Oslo" with info@herjedalskjokken.no.

## Non-correct social profiles

| orgnr | legal name | published value | verdict | evidence / reason | rule change |
|---|---|---|---|---|---|
| 926956531 | AIRIUS NORGE AS | https://www.youtube.com/@AiriusEuropeLtd | **RELATED** | manufacturer Airius Europe Ltd, UK (unchanged since d1000c) | A handle naming another legal form/entity (Ltd, Europe) is related. |
| 930468061 | SÆDALEN IDRETTSPARK AS | https://www.facebook.com/sedalenil | **RELATED** | sports club Sædalen IL (unchanged) | Inherits site verdict. |
| 930468061 | SÆDALEN IDRETTSPARK AS | https://www.instagram.com/sedalenil | **RELATED** | sports club Sædalen IL (unchanged) | Inherits site verdict. |
| 930685402 | CARFREAKS MEDIA AS | https://www.facebook.com/CarfreaksAs | **RELATED** | handle "Carfreaks AS" is the sister dealership's exact legal name | Handle equal to another Brreg entity name -> related. |
| 930685402 | CARFREAKS MEDIA AS | https://www.instagram.com/carfreaks_as | **RELATED** | handle "carfreaks_as" = CARFREAKS AS | Handle equal to another Brreg entity name -> related. |
| 930685402 | CARFREAKS MEDIA AS | https://www.tiktok.com/@carfreaks_as | **RELATED** | handle "carfreaks_as" = CARFREAKS AS | Handle equal to another Brreg entity name -> related. |
| 933907309 | AVINEERING SOLUTIONS AS | https://www.linkedin.com/company/avineering | **RELATED** | company page of the sister AviNeering AS | Inherits site verdict. |
| 996239721 | MILEPEL CAMPUS AS | https://www.facebook.com/milepel | **RELATED** | MILEPEL AS (993334073), separate Bergen entity (unchanged) | Handle equal to another Brreg entity name -> related. |
| 933682943 | SCOPE FILM AS | https://www.instagram.com/andresbratterud | **UNCLEAR** | owner's personal profile (unchanged) | Require a token overlap with legal name/brand or mark unconfirmed. |
| 933682943 | SCOPE FILM AS | https://www.facebook.com/Andressplease | **UNCLEAR** | owner's personal profile (unchanged) | Require a token overlap with legal name/brand or mark unconfirmed. |
| 997750233 | KJØKKENHUSET BODØ AS | https://www.facebook.com/kjokkenhuset.no | **UNCLEAR** | generic Kjøkkenhuset handle; kjokkenhuset.no does not resolve; site brand is Bodø Interiør (unchanged) | Require a token overlap with the site brand. |

## Non-correct contact claims

| orgnr | legal name | field | published value | verdict | reason | rule change |
|---|---|---|---|---|---|---|
| 925322830 | OTTADALEN ANLEGG AS | phone | 61238995 | **WRONG** | still a fax number: "Fax. 61 23 89 95" (flagged in d1000c, rule not yet applied) | Skip numbers labelled Fax/Telefaks, including tel: links. |
| 930685402 | CARFREAKS MEDIA AS | email | post@carfreaks.no | **RELATED** | contact of the sister dealership site | Inherits site verdict. |
| 930685402 | CARFREAKS MEDIA AS | phone | 62590313 | **RELATED** | dealership switchboard on the sister site; not this entity's Brreg phone | Inherits site verdict. |
| 933907309 | AVINEERING SOLUTIONS AS | email | info@avineering.com | **RELATED** | contact of AviNeering AS | Inherits site verdict. |
| 943310459 | DIA-TEAM AS | email | post-se@diateam.no | **RELATED** | Swedish sister Dia-Team AB (unchanged since d1000c) | Drop mailboxes tagged with a foreign country code (-se, -dk, -fi) or listed under a foreign office. |
| 816717132 | ROMSDAL INNOVASJON AS | phone | 98883816 | **UNCLEAR** | "Daglig leder Nordveggen Tlf: 988 83 816" (the secretariat company; unchanged) | A phone labelled with another organisation's role is not this entity's. |
| 932089114 | NORGES GEOTEKNISKE INSTITUTT AS | email | houston@ngi.no | **UNCLEAR** | listed under "NGI Houston", a US office with a +1 number; likely a separate US subsidiary | Drop contacts listed under a foreign office address. |
| 932089114 | NORGES GEOTEKNISKE INSTITUTT AS | email | perth@ngi.no | **UNCLEAR** | listed under "NGI Perth" (Australia); likely a separate subsidiary | Drop contacts listed under a foreign office address. |
| 979124945 | HERJEDALSKJØKKEN AS | phone | 92069096 | **UNCLEAR** | regional "HK Kjøkkenfornying i Telemark/Vestfold" office; no such sub-unit in Brreg (unchanged) | Regional-office numbers need a matching sub-unit. |
| 997688821 | HAMMERFESTINGEN AS | phone | 32277045 | **UNCLEAR** | shared newspaper customer-service number (unchanged) | Prefer numbers not shared across titles. |
| 975920712 | TASSEBEKK BORETTSLAG | registered_phone (no-website sample) | 02333 | **RELATED** | registered phone of TASSEBEKK BORETTSLAG is OBOS's 5-digit customer-service number; OBOS EIENDOMSFORVALTNING AS is FFØR | For BRL/ESEK with an FFØR, label a registry phone that is the manager's switchboard as the manager's, or drop it. |

## No-website companies (Wikidata and registry fields)

- All 31 registry-field contact claims (28 in the 40 random companies, 3 in the two Wikidata companies) match the live Brreg record exactly.
- Some registered e-mails sit on another organisation's domain but were filed by the entity itself and are labelled `registered_email`: jahn.k.nielsen@byggtech.no (Salhus Tomteselskap), log@budstikke.no (Lillehammer Media), geiteryggen@dnt.no (Geiterygghytta), tassebekk@styrerommet.no (the board's own mailbox on the OBOS portal). Judged CORRECT as registry facts.
- Both Wikidata social claims are linked by P2333 = the organisation number: BIK BOK AS (Q10429512, facebook bikbok) and ÅNUN LUND REJ STIFTELSE (Q127060522, facebook anun.minnefond). CORRECT.
- None of the 40 randomly drawn no-website companies has a social claim. Only 2 of all no-website companies in the run have one, and both were checked.

## Top rule changes (in order of impact)

1. **Sibling-stem guard for derived domains.** When a `name_derived` domain drops a legal-name token, name-search Brreg for that shorter stem. If an active entity whose name equals the stem exists (AVINEERING AS, CARFREAKS AS), the site is presumed to be that entity's: hold it, or publish it as `related_entity`, never `exact`. Prefer candidates that keep the full name (avineeringsolutions.no, carfreaksmedia.no); here none resolved to its own site. The guard also covers social handles equal to that entity's name (CarfreaksAs, carfreaks_as). This prevents both new RELATED websites, 4 social claims and 3 contacts.
2. **name_address needs the full legal name.** The address proof should require every distinctive legal-name token ("Solutions", "Media") near the address or in the ©/footer. Any other registered "X AS" printed with the same address defeats it: avineering.com prints "AviNeering AS Persvangveien 60, 2500 Tynset", which is another Brreg entity. A shared address is common for sister companies, so on its own it is not proof of identity.
3. **Shared hjemmeside in Brreg.** If another entity declares the same hjemmeside and the site's ©/behandlingsansvarlig names that entity, publish as related, even when our entity also declares it and a role holder appears on the page (Sædalen Idrettspark vs SÆDALEN IDRETTSLAG). This is the last d1000c website still published.
4. **Contact hygiene still pending from d1000c.** Skip numbers labelled Fax/Telefaks (Ottadalen 61 23 89 95 is still published). Drop mailboxes tagged with a foreign country (post-se@) or listed under a foreign office (NGI Houston/Perth). For BRL/ESEK with an FFØR, label a registry phone that is the manager's switchboard (OBOS 02333) as the manager's.
5. **Phone-only proof must be unique.** Fitcamp's only proof, 408 61 335, is also the registered phone of its parent SPREK NORGE AS. The privacy page saved it this time. Check that the phone is not registered to another entity before accepting phone-only proof.

