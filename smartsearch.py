#!/usr/bin/env python3

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import pyautogui
import pytesseract
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageOps, ImageStat
from rapidfuzz.fuzz import partial_ratio

try:
    import tkinter as tk
except ImportError:
    tk = None


APP_DIR = Path.home() / ".config" / "smartsearch"
CONFIG_FILE = APP_DIR / "config.json"
RESULTS_ROOT = Path.home() / "Documents" / "smartsearch-results"

DEFAULT_THRESHOLD = 85
SCROLL_AMOUNT = 5
SETTLE_DELAY = 0.75
END_PAGE_THRESHOLD = 1.5
END_PAGE_STAGNANT_SCANS = 3

pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.03


def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def ask(prompt, default=None):
    if default is None:
        return input(prompt).strip()
    value = input(f"{prompt} [{default}]: ").strip()
    return value if value else str(default)


def ask_choice(title, options, default=1):
    print(f"\n{title}")
    for i, option in enumerate(options, 1):
        print(f"{i}. {option}")

    while True:
        raw = input(f"> [{default}] ").strip()
        if not raw:
            return default
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return int(raw)
        print("Enter one of the listed numbers.")


def load_config():
    try:
        return json.loads(CONFIG_FILE.read_text())
    except Exception:
        return {}


def save_config(region):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"region": region}, indent=2))


def calibrate_region():
    print("\n── SELECT SEARCH AREA ──")

    print("\nMove the mouse to the TOP-LEFT of the area to search.")
    input("Press ENTER when ready...")
    tl = pyautogui.position()
    print(f"✓ Top-left: {tl.x}, {tl.y}")

    print("\nMove the mouse to the BOTTOM-RIGHT of the area to search.")
    input("Press ENTER when ready...")
    br = pyautogui.position()
    print(f"✓ Bottom-right: {br.x}, {br.y}")

    width = br.x - tl.x
    height = br.y - tl.y

    if width <= 0 or height <= 0:
        raise ValueError("Invalid region: bottom-right must be below/right of top-left.")

    region = [tl.x, tl.y, width, height]
    save_config(region)
    return region


def preprocess(img: Image.Image) -> Image.Image:
    gray = ImageOps.grayscale(img)
    gray = ImageEnhance.Contrast(gray).enhance(1.7)
    # 2x upscale helps Tesseract on small UI text
    return gray.resize((gray.width * 2, gray.height * 2))


def ocr_lines(img: Image.Image):
    processed = preprocess(img)

    data = pytesseract.image_to_data(
        processed,
        config="--psm 6",
        output_type=pytesseract.Output.DICT,
    )

    groups = {}

    for i, raw in enumerate(data["text"]):
        word = raw.strip()
        if not word:
            continue

        try:
            conf = float(data["conf"][i])
        except Exception:
            conf = -1

        key = (
            data["block_num"][i],
            data["par_num"][i],
            data["line_num"][i],
        )

        entry = groups.setdefault(
            key,
            {
                "words": [],
                "left": [],
                "top": [],
                "right": [],
                "bottom": [],
                "conf": [],
            },
        )

        x = int(data["left"][i])
        y = int(data["top"][i])
        w = int(data["width"][i])
        h = int(data["height"][i])

        entry["words"].append(word)
        entry["left"].append(x)
        entry["top"].append(y)
        entry["right"].append(x + w)
        entry["bottom"].append(y + h)
        if conf >= 0:
            entry["conf"].append(conf)

    lines = []

    for entry in groups.values():
        text = " ".join(entry["words"]).strip()
        if not text:
            continue

        # OCR was performed on a 2x image, so convert boxes back to screen scale.
        x1 = min(entry["left"]) // 2
        y1 = min(entry["top"]) // 2
        x2 = max(entry["right"]) // 2
        y2 = max(entry["bottom"]) // 2

        lines.append(
            {
                "text": text,
                "clean": clean_text(text),
                "bbox": (x1, y1, x2, y2),
                "ocr_conf": (
                    sum(entry["conf"]) / len(entry["conf"])
                    if entry["conf"]
                    else 0
                ),
            }
        )

    lines.sort(key=lambda x: (x["bbox"][1], x["bbox"][0]))
    return lines


def find_best_match(lines, target, mode, threshold):
    target_clean = clean_text(target)
    best = None

    for line in lines:
        candidate = line["clean"]
        if not candidate:
            continue

        if mode == "exact":
            matched = target_clean in candidate
            score = 100 if matched else 0
        else:
            score = partial_ratio(target_clean, candidate)
            matched = score >= threshold

        if matched and (best is None or score > best["score"]):
            best = dict(line)
            best["score"] = float(score)

    return best


