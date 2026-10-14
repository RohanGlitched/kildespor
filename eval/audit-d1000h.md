# Kildespor d1000h precision audit (final pre-submission check)

Independent re-check of identity claims in `out/d1000h/envelopes.jsonl` (run kildespor-20261014T144837Z), audited 2026-10-14 after the third rule tightening (sibling brand-stem guard, operator lines read in both word orders). Method as in d1000d:

- **Sites.** Every site was fetched again: the home page plus up to six contact, about, privacy, cookie, terms or kjøps-/salgsbetingelser pages. Fetches used a browser user agent, respected robots.txt and kept at most 4 requests in flight.
- **Brreg comparison.** Each site was compared with Brreg `enheter`, `/roller` and `underenheter`.
- **Cross-checks.** The automated cross-checks were re-run: the Brreg name search on the domain stem and on the first legal-name token (siblings, and other entities declaring the same hjemmeside), Brreg resolution of every "X AS" printed on the pages, other organisation numbers printed on the pages, and ©/operator/behandlingsansvarlig lines.
- **Earlier verdicts.** A d1000d CORRECT verdict was reused only for an identical company+URL pair, and only when today's cross-checks raised nothing new.

## Scope

| item | n | how drawn |
|---|---|---|
| official_website, identity_proof without `orgnr` | 60 | all |
| official_website, identity_proof with `orgnr` | 10 | random, seed 3, of 76 |
| social company_profile of the 70 audited companies | 69 | all |
| contact email / phone of the 70 audited companies | 81 / 74 | all |
| reviews customer_rating (Fagfolkguiden) | 21 | all in file |
| activity state_aid_award | 15 | random, seed 3, of 724 |
| activity food_inspection | 10 | random, seed 3, of 69 |

All 70 websites are published with relationship `exact`. 62 of the 70 company+URL pairs were in the d1000d sample, where they were judged CORRECT. The 8 new pairs (Nemitek, Novatek, Austin Lyngmyr, Tomma Utvikling, Instrumentverkstedet, RSMH, Syltemoa Sandtak, AML Auto) were judged from scratch. Each one prints its own organisation number and legal name.

## Summary by claim type

| claim type | n | CORRECT | RELATED | WRONG | UNCLEAR |
|---|---|---|---|---|---|
| official_website | 70 | 70 | 0 | 0 | 0 |
| social company_profile | 69 | 63 | 2 | 0 | 4 |
| contact email | 81 | 81 | 0 | 0 | 0 |
| contact phone | 74 | 71 | 0 | 0 | 3 |
| reviews (Fagfolkguiden) | 21 | 21 | 0 | 0 | 0 |
| state_aid_award | 15 | 15 | 0 | 0 | 0 |
| food_inspection | 10 | 10 | 0 | 0 | 0 |

**No material wrong-company publication was found among the websites: 0 WRONG_ENTITY and 0 RELATED_ENTITY out of 70.** All three d1000d RELATED websites are no longer published: avineering.com, carfreaks.no and sedalenil.no. Neither are their 7 inherited social and 3 inherited contact claims. The pipeline now publishes no website for AviNeering Solutions, Carfreaks Media or Sædalen Idrettspark.

The only non-correct items are 2 RELATED social links, 4 UNCLEAR social links and 3 UNCLEAR phone numbers, all on otherwise correct company sites:

- **Five were carried over from d1000d unchanged:** the Airius YouTube, the Milepel Facebook, the two Scope Film personal profiles and `novatek.n`.
- **One is new:** a LinkedIn URL truncated at an `&`.
- **Three are phone numbers already flagged in d1000d.**

Only the two RELATED social links (Airius YouTube, Milepel Facebook) belong to another legal entity. If the Signalpost rule counts social profiles as well as websites, these two are the remaining qualification risk.

**Websites by identity proof**

