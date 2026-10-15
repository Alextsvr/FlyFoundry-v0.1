## Phase 1 idea ranking (layer C: curated priors, NOT evidence)

117,600 candidate tuples (11,300 removed by hard gates / forbidden pairs). Score = weighted mean of 13 criteria under 5 weight sets, rescaled 0..1. Component values are judgement priors written once and not yet checked against sources.

### Exact top 25 (exhaustive; mean over the 5 weight sets)

| # | customer | problem | solution | revenue | channel | mean | worst set | rank range | legal check |
|---|---|---|---|---|---|---|---|---|---|
| 1 | small marketing agencies | duplicate and error detection in records | automated checker / validator | monthly subscription | partner referral | 0.699 | 0.671 | 4-149 |  |
| 2 | solo SaaS founders | duplicate and error detection in records | document parser and converter | monthly subscription | partner referral | 0.699 | 0.671 | 5-112 |  |
| 3 | small marketing agencies | duplicate and error detection in records | document parser and converter | monthly subscription | partner referral | 0.699 | 0.671 | 5-161 |  |
| 4 | solo SaaS founders | duplicate and error detection in records | automated checker / validator | monthly subscription | partner referral | 0.699 | 0.671 | 1-100 |  |
| 5 | small marketing agencies | duplicate and error detection in records | curated public-data digest | monthly subscription | partner referral | 0.698 | 0.677 | 1-245 |  |
| 6 | solo SaaS founders | duplicate and error detection in records | curated public-data digest | monthly subscription | partner referral | 0.698 | 0.677 | 2-195 |  |
| 7 | small marketing agencies | duplicate and error detection in records | API / data product | monthly subscription | partner referral | 0.691 | 0.640 | 1-1954 |  |
| 8 | solo SaaS founders | duplicate and error detection in records | API / data product | monthly subscription | partner referral | 0.691 | 0.640 | 4-2330 |  |
| 9 | small marketing agencies | duplicate and error detection in records | document parser and converter | usage-based fee | partner referral | 0.690 | 0.665 | 17-310 |  |
| 10 | solo SaaS founders | duplicate and error detection in records | automated checker / validator | usage-based fee | partner referral | 0.690 | 0.665 | 8-313 |  |
| 11 | solo SaaS founders | duplicate and error detection in records | document parser and converter | usage-based fee | partner referral | 0.690 | 0.665 | 7-235 |  |
| 12 | small marketing agencies | duplicate and error detection in records | automated checker / validator | usage-based fee | partner referral | 0.690 | 0.665 | 11-255 |  |
| 13 | small marketing agencies | tender and grant discovery | document parser and converter | monthly subscription | partner referral | 0.690 | 0.659 | 8-370 |  |
| 14 | solo SaaS founders | tender and grant discovery | automated checker / validator | monthly subscription | partner referral | 0.690 | 0.659 | 7-390 |  |
| 15 | solo SaaS founders | tender and grant discovery | document parser and converter | monthly subscription | partner referral | 0.690 | 0.659 | 4-384 |  |
| 16 | small marketing agencies | tender and grant discovery | automated checker / validator | monthly subscription | partner referral | 0.690 | 0.659 | 5-393 |  |
| 17 | small marketing agencies | duplicate and error detection in records | reconciliation engine | monthly subscription | partner referral | 0.689 | 0.646 | 19-1711 |  |
| 18 | solo SaaS founders | duplicate and error detection in records | reconciliation engine | monthly subscription | partner referral | 0.689 | 0.646 | 17-1458 |  |
| 19 | solo SaaS founders | manual reconciliation of data | automated checker / validator | monthly subscription | partner referral | 0.689 | 0.671 | 7-307 |  |
| 20 | solo SaaS founders | manual reconciliation of data | document parser and converter | monthly subscription | partner referral | 0.689 | 0.671 | 6-296 |  |
| 21 | small marketing agencies | manual reconciliation of data | automated checker / validator | monthly subscription | partner referral | 0.689 | 0.671 | 9-290 |  |
| 22 | small marketing agencies | manual reconciliation of data | document parser and converter | monthly subscription | partner referral | 0.689 | 0.671 | 11-328 |  |
| 23 | small marketing agencies | duplicate and error detection in records | curated public-data digest | usage-based fee | partner referral | 0.689 | 0.671 | 10-659 |  |
| 24 | solo SaaS founders | duplicate and error detection in records | curated public-data digest | usage-based fee | partner referral | 0.689 | 0.671 | 9-766 |  |
| 25 | solo SaaS founders | tender and grant discovery | curated public-data digest | monthly subscription | partner referral | 0.689 | 0.665 | 6-818 |  |