def screenshot_difference(a: Image.Image, b: Image.Image) -> float:
    a = ImageOps.grayscale(a).resize((160, 100))
    b = ImageOps.grayscale(b).resize((160, 100))
    diff = ImageChops.difference(a, b)
    return ImageStat.Stat(diff).mean[0]


def safe_slug(text):
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return (slug[:45] or "search")


def save_highlighted_screenshot(img, match, folder, index):
    output = img.copy().convert("RGB")
    draw = ImageDraw.Draw(output)

    x1, y1, x2, y2 = match["bbox"]
    pad = 6
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(output.width - 1, x2 + pad)
    y2 = min(output.height - 1, y2 + pad)

    # Thick outline without relying on a custom font.
    for offset in range(4):
        draw.rectangle(
            (x1 - offset, y1 - offset, x2 + offset, y2 + offset),
            outline="red",
        )

    label = f"MATCH {index} - {match['score']:.0f}%"
    label_y = max(0, y1 - 18)
    draw.rectangle((x1, label_y, x1 + 150, label_y + 16), fill="red")
    draw.text((x1 + 4, label_y + 2), label, fill="white")

    path = folder / f"match-{index:03d}.png"
    output.save(path)
    return path


class Overlay:
    def __init__(self):
        self.root = None
        self.windows = []

    def show(self, screen_bbox, duration=2.0):
        if tk is None:
            print("⚠ On-screen highlight unavailable: tkinter is not installed.")
            return

        try:
            if self.root is None:
                self.root = tk.Tk()
                self.root.withdraw()

            x1, y1, x2, y2 = screen_bbox
            thickness = 4

            for w in self.windows:
                try:
                    w.destroy()
                except Exception:
                    pass
            self.windows = []

            pieces = [
                (x1, y1, max(1, x2 - x1), thickness),
                (x1, y2 - thickness, max(1, x2 - x1), thickness),
                (x1, y1, thickness, max(1, y2 - y1)),
                (x2 - thickness, y1, thickness, max(1, y2 - y1)),
            ]

            for x, y, width, height in pieces:
                win = tk.Toplevel(self.root)
                win.overrideredirect(True)
                win.attributes("-topmost", True)
                try:
                    win.attributes("-alpha", 0.85)
                except Exception:
                    pass
                win.configure(bg="red")
                win.geometry(f"{width}x{height}+{x}+{y}")
                self.windows.append(win)

            self.root.update()
            end = time.time() + duration
            while time.time() < end:
                self.root.update()
                time.sleep(0.02)

            for w in self.windows:
                w.destroy()
            self.windows = []
            self.root.update()

        except Exception as e:
            print(f"⚠ Could not show overlay: {e}")