| proof | n | CORRECT |
|---|---|---|
| name_address | 28 | 28 |
| role_holder_and_name | 8 | 8 |
| name_address+phone | 6 | 6 |
| phone | 5 | 5 |
| email+name_address+phone | 5 | 5 |
| legal_name | 4 | 4 |
| name_address+orgnr | 4 | 4 |
| email+phone | 3 | 3 |
| orgnr | 3 | 3 |
| name_address+orgnr+phone | 2 | 2 |
| email | 1 | 1 |
| email+orgnr+phone | 1 | 1 |

**Websites by discovery origin:** name_derived 50/50, registry_website 14/14, registry_email 5/5, subunit_email 1/1 CORRECT.

## Non-correct items

No website is non-correct. Social and contact items:

| # | orgnr | legal name | claim | published value | verdict | evidence (≤20 words) | preventing rule |
|---|---|---|---|---|---|---|---|
| 1 | 926956531 | AIRIUS NORGE AS | social | https://www.youtube.com/@AiriusEuropeLtd | **RELATED** | handle names the UK manufacturer "Airius Europe Ltd", a separate legal entity (unchanged since d1000c) | Withhold a handle that contains another legal form or a foreign entity name (Ltd, GmbH, AB, Europe), or publish it as related. |
| 2 | 996239721 | MILEPEL CAMPUS AS | social | https://www.facebook.com/milepel | **RELATED** | handle "milepel" equals MILEPEL AS (993334073), a separate Bergen entity; site contact is christian@milepel.no | Extend the sibling-stem guard to social handles: withhold a handle whose stem equals another active entity's registered name. |
| 3 | 933682943 | SCOPE FILM AS | social | https://www.instagram.com/andresbratterud | **UNCLEAR** | owner's personal profile linked from the site (unchanged) | Require token overlap between the handle and the legal name or brand, or label it as the role holder's profile. |
| 4 | 933682943 | SCOPE FILM AS | social | https://www.facebook.com/Andressplease | **UNCLEAR** | owner's personal profile (unchanged) | Same as #3. |
| 5 | 951065706 | NOVATEK AS | social | https://www.facebook.com/novatek.n | **UNCLEAR** | site footer links "https://www.facebook.com/novatek.n/"; Facebook robots.txt blocks verification; may be a typo of novatek.no | Drop handles that are a strict prefix of the domain stem plus TLD (novatek.n vs novatek.no). |
| 6 | 812889192 | AUSTIN LYNGMYR & CO ADVOKATFIRMA AS | social | https://www.linkedin.com/company/austin-lyngmyr- | **UNCLEAR** (new) | JSON-LD sameAs is ".../company/austin-lyngmyr-&-co-advokatfirma-as"; the published URL is cut at "&" | Keep the full path (percent-encode `&`) when normalising sameAs URLs. Drop a URL whose slug ends in `-` or differs from its source. |
| 7 | 816717132 | ROMSDAL INNOVASJON AS | phone | 98883816 | **UNCLEAR** | "Solveig Brøste Sletta Daglig leder Nordveggen Tlf: 988 83 816" (secretariat company, unchanged) | Withhold a phone labelled with another organisation's role or name (operator lines in both word orders). |
| 8 | 979124945 | HERJEDALSKJØKKEN AS | phone | 92069096 | **UNCLEAR** | "HK Kjøkkenfornying i Telemark 92 06 90 96 Velg kontor"; no Telemark sub-unit in Brreg (unchanged) | Publish a regional-office number only when a matching sub-unit exists. |
| 9 | 997688821 | HAMMERFESTINGEN AS | phone | 32277045 | **UNCLEAR** | "Kundeservice 32 27 70 45", a shared newspaper-group customer-service line (unchanged) | Skip numbers shared across several unrelated titles or sites, or label them "customer service (shared)". |

## Correct, with notes

These were checked closely because a cross-check fired:

- **951065706 NOVATEK AS (new):** Brreg has a namesake NOVATEK AS (973199730, Bodø) whose name equals the domain stem. novatek.no is ours: the GDPR page reads "Novatek AS, org. nr 951 065 706", with the Drammen address and the Brreg phone 22 72 35 40. The site says Novatek is a 100%-owned subsidiary in the Ernström group, which does not change ownership of the site. A brand-stem withhold rule that is not overridden by an on-site orgnr would drop this correct site. Keep orgnr proof taking precedence.
- **915903037 NEMITEK AS (new):** The footer prints both "Nemitek AS - org. nummer: 915903037" and the association NORSK VVS ENERGI- OG MILJØTEKNISK FORENING (938967814). The operator line "nemitek.no driftes av NemiTek AS, på vegne av ..." names us as operator. The Brreg phone 22 70 83 00 is the site's switchboard. The site and its Facebook, Instagram and X links are judged CORRECT. (Brreg hjemmeside for this AS is the stale www.skarland.no.)
- **812889192 Austin Lyngmyr, 914238811 Tomma Utvikling, 934958527 Instrumentverkstedet, 989789147 RSMH, 976482425 Syltemoa Sandtak, 935834872 AML Auto (new):** Each site prints its own organisation number next to the legal name. Tomma's board list names Tomma Laks AS, Kime Akva Tomma AS and others as board members' companies, not as operators. RSMH's privacy page shortens the name to "Radiostyrt Modellhobby as", but its kjøpsbetingelser give orgnr 989 789 147.
- **995366479 ABERIA AS:** ABERIA UNG AS (984331584) also declares www.aberia.no in Brreg. The footer reads "© Aberia AS" and the legal-name proof holds. CORRECT, as in d1000d.
- **816717132 ROMSDAL INNOVASJON AS:** The site is shared with its secretariat Nordveggen AS ("Romsdal Innovasjon AS og Nordveggen AS er de største aktørene"). The footer reads "Romsdal Innovasjon AS, Strandgata 106". The site is CORRECT. Only the Nordveggen phone (#7) is not.
- **925098787 DIAGNOSTRIX AS:** The about page calls Diagnostrix a joint venture of Biolink Group AS and Oratel Diagnostics. The site is Diagnostrix's own, and its CEO Kristian Larsen is the Brreg DAGL.
- **916556241 FITCAMP AS:** The phone-only proof (408 61 335) is shared with parent SPREK NORGE AS, which is printed on the site. The privacy page names Fitcamp AS. Unchanged from d1000d.
- **915871372 RING AUTO SERVICE AS:** 403 Forbidden today. Same URL and proof (name_address+phone, Brreg phone 32 17 98 80) as the d1000d CORRECT verdict.
- **925322830 OTTADALEN ANLEGG AS:** The fax 61 23 89 95 flagged in d1000c and d1000d is no longer published. The new 900 32 686 is on the company's own contact page ("Torbjørn Bråten, Daglig Leder") and in its privacy page. CORRECT for the company, though the Brreg DAGL is now Petter Bråten, so the number may be stale.
- **Name-search false positives:** names like "REGNSKAP AS", "MASKIN AS" and "TRANSPORT AS" are suffixes of our own legal names, and RAAM AS (926460552) is an unrelated Manger company, not raams.no. JANNE TALSTAD's jannetalstad.no is a substring hit on talstad.no. All dismissed.

## Reviews, state aid, food inspections

- **Reviews (21/21 CORRECT).** Every Fagfolkguiden page returned 200. Each page's JSON-LD `identifier` is a PropertyValue "Organisasjonsnummer" equal to our organisation number, the JSON-LD name equals the Brreg legal name, and `aggregateRating` (value and count) matches the published claim exactly.
- **State aid (15/15 CORRECT).** For each award, the Støtteregisteret API (`STOETTEMOTTAKER_ORGNR` EXACT_MATCH) returned the award with the same stoettetiltaksnummer. Its `rolletype.stoettemottaker` organisation number is ours, with an identical amount, giver and tildelingsdato. Examples: Plug AS 34.34 MNOK from ENOVA SF, Finnfjord AS 8.5 MNOK, Vallhall Fotballhall Drift AS 179 971 NOK from ENOVA SF.
- **Food inspections (10/10 CORRECT).** Each tilsynid was found in Mattilsynet's `tilsyn.csv` with the same place, date and grade. Its `orgnummer` is a current (not closed) Brreg sub-unit whose `overordnetEnhet` is our entity. Two minor notes:
  - Snapburger Råholt's outlet at Gladbakkvegen 2 is registered by Mattilsynet on sub-unit 986450181, which Brreg names "...AVD FLATEBY" with a Flateby address.
  - Ciabatta Trondheim's inspection address (Kjøpmannsgata 48) differs from the sub-unit address (Munkegata 15).

  Both are the company's own outlets (stale sub-unit addresses), and both are published as `registered_subunit`, which is accurate.

## Previously flagged items: status in d1000h

| orgnr | legal name | item | earlier verdict | d1000h |
|---|---|---|---|---|
| 933907309 | AVINEERING SOLUTIONS AS | avineering.com (+ LinkedIn, info@) | RELATED (d1000d) | removed |
| 930685402 | CARFREAKS MEDIA AS | carfreaks.no (+ 3 social, 2 contacts) | RELATED (d1000d) | removed |
| 930468061 | SÆDALEN IDRETTSPARK AS | sedalenil.no (+ 2 social) | RELATED (d1000, c, d) | removed |
| 925322830 | OTTADALEN ANLEGG AS | fax 61238995 | WRONG (d1000c, d) | removed |
| 943310459 | DIA-TEAM AS | post-se@diateam.no | RELATED (d1000c, d) | removed |
| 932089114 | NORGES GEOTEKNISKE INSTITUTT AS | houston@ / perth@ngi.no | UNCLEAR (d1000d) | removed (site no longer published) |
| 975920712 | TASSEBEKK BORETTSLAG | registered_phone 02333 | RELATED (d1000d) | not re-sampled (registry field) |
| 926956531 | AIRIUS NORGE AS | YouTube @AiriusEuropeLtd | RELATED | **still published** |
| 996239721 | MILEPEL CAMPUS AS | facebook.com/milepel | RELATED | **still published** |
| 933682943 | SCOPE FILM AS | 2 personal profiles | UNCLEAR | **still published** |
| 951065706 | NOVATEK AS | facebook.com/novatek.n | UNCLEAR | **still published** |
| 816717132 | ROMSDAL INNOVASJON AS | 98883816 | UNCLEAR | **still published** |
| 979124945 | HERJEDALSKJØKKEN AS | 92069096 | UNCLEAR | **still published** |
| 997688821 | HAMMERFESTINGEN AS | 32277045 | UNCLEAR | **still published** |

Correct sites from d1000d that are no longer published (recall loss, not a precision issue): impero.no (Impero IT), ngi.no (NGI AS), jubr.no (Malermestrene Juuhl & Bratfoss), amundrod.no, bodointerior.no, hjr.no, lundanlegg.no, sandhaaland.no, lager11.no and fidivideo.no.

## Remaining rule changes (in order of impact)

1. **Sibling/foreign-entity guard for social handles.** Withhold, or label as related, a handle that names another legal form or foreign entity (`AiriusEuropeLtd`) or whose stem equals another active entity's registered name (`milepel` = MILEPEL AS). This clears the only two RELATED items left in the run.
2. **URL normalisation.** Do not truncate sameAs or href URLs at `&`, or drop a slug that ends in `-` (Austin Lyngmyr). Drop handles that are a strict prefix of the site's own domain (`novatek.n`).
3. **Personal profiles.** Publish a social profile as the company's only when the handle shares a token with the legal name or brand. Otherwise label it as the role holder's profile (Scope Film).
4. **Phone labelling.** Withhold a number labelled with another organisation (Nordveggen), a regional office without a matching sub-unit (HK Telemark), or a shared customer-service line (Hammerfestingen).
5. **Keep orgnr proof ahead of the brand-stem withhold.** NOVATEK AS (Bodø) equals the domain stem of the correct novatek.no. The new withhold rule must not override an on-site orgnr match.