### Owner-fit overlay: top 25 inside the owner's domain (owner profile: payments / reconciliation / settlement cycle, iGaming merchants, Python parsing of xlsx/PDF/CSV. Reported as an overlay, never mixed into the score.)

| # | customer | problem | solution | revenue | channel | mean | legal check |
|---|---|---|---|---|---|---|---|
| 1 | independent accountants | manual reconciliation of data | automated checker / validator | monthly subscription | partner referral | 0.679 |  |
| 2 | bookkeeping firms | manual reconciliation of data | automated checker / validator | monthly subscription | partner referral | 0.679 |  |
| 3 | bookkeeping firms | manual reconciliation of data | document parser and converter | monthly subscription | partner referral | 0.679 |  |
| 4 | independent accountants | manual reconciliation of data | document parser and converter | monthly subscription | partner referral | 0.679 |  |
| 5 | bookkeeping firms | manual reconciliation of data | curated public-data digest | monthly subscription | partner referral | 0.678 |  |
| 6 | independent accountants | manual reconciliation of data | curated public-data digest | monthly subscription | partner referral | 0.678 |  |
| 7 | bookkeeping firms | recurring report generation | automated checker / validator | monthly subscription | partner referral | 0.672 |  |
| 8 | bookkeeping firms | recurring report generation | document parser and converter | monthly subscription | partner referral | 0.672 |  |
| 9 | independent accountants | recurring report generation | document parser and converter | monthly subscription | partner referral | 0.672 |  |
| 10 | independent accountants | recurring report generation | automated checker / validator | monthly subscription | partner referral | 0.672 |  |
| 11 | bookkeeping firms | manual reconciliation of data | API / data product | monthly subscription | partner referral | 0.672 |  |
| 12 | independent accountants | manual reconciliation of data | API / data product | monthly subscription | partner referral | 0.672 |  |
| 13 | bookkeeping firms | recurring report generation | curated public-data digest | monthly subscription | partner referral | 0.671 |  |
| 14 | independent accountants | recurring report generation | curated public-data digest | monthly subscription | partner referral | 0.671 |  |
| 15 | bookkeeping firms | manual reconciliation of data | automated checker / validator | usage-based fee | partner referral | 0.671 |  |
| 16 | independent accountants | manual reconciliation of data | document parser and converter | usage-based fee | partner referral | 0.671 |  |
| 17 | independent accountants | manual reconciliation of data | automated checker / validator | usage-based fee | partner referral | 0.671 |  |
| 18 | bookkeeping firms | manual reconciliation of data | document parser and converter | usage-based fee | partner referral | 0.671 |  |
| 19 | bookkeeping firms | manual reconciliation of data | reconciliation engine | monthly subscription | partner referral | 0.670 |  |
| 20 | independent accountants | manual reconciliation of data | reconciliation engine | monthly subscription | partner referral | 0.670 |  |
| 21 | bookkeeping firms | manual reconciliation of data | curated public-data digest | usage-based fee | partner referral | 0.670 |  |
| 22 | independent accountants | manual reconciliation of data | curated public-data digest | usage-based fee | partner referral | 0.670 |  |
| 23 | bookkeeping firms | manual reconciliation of data | automated checker / validator | monthly subscription | marketplace listing | 0.670 |  |
| 24 | independent accountants | manual reconciliation of data | document parser and converter | monthly subscription | marketplace listing | 0.670 |  |
| 25 | bookkeeping firms | manual reconciliation of data | document parser and converter | monthly subscription | marketplace listing | 0.670 |  |

### Best candidate per problem type (diversity view)