def main():
    print(
        """
╔══════════════════════════════════╗
║       SMART SCREEN SEARCH        ║
╚══════════════════════════════════╝
"""
    )

    target = ""
    while not target:
        target = input("Word or phrase to search for:\n> ").strip()

    match_choice = ask_choice(
        "Match mode:",
        ["Exact phrase", "Fuzzy (recommended for OCR)"],
        default=2,
    )
    mode = "exact" if match_choice == 1 else "fuzzy"

    threshold = DEFAULT_THRESHOLD
    if mode == "fuzzy":
        while True:
            raw = ask("Fuzzy confidence", DEFAULT_THRESHOLD)
            try:
                threshold = int(raw)
                if 1 <= threshold <= 100:
                    break
            except ValueError:
                pass
            print("Enter a number from 1 to 100.")

    config = load_config()
    region = None

    if "region" in config and len(config["region"]) == 4:
        r = config["region"]
        use_old = input(
            f"\nUse previous search area? "
            f"({r[0]}, {r[1]}, {r[2]}x{r[3]}) [Y/n]: "
        ).strip().lower()

        if use_old in ("", "y", "yes"):
            region = r

    if region is None:
        region = calibrate_region()

    direction_choice = ask_choice(
        "Scroll direction:",
        ["Down", "Up"],
        default=1,
    )
    scroll_direction = -1 if direction_choice == 1 else 1

    output_choice = ask_choice(
        "When a match is found:",
        [
            "Highlight it on screen",
            "Save highlighted screenshot",
            "Both",
            "Just stop on it",
        ],
        default=3,
    )

    behavior_choice = ask_choice(
        "Search behavior:",
        ["Stop at first result", "Find every result"],
        default=1,
    )
    find_all = behavior_choice == 2

    save_shots = output_choice in (2, 3)
    show_overlay = output_choice in (1, 3)

    session_folder = None
    results_file = None

    if save_shots or find_all:
        stamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        session_folder = RESULTS_ROOT / f"{safe_slug(target)}_{stamp}"
        session_folder.mkdir(parents=True, exist_ok=True)
        results_file = session_folder / "results.txt"

        results_file.write_text(
            f"Search: {target}\n"
            f"Mode: {mode}\n"
            f"Threshold: {threshold if mode == 'fuzzy' else 'exact'}\n"
            f"Direction: {'down' if scroll_direction < 0 else 'up'}\n"
            f"Region: {region}\n\n"
        )

    overlay = Overlay()

    print("\n🔎 SEARCHING...")
    print("Ctrl+C = stop")
    print("Move mouse to the top-left screen corner = PyAutoGUI emergency stop\n")

    scan_count = 0
    match_count = 0
    stagnant = 0
    previous_after_scroll = None
    last_match_key = None

    try:
        while True:
            scan_count += 1
            shot = pyautogui.screenshot(region=tuple(region))
            lines = ocr_lines(shot)
            match = find_best_match(lines, target, mode, threshold)

            if match:
                # Suppress the same visible result on consecutive scans.
                x1, y1, x2, y2 = match["bbox"]
                current_key = (
                    clean_text(match["text"]),
                    round((y1 + y2) / 40),
                )

                if current_key != last_match_key:
                    match_count += 1
                    last_match_key = current_key

                    print(f"✓ MATCH #{match_count}")
                    print(f'  OCR: "{match["text"]}"')
                    print(f"  Match confidence: {match['score']:.0f}%")

                    screen_bbox = (
                        region[0] + x1,
                        region[1] + y1,
                        region[0] + x2,
                        region[1] + y2,
                    )

                    if show_overlay:
                        overlay.show(screen_bbox, duration=2.0)

                    saved_path = None
                    if save_shots:
                        saved_path = save_highlighted_screenshot(
                            shot, match, session_folder, match_count
                        )
                        print(f"  📸 {saved_path}")

                    if results_file:
                        with results_file.open("a") as f:
                            f.write(
                                f"Match {match_count}\n"
                                f"OCR: {match['text']}\n"
                                f"Match confidence: {match['score']:.0f}%\n"
                                f"Screenshot: {saved_path.name if saved_path else 'none'}\n\n"
                            )

                    if not find_all:
                        print("\n✅ Search stopped on the first result.")
                        break

                    # Move farther after a hit to reduce duplicate captures.
                    pyautogui.moveTo(region[0] + region[2] // 2, region[1] + region[3] // 2)
                    pyautogui.scroll(scroll_direction * (SCROLL_AMOUNT + 3))
                    time.sleep(SETTLE_DELAY)
                    previous_after_scroll = pyautogui.screenshot(region=tuple(region))
                    continue
            else:
                last_match_key = None

            if scan_count % 5 == 0:
                print(f"Scan {scan_count}... no new match")

            # Put mouse in the selected region so the correct pane receives scrolling.
            pyautogui.moveTo(
                region[0] + region[2] // 2,
                region[1] + region[3] // 2,
                duration=0.05,
            )

            before = shot
            pyautogui.scroll(scroll_direction * SCROLL_AMOUNT)
            time.sleep(SETTLE_DELAY)
            after = pyautogui.screenshot(region=tuple(region))

            change = screenshot_difference(before, after)

            if change < END_PAGE_THRESHOLD:
                stagnant += 1
            else:
                stagnant = 0

            if stagnant >= END_PAGE_STAGNANT_SCANS:
                print("\n⚠ The page stopped moving. End of scrollable content is likely reached.")
                break

            previous_after_scroll = after

    except KeyboardInterrupt:
        print("\n🛑 Search stopped by user.")
    except pyautogui.FailSafeException:
        print("\n🛑 PyAutoGUI emergency stop triggered.")
    finally:
        print("\n────────────────────────────")
        print("Search finished.")
        print(f"Matches: {match_count}")
        print(f"Scans: {scan_count}")
        if session_folder:
            print(f"Results: {session_folder}")
        print("────────────────────────────")


if __name__ == "__main__":
    main()
