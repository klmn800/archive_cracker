#!/usr/bin/env python3
"""
crack_rar.py - Password recovery tool for encrypted RAR archives.

Three-phase approach:
  Phase 1: User-provided guesses + automatic variations
  Phase 2: Common password dictionary (built-in top ~5,000)
  Phase 3: Brute-force short alphanumeric strings (1-6 chars)

Uses 7-Zip for password testing. No external dependencies.
"""

import argparse
import itertools
import json
import os
import shutil
import string
import subprocess
import sys
import time
from pathlib import Path


# 7-Zip path (standard Windows install location)
SEVEN_ZIP = r"C:\Program Files\7-Zip\7z.exe"


# ---------------------------------------------------------------------------
# 7-Zip helpers
# ---------------------------------------------------------------------------

def find_7zip() -> str:
    """Locate the 7z executable."""
    if os.path.isfile(SEVEN_ZIP):
        return SEVEN_ZIP
    result = shutil.which("7z")
    if result:
        return result
    print("\n  ERROR: 7-Zip not found.")
    print("  Install it from https://www.7-zip.org/ or add 7z.exe to your PATH.")
    sys.exit(1)


def try_password(archive: str, password: str, seven_zip: str) -> bool:
    """
    Test a single password against the archive.

    Uses '7z t' (test) which verifies without extracting -- faster and uses
    no disk space.  Returns True if the password is correct.
    """
    cmd = [
        seven_zip,
        "t",                    # test archive integrity
        archive,
        f"-p{password}",        # password to try
        "-bso0",                # suppress normal output
        "-bsp0",                # suppress progress
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


# ---------------------------------------------------------------------------
# Variation generator
# ---------------------------------------------------------------------------

def generate_variations(word: str) -> list[str]:
    """
    Given a base word, generate common variations people use when making
    passwords.  Returns a list of candidate passwords (including the
    original word).

    Variations include:
      - Original, lowercase, UPPERCASE, Title Case
      - Append common number suffixes (0-9, 00-99, common years, 123, etc.)
      - Prepend numbers
      - Common leet substitutions (a->@, e->3, o->0, etc.)
      - Reversed
      - Doubled (e.g., "catcat")
    """
    candidates = []
    word = word.strip()
    if not word:
        return candidates

    # Base forms
    bases = list(dict.fromkeys([
        word,
        word.lower(),
        word.upper(),
        word.capitalize(),
        word.title(),
        word.swapcase(),
    ]))

    # Common suffixes people append
    number_suffixes = (
        # Single digits
        [str(i) for i in range(10)]
        # Two-digit combos
        + [f"{i:02d}" for i in range(100)]
        # Three-digit
        + ["123", "321", "456", "789", "000", "111", "222", "333",
           "444", "555", "666", "777", "888", "999", "007"]
        # Common years
        + [str(y) for y in range(1980, 2026)]
        # Common 4-digit patterns
        + ["1234", "4321", "1111", "1337", "6969", "4200", "0000"]
        # Symbols
        + ["!", "!!", "!?", "@", "#", "$", ".", "*"]
    )

    for base in bases:
        candidates.append(base)
        for suffix in number_suffixes:
            candidates.append(base + suffix)
            candidates.append(suffix + base)

    # Leet speak (simple)
    leet_map = {"a": "@", "e": "3", "i": "1", "o": "0", "s": "$", "t": "7"}
    for base in [word.lower()]:
        leet = base
        for char, replacement in leet_map.items():
            leet = leet.replace(char, replacement)
        if leet != base:
            candidates.append(leet)
            candidates.append(leet.capitalize())
            for suffix in ["", "1", "12", "123", "!", "!!"]:
                candidates.append(leet + suffix)

    # Reversed
    candidates.append(word[::-1])
    candidates.append(word.lower()[::-1])

    # Doubled
    candidates.append(word + word)
    candidates.append(word.lower() + word.lower())

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    return unique


def generate_combo_variations(words: list[str]) -> list[str]:
    """
    Generate two-word combinations from the word list.
    People often smash two words/numbers together as a password.
    """
    candidates = []
    # Keep it reasonable -- only combine distinct pairs
    for a in words:
        for b in words:
            if a != b:
                candidates.append(a + b)
                candidates.append(a.lower() + b.lower())
                candidates.append(a.capitalize() + b.capitalize())
                candidates.append(a + "_" + b)
                candidates.append(a + "." + b)
    # Deduplicate
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    return unique


# ---------------------------------------------------------------------------
# Built-in common passwords (top ~700, covers a huge %)
# ---------------------------------------------------------------------------

COMMON_PASSWORDS = [
    # Top 100 most common passwords (various breach datasets)
    "123456", "password", "12345678", "qwerty", "123456789", "12345",
    "1234", "111111", "1234567", "dragon", "123123", "baseball", "abc123",
    "football", "monkey", "letmein", "shadow", "master", "666666",
    "qwertyuiop", "123321", "mustang", "1234567890", "michael", "654321",
    "superman", "1qaz2wsx", "7777777", "121212", "000000", "qazwsx",
    "123qwe", "killer", "trustno1", "jordan", "jennifer", "zxcvbnm",
    "asdfgh", "hunter", "buster", "soccer", "harley", "batman", "andrew",
    "tigger", "sunshine", "iloveyou", "2000", "charlie", "robert",
    "thomas", "hockey", "ranger", "daniel", "starwars", "klaster",
    "112233", "george", "computer", "michelle", "jessica", "pepper",
    "1111", "zxcvbn", "555555", "11111111", "131313", "freedom",
    "777777", "pass", "maggie", "159753", "aaaaaa", "ginger", "princess",
    "joshua", "cheese", "amanda", "summer", "love", "ashley", "nicole",
    "chelsea", "biteme", "matthew", "access", "yankees", "987654321",
    "dallas", "austin", "thunder", "taylor", "matrix", "mobilemail",
    "william", "corvette", "hello", "martin", "heather", "secret",
    "merlin", "diamond", "1234qwer", "gfhjkm", "hammer", "silver",
    # Extended common set
    "welcome", "password1", "password123", "admin", "admin123", "root",
    "toor", "pass123", "test", "test123", "guest", "master123",
    "changeme", "123abc", "abcd1234", "aa123456", "abc1234", "p@ssw0rd",
    "passw0rd", "pa55word", "passw0rd!", "password!", "password1!",
    "qwerty123", "qwerty1", "asdf", "asdfghjkl", "zxcvbnm123",
    "1q2w3e4r", "1q2w3e", "q1w2e3r4", "1qazxsw2", "zaq1xsw2",
    "login", "passwd", "letmein1", "trustno1", "welcome1", "monkey1",
    "dragon1", "master1", "shadow1", "sunshine1", "princess1",
    # Numeric patterns
    "0", "1", "12", "123", "1234", "12345", "123456", "1234567",
    "12345678", "123456789", "1234567890", "0000", "00000", "000000",
    "1111", "11111", "111111", "1212", "1313", "1010", "2222", "3333",
    "4444", "5555", "6666", "7777", "8888", "9999", "1122", "2233",
    "9876", "98765", "987654", "9876543", "98765432", "54321", "4321",
    "321", "21", "0987", "6789", "7890", "2580", "1470", "3692",
    "1357", "2468", "9999", "0123", "01234", "012345",
    # Single characters (user said it could even be one char)
    "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
    "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
    "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M",
    "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z",
    "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
    # Common words people use
    "love", "baby", "angel", "friend", "cool", "sexy", "hot", "god",
    "fuck", "bitch", "shit", "damn", "hell", "happy", "lucky", "money",
    "power", "magic", "rock", "star", "fire", "ice", "dark", "light",
    "king", "queen", "wolf", "eagle", "tiger", "lion", "bear", "hawk",
    "storm", "blade", "ghost", "ninja", "pirate", "knight", "wizard",
    "home", "house", "car", "dog", "cat", "fish", "bird",
    "red", "blue", "green", "black", "white", "gold", "silver",
    "apple", "orange", "banana", "cookie", "candy", "coffee", "pizza",
    "music", "guitar", "piano", "dance", "movie", "game", "play",
    "win", "lost", "open", "close", "start", "stop", "go", "run",
    # Common keyboard patterns
    "qwert", "asdfg", "zxcvb", "poiuy", "lkjhg", "mnbvc",
    "qazwsxedc", "1qa2ws", "zaq12wsx", "qweasdzxc",
    "!@#$%", "!@#$%^", "!@#$%^&", "!@#$%^&*",
    # Empty / space
    "", " ", "  ",
]


# ---------------------------------------------------------------------------
# Checkpoint / progress persistence
# ---------------------------------------------------------------------------
# Saves progress so you can stop and resume without re-trying passwords.
#
# checkpoint.json tracks:
#   - completed_phases: which phases finished without a hit
#   - brute_resume: last brute-force string tried (so we skip ahead)
#   - tried_count: total passwords tested across all runs
#
# tried.txt is an append-only log of every password attempted (phases 1-2).
# For phase 3 brute-force, we use positional resume instead of logging
# every attempt (since it can be millions).

CHECKPOINT_FILE = "crack_rar_checkpoint.json"
TRIED_LOG_FILE = "crack_rar_tried.txt"


class Progress:
    """Manages checkpoint state and the tried-password log."""

    def __init__(self, work_dir: Path):
        self.work_dir = work_dir
        self.checkpoint_path = work_dir / CHECKPOINT_FILE
        self.tried_log_path = work_dir / TRIED_LOG_FILE
        self.tried: set[str] = set()
        self.completed_phases: set[int] = set()
        self.brute_resume: str | None = None
        self.tried_count: int = 0
        self._load()

    def _load(self) -> None:
        """Load checkpoint and tried-password log from disk."""
        # Load checkpoint JSON
        if self.checkpoint_path.is_file():
            try:
                data = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
                self.completed_phases = set(data.get("completed_phases", []))
                self.brute_resume = data.get("brute_resume")
                self.tried_count = data.get("tried_count", 0)
            except (json.JSONDecodeError, KeyError):
                pass  # corrupt file, start fresh

        # Load tried passwords into memory (for phases 1-2 dedup)
        if self.tried_log_path.is_file():
            with open(self.tried_log_path, "r", encoding="utf-8",
                      errors="ignore") as f:
                for line in f:
                    self.tried.add(line.rstrip("\n"))

        if self.tried or self.completed_phases or self.brute_resume:
            print(f"  Resuming: {self.tried_count:,} passwords tried previously, "
                  f"phases {sorted(self.completed_phases) or 'none'} complete.")

    def _save_checkpoint(self) -> None:
        """Write the checkpoint JSON to disk."""
        data = {
            "completed_phases": sorted(self.completed_phases),
            "brute_resume": self.brute_resume,
            "tried_count": self.tried_count,
        }
        self.checkpoint_path.write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )

    def mark_tried(self, password: str) -> None:
        """Record a password as tried (phases 1-2 only)."""
        self.tried.add(password)
        self.tried_count += 1

    def flush_tried(self, passwords: list[str]) -> None:
        """Append a batch of passwords to the tried log file."""
        with open(self.tried_log_path, "a", encoding="utf-8") as f:
            for pw in passwords:
                f.write(pw + "\n")

    def mark_phase_complete(self, phase: int) -> None:
        """Mark a phase as fully exhausted (no match found)."""
        self.completed_phases.add(phase)
        self._save_checkpoint()

    def save_brute_resume(self, last_pw: str) -> None:
        """Save the brute-force resume point."""
        self.brute_resume = last_pw
        self._save_checkpoint()

    def is_phase_done(self, phase: int) -> bool:
        """Check if a phase was already completed in a prior run."""
        return phase in self.completed_phases

    def already_tried(self, password: str) -> bool:
        """Check if a password was already attempted."""
        return password in self.tried

    def reset(self) -> None:
        """Delete all progress files to start completely fresh."""
        if self.checkpoint_path.is_file():
            self.checkpoint_path.unlink()
        if self.tried_log_path.is_file():
            self.tried_log_path.unlink()
        self.tried.clear()
        self.completed_phases.clear()
        self.brute_resume = None
        self.tried_count = 0


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------

