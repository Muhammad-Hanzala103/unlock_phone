# ==============================================================================
# PRECISION A71 & DATA RECOVERY HELPER (V2 - C DRIVE VERSION)
# Crafted for: Muhammad Hanzala
# Direct, Step-by-Step, and Safe Diagnostics
# ==============================================================================

$ScriptDir = "C:\Project\unlock_phone"
$PythonScript = "$ScriptDir\recover_raw_usb_v2.py"

function Show-Header {
    Clear-Host
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host "         HANZALA'S SAMSUNG A71 & DATA RECOVERY SYSTEM SUITE (V2)      " -ForegroundColor Yellow -Bold
    Write-Host "======================================================================" -ForegroundColor Cyan
    Write-Host " Current workspace directory: $ScriptDir" -ForegroundColor Gray
    Write-Host "======================================================================" -ForegroundColor Cyan
}

function Show-Menu {
    Show-Header
    Write-Host "1) [Phone] Check ADB Connection Status" -ForegroundColor Green
    Write-Host "2) [Phone] Safe EFS Backup (dd dump with SHA256 verification)" -ForegroundColor Green
    Write-Host "3) [USB 1] Scan physical USB drives connected (Check PhysicalDrive ID)" -ForegroundColor Yellow
    Write-Host "4) [USB 1] Run Dry-Run Recovery Scan (No write, counts files)" -ForegroundColor Yellow
    Write-Host "5) [USB 1] Run Actual Movie-Fixed Raw Data Recovery (Saves to PC)" -ForegroundColor Yellow
    Write-Host "6) [Phone] Clean Magisk & LSPosed Bootloop Cleanup Guide" -ForegroundColor Green
    Write-Host "7) [Phone] Odin Official Pakistan (PAK) Firmware safe flashing notes" -ForegroundColor Green
    Write-Host "8) [PC] Dell Precision 3620 SSD / Unknown Device drivers help" -ForegroundColor Blue
    Write-Host "9) Exit" -ForegroundColor Red
    Write-Host "======================================================================" -ForegroundColor Cyan
}

