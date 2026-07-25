"""
tests/test_syncer.py - syncer 核心函数单元测试 (零依赖 unittest 运行)
"""

import io
import os
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sync"))

from syncer import (
    filter_skills,
    extract_skills_from_tarball,
    build_favorites,
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

    def test_extract_skills_from_tarball(self):
        # 模拟构建一个内存 tar.gz 归档文件
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            data = b"name: test-skill\ndescription: demo"
            ti = tarfile.TarInfo("repo-main/skills/my-skill/SKILL.md")
            ti.size = len(data)
            tar.addfile(ti, io.BytesIO(data))

        tarball_bytes = buf.getvalue()

        with tempfile.TemporaryDirectory() as tmpdir:
            source_dir = os.path.join(tmpdir, "test-source")
            extract_skills_from_tarball(
                tarball_bytes=tarball_bytes,
                remote_path="skills",
                wanted_skills=["my-skill"],
                source_dir=source_dir,
            )

            target_file = os.path.join(source_dir, "my-skill", "SKILL.md")
            self.assertTrue(os.path.isfile(target_file))
            with open(target_file, "rb") as f:
                self.assertEqual(f.read(), data)

    def test_build_favorites_normal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_skill_dir = os.path.join(tmpdir, "anthropics", "claude-api")
            os.makedirs(source_skill_dir, exist_ok=True)
            with open(os.path.join(source_skill_dir, "SKILL.md"), "w") as f:
                f.write("test")

            favorites = [
                {"source": "anthropics", "skills": ["claude-api"]}
            ]

            build_favorites(favorites, tmpdir)

            my_skill_path = os.path.join(tmpdir, "claude-api")
            self.assertTrue(os.path.exists(my_skill_path))
            self.assertTrue(os.path.isfile(os.path.join(my_skill_path, "SKILL.md")))

    def test_build_favorites_fallback(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            source_skill_dir = os.path.join(tmpdir, "anthropics", "claude-api")
            os.makedirs(source_skill_dir, exist_ok=True)
            with open(os.path.join(source_skill_dir, "SKILL.md"), "w") as f:
                f.write("test content")

            favorites = [
                {"source": "anthropics", "skills": ["claude-api"]}
            ]

            with patch("os.symlink", side_effect=PermissionError("Symlink not allowed")):
                build_favorites(favorites, tmpdir)

            my_skill_path = os.path.join(tmpdir, "claude-api")
            self.assertTrue(os.path.isdir(my_skill_path))
            self.assertFalse(os.path.islink(my_skill_path))
            with open(os.path.join(my_skill_path, "SKILL.md"), "r") as f:
                self.assertEqual(f.read(), "test content")


if __name__ == "__main__":
    unittest.main()