| problem | best combination | mean |
|---|---|---|
| duplicate and error detection in records | small marketing agencies / automated checker / validator / monthly subscription / partner referral | 0.699 |
| tender and grant discovery | small marketing agencies / document parser and converter / monthly subscription / partner referral | 0.690 |
| manual reconciliation of data | solo SaaS founders / automated checker / validator / monthly subscription / partner referral | 0.689 |
| recurring report generation | solo SaaS founders / document parser and converter / monthly subscription / partner referral | 0.682 |
| deadline and compliance tracking | small marketing agencies / document parser and converter / monthly subscription / marketplace listing | 0.675 |
| invoice and document data extraction | solo SaaS founders / document parser and converter / monthly subscription / partner referral | 0.675 |
| licence and registry monitoring | solo SaaS founders / automated checker / validator / monthly subscription / partner referral | 0.664 |
| regulatory change monitoring | small marketing agencies / automated checker / validator / monthly subscription / partner referral | 0.664 |
| market data digests and benchmarks | solo SaaS founders / document parser and converter / monthly subscription / partner referral | 0.661 |
| fee and overcharge auditing | small marketing agencies / document parser and converter / monthly subscription / partner referral | 0.646 |
| data cleanup and normalization | solo SaaS founders / automated checker / validator / monthly subscription / partner referral | 0.638 |
| lead discovery from public registries | small marketing agencies / automated checker / validator / monthly subscription / marketplace listing | 0.630 |
| subscription churn analysis | small marketing agencies / automated checker / validator / monthly subscription / partner referral | 0.628 |
| fragmented supplier information | solo SaaS founders / document parser and converter / monthly subscription / partner referral | 0.622 |
| fraud and anomaly flagging | small marketing agencies / automated checker / validator / monthly subscription / marketplace listing | 0.620 |
| tax and VAT data validation | solo SaaS founders / automated checker / validator / monthly subscription / marketplace listing | 0.610 |
| document localisation and translation workflow | small marketing agencies / document parser and converter / monthly subscription / partner referral | 0.608 |

### What the swarm added

10 islands x 100 x 60 gens = 60,000 evaluations, 20 repeats. Recall of the exact top-50: swarm 19% (worst 12%) vs random sampling with the same budget 37%. The space is small enough to enumerate, so enumeration is the authoritative ranking; the swarm is a consistency check, not a source of new ideas: it can only recombine the components written into the taxonomy.

### Named seed ideas under the same fitness

Seeds carry their own criterion vectors (H01-H12: three-track research; N1-N7, R1: priors or one-pass desk research, see confidence column), so their scores are NOT on the same footing as averaged components. Compare seeds with seeds.

| id | idea | confidence | mean | percentile vs generated | owner conflict-of-interest |
|---|---|---|---|---|---|
| H07 | Reconciliation Rescue | researched (3 tracks) | 0.717 | 100% | check: reconciliation rescue: synthesis already required a contract / moonlighting / non-compete check |
| H01 | Tender / RFP Scout | researched (3 tracks) | 0.645 | 98% |  |
| N5 | Licence and registry change monitoring (PSP licences etc.) | desk-researched 2026-10-15 (single pass, unverified) | 0.567 | 54% | check: licence monitoring: buyers include payment providers and merchants; check overlap with the employer's business |
| H05 | Public-Registry Trigger Leads | researched (3 tracks) | 0.550 | 39% |  |
| N6 | Regularly refreshed datasets (registry diffs / list diffs) | unresearched prior | 0.541 | 32% |  |
| H12 | B2B Intent Radar | researched (3 tracks) | 0.538 | 30% |  |
| N7 | Niche tender alerts (one sector or region) | desk-researched 2026-10-15 (single pass, unverified) | 0.521 | 18% |  |
| H06 | Website Problem -> Lead | researched (3 tracks) | 0.497 | 6% |  |
| R1 | Reconciliation / validation tool for small accounting and bookkeeping firms | desk-researched 2026-10-15 (single pass, unverified) | 0.473 | 1% | check: accounting firms serve merchants indirectly; use no employer data or employer-derived formats |
| N4 | EU invoice / VAT data checks for small e-commerce | unresearched prior | 0.467 | 1% |  |
| H11 | Grant / Subsidy Matcher | researched (3 tracks) | 0.451 | 0% |  |
| H09 | Distressed Asset Intelligence | researched (3 tracks) | 0.413 | 0% |  |
| H02 | Award -> Sub Intelligence | researched (3 tracks) | 0.409 | 0% |  |
| H08 | Catalogue / Compatibility Cleanup | researched (3 tracks) | 0.396 | 0% |  |
| H04 | B2B Quote Concierge | researched (3 tracks) | 0.371 | 0% |  |
| H10 | Marketplace Price-Anomaly | researched (3 tracks) | 0.362 | 0% |  |
| H03 | Rare Parts Sourcing | researched (3 tracks) | 0.211 | 0% |  |
| N3 | PSP settlement-report converters (template or small SaaS) | desk-researched 2026-10-15 (single pass, unverified) | 0.492 | 4% | GATED: PSP settlement converters sold to PSP merchants / their finance staff: direct merchant exposure unless sold only to accountants and with no employer-derived knowledge |
| N2 | Chargeback evidence packer | unresearched prior | 0.460 | 0% | GATED: builds chargeback evidence for merchants: direct merchant exposure |
| N1 | PSP fee / overcharge audit (success fee) | desk-researched 2026-10-15 (single pass, unverified) | 0.395 | 0% | GATED: audits merchants' payment-provider fees: direct merchant exposure |
