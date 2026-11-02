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


if __name__ == "__main__":
    unittest.main()
