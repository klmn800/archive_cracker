#!/usr/bin/env python3
"""
sort_unzip.py - Extract archives and sort files into category-based subfolders.

Extracts any common archive format (zip, rar, 7z, tar, gz, etc.) using 7-Zip,
then flattens all files and sorts them into human-friendly category folders
like Documents, Images, Spreadsheets, etc.
"""

import argparse
import getpass
import logging
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Category definitions
# ---------------------------------------------------------------------------
# Maps a human-readable category name to all the file extensions that belong
# in that bucket.  Extensions must be lowercase and include the leading dot.

CATEGORIES: dict[str, set[str]] = {
    "Documents": {
        ".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".pages",
        ".tex", ".md", ".epub", ".mobi", ".wps", ".wpd", ".log",
        ".nfo", ".xps", ".oxps",
    },
    "Spreadsheets": {
        ".xls", ".xlsx", ".xlsm", ".xlsb", ".csv", ".ods",
        ".numbers", ".tsv",
    },
    "Presentations": {
        ".ppt", ".pptx", ".pptm", ".odp", ".key",
    },
    "Images": {
        ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".tif",
        ".svg", ".webp", ".ico", ".heic", ".heif", ".raw", ".cr2",
        ".nef", ".arw", ".dng", ".psd", ".ai", ".eps", ".jfif",
    },
    "Videos": {
        ".mp4", ".avi", ".mov", ".mkv", ".wmv", ".flv", ".webm",
        ".m4v", ".mpg", ".mpeg", ".3gp", ".vob", ".ts", ".mts",
    },
    "Audio": {
        ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a",
        ".aiff", ".opus", ".mid", ".midi",
    },
    "Archives": {
        ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
        ".tgz", ".cab", ".iso", ".dmg",
    },
    "Code": {
        ".py", ".js", ".html", ".htm", ".css", ".java", ".cpp",
        ".c", ".h", ".hpp", ".rb", ".go", ".rs", ".ts", ".jsx",
        ".tsx", ".php", ".swift", ".kt", ".scala", ".r", ".m",
        ".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg",
        ".conf", ".sh", ".bat", ".cmd", ".ps1", ".sql", ".vue",
        ".ipynb",
    },
    "Databases": {
        ".db", ".sqlite", ".sqlite3", ".mdb", ".accdb",
    },
    "Fonts": {
        ".ttf", ".otf", ".woff", ".woff2", ".eot", ".fon",
    },
    "Executables": {
        ".exe", ".msi", ".app", ".deb", ".rpm", ".apk", ".com",
        ".scr",
    },
    "Shortcuts": {
        ".lnk", ".url", ".webloc",
    },
}

# Build reverse lookup: extension -> category name
_EXT_TO_CATEGORY: dict[str, str] = {}
for _cat, _exts in CATEGORIES.items():
    for _ext in _exts:
        _EXT_TO_CATEGORY[_ext] = _cat

# 7-Zip path (standard Windows install location)
SEVEN_ZIP = r"C:\Program Files\7-Zip\7z.exe"

# Archive extensions the tool will accept as input
ARCHIVE_EXTENSIONS = {
    ".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz",
    ".tgz", ".cab", ".iso",
}


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------

def setup_logging(output_dir: Path, verbose: bool = False) -> logging.Logger:
    """Configure console + file logging. Returns the logger."""
    logger = logging.getLogger("sort_unzip")
    logger.setLevel(logging.DEBUG)

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG if verbose else logging.INFO)
    console.setFormatter(logging.Formatter("  %(message)s"))
    logger.addHandler(console)

    # File handler (always verbose, lives next to sorted output)
    log_path = output_dir / "sort_unzip.log"
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                          datefmt="%Y-%m-%d %H:%M:%S")
    )
    logger.addHandler(file_handler)

    return logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_category(filename: str) -> str:
    """Return the category name for a file based on its extension."""
    ext = Path(filename).suffix.lower()
    return _EXT_TO_CATEGORY.get(ext, "Other")


