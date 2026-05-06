import re
import shutil
from pathlib import Path

# ====== 需要你改的 3 个路径 ======
SRC_ROOT = Path(r"D:\lww")                  # 你的下载根目录（原目录）
DST_IMAGES = Path(r"D:\lww_collect\images") # 新的图片汇总目录
DST_VIDEOS = Path(r"D:\lww_collect\videos") # 新的视频汇总目录

# ====== 可选：只处理这些后缀 ======
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VID_EXT = {".mp4", ".mov", ".m4v"}

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def safe_copy(src: Path, dst: Path) -> Path:
    """
    复制到 dst；如果同名已存在，则自动加 _02 / _03 ...
    """
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
    if not SRC_ROOT.exists():
        raise FileNotFoundError(SRC_ROOT)

    DST_IMAGES.mkdir(parents=True, exist_ok=True)
    DST_VIDEOS.mkdir(parents=True, exist_ok=True)

    img_count = 0
    vid_count = 0

    # 遍历：SRC_ROOT / YYYY-MM-DD / mid / images|videos / files
    for date_dir in SRC_ROOT.iterdir():
        if not date_dir.is_dir():
            continue
        date_str = date_dir.name
        if not DATE_RE.match(date_str):
            # 跳过 _failed.txt 等非日期目录
            continue

        for mid_dir in date_dir.iterdir():
            if not mid_dir.is_dir():
                continue
            mid = mid_dir.name

            # 图片
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
                    safe_copy(f, DST_IMAGES / new_name)
                    img_count += 1

            # 视频
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
                    safe_copy(f, DST_VIDEOS / new_name)
                    vid_count += 1

    print("DONE")
    print("images:", img_count, "=>", str(DST_IMAGES))
    print("videos:", vid_count, "=>", str(DST_VIDEOS))

if __name__ == "__main__":
    main()
