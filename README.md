# GitGlance

**Score any GitHub profile for hackathon-readiness in one command.**

GitGlance analyzes a GitHub profile the way selection committees do — real projects vs filler, commit consistency, profile hygiene, and community signals — and prints a transparent 100-point report with exact fixes.

```
$ python glance.py rakshithreddy-aredla

  GitGlance report: @rakshithreddy-aredla
  =======================================

  TOTAL SCORE: 78/100  [GOOD]

  Project Quality    34/40  [######### ]
      - 4 original repos with code
      - 2 substantial repos: Arkaira, EnvGuard
      ...
```

## Why

Selection processes that rank by GitHub profile look past stars. GitGlance encodes those rules explicitly, so you know what to fix next instead of guessing.

## Scoring model

| Category | Points | What counts |
|---|---|---|
| Project Quality | 40 | Original repos with real code (>5MB), clear descriptions, stars |
| Consistency | 30 | Distinct active days + push events in public activity |
| Profile Hygiene | 20 | Bio, location, profile README repo, follower base |
| Community | 10 | Healthy follower/following ratio, personal site link |

## Install & use

Requires Python 3.10+ and nothing else — zero dependencies, stdlib only.

```bash
git clone https://github.com/rakshithreddy-aredla/GitGlance.git
cd GitGlance
python glance.py <any-github-username>        # text report
python glance.py <username> --json            # machine-readable
```

Works without a token for public data; auto-retries on rate limits.

## How it works

1. `glance.py` fetches public user, repo, and event data via the GitHub REST API.
2. Four independent scorers (`score_project_quality`, `score_consistency`, `score_profile_hygiene`, `score_community`) each return points + human-readable notes explaining every deduction.
3. The report sorts fixes by impact: substantial projects first, then steady public commits.

## Testing

```bash
python -m unittest test_glance.py -v
```

24 assertions covering all scorers, caps, and edge cases (empty profiles, filler repos, rate limits).

## Roadmap

- [ ] Trend analysis: score over time, not just a snapshot
- [ ] Language diversity weighting
- [ ] Output as a shareable SVG card

## License

MIT © Rakshith Reddy Aredla
