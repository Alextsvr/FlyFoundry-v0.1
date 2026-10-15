# Phase 1 research round 1 (2026-10-15): five candidates, desk research

Method: one independent research agent per candidate (WebSearch/WebFetch only, 6-10 calls each, never bypassing blocks), fixed output schema: competitors with URLs, legal/data terms, demand evidence with levels (L1 assumption, L2 market signal, L3 commercial evidence), proposed 1-5 scores, cheapest real-world test, verdict. The agents' reports are model output: several claims rest on page titles or competitor-authored comparison pages, and I did not re-verify them. Scores in `data/seeds_new.csv` were replaced by the agents' proposals for these candidates; nothing reached L4.

| Candidate | Verdict | Strongest reason | Decisive unknown |
|---|---|---|---|
| N1 PSP fee / overcharge audit | WEAK | incumbents already work on contingency (Cost Analysts 50/50 split, PaymentID, Juspay) and acquirers give statement audits away free as lead-gen | any EU/Baltic demand; confidentiality clauses in acquirer contracts |
| N3 PSP settlement-report converters | WEAK | buyer hard to reach, willingness to pay unproven; Stripe/Shopify segment covered by A2X, Link My Books, Synder, native Xero | whether Adyen / high-risk PSP / Baltic ledgers (Merit, Standard Books, Directo) are really unserved |
| R1 Reconciliation for small accounting firms | WEAK | no evidence they pay for exception-report tooling beyond EUR 15-60/month extraction tools; mainstream niche crowded | Latvian AML status of a data-touching service (outsourced accountants are VID-supervised and licensed) |
| N5 Licence / registry monitoring | WEAK | direct competitors already live: PaymentProviders.io License Watch (19 registries), LiSense (GB gambling licences, launched 2026-09-03) | national register terms; price anchors |
| N7 Niche tender alerts | WEAK | iepirkumi.io covers Latvian + TED notices with AI matching for EUR 19/month; free official alerts exist | any premium for curation or bid support |

Common pattern: (1) acquisition is the weak link for every candidate because the system does no outreach and the owner has no known audience; (2) willingness to pay at solo-operator prices is anchored at EUR 15-60 per month or by free substitutes; (3) the owner's domain edge (reconciliation, PSP formats) shows up as high automation and MVP scores but not as demand evidence; (4) no candidate has L3 evidence in the segment the owner would actually serve.

Cheapest real-world test per candidate (each under a week, under EUR 50, run by the owner by hand): N1 offer a free 'fee check' to 5-10 warm contacts and look for >=1% recoverable overcharge in 2 of 5 statements plus one success-fee agreement; N3 and R1 offer a free sample conversion / exception report for real exports in 2-3 accountant or iGaming-finance communities (success: >=3 files received, >=1 stated price); N5 publish a free weekly Baltic/Nordic PI/EMI licence-change digest and ask 10-15 compliance contacts for price points (success: >=3 price points or pre-orders); N7 pick one sector, publish a sample digest and a EUR 49/month offer (success: >=3 pre-paid commitments at >=2x the EUR 19 anchor; zero means kill).

Not researched in this round: N2 (chargeback evidence), N4 (EU VAT/invoice checks), N6 (refreshed datasets) and the generated combinations; they keep their unresearched-prior scores.
