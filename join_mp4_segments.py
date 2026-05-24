import argparse
import subprocess
import sys
from pathlib import Path


DEFAULT_INPUT = Path(r"C:\Recovered_Wedding_USB6_REPAIRED")
DEFAULT_FOLDERS = (
    "wedding_video_017_segments",
    "wedding_video_171_segments",
    "wedding_video_322_segments",
)


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def write_concat_list(segment_files: list[Path], list_file: Path):
    with list_file.open("w", encoding="utf-8") as fh:
        for item in segment_files:
            safe_path = item.as_posix().replace("'", "'\\''")
            fh.write(f"file '{safe_path}'\n")


def join_folder(base_dir: Path, folder_name: str, overwrite: bool) -> str:
    folder = base_dir / folder_name
    if not folder.exists():
        return f"MISS  {folder_name}: folder not found"

    segment_files = sorted(folder.glob("*.mp4"))
    if not segment_files:
        return f"SKIP  {folder_name}: no MP4 segments found"

    source_name = folder_name.replace("_segments", "")
    output_file = base_dir / f"JOINED_{source_name}.mp4"
    list_file = base_dir / f"concat_{source_name}.txt"

    if output_file.exists() and not overwrite:
        return f"SKIP  {folder_name}: output exists ({output_file})"

    write_concat_list(segment_files, list_file)

    command = [
        ffmpeg_exe(),
        "-y" if overwrite else "-n",
        "-hide_banner",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_file),
    ]

    result = subprocess.run(command, text=True, capture_output=True)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().splitlines()
        last_line = detail[-1] if detail else "unknown ffmpeg error"
        return f"FAIL  {folder_name}: {last_line}"

    size = output_file.stat().st_size
    return f"DONE  {folder_name}: {len(segment_files)} segments -> {output_file} ({size:,} bytes)"


def parse_args():
    parser = argparse.ArgumentParser(description="Join recovered MP4 segment folders into single MP4 files.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Folder containing *_segments directories.")
    parser.add_argument("--folders", nargs="*", default=list(DEFAULT_FOLDERS), help="Segment folders to join.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing JOINED_*.mp4 files.")
    return parser.parse_args()


def main():
    args = parse_args()
    base_dir = Path(args.input)
    print("======================================================================")
    print("                 MP4 SEGMENT JOIN TOOL - NON-DESTRUCTIVE              ")
    print("======================================================================")
    print(f"Input: {base_dir}")
    print("======================================================================")
    for folder_name in args.folders:
        print(join_folder(base_dir, folder_name, args.overwrite))
    print("======================================================================")


if __name__ == "__main__":
    sys.exit(main())
