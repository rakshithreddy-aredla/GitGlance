#!/usr/bin/env python3
"""GitGlance - Score any GitHub profile for hackathon/selection readiness.

Usage:
    python glance.py <username> [--json]

Fetches public profile + repo data from the GitHub REST API (no token needed
for public data; respects rate limits) and prints a scored report:

  - Project Quality  (40 pts): real code vs filler, languages, stars, forks
  - Consistency      (30 pts): commit activity spread over the last year
  - Profile Hygiene  (20 pts): bio, location, pinned work, README presence
  - Community        (10 pts): followers, following ratio, public events

The scoring rules are transparent and printed with the report, so you always
know exactly what to fix next.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
UA = "GitGlance/1.0 (+https://github.com/rakshithreddy-aredla/GitGlance)"


def get(path: str) -> object:
    """GET <API>/<path> with a polite UA and simple retry on rate limit."""
    req = urllib.request.Request(f"{API}/{path}", headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as res:
                return json.loads(res.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (403, 429) and attempt < 2:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError(f"failed to fetch {path}")


def fetch_user(username: str) -> dict:
    return get(f"users/{username}")


def fetch_repos(username: str) -> list:
    repos, page = [], 1
    while True:
        batch = get(f"users/{username}/repos?per_page=100&page={page}")
        if not batch:
            break
        repos.extend(batch)
        page += 1
        if len(repos) >= 400:
            break
    return repos


def fetch_events(username: str) -> list:
    try:
        return get(f"users/{username}/events/public")
    except Exception:
        return []


# ---------------------------------------------------------------- scoring ---

def score_project_quality(repos: list) -> tuple[int, list]:
    """40 pts. Rewards real projects (size, language, structure) over filler."""
    pts, notes = 0, []
    originals = [r for r in repos if not r["fork"]]
    if not originals:
        return 0, ["No original (non-fork) public repos."]

    has_code = [r for r in originals if r["language"]]
    pts += min(len(has_code), 6) * 2          # up to 12: breadth of real code
    if len(has_code) >= 4:
        notes.append(f"{len(has_code)} original repos with code")

    big = [r for r in has_code if r["size"] > 5000]  # ~ >5MB of working code
    pts += min(len(big), 3) * 4              # up to 12: substantial projects
    if big:
        notes.append(f"{len(big)} substantial repos: {', '.join(r['name'] for r in big[:3])}")

    starred = [r for r in has_code if r["stargazers_count"] > 0]
    pts += min(len(starred), 4) * 2          # up to 8: external validation
    if starred:
        notes.append(f"starred: {', '.join(r['name'] for r in starred[:3])}")

    with_desc = [r for r in originals if r["description"]]
    pts += min(len(with_desc), 4) * 2        # up to 8: clear descriptions
    missing = [r["name"] for r in originals if not r["description"]]
    if missing:
        notes.append(f"repos missing description: {', '.join(missing[:4])}")
    else:
        notes.append("all repos have descriptions")

    if (pts, notes) == (0, []):
        notes.append("original repos exist but look like filler (no code/stars)")
    return min(pts, 40), notes


def score_consistency(events: list, repos: list) -> tuple[int, list]:
    """30 pts. Rewards steady activity over the last ~90 days of public events."""
    pts, notes = 0, []
    if not events:
        return 5, ["No recent public activity visible (private-commits don't count here)."]

    now = time.time()
    pushes = [e for e in events if e["type"] == "PushEvent"]
    days = {e["created_at"][:10] for e in events}
    recent_90 = {e["created_at"][:10] for e in events if now - 86400 * 90 <= _epoch(e["created_at"])}

    pts += min(len(days), 10) * 2            # up to 20: active distinct days
    pts += min(len(pushes), 20)              # up to 20... capped below
    pts = min(pts, 30)

    notes.append(f"{len(days)} distinct active days in recent public events")
    notes.append(f"{len(recent_90)} of those days fall within the last 90 days")
    if pushes:
        notes.append(f"{len(pushes)} recent push events")
    return pts, notes


def _epoch(iso: str) -> float:
    import datetime as dt
    return dt.datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").timestamp()


def score_profile_hygiene(user: dict, repos: list) -> tuple[int, list]:
    """20 pts. Bio, location, profile README, pinned-style showcase."""
    pts, notes = 0, []
    if user.get("bio"):
        pts += 5
        notes.append("bio present")
    else:
        notes.append("no bio (add one in 1 line)")
    if user.get("location"):
        pts += 3
        notes.append(f"location: {user['location']}")
    else:
        notes.append("no location (matters for city-based selection)")
    login = user["login"]
    readme_repos = [r for r in repos if r["name"].lower() == login.lower()]
    if readme_repos:
        pts += 6
        notes.append("profile README repo exists")
    else:
        notes.append(f"no {login}/{login} profile README repo")
    followers = user.get("followers", 0)
    if followers >= 10:
        pts += 6
        notes.append(f"{followers} followers")
    elif followers >= 3:
        pts += 3
        notes.append(f"{followers} followers")
    else:
        notes.append("few followers - contribute & connect to grow this")
    return min(pts, 20), notes


def score_community(user: dict) -> tuple[int, list]:
    """10 pts. Following pattern sanity + a nudge toward collaboration."""
    pts, notes = 0, []
    followers, following = user.get("followers", 0), user.get("following", 0)
    if following == 0:
        # neutral state: follows nobody - neither spammy nor established
        pts += 4 if followers >= 10 else 2
        notes.append("follows no one - neutral follow pattern")
    else:
        ratio = followers / max(following, 1)
        if ratio >= 1:
            pts += 4
            notes.append("follower/following ratio healthy (>= 1)")
        else:
            notes.append("following many more than followers - looks spammy")
    if followers >= 20:
        pts += 4
        notes.append(f"{followers} followers")
    elif followers >= 5:
        pts += 2
        notes.append(f"{followers} followers - growing")
    if user.get("blog") or user.get("twitter_username"):
        pts += 2
        notes.append("personal site/social link present")
    return min(pts, 10), notes


# ---------------------------------------------------------------- report ---

def render(username: str, user: dict, repos: list, events: list, scores: dict) -> str:
    total = scores["total"]
    band = (
        "EXCELLENT" if total >= 80 else
        "GOOD" if total >= 60 else
        "FAIR" if total >= 40 else
        "NEEDS WORK"
    )
    lines = []
    lines.append("")
    lines.append(f"  GitGlance report: @{username}")
    lines.append(f"  {'=' * (20 + len(username))}")
    lines.append(f"  Name:      {user.get('name') or '-'}")
    lines.append(f"  Bio:       {user.get('bio') or '-'}")
    lines.append(f"  Location:  {user.get('location') or '-'}")
    lines.append(f"  Repos:     {user.get('public_repos')} public ({sum(1 for r in repos if not r['fork'])} original, {sum(1 for r in repos if r['fork'])} forks)")
    lines.append(f"  Followers: {user.get('followers')}")
    lines.append("")
    lines.append(f"  TOTAL SCORE: {total}/100  [{band}]")
    lines.append("")
    for key, (label, max_pts) in {
        "project_quality": ("Project Quality", 40),
        "consistency": ("Consistency", 30),
        "profile_hygiene": ("Profile Hygiene", 20),
        "community": ("Community", 10),
    }.items():
        got, notes = scores[key]
        bar = "#" * round(got / max_pts * 10)
        lines.append(f"  {label:<16} {got:>3}/{max_pts}  [{bar:<10}]")
        for n in notes:
            lines.append(f"      - {n}")
    lines.append("")
    lines.append("  Fix highest-impact items first: real projects with descriptions,")
    lines.append("  then steady public commits. Re-run GitGlance after each change.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(prog="glance.py", description="Score a GitHub profile for hackathon readiness.")
    parser.add_argument("username", help="GitHub username to score")
    parser.add_argument("--json", action="store_true", help="output JSON instead of text")
    args = parser.parse_args()

    try:
        user = fetch_user(args.username)
        repos = fetch_repos(args.username)
        events = fetch_events(args.username)
    except urllib.error.HTTPError as e:
        print(f"error: GitHub API returned {e.code} for {args.username}", file=sys.stderr)
        return 1
    except (urllib.error.URLError, RuntimeError) as e:
        print(f"error: could not reach GitHub: {e}", file=sys.stderr)
        return 1

    pq_pts, pq_notes = score_project_quality(repos)
    co_pts, co_notes = score_consistency(events, repos)
    ph_pts, ph_notes = score_profile_hygiene(user, repos)
    cm_pts, cm_notes = score_community(user)

    scores = {
        "total": pq_pts + co_pts + ph_pts + cm_pts,
        "project_quality": (pq_pts, pq_notes),
        "consistency": (co_pts, co_notes),
        "profile_hygiene": (ph_pts, ph_notes),
        "community": (cm_pts, cm_notes),
    }

    if args.json:
        print(json.dumps({
            "username": args.username,
            "total": scores["total"],
            **{k: {"points": v[0], "notes": v[1]} for k, v in scores.items() if k != "total"},
        }, indent=2))
    else:
        print(render(args.username, user, repos, events, scores))
    return 0


if __name__ == "__main__":
    sys.exit(main())