def unique_path(dest: Path) -> Path:
    """If *dest* already exists, append (1), (2), ... until we find a free name."""
    if not dest.exists():
        return dest
    stem = dest.stem
    suffix = dest.suffix
    parent = dest.parent
    counter = 1
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def find_7zip() -> str:
    """Locate the 7z executable. Returns the path or exits with an error."""
    # Check the standard install location first
    if os.path.isfile(SEVEN_ZIP):
        return SEVEN_ZIP
    # Try PATH
    result = shutil.which("7z")
    if result:
        return result
    print("\n  ERROR: 7-Zip not found.")
    print("  Install it from https://www.7-zip.org/ or add 7z.exe to your PATH.")
    sys.exit(1)


def archive_is_encrypted(archive_path: Path, seven_zip: str) -> bool:
    """Check if an archive is password-protected by listing it with 7-Zip."""
    cmd = [seven_zip, "l", str(archive_path), "-slt"]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            input="\n",  # send empty line so 7z doesn't hang on password prompt
        )
        # If 7z asks for a password or reports encryption, it's encrypted
        if "Enter password" in result.stdout or "Encrypted = +" in result.stdout:
            return True
        return False
    except Exception:
        return False


def extract_archive(archive_path: Path, dest_dir: Path, seven_zip: str,
                     logger: logging.Logger, password: str | None = None) -> bool:
    """
    Extract *archive_path* into *dest_dir* using 7-Zip.

    Returns True on success, False on failure.
    """
    logger.info("Extracting: %s", archive_path.name)
    logger.debug("  -> %s", dest_dir)

    cmd = [
        seven_zip,
        "x",                    # extract with full paths (into temp dir)
        str(archive_path),
        f"-o{dest_dir}",        # output directory
        "-y",                   # assume yes to prompts
        "-bso0",                # suppress normal output
        "-bsp0",                # suppress progress output
    ]

    if password:
        cmd.append(f"-p{password}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "Wrong password" in stderr or "Data Error" in result.stdout:
                logger.error("Wrong password. Extraction failed.")
            else:
                logger.error("7-Zip failed (exit code %d):\n%s",
                             result.returncode, stderr)
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("Extraction timed out after 10 minutes.")
        return False
    except FileNotFoundError:
        logger.error("Could not run 7-Zip at: %s", seven_zip)
        return False


def collect_files(root_dir: Path) -> list[Path]:
    """
    Walk *root_dir* recursively and return a flat list of all file paths.
    Skips hidden files/directories (names starting with '.').
    """
    files = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Skip hidden directories
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for fname in filenames:
            if not fname.startswith("."):
                files.append(Path(dirpath) / fname)
    return files


# ---------------------------------------------------------------------------
# Main sorting logic
# ---------------------------------------------------------------------------

def sort_files(files: list[Path], output_dir: Path, logger: logging.Logger,
               dry_run: bool = False) -> dict[str, list[str]]:
    """
    Sort *files* into category subfolders under *output_dir*.

    Returns a dict of {category: [filename, ...]} for the summary report.
    """
    results: dict[str, list[str]] = defaultdict(list)
    total = len(files)

    for i, src in enumerate(files, 1):
        category = get_category(src.name)
        dest_dir = output_dir / category
        dest_path = unique_path(dest_dir / src.name)

        if dry_run:
            logger.info("[%d/%d] %s -> %s/", i, total, src.name, category)
        else:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest_path))
            logger.debug("[%d/%d] %s -> %s/%s",
                         i, total, src.name, category, dest_path.name)

        # Progress update every 100 files (console only)
        if i % 100 == 0:
            logger.info("  ... processed %d / %d files", i, total)

        results[category].append(dest_path.name if not dry_run else src.name)

    return dict(results)


