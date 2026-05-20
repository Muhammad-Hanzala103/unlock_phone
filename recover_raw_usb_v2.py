# ==============================================================================
# PRECISION RAW USB DATA RECOVERY TOOL (V2 - MOVIE FIXED + ALIGNMENT FIXED + LIMITS FIXED)
# Designed for: Muhammad Hanzala
# Recovers: Full-size Wedding Videos (MP4, MOV) and Photos (JPEG, PNG)
# Safe, Fast, and Direct
# ==============================================================================

import os
import sys
import time
import ctypes
import subprocess

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# Ensure script is run with full Administrator privileges
if not is_admin():
    print("======================================================================")
    print("❌ ERROR: ADMINISTRATOR PRIVILEGES REQUIRED!")
    print("======================================================================")
    print("Hanzala, this script MUST be run from an elevated command prompt.")
    print("Please follow these steps:")
    print("1. Click Windows Start, search for 'PowerShell' or 'CMD'.")
    print("2. Right-click and choose 'Run as Administrator'.")
    print("3. Navigate to this folder and run the script again.")
    print("======================================================================")
    input("Press Enter to exit...")
    sys.exit(1)

# File Signatures
SIGNATURES = {
    'jpg': {
        'start': b'\xff\xd8\xff',
        'end': b'\xff\xd9',
        'max_size': 35 * 1024 * 1024  # Max 35 MB
    },
    'png': {
        'start': b'\x89PNG\r\n\x1a\n',
        'end': b'\xaeB`\x82',
        'max_size': 35 * 1024 * 1024
    },
    'mp4_mov': {
        'start': b'ftyp',
        'max_size': 15 * 1024 * 1024 * 1024  # Max 15 GB
    }
}

def get_windows_disk_size(drive_id):
    """
    Queries the exact disk size in bytes using PowerShell to avoid direct raw seek limitations.
    """
    try:
        cmd = f"powershell -Command \"(Get-Disk -Number {drive_id}).Size\""
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().strip()
        if output.isdigit():
            return int(output)
    except:
        pass
    # Fallback default if query fails
    return 62 * 1024 * 1024 * 1024 

