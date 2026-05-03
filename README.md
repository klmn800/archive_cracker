# archive_cracker

Two command-line tools for dealing with old archives: one to recover forgotten passwords, and one to extract and organize the contents by file type.

The cracker exists because the sorter wasn't enough. I built `sort_unzip.py` to clean up an old `.rar` full of mixed files, then realized I'd forgotten the password. So I built `crack_rar.py` to get back in.

**No Python dependencies required** -- both tools use only the standard library plus [7-Zip](https://www.7-zip.org/), which handles the actual archive work.

## Prerequisites

- **Python 3.12+**
- **7-Zip** installed at the default location (`C:\Program Files\7-Zip\7z.exe`) or on your PATH

---

## Tool 1: crack_rar.py -- Password Recovery

Recovers forgotten passwords on your own encrypted archives. Uses a three-phase approach that starts smart (your guesses) before resorting to brute-force.

### The Three Phases

**Phase 1 -- Personal guesses + variations**

You provide seed words (names, numbers, favorite words) and the tool generates ~1,500-2,000 variations per word:
- Case variations: `fluffy`, `FLUFFY`, `Fluffy`
- Number suffixes/prefixes: `fluffy1`, `fluffy99`, `fluffy2019`, `2019fluffy`
- Leet speak: `flu$$y`
- Reversed: `yffulf`
- Doubled: `fluffyfluffy`
- Two-word combos (if multiple seeds): `fluffy2019`, `angus_fluffy`, `AngusFluffy`

**Phase 2 -- Common passwords dictionary**

A built-in list of several hundred frequently-used passwords: `password`, `123456`, `qwerty`, all single characters, keyboard patterns, common names, etc.

**Phase 3 -- Brute-force**

Systematically tries every lowercase alphanumeric combination from 1 character up to a configurable maximum (default: 5). Gets slow at higher lengths:

| Length | Combinations | Estimated time at 25/sec |
|---|---|---|
| 1-3 | ~47,000 | ~30 minutes |
| 4 | 1.7 million | ~19 hours |
| 5 | 60 million | ~28 days |
| 6 | 2.2 billion | ~2.7 years |

### Usage

```bash
# Personal guesses inline
python crack_rar.py Documents.rar --words "angus,fluffy,2019,wedding"

# Personal guesses from a text file (one word per line)
python crack_rar.py Documents.rar --wordlist my_guesses.txt

# Both at once
python crack_rar.py Documents.rar --wordlist my_guesses.txt --words "extra,words"

# Skip to a specific phase
python crack_rar.py Documents.rar --phase 2
python crack_rar.py Documents.rar --phase 3

# Increase brute-force max length
python crack_rar.py Documents.rar --brute-max 6

# Clear saved progress and start over
python crack_rar.py Documents.rar --words "cat,dog" --reset
```

### Wordlist File Format

Plain text, one word per line. These are *seed words* -- the tool generates all the variations automatically. You don't need to write out `fluffy1`, `fluffy2`, etc.; just write `fluffy`.

```
angus
fluffy
wedding
2019
2222
june
```

### Resume Support

The tool saves progress automatically. If you stop it (Ctrl+C) and run the same command again, it picks up where it left off:

- Phases 1-2: every tried password is logged to `crack_rar_tried.txt` and skipped on restart
- Phase 3: the exact brute-force position is saved to `crack_rar_checkpoint.json`
- Completed phases are skipped entirely

Progress files are saved next to the archive and are automatically cleaned up when the password is found. Use `--reset` to wipe them manually.

### Options

| Flag | Description |
|---|---|
| `--wordlist`, `-w` | Path to a text file of seed words |
| `--words` | Comma-separated seed words |
| `--phase` | Start from a specific phase (1, 2, or 3) |
| `--brute-max` | Max length for brute-force (default: 5) |
| `--reset` | Clear saved progress, start fresh |

### Using Larger Password Lists

The built-in common passwords list in `crack_rar.py` is decent but small. For tougher passwords, you can feed in much larger wordlists from the security research community.

#### RockYou (14 million passwords)

The most well-known password list, sourced from a 2009 data breach. It's the standard starting point for password recovery and is freely available.

**How to get it:**

1. **From Kali Linux / SecLists (GitHub):**
   Search for "SecLists" on GitHub -- it's a collection of security testing wordlists maintained by Daniel Miessler. The RockYou list lives at:
   ```
   SecLists/Passwords/Leaked-Databases/rockyou.txt.tar.gz
   ```
   Download and extract the `.tar.gz` to get `rockyou.txt`.

2. **Direct search:**
   Search the web for `rockyou.txt download` -- many security sites host it.

**How to use it:**

Drop the file in your project folder (or anywhere) and point to it:

```bash
python crack_rar.py Documents.rar --wordlist rockyou.txt
```

Note: at 14 million entries and ~25 attempts/sec, a full run through RockYou takes roughly 6-7 days. But passwords are sorted by frequency (most common first), so the most likely candidates are tried early.

#### Other Notable Wordlists

All of these can be found in the **SecLists** GitHub repository or by searching online:

| List | Size | Good for |
|---|---|---|
| `rockyou.txt` | 14 million | General purpose, the classic |
| `10-million-password-list-top-1000000.txt` | 1 million | Faster subset, still high coverage |
| `common-credentials/10k-most-common.txt` | 10,000 | Quick first pass |
| `darkweb2017-top10000.txt` | 10,000 | More recent breach data |
| `xato-net-10-million-passwords.txt` | 10 million | Alternative large list |

#### Combining Approaches

You can use a large wordlist alongside your personal guesses. Phase 1 (personal + variations) runs first, then the wordlist runs as Phase 2:

```bash
python crack_rar.py Documents.rar --words "mydog,2019" --wordlist rockyou.txt
```

Or if you've already exhausted your personal guesses and the built-in list, jump straight to the external wordlist:

```bash
python crack_rar.py Documents.rar --wordlist rockyou.txt --phase 2
```

#### Important Notes on External Wordlists

- Large wordlists are used as-is (one attempt per line). The variation engine from Phase 1 is **not** applied to wordlist entries -- that would turn 14 million into billions.
- The resume system works with external wordlists too. If you stop mid-run, already-tried passwords are skipped on restart.
- These lists exist because of real data breaches. They're used legitimately by security researchers, penetration testers, and people recovering their own forgotten passwords. Use them responsibly.

---

## Tool 2: sort_unzip.py -- Extract & Organize

Extracts any common archive format and sorts all files into category-based subfolders. Flattens nested folder structures so everything is organized purely by file type. Pairs naturally with the cracker -- once you've recovered the password, run this to actually unpack and tidy the contents.

### Categories

| Folder | What goes in it |
|---|---|
| Documents | .pdf, .docx, .txt, .rtf, .epub, .md, ... |
| Spreadsheets | .xlsx, .csv, .ods, .xlsm, ... |
| Presentations | .pptx, .odp, .key, ... |
| Images | .jpg, .png, .gif, .psd, .svg, .heic, ... |
| Videos | .mp4, .avi, .mov, .mkv, .wmv, ... |
| Audio | .mp3, .wav, .flac, .aac, .ogg, ... |
| Archives | .zip, .rar, .7z, .tar, .iso, ... |
| Code | .py, .js, .html, .json, .xml, ... |
| Databases | .db, .sqlite, .mdb, .accdb |
| Fonts | .ttf, .otf, .woff, .woff2 |
| Executables | .exe, .msi, .apk, ... |
| Shortcuts | .lnk, .url |
| Other | Anything not recognized |

### Usage

```bash
# Basic -- creates a "Documents_sorted" folder next to the archive
python sort_unzip.py Documents.rar

# Specify where sorted files should go
python sort_unzip.py Documents.rar --output C:\Users\Me\Documents

# Preview what would happen without moving anything
python sort_unzip.py Documents.rar --dry-run

# Password-protected archive
python sort_unzip.py Documents.rar -p "mypassword"

# See every file as it's sorted (not just progress updates)
python sort_unzip.py Documents.rar --verbose

# Interactive mode (prompts for everything)
python sort_unzip.py
```

### Supported Archive Formats

Anything 7-Zip can handle: `.zip`, `.rar`, `.7z`, `.tar`, `.gz`, `.bz2`, `.xz`, `.tgz`, `.cab`, `.iso`

### What It Does

1. Detects if the archive is password-protected (prompts you if so)
2. Extracts everything to a temporary directory
3. Walks through all extracted files (ignoring hidden files)
4. Moves each file into a category subfolder based on its extension
5. Handles duplicate filenames by appending `(1)`, `(2)`, etc.
6. Prints a summary showing how many files landed in each category
7. Saves a detailed log (`sort_unzip.log`) in the output directory
8. Cleans up the temporary extraction directory

### Options

| Flag | Description |
|---|---|
| `--output`, `-o` | Output directory (default: `<archive_name>_sorted/`) |
| `--dry-run`, `-n` | Preview only, don't move files |
| `--password`, `-p` | Archive password (auto-prompts if needed) |
| `--verbose`, `-v` | Show every file in console output |

---

## Files Generated

| File | Created by | Purpose |
|---|---|---|
| `crack_rar_checkpoint.json` | crack_rar | Phase status + brute-force resume point |
| `crack_rar_tried.txt` | crack_rar | Log of all attempted passwords |
| `*_sorted/` | sort_unzip | Output folder with categorized files |
| `sort_unzip.log` | sort_unzip | Detailed extraction/sorting log |

The `crack_rar` progress files are automatically deleted when a password is found.

## License

MIT -- see [LICENSE](LICENSE).