def print_summary(results: dict[str, list[str]], logger: logging.Logger,
                  dry_run: bool = False) -> None:
    """Print a nice summary table of what was sorted where."""
    total = sum(len(v) for v in results.values())
    prefix = "[DRY RUN] " if dry_run else ""

    logger.info("")
    logger.info("=" * 50)
    logger.info("%sSorting complete!", prefix)
    logger.info("=" * 50)
    logger.info("")

    # Sort categories by file count (descending) for a useful overview
    for category, files in sorted(results.items(), key=lambda x: -len(x[1])):
        logger.info("  %-20s %5d files", category, len(files))

    logger.info("  %s", "-" * 32)
    logger.info("  %-20s %5d files", "TOTAL", total)
    logger.info("")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments, falling back to interactive prompts."""
    parser = argparse.ArgumentParser(
        description="Extract an archive and sort files into category folders.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python sort_unzip.py Documents.rar
  python sort_unzip.py Documents.zip --output ./sorted
  python sort_unzip.py backup.7z --dry-run
  python sort_unzip.py  (interactive mode)
        """,
    )
    parser.add_argument(
        "archive", nargs="?", default=None,
        help="Path to the archive file (zip, rar, 7z, tar, etc.)",
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output directory for sorted files (default: same folder as archive)",
    )
    parser.add_argument(
        "--dry-run", "-n", action="store_true",
        help="Preview what would happen without moving any files",
    )
    parser.add_argument(
        "--password", "-p", default=None,
        help="Password for encrypted archives (omit to be prompted if needed)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show detailed per-file logging in the console",
    )

    args = parser.parse_args()

    # Interactive fallback if no archive was specified
    if args.archive is None:
        print("\n  sort_unzip - Archive extractor and file sorter")
        print("  " + "=" * 46)
        args.archive = input("\n  Path to archive file: ").strip().strip('"')
        if not args.archive:
            print("  No archive specified. Exiting.")
            sys.exit(0)

        out = input("  Output directory (Enter = same folder as archive): ").strip().strip('"')
        if out:
            args.output = out

        dry = input("  Dry run? (y/N): ").strip().lower()
        args.dry_run = dry in ("y", "yes")

    return args


def main() -> None:
    """Entry point."""
    args = parse_args()

    # Validate archive path
    archive = Path(args.archive).resolve()
    if not archive.is_file():
        print(f"\n  ERROR: File not found: {archive}")
        sys.exit(1)

    if archive.suffix.lower() not in ARCHIVE_EXTENSIONS:
        print(f"\n  WARNING: '{archive.suffix}' may not be a supported archive format.")
        print(f"  Supported: {', '.join(sorted(ARCHIVE_EXTENSIONS))}")
        proceed = input("  Try anyway? (y/N): ").strip().lower()
        if proceed not in ("y", "yes"):
            sys.exit(0)

    # Determine output directory
    if args.output:
        output_dir = Path(args.output).resolve()
    else:
        output_dir = archive.parent / f"{archive.stem}_sorted"

    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up logging (goes to both console and a log file in the output dir)
    logger = setup_logging(output_dir, verbose=args.verbose)

    logger.info("")
    logger.info("sort_unzip - Archive extractor and file sorter")
    logger.info("=" * 50)
    logger.info("  Archive:  %s", archive.name)
    logger.info("  Output:   %s", output_dir)
    logger.info("  Dry run:  %s", "Yes" if args.dry_run else "No")
    logger.info("")

    # Find 7-Zip
    seven_zip = find_7zip()
    logger.debug("Using 7-Zip: %s", seven_zip)

    # Handle password: auto-detect encrypted archives, prompt if needed
    password = args.password
    if password is None and archive_is_encrypted(archive, seven_zip):
        logger.info("Archive is password-protected.")
        password = getpass.getpass("  Enter password: ")

    # Extract into a temporary directory, then sort from there
    temp_dir = output_dir / "_extracted_temp"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Step 1: Extract
        success = extract_archive(archive, temp_dir, seven_zip, logger,
                                  password=password)
        if not success:
            logger.error("Extraction failed. Aborting.")
            sys.exit(1)

        # Step 2: Collect all extracted files (flatten)
        files = collect_files(temp_dir)
        if not files:
            logger.warning("Archive appears to be empty -- no files found.")
            sys.exit(0)

        logger.info("Found %d files to sort.", len(files))
        logger.info("")

        # Step 3: Sort into category folders
        results = sort_files(files, output_dir, logger, dry_run=args.dry_run)

        # Step 4: Summary
        print_summary(results, logger, dry_run=args.dry_run)

        if args.dry_run:
            logger.info("This was a dry run. No files were moved.")
            logger.info("Run again without --dry-run to sort for real.")
        else:
            logger.info("Files sorted into: %s", output_dir)
            logger.info("Log saved to: %s", output_dir / "sort_unzip.log")

    finally:
        # Clean up the temp extraction directory
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug("Cleaned up temp directory.")

    logger.info("")


if __name__ == "__main__":
    main()
