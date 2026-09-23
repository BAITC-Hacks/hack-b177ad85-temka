# Evaluation report

Date: 2026-09-23  
Revision evaluated: `6fc0149` (`agent.py` is still the organizer template)  
Environment: local mock only; the mock score is not a prediction of the judging score.

## Checks

| Check | Result |
| --- | --- |
| `python local_eval.py` | PASS, exit 0; seed 42 net result `-1,035,279` |
| `python local_eval.py --runs 10` | PASS, exit 0; all 10 seeds negative |
| `python make_submission.py` | PASS, exit 0; generated 2 campaigns |
| Regenerate and compare `submission.csv` | PASS; contents match exactly |
| `python -m py_compile ...` for agent and support modules | PASS, exit 0 |
| Candidate prior integrity | PASS; 12 unique rows, tariff codes valid, audience counts match profile |

## Ten-seed results

`budget left` is the 100,000-unit budget minus the full pilot and final-campaign spend. `Campaigns` counts final campaigns, excluding pilots.

| Seed | Net result | Pilots | Contacts | Spend | Budget left | Campaigns | Largest campaign |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | -1,019,431 | 6 | 5,958 | 23,832 | 76,168 | 2 | 2,950 |
| 1 | -576,204 | 6 | 12,404 | 49,616 | 50,384 | 4 | 4,726 |
| 2 | -338,971 | 6 | 9,786 | 39,144 | 60,856 | 4 | 2,950 |
| 3 | -140,281 | 6 | 900 | 3,600 | 96,400 | 0 | 150 |
| 4 | -1,019,237 | 6 | 5,958 | 23,832 | 76,168 | 2 | 2,950 |
| 5 | -366,964 | 6 | 5,570 | 22,280 | 77,720 | 2 | 2,950 |
| 6 | -320,312 | 6 | 9,454 | 37,816 | 62,184 | 3 | 4,726 |
| 7 | -348,932 | 6 | 7,734 | 30,936 | 69,064 | 2 | 4,726 |
| 8 | -76,493 | 6 | 4,728 | 18,912 | 81,088 | 2 | 2,108 |
| 9 | -601,538 | 6 | 10,684 | 42,736 | 57,264 | 3 | 4,726 |

Summary: median `-357,948`, minimum `-1,019,431`, maximum `-76,493`, positive runs `0/10`. The result stays negative across seeds. This is a weak baseline, not a release-ready strategy.

## Limit checks

All observed runs stayed within the configured limits: 6/20 pilots, at most 12,404/15,000 contacts, at most 49,616/100,000 budget spent, at most 4/10 final campaigns, and at most 4,726/5,000 contacts in a campaign.

For the seed-42 single run, the agent used 6 pilots and 5,570 total contacts. Full strategy spend was 22,280, leaving 77,720; the environment showed 96,400 remaining immediately after pilots and before final campaigns. Net result was `-1,035,279`.

## Candidate prior check

`candidate_prior.csv` has 12 unique current-tariff/ARPU-segment/target-tariff combinations. All tariff codes exist, and all stored audience sizes match counts recomputed from `customer_profile.csv`. Historical estimates are candidate-ranking priors only; pilot results still need to guide final campaign selection.

## Follow-up

The agent needs a better selection and pilot strategy before submission. Integrate and evaluate the candidate prior after its owner hands it off. Also review the unexplained, unused `a = 500` assignment in `mock_environment.py`, introduced in commit `bfffcce`; it has no references and was left untouched during this evaluation.