def read_unaligned(disk, pos, size):
    """
    Reads 'size' bytes from raw physical disk at arbitrary byte position 'pos' 
    by aligning seeks and reads to 512-byte sector boundaries. 
    Prevents Windows OSError [Errno 22] Invalid argument.
    """
    aligned_pos = (pos // 512) * 512
    skip_bytes = pos % 512
    
    # Read block must be a multiple of 512 bytes
    total_to_read = ((skip_bytes + size + 511) // 512) * 512
    
    original_pos = disk.tell()
    try:
        disk.seek(aligned_pos)
        data = disk.read(total_to_read)
        return data[skip_bytes : skip_bytes + size]
    except:
        return b""
    finally:
        disk.seek(original_pos)

def parse_mp4_length(disk, start_disk_offset):
    """
    Parses the top-level atom/box structures sequentially to find the exact end 
    and size of an MP4/MOV file. Aligned to 512-byte sector boundaries.
    """
    current_pos = start_disk_offset
    total_file_size = 0
    
    known_boxes = {
        b'ftyp', b'mdat', b'moov', b'free', b'skip', 
        b'wide', b'uuid', b'meta', b'pdin', b'ctts'
    }
    
    # Cameras usually write 3 to 10 top-level boxes
    for _ in range(15):
        try:
            header = read_unaligned(disk, current_pos, 8)
            if len(header) < 8:
                break
                
            box_size = int.from_bytes(header[0:4], byteorder='big')
            box_type = header[4:8]
            
            # Extended 64-bit size (if size is 1)
            if box_size == 1:
                ext_header = read_unaligned(disk, current_pos + 8, 8)
                if len(ext_header) < 8:
                    break
                box_size = int.from_bytes(ext_header, byteorder='big')
                
            # Validation: Size must be realistic and box type must be standard ASCII
            if box_size < 8:
                break
                
            # If the box name is valid ASCII or in known box types, keep traversing
            is_valid_type = box_type in known_boxes or all(32 <= b <= 126 for b in box_type)
            if not is_valid_type:
                break
                
            total_file_size += box_size
            current_pos += box_size
        except Exception:
            break
            
    # Safe validation limit
    if total_file_size < 100:
        return 0
    return total_file_size

def recover_file(disk, start_disk_offset, file_size, out_filename):
    """
    Writes file blocks directly from physical disk to target PC file using aligned sector reads.
    """
    with open(out_filename, "wb") as out_f:
        bytes_written = 0
        while bytes_written < file_size:
            to_read = min(1024 * 1024, file_size - bytes_written)  # 1 MB read chunks
            chunk = read_unaligned(disk, start_disk_offset + bytes_written, to_read)
            if not chunk:
                break
            out_f.write(chunk)
            bytes_written += len(chunk)

def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="Precision MP4/MOV Raw Sector Recovery Carving Tool")
    parser.add_argument("--drive", required=True, help="PhysicalDrive ID, e.g. 1")
    parser.add_argument("--out", required=True, help="PC target directory to save files")
    parser.add_argument("--dry-run", action="store_true", help="Scan and count without writing files")
    return parser.parse_args()

def main():
    args = parse_args()
    
    drive_path = f"\\\\.\\PhysicalDrive{args.drive}"
    out_dir = args.out
    dry_run = args.dry_run
    
    # Safety Check
    if out_dir.lower().startswith("e:"):
        print("❌ SAFETY ALERT: Destination cannot be Drive E: (source USB drive)!")
        sys.exit(1)
        
    if not dry_run and not os.path.exists(out_dir):
        os.makedirs(out_dir)
        
    print("======================================================================")
    print("         PRECISION RAW USB CARVING TOOL - MOVIE FIXED                 ")
    print("======================================================================")
    print(f" Source Drive:  {drive_path}")
    print(f" Target Output: {out_dir}")
    print(f" Mode:          {'DRY-RUN (No writing)' if dry_run else 'ACTUAL RECOVERY'}")
    print("======================================================================")
    print("Starting sector scanning. Please wait...")
    
    # Get exact physical disk size using PowerShell query (safest method)
    disk_size = get_windows_disk_size(args.drive)
    
    try:
        disk = open(drive_path, "rb")
    except Exception as e:
        print(f"❌ FAILED TO OPEN DRIVE: {e}")
        print("Please check if the drive number is correct and powershell is Run as Administrator.")
        sys.exit(1)
        
    chunk_size = 8 * 1024 * 1024  # 8 MB high-performance buffer
    overlap = 1 * 1024 * 1024    # 1 MB overlap
    
    total_scanned = 0
    start_time = time.time()
    
    counts = {'jpg': 0, 'png': 0, 'video': 0}
    buffer = b""
    disk_offset = 0
    
    try:
        while True:
            try:
                # Boundary safety check
                if disk_offset >= disk_size:
                    break
                
                # Adjust read size if near the end of disk
                to_read = min(chunk_size, disk_size - disk_offset)
                if to_read <= 0:
                    break
                    
                new_data = disk.read(to_read)
                if not new_data:
                    break
                buffer = buffer + new_data
            except Exception as e:
                # Stop if we are already out of bounds
                if disk_offset >= disk_size:
                    break
                print(f"\n⚠️ Warning: Skipped unreadable sector block at {disk_offset // (1024*1024)} MB (Error: {e})")
                disk.seek(disk_offset + chunk_size)
                disk_offset += chunk_size
                buffer = b""
                continue
                
            disk_offset += len(new_data)
            total_scanned += len(new_data)
            
            # Scan inside buffer
            i = 0
            buffer_len = len(buffer)
            
            while i < buffer_len - overlap:
                # 1. MP4/MOV Scanner (Dynamic Box parsing)
                if buffer[i:i+4] == SIGNATURES['mp4_mov']['start']:
                    start_disk_pos = (disk_offset - buffer_len) + i - 4
                    
                    # Parse length of entire video file
                    file_size = parse_mp4_length(disk, start_disk_pos)
                    
                    # SAFETY CHECK: File size must fit inside physical drive and be reasonable
                    if 1000 < file_size < SIGNATURES['mp4_mov']['max_size'] and (start_disk_pos + file_size) <= disk_size:
                        counts['video'] += 1
                        if not dry_run:
                            filename = os.path.join(out_dir, f"wedding_video_{counts['video']:03d}.mp4")
                            recover_file(disk, start_disk_pos, file_size, filename)
                            
                        # Skip physical disk and buffer scanning beyond this file
                        end_disk_pos = start_disk_pos + file_size
                        disk.seek(end_disk_pos)
                        disk_offset = end_disk_pos
                        buffer = b""
                        break  # Break inner loop to read new data from skipped position
                    else:
                        i += 1
                        
                # 2. JPEG Scanner
                elif buffer[i:i+3] == SIGNATURES['jpg']['start']:
                    start_disk_pos = (disk_offset - buffer_len) + i
                    end_idx = buffer.find(SIGNATURES['jpg']['end'], i)
                    
                    if end_idx != -1 and (end_idx - i) < SIGNATURES['jpg']['max_size']:
                        file_size = end_idx - i + 2
                        
                        # Safety check for image size boundary
                        if (start_disk_pos + file_size) <= disk_size:
                            counts['jpg'] += 1
                            if not dry_run:
                                filename = os.path.join(out_dir, f"photo_{counts['jpg']:05d}.jpg")
                                recover_file(disk, start_disk_pos, file_size, filename)
                            i += file_size
                        else:
                            i += 1
                    else:
                        i += 1
                        
                # 3. PNG Scanner
                elif buffer[i:i+8] == SIGNATURES['png']['start']:
                    start_disk_pos = (disk_offset - buffer_len) + i
                    end_idx = buffer.find(SIGNATURES['png']['end'], i)
                    
                    if end_idx != -1 and (end_idx - i) < SIGNATURES['png']['max_size']:
                        file_size = end_idx - i + len(SIGNATURES['png']['end'])
                        
                        # Safety check for image size boundary
                        if (start_disk_pos + file_size) <= disk_size:
                            counts['png'] += 1
                            if not dry_run:
                                filename = os.path.join(out_dir, f"photo_{counts['png']:05d}.png")
                                recover_file(disk, start_disk_pos, file_size, filename)
                            i += file_size
                        else:
                            i += 1
                    else:
                        i += 1
                else:
                    i += 1
                    
            # Retain overlap
            if len(buffer) > overlap:
                buffer = buffer[-overlap:]
            else:
                buffer = b""
                
            elapsed = time.time() - start_time
            speed = (total_scanned / (1024 * 1024)) / elapsed if elapsed > 0 else 0
            sys.stdout.write(
                f"\rScanned: {total_scanned // (1024*1024)} MB / {disk_size // (1024*1024)} MB | Speed: {speed:.1f} MB/s | Photos: {counts['jpg'] + counts['png']} | Videos: {counts['video']}"
            )
            sys.stdout.flush()
            
    except KeyboardInterrupt:
        print("\n⚠️ Scan paused by user.")
    finally:
        disk.close()
        
    elapsed_total = time.time() - start_time
    print("\n\n======================================================================")
    print("                      RECOVERY COMPLETED!                             ")
    print("======================================================================")
    print(f" Total time elapsed:  {elapsed_total:.1f} seconds")
    print(f" Total sectors read:  {total_scanned // (1024*1024)} MB / {disk_size // (1024*1024)} MB")
    print(f" Photos Recovered:    {counts['jpg'] + counts['png']}")
    print(f" Videos Recovered:    {counts['video']}")
    print(f" Saved Location:      {out_dir}")
    print("======================================================================")

if __name__ == "__main__":
    main()
