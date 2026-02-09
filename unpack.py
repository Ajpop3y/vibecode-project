### If you send your PDF snapshot to a friend or colleague who doesn't have Vibecode installed, you can just send them this single script along with the PDF. They can run it to instantly restore your project.

import os
import re
import json
import zlib
import base64
import sys
import argparse
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# Check for required library
try:
    from pypdf import PdfReader
except ImportError:
    print("❌ Error: 'pypdf' is not installed.")
    print("   Please run: pip install pypdf")
    sys.exit(1)


class DigitalTwinError(Exception):
    """
    Raised when the embedded high-fidelity manifest is missing or corrupt.
    ECR #006: Digital Twin Integrity Enforcement
    """
    pass


def attempt_manifest_extraction(full_text):
    """
    Tries to extract and decode the embedded Digital Twin manifest.
    
    Returns:
        dict: The file map if successful
        
    Raises:
        DigitalTwinError: If manifest is missing, corrupted, or checksum fails
    """
    import hashlib
    
    # Look for Digital Twin Manifest
    pattern = r"--- VIBECODE_RESTORE_BLOCK_START ---\s*(.*?)\s*--- VIBECODE_RESTORE_BLOCK_END ---"
    match = re.search(pattern, full_text, re.DOTALL)
    
    if not match:
        raise DigitalTwinError("No Digital Twin manifest found in PDF.")
    
    raw_payload = match.group(1).strip()
    
    # Check for checksum (new format: sha256:<hash>\n<payload>)
    if raw_payload.startswith("sha256:"):
        lines = raw_payload.split('\n', 1)
        if len(lines) != 2:
            raise DigitalTwinError("Invalid manifest format: missing payload after checksum.")
        
        expected_checksum = lines[0].replace("sha256:", "").strip()
        payload = lines[1]
        
        # Validate checksum (SCRUB all whitespace caused by PDF wrapping)
        clean_payload = "".join(payload.split())
        actual_checksum = hashlib.sha256(clean_payload.encode('utf-8')).hexdigest()
        if actual_checksum != expected_checksum:
            raise DigitalTwinError(
                f"Checksum mismatch! Expected {expected_checksum[:16]}..., got {actual_checksum[:16]}... "
                "PDF may be corrupted or tampered."
            )
        logger.info("✅ Checksum validated")
    else:
        # Legacy format without checksum (backward compatible)
        payload = raw_payload
        logger.warning("⚠️ No checksum found (legacy snapshot). Proceeding without validation.")
    
    try:
        # 1. Decode base64
        compressed_data = base64.b64decode(payload)
        # 2. Decompress zlib
        json_bytes = zlib.decompress(compressed_data)
        # 3. Parse JSON
        file_map = json.loads(json_bytes.decode('utf-8'))
        return file_map
        
    except base64.binascii.Error as e:
        raise DigitalTwinError(f"Manifest base64 decoding failed: {e}")
    except zlib.error as e:
        raise DigitalTwinError(f"Manifest decompression failed: {e}")
    except json.JSONDecodeError as e:
        raise DigitalTwinError(f"Manifest JSON parsing failed: {e}")
    except Exception as e:
        raise DigitalTwinError(f"Manifest extraction failed: {e}")


def emergency_scrape_fallback(full_text, output_dir):
    """
    Legacy method: Scrapes visual text from PDF.
    
    WARNING: Python indentation will likely be lost!
    This should ONLY be used as a last resort when --force-scrape is set.
    """
    logger.warning("")
    logger.warning("=" * 60)
    logger.warning("⚠️  WARNING: EMERGENCY VISUAL SCRAPE ACTIVE")
    logger.warning("=" * 60)
    logger.warning("You are bypassing Digital Twin integrity checks.")
    logger.warning("Visual PDF scraping DESTROYS Python whitespace.")
    logger.warning("The output code may have INVALID INDENTATION/SYNTAX.")
    logger.warning("Use this only to recover logic, NOT executable code.")
    logger.warning("=" * 60)
    logger.warning("")
    
    # Clean artifacts
    clean_pattern = r"\\"
    cleaned_text = re.sub(clean_pattern, "", full_text)

    # Find blocks
    block_pattern = r"--- START_FILE: (.*?) ---\n(.*?)--- END_FILE ---"
    matches = re.findall(block_pattern, cleaned_text, re.DOTALL)

    if not matches:
        print("❌ No files found via text scraping either.")
        sys.exit(1)

    count = 0
    for filename, content in matches:
        filename = filename.strip()
        if len(filename) > 200 or "\n" in filename:
            continue

        full_path = os.path.join(output_dir, filename)
        
        try:
            dir_name = os.path.dirname(full_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content.strip())
            count += 1
            print(f"  ⚠ Scraped: {filename}")
        except Exception as e:
            print(f"  ⚠ Error saving {filename}: {e}")

    print(f"\n⚠️ Emergency Extraction Complete: {count} files recovered (LOSSY).")
    print("   Please manually verify indentation before using this code.")


