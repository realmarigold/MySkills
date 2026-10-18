"""
tests/test_syncer.py - syncer 核心函数单元测试 (零依赖 unittest 运行)
"""

import io
import os
import tarfile
import tempfile
import unittest

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sync"))

from syncer import (
    filter_skills,
    extract_skills_from_tarball,
    extract_single_skill_from_tarball,
    cleanup_skills_dir,
)


class TestSyncer(unittest.TestCase):

    def test_filter_skills_include(self):
        all_skills = ["skill-a", "skill-b", "skill-c"]
        source = {
            "name": "test",
            "mode": "include",
            "include": ["skill-a", "skill-c", "skill-missing"],
        }
        filtered = filter_skills(all_skills, source)
        self.assertEqual(filtered, ["skill-a", "skill-c"])

    def test_filter_skills_exclude(self):
        all_skills = ["skill-a", "skill-b", "skill-c"]
        source = {
            "name": "test",
            "mode": "exclude",
            "exclude": ["skill-b"],
        }
        filtered = filter_skills(all_skills, source)
        self.assertEqual(filtered, ["skill-a", "skill-c"])

    def test_extract_skills_from_tarball_flat(self):
        # 模拟构建一个内存 tar.gz 归档文件
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            data = b"---\nname: my-skill\ndescription: demo\n---\n"
            ti = tarfile.TarInfo("repo-main/skills/engineering/my-skill/SKILL.md")
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))

        tarball_bytes = buf.getvalue()

        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = os.path.join(tmpdir, "skills")
            os.makedirs(skills_dir, exist_ok=True)
            # 预先放置一个模拟 Windows 伪符号链接同名普通文件，验证能被自动替换
            pseudo_symlink = os.path.join(skills_dir, "my-skill")
            with open(pseudo_symlink, "w") as f:
                f.write("anthropics/my-skill")

            extract_skills_from_tarball(
                tarball_bytes=tarball_bytes,
                remote_path="skills/engineering",
                wanted_skills=["my-skill"],
                skills_dir=skills_dir,
            )

            target_file = os.path.join(skills_dir, "my-skill", "SKILL.md")
            self.assertTrue(os.path.isdir(os.path.join(skills_dir, "my-skill")))
            self.assertTrue(os.path.isfile(target_file))
            with open(target_file, "rb") as f:
                self.assertEqual(f.read(), data)

    def test_extract_single_skill_from_tarball(self):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            skill_data = b"---\nname: context-hygiene\ndescription: clean code\n---\n"
            ti1 = tarfile.TarInfo("realmarigold-context-hygiene-abc/SKILL.md")
            ti1.size = len(skill_data)
            tar.addfile(ti1, io.BytesIO(skill_data))

            script_data = b"print('scan')"
            ti2 = tarfile.TarInfo("realmarigold-context-hygiene-abc/scripts/hygiene_scan.py")
            ti2.size = len(script_data)
            tar.addfile(ti2, io.BytesIO(script_data))

            ignored_data = b"ignored"
            ti3 = tarfile.TarInfo("realmarigold-context-hygiene-abc/.github/workflows/ci.yml")
            ti3.size = len(ignored_data)
            tar.addfile(ti3, io.BytesIO(ignored_data))

        tarball_bytes = buf.getvalue()

        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = os.path.join(tmpdir, "skills")
            extract_single_skill_from_tarball(
                tarball_bytes=tarball_bytes,
                remote_path="",
                skill_name="context-hygiene",
                skills_dir=skills_dir,
            )

            self.assertTrue(os.path.isfile(os.path.join(skills_dir, "context-hygiene", "SKILL.md")))
            self.assertTrue(os.path.isfile(os.path.join(skills_dir, "context-hygiene", "scripts", "hygiene_scan.py")))
            self.assertFalse(os.path.exists(os.path.join(skills_dir, "context-hygiene", ".github")))

    def test_cleanup_skills_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. 有效 skill 目录
            valid_skill = os.path.join(tmpdir, "claude-api")
            os.makedirs(valid_skill, exist_ok=True)
            with open(os.path.join(valid_skill, "SKILL.md"), "w") as f:
                f.write("valid")

            # 2. 旧版二级分类目录 (如 anthropics/, my/)
            legacy_source = os.path.join(tmpdir, "anthropics", "claude-api")
            os.makedirs(legacy_source, exist_ok=True)
            legacy_my = os.path.join(tmpdir, "my")
            os.makedirs(legacy_my, exist_ok=True)

            # 3. 过期淘汰的普通文件/伪链接
            stale_file = os.path.join(tmpdir, "old-skill")
            with open(stale_file, "w") as f:
                f.write("anthropics/old-skill")

            cleanup_skills_dir(tmpdir, active_skills={"claude-api"})

            self.assertEqual(os.listdir(tmpdir), ["claude-api"])
            self.assertTrue(os.path.isfile(os.path.join(valid_skill, "SKILL.md")))


if __name__ == "__main__":
    unittest.main()
