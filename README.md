# SmartSearch

**SmartSearch** is a Linux desktop utility that acts like a visual `Ctrl+F`.

Instead of relying on an app or website's built-in search, SmartSearch reads visible text with OCR, scrolls automatically, and looks for the word or phrase you entered. It can stop on the first result, search for every result, highlight matches on screen, and save highlighted screenshots.

This makes it useful for websites, chats, logs, documents, dashboards, and other interfaces where normal search is limited or unavailable.

## Features

- Exact or fuzzy OCR matching
- Interactive screen-area selection
- Automatic scrolling up or down
- On-screen match highlighting
- Highlighted screenshot capture
- Stop on first result or find every result
- Remembers your previous search region
- Basic end-of-page / end-of-scroll detection
- Results saved automatically to `~/Documents/smartsearch-results/`
- PyAutoGUI failsafe support
- No app-specific API required; it searches what is visually displayed on screen

## How it works

SmartSearch repeatedly:

1. Captures the selected area of your screen.
2. Preprocesses the image for OCR.
3. Reads visible text with Tesseract.
4. Checks for the phrase you entered.
5. Highlights or saves the match if found.
6. Scrolls and repeats until the search finishes.

## Requirements

SmartSearch is currently intended for Linux desktop environments.

You need:

- Python 3
- Tesseract OCR
- Tkinter
- `scrot`
- A desktop session compatible with PyAutoGUI

### Ubuntu / Linux Mint / Debian

Install the system dependencies:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip tesseract-ocr python3-tk scrot
```

Create a virtual environment:

```bash
python3 -m venv ~/.smartsearch-env
source ~/.smartsearch-env/bin/activate
```

Install the Python dependencies:

```bash
pip install -r requirements.txt
```

## Run

Activate the environment:

```bash
source ~/.smartsearch-env/bin/activate
```

Then start SmartSearch:

```bash
python smartsearch.py
```

SmartSearch will ask you for:

1. The word or phrase to search for
2. Exact or fuzzy matching
3. The screen boundaries to search
4. Scroll direction
5. Whether to highlight, save screenshots, do both, or just stop
6. Whether to stop at the first result or find every result

## Fuzzy matching

OCR is not always perfect. For example, Tesseract might read:

```text
permission denied
```

as:

```text
permission denled
```

Fuzzy matching compares how similar the OCR result is to your search phrase. SmartSearch defaults to an 85% confidence threshold, which helps recover matches even when OCR makes small mistakes.

## Results

When screenshot saving is enabled, SmartSearch creates a timestamped folder inside:

```text
~/Documents/smartsearch-results/
```

Example:

```text
smartsearch-results/
└── permission-denied_2026-08-17_01-14-25/
    ├── match-001.png
    ├── match-002.png
    ├── match-003.png
    └── results.txt
```

Each screenshot includes a box around the OCR line that matched.

## Controls

- `Ctrl+C` — stop the search
- Move the mouse to the top-left corner of the screen — trigger PyAutoGUI's emergency failsafe

## Notes

- Keep the target application visible while SmartSearch runs.
- Avoid moving or resizing the target window after selecting the search area.
- OCR accuracy depends on font size, contrast, scaling, and the application being searched.
- Smaller search regions are generally faster and more accurate than scanning the whole screen.
- Linux Wayland environments may restrict screenshot or input automation. X11-compatible sessions are generally easier to use with PyAutoGUI.

## Safety

SmartSearch controls your mouse wheel and reads pixels from the selected area of your screen. Test it on non-critical content first and keep PyAutoGUI's failsafe enabled.

## License

SmartSearch is released under the MIT License. See [`LICENSE`](LICENSE).

## Contributing

Bug reports, feature ideas, and pull requests are welcome.

Some ideas for future releases:

- Drag-to-select regions
- Configurable scroll speed
- Search history
- Regex and multi-keyword modes
- Better duplicate-result detection
- GUI mode
- OCR language selection
- Export to CSV or JSON
- Smarter page-end detection
