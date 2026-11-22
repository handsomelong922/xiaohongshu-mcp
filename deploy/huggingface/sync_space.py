"""Publish this fork to the existing Hugging Face Docker Space.

This script only changes the *staging directory*, never files checked out from
upstream. The fork can continue receiving upstream changes via Sync fork.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

DEFAULT_SPACE = "handsomelong325/dots-mcp"

# Keep the Space source minimal and avoid uploading workflow definitions,
# local account state, and unrelated documentation. Only tracked files are used.
SKIP_DIRS = (
    ".github/",
    ".cursor/",
    ".vscode/",
    "deploy/",
    "docs/",
    "donate/",
    "examples/",
    "skills/",
)
SKIP_FILES = {
    ".env",
    ".env.example",
    ".gitignore",
    "AGENTS.md",
    "CLAUDE.md",
    "CONTRIBUTING.md",
    "DONATIONS.md",
    "README_EN.md",
    ".session.json",
    "cookies.json",
}


def tracked_files(root: Path) -> list[Path]:
    output = subprocess.check_output(["git", "ls-files", "-z"], cwd=root)
    return [Path(path.decode("utf-8")) for path in output.split(b"\x00") if path]


def should_copy(path: Path) -> bool:
    relative = path.as_posix()
    if relative in SKIP_FILES or relative.endswith("_test.go"):
        return False
    if relative.startswith(SKIP_DIRS):
        return False
    if relative.startswith(".browser_data/") or relative.startswith("data/"):
        return False
    if path.name.startswith(".env.") or path.name in {".session.json", "cookies.json"}:
        return False
    if path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
        return False
    return True


def prepare_stage(root: Path, destination: Path) -> list[str]:
    copied = []
    for path in tracked_files(root):
        source = root / path
        if not should_copy(path) or not source.is_file() or source.is_symlink():
            continue
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        copied.append(path.as_posix())

    # Use the actual forked Go project and its original Dockerfile, but route
    # the new XHS login state into the pre-existing HF /data persistent volume.
    dockerfile = destination / "Dockerfile"
    original = dockerfile.read_text(encoding="utf-8")
    marker = "ENV HOME=/app/data/home\nENV XDG_CONFIG_HOME=/app/data/config"
    if original.count(marker) != 1:
        raise RuntimeError(
            "Upstream Dockerfile layout changed; update HF environment overlay "
            "before deployment. No Space files have been modified."
        )
    dockerfile.write_text(
        original.replace(
            marker,
            "ENV HOME=/data/home\n"
            "ENV XDG_CONFIG_HOME=/data/config\n"
            "ENV COOKIES_PATH=/data/cookies.json",
        ),
        encoding="utf-8",
    )

    # Hugging Face reads metadata from the root README, not from an extra file.
    card = root / "deploy" / "huggingface" / "README.space.md"
    shutil.copyfile(card, destination / "README.md")
    required = ["Dockerfile", "go.mod", "go.sum", "main.go", "browser/browser_version.txt"]
    missing = [name for name in required if not (destination / name).is_file()]
    if missing:
        raise RuntimeError(f"Fork is missing required build files: {missing}")
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description="Deploy the fork to Hugging Face Spaces")
    parser.add_argument("--dry-run", action="store_true", help="Prepare and validate locally only")
    parser.add_argument("--output", type=Path, help="Keep prepared files in this directory in dry-run mode")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    space_id = os.environ.get("HF_SPACE_ID", DEFAULT_SPACE).strip()
    if space_id != DEFAULT_SPACE:
        raise RuntimeError(f"Refusing unexpected Space target: {space_id!r}")

    with tempfile.TemporaryDirectory(prefix="xiaohongshu-hf-") as temporary:
        stage = Path(temporary) / "space"
        stage.mkdir()
        copied = prepare_stage(root, stage)
        print(f"Prepared {len(copied)} tracked source files for {space_id}")
        print("Docker MCP port: 18060; persisted login: /data/cookies.json")

        if args.dry_run:
            if args.output:
                if args.output.exists():
                    raise FileExistsError(f"Output directory already exists: {args.output}")
                shutil.copytree(stage, args.output)
            print("Dry-run complete: no remote changes made")
            return

        token = os.environ.get("HF_TOKEN", "").strip()
        if not token:
            raise RuntimeError("Missing GitHub Actions secret HF_TOKEN")

        # Imported lazily so the dry-run doesn't need any network dependencies.
        from huggingface_hub import HfApi

        api = HfApi(token=token)
        space = api.space_info(repo_id=space_id)
        if not space.private:
            raise RuntimeError(
                "The target HF Space must be Private before deployment: "
                "this MCP can post, like, and comment on your XHS account."
            )
        if space.sdk and space.sdk != "docker":
            raise RuntimeError(f"Existing Space SDK is not Docker: {space.sdk!r}")

        revision = subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=root, text=True
        ).strip()
        commit = api.upload_folder(
            repo_id=space_id,
            repo_type="space",
            folder_path=str(stage),
            # Explicitly remove all old dots.ai/Playwright files on first
            # replacement, and stale files from subsequent upstream syncs.
            delete_patterns=["*", "**/*"],
            commit_message=f"Deploy xiaohongshu-mcp fork {revision}",
        )
        print(f"Published to {space_id}: {commit.commit_url}")
        print(f"MCP URL: https://handsomelong325-dots-mcp.hf.space/mcp")
        print("Verify HF build logs and scan XHS login QR code on first deployment")


if __name__ == "__main__":
    main()
