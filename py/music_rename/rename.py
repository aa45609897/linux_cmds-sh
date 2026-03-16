from pathlib import Path
import re
import csv
import subprocess
from difflib import SequenceMatcher
from datetime import datetime

BASE_DIR = Path.cwd()
ORIGIN_DIR = BASE_DIR / "origin"
GENERATE_DIR = BASE_DIR / "generate"
CSV_PATH = BASE_DIR / "process_result.csv"

AUDIO_EXTS = {".mp3", ".mp4", ".m4a"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png"}

MATCH_THRESHOLD = 0.35


def remove_date_suffix(name: str) -> str:
    return re.sub(r'(-\d{8,14})+$', '', name).strip(" -_")


def normalize_for_match(name: str) -> str:
    s = remove_date_suffix(name)
    s = re.sub(r'^封面-+', '', s)
    s = s.lower()
    s = re.sub(r'[\s_\-—–·丨|【】\[\]（）()《》!！?？:：,.，。]+', '', s)
    return s


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def find_best_cover(audio_file: Path, image_files: list[Path]):
    audio_key = normalize_for_match(audio_file.stem)

    best_file = None
    best_score = 0.0

    for img in image_files:
        img_key = normalize_for_match(img.stem)
        score = similarity(audio_key, img_key)

        if audio_key and img_key and (audio_key in img_key or img_key in audio_key):
            score += 0.25

        if score > best_score:
            best_score = score
            best_file = img

    if best_score >= MATCH_THRESHOLD:
        return best_file, round(best_score, 4)
    return None, round(best_score, 4)


def ensure_unique_output(path: Path) -> Path:
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    index = 2

    while True:
        candidate = parent / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def write_csv_header_if_needed(csv_path: Path):
    if not csv_path.exists():
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow([
                "time",
                "source_file",
                "source_ext",
                "output_file",
                "clean_name",
                "matched_cover",
                "match_score",
                "status",
                "message",
            ])


def append_csv_row(csv_path: Path, row: list):
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(row)


def collect_files(directory: Path):
    audio_files = []
    image_files = []

    for p in directory.iterdir():
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        if ext in AUDIO_EXTS:
            audio_files.append(p)
        elif ext in IMAGE_EXTS:
            image_files.append(p)

    return audio_files, image_files


def check_ffmpeg():
    try:
        result = subprocess.run(
            ["ffmpeg", "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True
        )
        return True, result.stdout.splitlines()[0] if result.stdout else "ffmpeg found"
    except Exception as e:
        return False, str(e)


def convert_with_cover(src_audio: Path, dst_m4a: Path, cover_file: Path | None):
    """
    转成 m4a，并在有封面时嵌入封面
    """
    if cover_file:
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(src_audio),
            "-i", str(cover_file),
            "-map", "0:a:0",
            "-map", "1:v:0",
            "-c:a", "aac",
            "-b:a", "192k",
            "-c:v", "mjpeg",
            "-disposition:v:0", "attached_pic",
            "-movflags", "+faststart",
            str(dst_m4a)
        ]
    else:
        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(src_audio),
            "-vn",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(dst_m4a)
        ]

    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="ignore"
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffmpeg failed")


def main():
    GENERATE_DIR.mkdir(parents=True, exist_ok=True)

    if not ORIGIN_DIR.exists():
        print(f"未找到目录: {ORIGIN_DIR}")
        return

    ok, ffmpeg_msg = check_ffmpeg()
    if not ok:
        print("未检测到 ffmpeg，无法转 m4a。")
        print(ffmpeg_msg)
        return

    print(f"检测到 ffmpeg: {ffmpeg_msg}")

    audio_files, image_files = collect_files(ORIGIN_DIR)

    if not audio_files:
        print("origin 中没有找到音频文件（mp3/mp4/m4a）。")
        return

    write_csv_header_if_needed(CSV_PATH)

    print(f"音频文件数: {len(audio_files)}")
    print(f"封面文件数: {len(image_files)}")
    print(f"输出目录: {GENERATE_DIR}")
    print(f"CSV记录: {CSV_PATH}")
    print("-" * 60)

    for audio_file in audio_files:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        clean_name = remove_date_suffix(audio_file.stem) or audio_file.stem
        output_path = ensure_unique_output(GENERATE_DIR / f"{clean_name}.m4a")

        cover_file = None
        match_score = 0.0

        try:
            cover_file, match_score = find_best_cover(audio_file, image_files)

            print(f"处理: {audio_file.name}")
            print(f" -> 输出: {output_path.name}")
            if cover_file:
                print(f" -> 封面: {cover_file.name} (score={match_score})")
            else:
                print(f" -> 封面: 未匹配 (best_score={match_score})")

            convert_with_cover(audio_file, output_path, cover_file)

            append_csv_row(CSV_PATH, [
                now,
                audio_file.name,
                audio_file.suffix.lower(),
                output_path.name,
                clean_name,
                cover_file.name if cover_file else "",
                match_score,
                "success",
                "ok",
            ])

            print(" -> 完成\n")

        except Exception as e:
            append_csv_row(CSV_PATH, [
                now,
                audio_file.name,
                audio_file.suffix.lower(),
                output_path.name,
                clean_name,
                cover_file.name if cover_file else "",
                match_score,
                "failed",
                str(e),
            ])

            print(f" -> 失败: {e}\n")

    print("-" * 60)
    print("处理完成")


if __name__ == "__main__":
    main()