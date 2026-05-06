import re
import shutil
import os
from pathlib import Path

from weibo_env import env_path


IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VID_EXT = {".mp4", ".mov", ".m4v"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def safe_copy(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.exists():
        shutil.copy2(src, dst)
        return dst
    stem, suffix = dst.stem, dst.suffix
    for i in range(2, 10000):
        cand = dst.with_name(f"{stem}_{i:02d}{suffix}")
        if not cand.exists():
            shutil.copy2(src, cand)
            return cand
    raise RuntimeError(f"Too many duplicates for {dst.name}")


def main():
    from weibo_bootstrap import ensure_job_env

    ensure_job_env(allow_missing_target=True)
    media_base = Path(os.environ.get("WEIBO_DOWNLOAD_DIR", "media")).expanduser()
    src_root = env_path("WEIBO_COLLECT_SRC", media_base)
    dst_images = env_path("WEIBO_COLLECT_DST_IMAGES", media_base.parent / "collected" / "images")
    dst_videos = env_path("WEIBO_COLLECT_DST_VIDEOS", media_base.parent / "collected" / "videos")

    if not src_root.exists():
        raise FileNotFoundError(src_root)

    dst_images.mkdir(parents=True, exist_ok=True)
    dst_videos.mkdir(parents=True, exist_ok=True)

    img_count = 0
    vid_count = 0

    for date_dir in src_root.iterdir():
        if not date_dir.is_dir():
            continue
        date_str = date_dir.name
        if not DATE_RE.match(date_str):
            continue

        for mid_dir in date_dir.iterdir():
            if not mid_dir.is_dir():
                continue
            mid = mid_dir.name

            images_dir = mid_dir / "images"
            if images_dir.exists():
                files = sorted([p for p in images_dir.iterdir() if p.is_file()])
                seq = 0
                for f in files:
                    ext = f.suffix.lower()
                    if ext not in IMG_EXT:
                        continue
                    seq += 1
                    new_name = f"{date_str}_{mid}_img{seq:03d}{ext}"
                    safe_copy(f, dst_images / new_name)
                    img_count += 1

            videos_dir = mid_dir / "videos"
            if videos_dir.exists():
                files = sorted([p for p in videos_dir.iterdir() if p.is_file()])
                seq = 0
                for f in files:
                    ext = f.suffix.lower()
                    if ext not in VID_EXT:
                        continue
                    seq += 1
                    new_name = f"{date_str}_{mid}_vid{seq:03d}{ext}"
                    safe_copy(f, dst_videos / new_name)
                    vid_count += 1

    print("DONE")
    print("images:", img_count, "=>", str(dst_images))
    print("videos:", vid_count, "=>", str(dst_videos))


if __name__ == "__main__":
    main()