def run_phase(archive: str, passwords: list[str], seven_zip: str,
              phase_name: str, progress: Progress,
              phase_num: int) -> str | None:
    """
    Try each password in the list, skipping any already tried.
    Shows live progress.  Returns the correct password or None.
    """
    # Filter out passwords we've already tried in a previous run
    remaining = [pw for pw in passwords if not progress.already_tried(pw)]
    skipped = len(passwords) - len(remaining)
    total = len(remaining)

    if total == 0:
        if skipped > 0:
            print(f"\n  --- {phase_name} ---")
            print(f"  All {skipped:,} candidates already tried. Skipping.")
        return None

    print(f"\n  --- {phase_name} ---")
    if skipped > 0:
        print(f"  Skipping {skipped:,} already-tried passwords.")
    print(f"  Candidates to try: {total:,}")

    batch: list[str] = []  # buffer for flushing to tried log
    start = time.time()

    for i, pw in enumerate(remaining, 1):
        # Display progress every 50 attempts and on the first one
        if i == 1 or i % 50 == 0 or i == total:
            elapsed = time.time() - start
            rate = i / elapsed if elapsed > 0 else 0
            display_pw = pw if len(pw) <= 20 else pw[:17] + "..."
            print(f"\r  [{i:,}/{total:,}] {rate:.0f}/sec | trying: {display_pw:<25}",
                  end="", flush=True)

        if try_password(archive, pw, seven_zip):
            elapsed = time.time() - start
            print(f"\r  [{i:,}/{total:,}] FOUND after {elapsed:.1f}s{' ' * 30}")
            # Flush remaining batch before returning
            if batch:
                progress.flush_tried(batch)
            return pw

        progress.mark_tried(pw)
        batch.append(pw)

        # Flush to disk every 500 passwords
        if len(batch) >= 500:
            progress.flush_tried(batch)
            batch.clear()

    # Flush any remaining
    if batch:
        progress.flush_tried(batch)

    elapsed = time.time() - start
    print(f"\r  [{total:,}/{total:,}] exhausted in {elapsed:.1f}s{' ' * 30}")
    progress.mark_phase_complete(phase_num)
    return None


