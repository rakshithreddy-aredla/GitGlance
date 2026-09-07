"""Tests for GitGlance scoring logic (no network needed - fixtures only)."""

import unittest

import glance


def repo(name, language="Python", size=10000, stars=2, desc="A tool", fork=False):
    return {
        "name": name, "language": language, "size": size,
        "stargazers_count": stars, "description": desc, "fork": fork,
    }


def event(kind, iso):
    return {"type": kind, "created_at": iso}


class TestProjectQuality(unittest.TestCase):
    def test_no_original_repos_scores_zero(self):
        pts, notes = glance.score_project_quality([repo("x", fork=True)])
        self.assertEqual(pts, 0)
        self.assertTrue(any("No original" in n for n in notes))

    def test_full_marks_capped_at_40(self):
        repos = [repo(f"r{i}") for i in range(10)]
        pts, _ = glance.score_project_quality(repos)
        self.assertEqual(pts, 40)

    def test_filler_repos_score_low(self):
        repos = [repo("empty", language=None, size=1, stars=0, desc=None)]
        pts, _ = glance.score_project_quality(repos)
        self.assertLess(pts, 10)

    def test_description_bonus(self):
        with_desc = [repo("a", desc="x"), repo("b", desc="y")]
        without = [repo("a", desc=None), repo("b", desc=None)]
        self.assertGreater(
            glance.score_project_quality(with_desc)[0],
            glance.score_project_quality(without)[0],
        )


class TestConsistency(unittest.TestCase):
    def test_no_events_gets_pity_points_only(self):
        pts, notes = glance.score_consistency([], [])
        self.assertEqual(pts, 5)
        self.assertTrue(any("No recent public activity" in n for n in notes))

    def test_many_active_days_scores_well(self):
        events = [event("PushEvent", f"2026-09-{d:02d}T10:00:00Z") for d in range(1, 11)]
        pts, notes = glance.score_consistency(events, [])
        self.assertEqual(pts, 30)
        self.assertTrue(any("distinct active days" in n for n in notes))


class TestProfileHygiene(unittest.TestCase):
    def test_full_profile(self):
        user = {"login": "dev", "bio": "builder", "location": "Hyderabad", "followers": 15}
        repos = [repo("dev")]
        pts, notes = glance.score_profile_hygiene(user, repos)
        self.assertEqual(pts, 20)
        self.assertTrue(any("profile README" in n for n in notes))

    def test_bare_profile(self):
        user = {"login": "dev", "bio": None, "location": None, "followers": 0}
        pts, notes = glance.score_profile_hygiene(user, [])
        self.assertEqual(pts, 0)


class TestCommunity(unittest.TestCase):
    def test_healthy_ratio_and_blog(self):
        user = {"followers": 30, "following": 10, "blog": "https://dev.example"}
        pts, _ = glance.score_community(user)
        self.assertEqual(pts, 10)

    def test_spammy_follow_pattern(self):
        user = {"followers": 2, "following": 500, "blog": None, "twitter_username": None}
        pts, notes = glance.score_community(user)
        self.assertLess(pts, 5)
        self.assertTrue(any("spammy" in n for n in notes))


if __name__ == "__main__":
    unittest.main()