while ($true) {
    Show-Menu
    $choice = Read-Host "Select an option [1-9]"
    
    switch ($choice) {
        "1" {
            Show-Header
            Write-Host ">>> Checking ADB Devices <<<" -ForegroundColor Cyan
            adb devices
            Write-Host ""
            Read-Host "Press any key to return to main menu..."
        }
        
        "2" {
            Show-Header
            Write-Host ">>> Samsung A71 Safe EFS Backup Module <<<" -ForegroundColor Cyan
            Write-Host "Ensure USB Debugging is ON and A71 has Root access (Magisk shell prompt)." -ForegroundColor Yellow
            $confirm = Read-Host "Proceed with backup? (y/n)"
            if ($confirm -eq 'y' -or $confirm -eq 'Y') {
                Write-Host "Checking if device is rooted..." -ForegroundColor Cyan
                $suCheck = adb shell "su -c 'id'"
                if ($suCheck -like "*uid=0*") {
                    Write-Host "[✔] Root access confirmed. Dumping EFS partitions..." -ForegroundColor Green
                    
                    # Target Backup Directories on A71
                    # A71 has efs (/dev/block/by-name/efs)
                    $efsPath = adb shell "su -c 'readlink -f /dev/block/by-name/efs'"
                    $efsPath = $efsPath.Trim()
                    
                    if ($efsPath) {
                        Write-Host "Found EFS partition block: $efsPath" -ForegroundColor Cyan
                        
                        # Creating temp directories on Android
                        adb shell "mkdir -p /data/local/tmp/efs_backup"
                        Write-Host "Creating raw backup on Android storage..." -ForegroundColor Cyan
                        adb shell "su -c 'dd if=$efsPath of=/data/local/tmp/efs_backup/efs.img bs=4096'"
                        
                        # Calculating checksums on Android
                        Write-Host "Calculating SHA256 checksum on Android..." -ForegroundColor Cyan
                        $androidHash = adb shell "su -c 'sha256sum /data/local/tmp/efs_backup/efs.img'"
                        $androidHash = ($androidHash -split " ")[0].Trim()
                        
                        # Pulling file to PC C:\Project\unlock_phone\backup
                        $localBackupDir = "$ScriptDir\A71_EFS_Backup"
                        if (!(Test-Path $localBackupDir)) {
                            New-Item -ItemType Directory -Path $localBackupDir | Out-Null
                        }
                        
                        Write-Host "Pulling EFS image to PC folder ($localBackupDir)..." -ForegroundColor Cyan
                        adb pull "/data/local/tmp/efs_backup/efs.img" "$localBackupDir\efs.img"
                        
                        # Cleanup temp Android files
                        adb shell "rm -rf /data/local/tmp/efs_backup"
                        
                        # Calculating checksum on PC
                        Write-Host "Calculating SHA256 checksum on PC..." -ForegroundColor Cyan
                        $pcHashObj = Get-FileHash "$localBackupDir\efs.img" -Algorithm SHA256
                        $pcHash = $pcHashObj.Hash.ToLower().Trim()
                        
                        # Verify integrity
                        Write-Host "Android Hash: $androidHash" -ForegroundColor Gray
                        Write-Host "PC Hash:      $pcHash" -ForegroundColor Gray
                        
                        if ($androidHash -eq $pcHash) {
                            Write-Host "[✔] INTEGRITY VERIFIED! EFS Backup is 100% authentic and uncorrupted." -ForegroundColor Green
                            Write-Host "EFS Image path: $localBackupDir\efs.img" -ForegroundColor Green
                            # Save hash file
                            $androidHash | Out-File "$localBackupDir\efs_checksum.sha256"
                        } else {
                            Write-Host "[❌] INTEGRITY ERROR: Hash mismatch! Please verify cable quality and try again." -ForegroundColor Red
                        }
                    } else {
                        Write-Host "[❌] Failed to detect EFS partition path block automatically." -ForegroundColor Red
                    }
                } else {
                    Write-Host "[❌] ROOT DENIED: Please make sure Magisk Grant popup is accepted on your phone screen." -ForegroundColor Red
                }
            }
            Read-Host "Press any key to return to main menu..."
        }
        
        "3" {
            Show-Header
            Write-Host ">>> USB Drives Scanner <<<" -ForegroundColor Cyan
            Write-Host "Connected USB disks details (Get-Disk query):" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "Hanzala, look for the disk matching ~58.9 GB. That is your Drive E!:" -ForegroundColor Green
            Write-Host "----------------------------------------------------------------------"
            Get-Disk | Where-Object { $_.BusType -eq "USB" } | ForEach-Object {
                Write-Host " -> Physical Disk ID:   PhysicalDrive$($_.Number)" -ForegroundColor Cyan
                Write-Host " -> Size (Capacity):    $([Math]::Round($_.Size / 1GB, 2)) GB" -ForegroundColor Cyan
                Write-Host " -> Friendly Name:      $($_.FriendlyName)" -ForegroundColor Cyan
                Write-Host " -> Status:             $($_.OperationalStatus)" -ForegroundColor Cyan
                Write-Host "----------------------------------------------------------------------"
            }
            Write-Host "NOTE: Note down the PhysicalDrive number (e.g. PhysicalDrive2 or PhysicalDrive3)." -ForegroundColor Yellow
            Write-Host ""
            Read-Host "Press any key to return to main menu..."
        }
        
        "4" {
            Show-Header
            Write-Host ">>> USB Recovery Script: Dry-Run Scan <<<" -ForegroundColor Cyan
            Write-Host "This will NOT recover or save files. It only scans and tells you what files exist." -ForegroundColor Yellow
            $driveNum = Read-Host "Enter PhysicalDrive Number (e.g., 2)"
            
            if ($driveNum -match '^\d+$') {
                Write-Host "Launching dry-run sector scan..." -ForegroundColor Cyan
                python "$PythonScript" --drive $driveNum --out "C:\temp" --dry-run
            } else {
                Write-Host "Invalid Drive Number." -ForegroundColor Red
            }
            Read-Host "Press any key to return to main menu..."
        }
        
        "5" {
            Show-Header
            Write-Host ">>> USB Recovery Script: Actual Raw Recovery <<<" -ForegroundColor Cyan
            Write-Host "This will recover photos/videos onto a PC directory. NEVER save back to USB!" -ForegroundColor Red
            Write-Host ""
            $driveNum = Read-Host "Enter PhysicalDrive Number (e.g., 2)"
            $targetDir = Read-Host "Enter target PC folder to save files (e.g., C:\Recovered_Wedding_USB3)"
            
            if ($driveNum -match '^\d+$' -and $targetDir) {
                Write-Host "Launching actual recovery on PhysicalDrive$driveNum, saving to $targetDir..." -ForegroundColor Green
                python "$PythonScript" --drive $driveNum --out "$targetDir"
            } else {
                Write-Host "Invalid Drive Number or Directory." -ForegroundColor Red
            }
            Read-Host "Press any key to return to main menu..."
        }
        
        "6" {
            Show-Header
            Write-Host ">>> Magisk & LSPosed Bootloop Cleanup Guide <<<" -ForegroundColor Cyan
            Write-Host "Agar custom settings/modules ki wajah se A71 soft brick ya bootloop ho jaye:" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "1. Safe Mode Boot: Phone restart karte waqt Volume Down press karke rakhein."
            Write-Host "   Is se saare Magisk modules temporary disable ho jate hain aur system boots safely."
            Write-Host "2. Safe Mode boot hone ke baad, Magisk app open karke problem dene wale Module ko remove karein."
            Write-Host "3. ADB method: Custom recovery (TWRP/OrangeFox) ya rooted shell mein:"
            Write-Host "   adb shell"
            Write-Host "   su"
            Write-Host "   touch /data/adb/modules/disable"
            Write-Host "   (Is se saare modules automatically block ho jayenge aur custom loop break ho jayega)."
            Write-Host ""
            Read-Host "Press any key to return to main menu..."
        }
        
        "7" {
            Show-Header
            Write-Host ">>> Official Pakistan (PAK) Firmware Flashing with Odin <<<" -ForegroundColor Cyan
            Write-Host "A715F baseband model ko direct original firmware state par lane ke liye guidelines:" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "1. Samsung official Pakistan (PAK/XSG) firmware file select karein matching version A715FXXSBDXB1."
            Write-Host "2. Odin tool open karein. Apne fields assign karein:"
            Write-Host "   - BL field: BL_... file"
            Write-Host "   - AP field: AP_... file"
            Write-Host "   - CP field: CP_... file"
            Write-Host "   - CSC field: HOME_CSC_... file (AGAR DATA SAFE RAKHNA HAI!)."
            Write-Host "     NOTE: Agar normal CSC use kiya to phone full factory reset ho jayega. HOME_CSC safe hai."
            Write-Host "3. Phone Download Mode mein connect karein (Volume Up + Down press karke USB attach karein)."
            Write-Host "4. Status indicator blue aane par 'Start' click karein aur success pass hone tak cable mat nikalein."
            Write-Host ""
            Read-Host "Press any key to return to main menu..."
        }
        
        "8" {
            Show-Header
            Write-Host ">>> Dell Precision 3620 PC Storage / Unknown Device Help <<<" -ForegroundColor Cyan
            Write-Host "Dell Tower ka secondary SSD ya unknown controller driver fix:" -ForegroundColor Yellow
            Write-Host ""
            Write-Host "1. Device Manager open karein (devmgmt.msc)."
            Write-Host "2. Unknown Device/PCI Device standard properties -> Details tab -> Hardware IDs select karein."
            Write-Host "3. Dell Support official site se 'Intel Rapid Storage Technology (RST) Driver' and 'Intel Chipset Device Software' download karein."
            Write-Host "4. Setup run karke PC reboot karein. Storage Controllers automatically active ho jayenge aur SSD detect ho jayegi."
            Write-Host ""
            Read-Host "Press any key to return to main menu..."
        }
        
        "9" {
            Clear-Host
            Write-Host "Exiting. Allah Hafiz!" -ForegroundColor Yellow
            break
        }
    }
}
