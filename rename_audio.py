"""
rename_audio.py
----------------
Compares old vs new *_english.json files to determine what attire folders
and audio files were renamed. Applies folder renames across ALL language
subfolders (since attire folder names are language-agnostic), but only
applies individual file renames to the english folder (only language we
have new JSONs for).

Repo structure assumed:
  NowhereAudios/
    CharactersJson/
      rahu_english.json
      rahu_chinese.json
      rahu_japanese.json
      rahu_korean.json
    audio/
      rahu/
        english/
          default/
            vo_rahu_cacha_001.aac
          radiant_stealth/
        chinese/
          default/
        japanese/
          default/
        korean/
          default/

  (action repo)/
    newJson/
      voicelines/
        rahu_english.json     <- newly generated
      characters.json

Usage:
  python rename_audio.py
    --old-dir  ./NowhereAudios/CharactersJson
    --new-dir  ./newJson/voicelines
    --audio-dir ./NowhereAudios/audio
    --dry-run true
"""

import argparse
import json
import os
import sys


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--old-dir",    required=True, help="CharactersJson folder in the audio repo")
    parser.add_argument("--new-dir",    required=True, help="newJson/voicelines folder in this repo")
    parser.add_argument("--audio-dir",  required=True, help="audio/ folder in the audio repo")
    parser.add_argument("--dry-run",    default="true")
    return parser.parse_args()


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def strip_prefix(filename):
    return filename[5:] if filename.startswith("File:") else filename


def build_attire_map(old_data, new_data):
    """
    Match old attire keys -> new attire keys by filename overlap.
    Returns {old_attire: new_attire}.
    Only includes pairs where something actually changed.
    """
    attire_map = {}
    used_old = set()

    for new_attire in new_data:
        new_files = {
            strip_prefix(l["filename"])
            for l in new_data[new_attire]
            if l.get("filename")
        }

        best_old, best_score = None, 0
        for old_attire in old_data:
            if old_attire in used_old:
                continue
            old_files = {
                strip_prefix(l["filename"])
                for l in old_data[old_attire]
                if l.get("filename")
            }
            score = len(new_files & old_files)
            if score > best_score:
                best_old, best_score = old_attire, score

        if best_old and best_score > 0:
            attire_map[best_old] = new_attire
            used_old.add(best_old)

    # Only keep pairs where the name actually changed
    return {old: new for old, new in attire_map.items() if old != new}


def main():
    args = parse_args()
    dry_run = args.dry_run.lower() != "false"

    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}\n")

    renames = 0
    errors  = 0

    # Only english JSONs exist in newJson/voicelines
    new_files = {f for f in os.listdir(args.new_dir) if f.endswith("_english.json")}
    old_files = {f for f in os.listdir(args.old_dir) if f.endswith("_english.json")}
    common    = new_files & old_files

    print(f"Comparing {len(common)} character(s) with updated English JSONs\n")

    for json_file in sorted(common):
        char_name = json_file.replace("_english.json", "")
        old_data  = load_json(os.path.join(args.old_dir, json_file))
        new_data  = load_json(os.path.join(args.new_dir, json_file))

        char_audio = os.path.join(args.audio_dir, char_name)
        if not os.path.isdir(char_audio):
            print(f"  ⚠  No audio folder for {char_name!r} — skipping\n")
            continue

        attire_map = build_attire_map(old_data, new_data)

        if not attire_map:
            # No folder renames — still check individual files below
            pass
        else:
            print(f"[{char_name}] Attire renames detected:")
            for old_a, new_a in attire_map.items():
                print(f"  {old_a!r}  →  {new_a!r}")

        # ── Step 1: rename attire folders across ALL languages ────────────
        if attire_map:
            for lang in sorted(os.listdir(char_audio)):
                lang_path = os.path.join(char_audio, lang)
                if not os.path.isdir(lang_path):
                    continue

                for old_attire, new_attire in attire_map.items():
                    old_folder = os.path.join(lang_path, old_attire)
                    new_folder = os.path.join(lang_path, new_attire)

                    if not os.path.isdir(old_folder):
                        # Folder might not exist for all languages — that's fine
                        continue
                    if os.path.exists(new_folder):
                        print(f"  ⚠  Target already exists, skipping: {new_folder}")
                        errors += 1
                        continue

                    print(f"  FOLDER [{lang}]  {old_folder}  →  {new_folder}")
                    if not dry_run:
                        os.rename(old_folder, new_folder)
                    renames += 1

        # ── Step 2: rename individual files — English only ────────────────
        english_path = os.path.join(char_audio, "english")
        if not os.path.isdir(english_path):
            continue

        # For attires that didn't rename, still check for file-level changes
        full_attire_map = {old: new for old, new in build_attire_map(old_data, new_data).items()}
        # Also include unchanged attires
        for attire in new_data:
            if attire not in full_attire_map.values():
                full_attire_map[attire] = attire

        for old_attire, new_attire in full_attire_map.items():
            # After a live rename the folder is at new_attire; during dry-run still old
            attire_path = os.path.join(english_path, old_attire if dry_run else new_attire)
            if not os.path.isdir(attire_path):
                continue

            old_list = [
                strip_prefix(l["filename"])
                for l in old_data.get(old_attire, [])
                if l.get("filename")
            ]
            new_list = [
                strip_prefix(l["filename"])
                for l in new_data.get(new_attire, [])
                if l.get("filename")
            ]
            files_on_disk = set(os.listdir(attire_path))

            for idx, old_file in enumerate(old_list):
                if idx >= len(new_list):
                    break
                new_file = new_list[idx]
                if old_file == new_file:
                    continue

                if old_file not in files_on_disk:
                    print(f"  ⚠  Missing on disk: {os.path.join(attire_path, old_file)}")
                    errors += 1
                    continue
                if new_file in files_on_disk and not dry_run:
                    print(f"  ⚠  Target already exists: {os.path.join(attire_path, new_file)}")
                    errors += 1
                    continue

                print(f"  FILE [english/{old_attire}]  {old_file}  →  {new_file}")
                if not dry_run:
                    os.rename(
                        os.path.join(attire_path, old_file),
                        os.path.join(attire_path, new_file),
                    )
                renames += 1

    print(f"\n{'─' * 50}")
    print(f"{'Would apply' if dry_run else 'Applied'}: {renames} rename(s), {errors} warning(s)")
    if dry_run and renames > 0:
        print("Run with --dry-run false to apply.")
    elif renames == 0:
        print("Everything is already in sync.")


if __name__ == "__main__":
    main()