def restore_from_manifest(file_map, output_dir):
    """
    Restores files from a valid Digital Twin manifest.
    """
    restored_count = 0
    for rel_path, content in file_map.items():
        # Security: Prevent path traversal
        safe_path = os.path.normpath(rel_path)
        if safe_path.startswith("..") or os.path.isabs(safe_path):
            print(f"⚠  Skipping unsafe path: {rel_path}")
            continue
        
        full_path = os.path.join(output_dir, safe_path)
        dir_name = os.path.dirname(full_path)
        
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        restored_count += 1
            
    return restored_count


def unpack_pdf(pdf_path, output_dir, force_scrape=False):
    """
    Main restoration function with Digital Twin Integrity Enforcement.
    
    ECR #006: Abolishes silent fallback to lossy text scraping.
    Requires --force-scrape flag for emergency recovery.
    """
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        sys.exit(1)

    # Use absolute path for output to avoid confusion
    output_dir = os.path.abspath(output_dir)
    print(f"📦 Unpacking: {pdf_path}")
    print(f"📂 Target:    {output_dir}")
    
    # Step 1: Read PDF
    try:
        reader = PdfReader(pdf_path)
        full_text = ""
        for page in reader.pages:
            text = page.extract_text()
            if text:
                full_text += text + "\n"
    except Exception as e:
        print(f"❌ Error reading PDF: {e}")
        sys.exit(1)
    
    # Step 2: Attempt Digital Twin Extraction (The Safe Path)
    print("🔍 Searching for Digital Twin Manifest...")
    
    try:
        file_map = attempt_manifest_extraction(full_text)
        print("⚡ Manifest found! Restoring with 100% fidelity...")
        
        restored_count = restore_from_manifest(file_map, output_dir)
        print(f"\n✨ Success! Restored {restored_count} files with perfect fidelity.")
        
    except DigitalTwinError as e:
        # Step 3: Integrity Check Failed
        print(f"\n❌ CRITICAL: {e}")
        
        if force_scrape:
            # Step 4: Emergency "Break Glass" Path (User Acknowledged Risk)
            emergency_scrape_fallback(full_text, output_dir)
        else:
            # Step 5: Safe Abort (Protect User from Silent Corruption)
            print("")
            print("=" * 60)
            print("[!] RESTORATION ABORTED to protect codebase integrity.")
            print("=" * 60)
            print("")
            print("The Digital Twin manifest is missing or corrupted.")
            print("Automatic fallback to text scraping has been DISABLED")
            print("because it produces syntactically invalid Python code.")
            print("")
            print("If you understand the risks and need partial recovery,")
            print("run again with the emergency flag:")
            print("")
            print(f"    python unpack.py \"{pdf_path}\" --force-scrape")
            print("")
            sys.exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Vibecode Digital Twin Restorer",
        epilog="For more info: https://github.com/vibecode"
    )
    parser.add_argument("pdf_path", help="Path to the Vibecode PDF snapshot.")
    parser.add_argument("--output", "-o", default=".", 
                        help="Output directory (default: current dir).")
    parser.add_argument("--force-scrape", action="store_true",
                        help="EMERGENCY ONLY: Attempt lossy text scraping if manifest is corrupt.")
    
    args = parser.parse_args()
    unpack_pdf(args.pdf_path, args.output, force_scrape=args.force_scrape)