def brute_force_generator(max_length: int, charset: str,
                          resume_after: str | None = None):
    """
    Yield all strings of length 1..max_length from the given charset.
    If resume_after is set, skip everything up to and including that string.
    """
    skipping = resume_after is not None

    for length in range(1, max_length + 1):
        count = len(charset) ** length
        if skipping and resume_after is not None and len(resume_after) > length:
            # Entire length block was already done, skip it
            print(f"\n  Skipping {length}-char block ({count:,} candidates, "
                  f"already done)...")
            continue
        print(f"\n  Brute-forcing {length}-character combinations "
              f"({count:,} candidates)...")
        for combo in itertools.product(charset, repeat=length):
            pw = "".join(combo)
            if skipping:
                if pw == resume_after:
                    skipping = False
                    print(f"\n  Resumed after '{resume_after}'.")
                continue
            yield pw


def run_brute_force(archive: str, seven_zip: str, progress: Progress,
                    max_length: int = 6) -> str | None:
    """
    Phase 3: systematic brute-force of short alphanumeric passwords.
    Saves checkpoint periodically so progress isn't lost on interrupt.
    """
    charset = string.ascii_lowercase + string.digits
    print(f"\n  --- Phase 3: Brute-force (1-{max_length} chars, "
          f"a-z + 0-9) ---")

    if progress.brute_resume:
        print(f"  Resuming after: '{progress.brute_resume}'")
    else:
        print(f"  Starting from scratch.")
    print(f"  This may take a while for longer lengths.")

    start = time.time()
    count = 0
    last_pw = ""

    for pw in brute_force_generator(max_length, charset, progress.brute_resume):
        count += 1
        last_pw = pw

        if count % 50 == 0:
            elapsed = time.time() - start
            rate = count / elapsed if elapsed > 0 else 0
            print(f"\r  [{count:,} tried] {rate:.0f}/sec | trying: {pw:<10}",
                  end="", flush=True)

        if try_password(archive, pw, seven_zip):
            elapsed = time.time() - start
            print(f"\r  [{count:,} tried] FOUND after {elapsed:.1f}s{' ' * 20}")
            return pw

        # Save checkpoint every 1,000 attempts
        if count % 1000 == 0:
            progress.brute_resume = pw
            progress.tried_count += 1000
            progress.save_brute_resume(pw)

    # Final checkpoint
    if last_pw:
        progress.brute_resume = last_pw
        progress.save_brute_resume(last_pw)

    elapsed = time.time() - start
    print(f"\r  [{count:,} tried] exhausted in {elapsed:.1f}s{' ' * 20}")
    progress.mark_phase_complete(3)
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Recover the password for your own encrypted RAR archive.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  python crack_rar.py Documents.rar --wordlist my_guesses.txt
  python crack_rar.py Documents.rar --words "cat,dog,myname,1234"
  python crack_rar.py Documents.rar --phase 2
  python crack_rar.py Documents.rar --brute-max 5
        """,
    )
    parser.add_argument(
        "archive",
        help="Path to the encrypted RAR archive",
    )
    parser.add_argument(
        "--wordlist", "-w", default=None,
        help="Path to a text file with one password guess per line",
    )
    parser.add_argument(
        "--words", default=None,
        help="Comma-separated list of personal guess words (e.g., "
             "'cat,fluffy,birthday,2019')",
    )
    parser.add_argument(
        "--phase", type=int, default=0, choices=[0, 1, 2, 3],
        help="Start from a specific phase (0=all, 1=personal, 2=common, "
             "3=brute-force)",
    )
    parser.add_argument(
        "--brute-max", type=int, default=5,
        help="Max password length for brute-force phase (default: 5)",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Clear all saved progress and start fresh",
    )
    return parser.parse_args()


def load_wordlist(path: str) -> list[str]:
    """Load passwords from a text file, one per line."""
    words = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            word = line.strip()
            if word:
                words.append(word)
    return words


def main() -> None:
    args = parse_args()

    archive = Path(args.archive).resolve()
    if not archive.is_file():
        print(f"\n  ERROR: File not found: {archive}")
        sys.exit(1)

    seven_zip = find_7zip()

    print("\n  crack_rar - RAR Password Recovery Tool")
    print("  " + "=" * 42)
    print(f"  Archive:    {archive.name}")
    print(f"  Size:       {archive.stat().st_size / (1024*1024):.0f} MB")
    print(f"  Brute-max:  {args.brute_max} characters")

    # Initialize progress tracker (saves to files next to the archive)
    progress = Progress(archive.parent)

    if args.reset:
        progress.reset()
        print("  Progress:   Reset (starting fresh)")

    # Collect personal guesses
    personal_words = []
    if args.wordlist:
        personal_words.extend(load_wordlist(args.wordlist))
        print(f"  Wordlist:   {args.wordlist} ({len(personal_words)} words)")
    if args.words:
        personal_words.extend([w.strip() for w in args.words.split(",") if w.strip()])

    found = None
    start_phase = args.phase if args.phase > 0 else 1

    # Phase 1: Personal guesses + variations
    if start_phase <= 1 and personal_words and not progress.is_phase_done(1):
        print(f"\n  Building variations from {len(personal_words)} personal words...")
        phase1 = []
        for word in personal_words:
            phase1.extend(generate_variations(word))
        # Also add two-word combos
        if len(personal_words) > 1:
            phase1.extend(generate_combo_variations(personal_words))
        # Deduplicate
        seen = set()
        phase1_unique = []
        for p in phase1:
            if p not in seen:
                seen.add(p)
                phase1_unique.append(p)
        found = run_phase(str(archive), phase1_unique, seven_zip,
                          "Phase 1: Personal guesses + variations",
                          progress, phase_num=1)
    elif start_phase <= 1 and progress.is_phase_done(1):
        print("\n  Phase 1 already completed in a prior run. Skipping.")

    # Phase 2: Common passwords
    if found is None and start_phase <= 2 and not progress.is_phase_done(2):
        found = run_phase(str(archive), COMMON_PASSWORDS, seven_zip,
                          "Phase 2: Common passwords dictionary",
                          progress, phase_num=2)
    elif found is None and start_phase <= 2 and progress.is_phase_done(2):
        print("\n  Phase 2 already completed in a prior run. Skipping.")

    # Phase 3: Brute-force
    if found is None and start_phase <= 3 and not progress.is_phase_done(3):
        found = run_brute_force(str(archive), seven_zip, progress,
                                max_length=args.brute_max)
    elif found is None and start_phase <= 3 and progress.is_phase_done(3):
        print(f"\n  Phase 3 already completed (up to {args.brute_max} chars). Skipping.")

    # Results
    print("\n  " + "=" * 42)
    if found is not None:
        print(f"  PASSWORD FOUND: {found}")
        print(f"  " + "=" * 42)
        print(f"\n  You can now extract with:")
        print(f'  python sort_unzip.py "{archive}" -p "{found}"')
        # Clean up progress files -- we're done!
        progress.reset()
        print("\n  (Progress files cleaned up.)")
    else:
        print("  Password not found in any phase.")
        print("  " + "=" * 42)
        print(f"\n  Progress saved -- {progress.tried_count:,} total attempts recorded.")
        print("  Re-run the same command to resume where you left off.")
        print("\n  Suggestions:")
        print("  - Add more personal guesses with --words or --wordlist")
        print(f"  - Increase brute-force length with --brute-max {args.brute_max + 1}")
        print("  - Use --reset to clear progress and start over")
        print("  - Think about what password you might have used back then")

    print()


if __name__ == "__main__":
    main()
