import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import sync


class Naming(unittest.TestCase):
    def test_pretty_name(self):
        self.assertEqual(sync.pretty_name("antigravity/claude-sonnet-5-5"), "Claude Sonnet 5.5")
        self.assertEqual(sync.pretty_name("claude/claude-opus-4-20250514"), "Claude Opus 4 (2025-05-14)")

    def test_tag_styles(self):
        m = "antigravity/claude-sonnet-5-5"
        self.assertEqual(sync.tagged_name(m, "prefix"), "[Antigravity] Claude Sonnet 5.5")
        self.assertEqual(sync.tagged_name(m, "short-prefix"), "[AG] Claude Sonnet 5.5")
        self.assertEqual(sync.tagged_name(m, "short-suffix"), "Claude Sonnet 5.5 (AG)")
        self.assertEqual(sync.tagged_name(m, "none"), "Claude Sonnet 5.5")

    def test_unknown_provider_short(self):
        self.assertEqual(sync.provider_short("my-proxy"), "MP")  # initials of the title-cased name
        self.assertEqual(sync.provider_short("openrouter"), "OR")


class Url(unittest.TestCase):
    def test_normalize(self):
        self.assertEqual(sync.normalize_url("192.168.1.20"), "http://192.168.1.20:20128")
        self.assertEqual(sync.normalize_url("http://host:1234/v1/"), "http://host:1234")
        self.assertEqual(sync.normalize_url("localhost"), "http://localhost:20128")


class Grouping(unittest.TestCase):
    CATALOG = {"a/m", "a/m-low", "a/m-high", "a/solo-high"}

    def test_folds_when_base_exists(self):
        e = sync.build_entries(["a/m", "a/m-low", "a/m-high"], self.CATALOG)
        self.assertEqual(len(e), 1)
        self.assertEqual(e[0]["slug"], "a/m")
        opts = [o["id"] for o in e[0]["capabilities"]["optionDescriptors"][0]["options"]]
        self.assertEqual(opts, ["low", "high"])

    def test_no_fold_without_base(self):
        e = sync.build_entries(["a/solo-high"], self.CATALOG)
        self.assertEqual([x["slug"] for x in e], ["a/solo-high"])

    def test_no_group(self):
        e = sync.build_entries(["a/m", "a/m-low"], self.CATALOG, group=False)
        self.assertEqual(len(e), 2)


class AssetLinking(unittest.TestCase):
    def test_link_assets(self):
        import tempfile
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            os.makedirs(os.path.join(src, "skills"))
            os.makedirs(os.path.join(src, "commands"))
            with open(os.path.join(src, "CLAUDE.md"), "w") as f:
                f.write("test")

            linked = sync.link_shared_assets(dst, source_path=src)
            self.assertEqual(sorted(linked), ["CLAUDE.md", "commands", "skills"])
            self.assertTrue(os.path.islink(os.path.join(dst, "skills")))
            self.assertTrue(os.path.islink(os.path.join(dst, "CLAUDE.md")))

            # Re-running does not re-link or fail
            linked2 = sync.link_shared_assets(dst, source_path=src)
            self.assertEqual(linked2, [])

    def test_links_everything_but_local_state(self):
        import tempfile
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            for d in ("plugins/cache", "projects/p1", "sessions", "agents"):
                os.makedirs(os.path.join(src, d))
            for f in ("history.jsonl", "remote-settings.json", "settings.json"):
                open(os.path.join(src, f), "w").close()
            os.makedirs(os.path.join(dst, "plugins", "cache"))
            open(os.path.join(dst, "plugins", "cache", "new.json"), "w").close()  # moved into src
            open(os.path.join(dst, "plugins", "x.json"), "w").close()
            open(os.path.join(src, "plugins", "x.json"), "w").close()  # conflict: kept in .bak
            os.makedirs(os.path.join(dst, "projects", "p2"))
            os.makedirs(os.path.join(dst, "todos"))  # only in dst: moved into src
            os.makedirs(os.path.join(dst, "sessions"))
            os.symlink(src, os.path.join(dst, "agents"))  # user's own link: untouched
            linked = sync.link_shared_assets(dst, source_path=src)
            self.assertEqual(linked, ["history.jsonl", "plugins", "projects", "todos"])
            for item in linked:
                self.assertEqual(os.path.realpath(os.path.join(dst, item)), os.path.realpath(os.path.join(src, item)))
            self.assertTrue(os.path.exists(os.path.join(src, "plugins", "cache", "new.json")))
            self.assertTrue(os.path.isdir(os.path.join(src, "projects", "p2")))
            baks = [n for n in os.listdir(dst) if n.startswith("plugins.bak.")]
            self.assertEqual(os.listdir(os.path.join(dst, baks[0])), ["x.json"])
            self.assertFalse(any(n.startswith("projects.bak.") for n in os.listdir(dst)))
            self.assertFalse(os.path.islink(os.path.join(dst, "sessions")))
            self.assertFalse(os.path.lexists(os.path.join(dst, "remote-settings.json")))
            self.assertEqual(os.readlink(os.path.join(dst, "agents")), src)

    def test_share_settings_keeps_local_keys(self):
        import tempfile
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            sync.write_json_atomic(os.path.join(src, "settings.json"),
                                   {"env": {"A": "src"}, "model": "m1", "enabledPlugins": {"p@m": True}, "theme": "dark"})
            sync.write_json_atomic(os.path.join(dst, "settings.json"), {"env": {"A": "dst"}, "theme": "light"})
            self.assertEqual(sorted(sync.share_settings(dst, source_path=src)), ["enabledPlugins", "theme"])
            got = sync.read_json(os.path.join(dst, "settings.json"))
            self.assertEqual(got, {"env": {"A": "dst"}, "theme": "dark", "enabledPlugins": {"p@m": True}})
            self.assertEqual(sync.share_settings(dst, source_path=src), [])

    def test_promote_synced_skills(self):
        import tempfile
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            typst_dir = os.path.join(src, "skills", "synced", "acc1", "typst")
            os.makedirs(typst_dir)
            with open(os.path.join(typst_dir, "SKILL.md"), "w") as f:
                f.write("---\nname: typst\n---")

            sync.link_shared_assets(dst, source_path=src)
            top_typst = os.path.join(src, "skills", "typst")
            self.assertTrue(os.path.islink(top_typst))
            self.assertEqual(os.path.realpath(top_typst), os.path.realpath(typst_dir))


class CustomModels(unittest.TestCase):
    def test_custom_models_parsed(self):
        import io, json
        from unittest import mock
        body = json.dumps({"models": {"antigravity": [{"id": "gemini-4-argon", "source": "manual"}]}}).encode()
        with mock.patch("urllib.request.urlopen", return_value=io.BytesIO(body)):
            self.assertEqual(sync.fetch_custom_models("http://x", "k"), ["antigravity/gemini-4-argon"])
        with mock.patch("urllib.request.urlopen", side_effect=OSError("down")):
            self.assertEqual(sync.fetch_custom_models("http://x", "k"), [])


if __name__ == "__main__":
    unittest.main()
