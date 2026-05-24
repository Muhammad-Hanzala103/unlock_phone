import argparse
import mmap
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

BRANDS = {
    b"isom",
    b"iso2",
    b"mp41",
    b"mp42",
    b"avc1",
    b"qt  ",
    b"3gp4",
    b"M4V ",
    b"M4A ",
}

SYNTHETIC_FTYP = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
SCAN_TYPES = (b"ftyp", b"moov", b"mdat")
COPY_CHUNK_SIZE = 8 * 1024 * 1024
MAX_BOX_SIZE = 4300 * 1024 * 1024


@dataclass(frozen=True)
class Box:
    offset: int
    size: int
    box_type: bytes
    header_size: int = 8

    @property
    def end(self) -> int:
        return self.offset + self.size

    @property
    def data_offset(self) -> int:
        return self.offset + self.header_size


@dataclass(frozen=True)
class RepairPlan:
    ftyp: Box | None
    ftyp_signature_offset: int | None
    moov: Box
    mdat: Box
    synthetic_ftyp: bool

    @property
    def output_size(self) -> int:
        return len(SYNTHETIC_FTYP) + self.moov.size + self.mdat.size


def fmt_size(size: int) -> str:
    units = ("B", "KB", "MB", "GB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.2f} {unit}"
        value /= 1024
    return f"{size} B"


def read_box_header_from_view(view, offset: int) -> Box | None:
    file_size = len(view)
    if offset < 0 or offset + 8 > file_size:
        return None

    box_size = int.from_bytes(view[offset : offset + 4], "big")
    box_type = bytes(view[offset + 4 : offset + 8])
    header_size = 8

    if box_size == 1:
        if offset + 16 > file_size:
            return None
        box_size = int.from_bytes(view[offset + 8 : offset + 16], "big")
        header_size = 16
    elif box_size == 0:
        box_size = file_size - offset

    if box_type not in TOP_LEVEL_BOXES:
        return None
    if box_size < header_size:
        return None
    if box_size > MAX_BOX_SIZE:
        return None
    if offset + box_size > file_size:
        return None

    return Box(offset=offset, size=box_size, box_type=box_type, header_size=header_size)


def is_valid_ftyp(view, box: Box) -> bool:
    if box.box_type != b"ftyp" or box.size < 16:
        return False
    major_brand = bytes(view[box.offset + 8 : box.offset + 12])
    compatible = bytes(view[box.offset + 16 : box.end])
    if major_brand in BRANDS:
        return True
    return any(brand in compatible for brand in BRANDS)


def iter_signature_offsets(view, signature: bytes):
    offset = view.find(signature)
    while offset != -1:
        yield offset
        offset = view.find(signature, offset + 1)


def collect_boxes(view) -> dict[bytes, list[Box]]:
    found = {box_type: [] for box_type in SCAN_TYPES}
    seen: set[tuple[int, bytes]] = set()

    for box_type in SCAN_TYPES:
        for signature_offset in iter_signature_offsets(view, box_type):
            header_offset = signature_offset - 4
            box = read_box_header_from_view(view, header_offset)
            if not box or box.box_type != box_type:
                continue
            key = (box.offset, box.box_type)
            if key in seen:
                continue
            seen.add(key)
            found[box_type].append(box)

    return found


def first_ftyp_signature(view) -> int | None:
    offset = view.find(b"ftyp")
    return None if offset == -1 else offset


def choose_repair_plan(path: Path) -> tuple[RepairPlan | None, str]:
    with path.open("rb") as fh:
        with mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as view:
            boxes = collect_boxes(view)
            ftyp_boxes = [box for box in boxes[b"ftyp"] if is_valid_ftyp(view, box)]
            moov_boxes = sorted(boxes[b"moov"], key=lambda item: item.size, reverse=True)
            mdat_boxes = sorted(boxes[b"mdat"], key=lambda item: item.size, reverse=True)

            if not moov_boxes:
                return None, "no valid moov box found"
            if not mdat_boxes:
                return None, "no valid mdat box found"

            ftyp_box = min(ftyp_boxes, key=lambda item: item.offset) if ftyp_boxes else None
            ftyp_sig = first_ftyp_signature(view)
            best: RepairPlan | None = None
            best_score = -1

            for moov in moov_boxes[:12]:
                for mdat in mdat_boxes[:12]:
                    if moov.offset == mdat.offset:
                        continue
                    if moov.size < 256 or mdat.size < 1024 * 1024:
                        continue
                    score = mdat.size + moov.size
                    if score > best_score:
                        best = RepairPlan(
                            ftyp=ftyp_box,
                            ftyp_signature_offset=ftyp_sig,
                            moov=moov,
                            mdat=mdat,
                            synthetic_ftyp=ftyp_box is None,
                        )
                        best_score = score

            if not best:
                return None, "no coherent moov/mdat pair found"

            return best, "ok"


def patch_chunk_offsets(moov_data: bytearray, delta: int) -> tuple[int, int]:
    patched_stco = 0
    patched_co64 = 0
    cursor = 0

    while True:
        idx = moov_data.find(b"stco", cursor)
        if idx == -1:
            break
        box_start = idx - 4
        if box_start >= 0:
            box_size = int.from_bytes(moov_data[box_start:idx], "big")
            entry_count_offset = idx + 8
            entries_offset = idx + 12
            if box_size >= 16 and box_start + box_size <= len(moov_data):
                entry_count = int.from_bytes(moov_data[entry_count_offset:entries_offset], "big")
                entries_end = entries_offset + (entry_count * 4)
                if entries_end <= box_start + box_size:
                    for pos in range(entries_offset, entries_end, 4):
                        old = int.from_bytes(moov_data[pos : pos + 4], "big")
                        new = old + delta
                        if not 0 <= new <= 0xFFFFFFFF:
                            raise ValueError("stco offset adjustment overflow")
                        moov_data[pos : pos + 4] = new.to_bytes(4, "big")
                    patched_stco += 1
        cursor = idx + 4

    cursor = 0
    while True:
        idx = moov_data.find(b"co64", cursor)
        if idx == -1:
            break
        box_start = idx - 4
        if box_start >= 0:
            box_size = int.from_bytes(moov_data[box_start:idx], "big")
            entry_count_offset = idx + 8
            entries_offset = idx + 12
            if box_size >= 20 and box_start + box_size <= len(moov_data):
                entry_count = int.from_bytes(moov_data[entry_count_offset:entries_offset], "big")
                entries_end = entries_offset + (entry_count * 8)
                if entries_end <= box_start + box_size:
                    for pos in range(entries_offset, entries_end, 8):
                        old = int.from_bytes(moov_data[pos : pos + 8], "big")
                        new = old + delta
                        if not 0 <= new <= 0xFFFFFFFFFFFFFFFF:
                            raise ValueError("co64 offset adjustment overflow")
                        moov_data[pos : pos + 8] = new.to_bytes(8, "big")
                    patched_co64 += 1
        cursor = idx + 4

    return patched_stco, patched_co64


def copy_range(src_fh, dst_fh, start: int, size: int):
    src_fh.seek(start)
    remaining = size
    while remaining > 0:
        chunk = src_fh.read(min(COPY_CHUNK_SIZE, remaining))
        if not chunk:
            break
        dst_fh.write(chunk)
        remaining -= len(chunk)

    if remaining:
        raise OSError(f"copy ended early with {remaining} bytes remaining")


def write_repaired_file(src: Path, dst: Path, plan: RepairPlan) -> tuple[int, int]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with src.open("rb") as in_fh, dst.open("wb") as out_fh:
        ftyp_data = SYNTHETIC_FTYP
        if plan.ftyp and not plan.synthetic_ftyp:
            in_fh.seek(plan.ftyp.offset)
            ftyp_data = in_fh.read(plan.ftyp.size)

        in_fh.seek(plan.moov.offset)
        moov_data = bytearray(in_fh.read(plan.moov.size))

        new_mdat_data_offset = len(ftyp_data) + len(moov_data) + plan.mdat.header_size
        old_mdat_data_offset = plan.mdat.data_offset
        delta = new_mdat_data_offset - old_mdat_data_offset
        patched_stco, patched_co64 = patch_chunk_offsets(moov_data, delta)

        out_fh.write(ftyp_data)
        out_fh.write(moov_data)
        copy_range(in_fh, out_fh, plan.mdat.offset, plan.mdat.size)

    return patched_stco, patched_co64


def repair_file(src: Path, out_dir: Path) -> str:
    original_size = src.stat().st_size
    plan, reason = choose_repair_plan(src)
    if not plan:
        return f"SKIP  {src.name}: {reason} (source={fmt_size(original_size)})"

    out_file = out_dir / f"REPAIRED_{src.name}"
    patched_stco, patched_co64 = write_repaired_file(src, out_file, plan)
    repaired_size = out_file.stat().st_size
    ftyp_note = (
        f"ftyp={plan.ftyp.offset:,}"
        if plan.ftyp and not plan.synthetic_ftyp
        else f"ftyp=synthetic(sig={plan.ftyp_signature_offset})"
    )

    return (
        f"DONE  {src.name}: source={fmt_size(original_size)} "
        f"{ftyp_note} moov={plan.moov.offset:,}/{fmt_size(plan.moov.size)} "
        f"mdat={plan.mdat.offset:,}/{fmt_size(plan.mdat.size)} "
        f"patched=stco:{patched_stco},co64:{patched_co64} "
        f"output={fmt_size(repaired_size)} -> {out_file}"
    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Repair MP4 files recovered with broken leading ftyp data."
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
