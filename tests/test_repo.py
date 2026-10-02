from __future__ import annotations

import unittest

from helpers import make_project, write
from sources import repo

H = "0123456789abcdef"


class ContextPackTest(unittest.TestCase):
    def test_empty_project(self):
        self.assertEqual(repo.context_pack_status(make_project()),
                         {"facts": False, "pending_file": False, "pending_open": 0})

    def test_counts_unchecked_items_only(self):
        project = make_project()
        write(project, "wow/context-pack/facts.md", "# Facts\n")
        write(project, "wow/context-pack/pending-owner.md",
              "- [ ] North Star\n- [x] SLA: [SIN DEFINIR] (accepted)\n  - [ ] rollout\n")
        self.assertEqual(repo.context_pack_status(project),
                         {"facts": True, "pending_file": True, "pending_open": 2})


class PacketTest(unittest.TestCase):
    def test_ok_stale_missing(self):
        project = make_project()
        write(project, "wow/pb/prd.md", f"<!-- wow: manifest-hash={H} template=pb-9b19a89 -->\n# PRD\n")
        write(project, "wow/pb/rfc.md", "<!-- wow: manifest-hash=ffffffffffffffff -->\n")
        write(project, "wow/pb/epic-E1.md", f"<!-- wow: manifest-hash={H} template=pb-9b19a89 -->\n")
        self.assertEqual(repo.packet_status(project, H, ["E1", "E2"]),
                         {"prd": "ok", "rfc": "stale", "epics": {"E1": "ok", "E2": "missing"}})


class SubmoduleTest(unittest.TestCase):
    def test_submodule_paths(self):
        project = make_project()
        write(project, ".gitmodules", '[submodule "a"]\n\tpath = mfe-x\n[submodule "b"]\n  path = bff-x\n')
        self.assertEqual(repo.submodule_paths(project), ["mfe-x", "bff-x"])
        self.assertEqual(repo.submodule_paths(make_project()), [])


class PacketTemplateTest(unittest.TestCase):
    def test_template_id_required(self):
        project = make_project()
        write(project, "wow/pb/prd.md", f"<!-- wow: manifest-hash={H} template=pb-9b19a89 -->\n")
        write(project, "wow/pb/rfc.md", f"<!-- wow: manifest-hash={H} -->\n")
        status = repo.packet_status(project, H, [])
        self.assertEqual((status["prd"], status["rfc"]), ("ok", "stale"))

    def test_pending_items(self):
        project = make_project()
        write(project, "wow/context-pack/pending-owner.md", "- [ ] North Star\n- [x] SLA\n  - [ ] rollout\n")
        self.assertEqual(repo.pending_items(project), ["North Star", "rollout"])


class ChildReposTest(unittest.TestCase):
    def test_nested_repos_up_to_three_levels_skipping_noise(self):
        project = make_project()
        write(project, "engine/prism-group/.git/HEAD", "ref: refs/heads/main\n")
        write(project, "engine/prism-analyzer/.git", "gitdir: ../prism-group/.git/worktrees/x\n")
        write(project, "product/dora-group/platform-dora-bff/.git/HEAD", "x")
        write(project, "product/dora-group/platform-dora-bff/vendor/inner/.git/HEAD", "x")
        write(project, "product/catalog/.history/.git/HEAD", "x")
        write(project, "node_modules/pkg/.git/HEAD", "x")
        write(project, "a/b/c/d/.git/HEAD", "x")
        self.assertEqual(repo.child_repos(project), [
            "engine/prism-analyzer", "engine/prism-group", "product/dora-group/platform-dora-bff"])

    def test_submodules_are_included_and_project_root_is_not(self):
        project = make_project()
        write(project, ".git/HEAD", "x")
        write(project, ".gitmodules", '[submodule "a"]\n\tpath = deep/x/y/z\n')
        write(project, "deep/x/y/z/.git", "gitdir: x\n")
        self.assertEqual(repo.child_repos(project), ["deep/x/y/z"])


if __name__ == "__main__":
    unittest.main()
