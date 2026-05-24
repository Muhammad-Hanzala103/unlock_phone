import argparse
import os
from dataclasses import dataclass
from pathlib import Path


TARGET_FILES = (
    "wedding_video_017.mp4",
    "wedding_video_171.mp4",
    "wedding_video_322.mp4",
    "wedding_video_863.mp4",
    "wedding_video_864.mp4",
    "wedding_video_865.mp4",
)

TOP_LEVEL_BOXES = {
    b"ftyp",
    b"mdat",
    b"moov",
    b"free",
    b"skip",
    b"wide",
    b"uuid",
}

SCAN_CHUNK_SIZE = 8 * 1024 * 1024
COPY_CHUNK_SIZE = 8 * 1024 * 1024
MAX_BOX_COUNT = 128
MAX_CANDIDATE_SPAN = 4300 * 1024 * 1024


@dataclass
class Box:
    offset: int
    size: int
    box_type: bytes


@dataclass
class Candidate:
    start: int
    end: int
    boxes: list[Box]
    has_mdat: bool
    has_moov: bool

    @property
    def size(self) -> int:
        return self.end - self.start


def fmt_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def iter_ftyp_offsets(path: Path):
    tail = b""
    offset = 0
    with path.open("rb") as fh:
        while True:
            data = fh.read(SCAN_CHUNK_SIZE)
            if not data:
                break
            buf = tail + data
            base_offset = offset - len(tail)
            idx = buf.find(b"ftyp")
            while idx != -1:
                if base_offset + idx >= 4:
                    yield base_offset + idx - 4
                idx = buf.find(b"ftyp", idx + 1)
            tail = buf[-7:]
            offset += len(data)


def read_box_header(fh, offset: int, file_size: int):
    if offset < 0 or offset + 8 > file_size:
        return None

    fh.seek(offset)
    header = fh.read(16)
    if len(header) < 8:
        return None

    box_size = int.from_bytes(header[0:4], "big")
    box_type = header[4:8]
    header_size = 8

    if box_size == 1:
        if len(header) < 16:
            return None
        box_size = int.from_bytes(header[8:16], "big")
        header_size = 16
    elif box_size == 0:
        box_size = file_size - offset

    if box_size < header_size:
        return None
    if offset + box_size > file_size:
        return None
    if box_type not in TOP_LEVEL_BOXES:
        return None

    return Box(offset=offset, size=box_size, box_type=box_type)


def parse_candidate(path: Path, start: int) -> Candidate | None:
    file_size = path.stat().st_size
    boxes: list[Box] = []
    cursor = start
    has_mdat = False
    has_moov = False

    with path.open("rb") as fh:
        first_box = read_box_header(fh, cursor, file_size)
        if not first_box or first_box.box_type != b"ftyp":
            return None

        cursor += first_box.size
        boxes.append(first_box)

        for _ in range(MAX_BOX_COUNT - 1):
            if cursor >= file_size:
                break
            if cursor - start > MAX_CANDIDATE_SPAN:
                return None

            box = read_box_header(fh, cursor, file_size)
            if not box:
                break

            boxes.append(box)
            has_mdat = has_mdat or box.box_type == b"mdat"
            has_moov = has_moov or box.box_type == b"moov"
            cursor += box.size

            if has_mdat and has_moov:
                # Keep parsing contiguous harmless trailing boxes, but this is now viable.
                continue

    if len(boxes) < 3 or not has_mdat or not has_moov:
        return None
    if boxes[0].box_type != b"ftyp":
        return None

    return Candidate(
        start=start,
        end=boxes[-1].offset + boxes[-1].size,
        boxes=boxes,
        has_mdat=has_mdat,
        has_moov=has_moov,
    )


def find_best_candidate(path: Path) -> Candidate | None:
    candidates: list[Candidate] = []
    for start in iter_ftyp_offsets(path):
        candidate = parse_candidate(path, start)
        if candidate:
            candidates.append(candidate)

    if not candidates:
        return None

    # Prefer the largest valid contiguous MP4 segment; tiny segments can be thumbnails/previews.
    return max(candidates, key=lambda item: item.size)


def copy_range(src: Path, dst: Path, start: int, end: int):
    remaining = end - start
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as in_fh, dst.open("wb") as out_fh:
        in_fh.seek(start)
        while remaining > 0:
            chunk = in_fh.read(min(COPY_CHUNK_SIZE, remaining))
            if not chunk:
                break
            out_fh.write(chunk)
            remaining -= len(chunk)

    if remaining:
        raise OSError(f"copy ended early with {remaining} bytes remaining")


def repair_file(src: Path, out_dir: Path) -> str:
    original_size = src.stat().st_size
    candidate = find_best_candidate(src)
    if not candidate:
        return (
            f"SKIP  {src.name}: no valid MP4 segment found "
            f"(original {fmt_size(original_size)})"
        )

    out_file = out_dir / f"REPAIRED_{src.name}"
    copy_range(src, out_file, candidate.start, candidate.end)

    box_names = ",".join(box.box_type.decode("ascii") for box in candidate.boxes)
    return (
        f"DONE  {src.name}: start={candidate.start:,} "
        f"size={fmt_size(candidate.size)} boxes={box_names} -> {out_file}"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Repair MP4 files recovered with a broken leading ftyp size."
    )
    parser.add_argument(
        "--input",
        default=r"C:\Recovered_Wedding_USB6",
        help="Folder containing recovered wedding_video_*.mp4 files.",
    )
    parser.add_argument(
        "--output",
        default=r"C:\Recovered_Wedding_USB6_REPAIRED",
        help="Folder where repaired files will be written.",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        default=list(TARGET_FILES),
        help="Specific filenames to repair.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    input_dir = Path(args.input)
    output_dir = Path(args.output)

    print("======================================================================")
    print("                 MP4 REPAIR TOOL - NON-DESTRUCTIVE                    ")
    print("======================================================================")
    print(f"Input:  {input_dir}")
    print(f"Output: {output_dir}")
    print("======================================================================")

    for name in args.files:
        src = input_dir / name
        if not src.exists():
            print(f"MISS  {name}: source file not found")
            continue
        try:
            print(repair_file(src, output_dir))
        except Exception as exc:
            print(f"FAIL  {name}: {exc}")

    print("======================================================================")


if __name__ == "__main__":
    main()
