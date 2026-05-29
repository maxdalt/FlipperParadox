# Paradox RFID Generator

A Python utility that generates Flipper Zero compatible `.rfid` files for Paradox access control cards. Supply a single card via command-line arguments or process hundreds of cards at once from a CSV file.

---

## Requirements

- Python 3.6 or newer
- No external libraries — uses only Python's built-in modules

Check your Python version:
```bash
python3 --version
```

---

## Files

```
paradox_rfid_generator.py   The main script
cards.csv                   Your input CSV (you provide this)
README.md                   This file
```

---

## Usage

### Mode 1 — Single Card

Generate one `.rfid` file directly from the command line:

```bash
python3 paradox_rfid_generator.py --fc 22 --card 31352
```

With a custom output directory:
```bash
python3 paradox_rfid_generator.py --fc 22 --card 31352 /path/to/output/
```

The `--fc` and `--card` flags can be supplied in any order:
```bash
python3 paradox_rfid_generator.py --card 31352 --fc 22
```

**Example output:**
```
Paradox RFID Generator - Single Card Mode
  FC:         22
  Card ID:    31352
  CRC:        126 (0x7E)
  Data:       00 05 9E 9E 1F B0
  Output:     ./22_31352.rfid

Done.
```

---

### Mode 2 — CSV Batch

Process multiple cards from a CSV file:

```bash
python3 paradox_rfid_generator.py cards.csv
```

With a custom output directory for the `.rfid` files:
```bash
python3 paradox_rfid_generator.py cards.csv /path/to/output/
```

**Example output:**
```
Paradox RFID Generator - CSV Batch Mode
  Input CSV:  cards.csv
  Output dir: ./

Processing 4 rows...

#     FC     CARD     CRC   HEX Data              Status
----------------------------------------------------------------------
1     7      6286     20    00 01 C6 23 85 30     OK -> 7_6286.rfid
2     22     31352    126   00 05 9E 9E 1F B0     OK -> 22_31352.rfid
3     209    63321    24    00 34 7D D6 46 30     OK -> 209_63321.rfid
4     45     8508     72    00 0B 48 4F 12 30     OK -> 45_8508.rfid

Done.
  CSV updated:    cards.csv
  .rfid files:    4 written to './'
```

---

## CSV Format

Your CSV file must have `FC` and `CARD` as column headers (uppercase). Additional columns are ignored.

```csv
FC,CARD
7,6286
22,31352
209,63321
45,8508
```

| Field | Valid Range | Description       |
|-------|-------------|-------------------|
| FC    | 1 – 255     | Facility Code     |
| CARD  | 1 – 65535   | Card ID number    |

After processing, a `HEX` column is appended to the CSV in-place:

```csv
FC,CARD,HEX
7,6286,00 01 C6 23 85 30
22,31352,00 05 9E 9E 1F B0
```

> **Note:** CSV files saved from Microsoft Excel may include a hidden UTF-8 BOM marker. The script handles this automatically.

---

## Output Files

Each generated `.rfid` file follows the Flipper Zero Paradox format:

```
Filetype: Flipper RFID key
Version: 1
Key type: Paradox
Data: 00 01 C6 23 85 30
```

Files are named using the convention `FC_CARD.rfid` — for example, `7_6286.rfid`.

To use on a Flipper Zero, copy the `.rfid` files to the `/ext/lfrfid/` folder on the SD card and open them from the RFID app.

---

## Bit Layout

The 6-byte data field encodes the following information:

| Bits  | Field              |
|-------|--------------------|
| 0–9   | Leading zeros      |
| 10–17 | Facility Code (FC) |
| 18–33 | Card ID            |
| 34–41 | CRC-8 checksum     |
| 42–43 | Protocol stop bits (always `1 1`) |
| 44–47 | Padding zeros      |

The CRC uses polynomial `0x31`, init `0x00`, with input/output reflection and a final XOR of `0x06`.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `python` not recognised | Try `python3`. If not found, install from [python.org](https://python.org) |
| `ERROR: CSV must have 'FC' and 'CARD' column headers` | Check headers are exactly `FC` and `CARD` — uppercase, no spaces |
| `ERROR: File not found` | Check the filename and path you typed match the actual file |
| Row shows `ERROR` in output | FC must be 1–255 and CARD must be 1–65535. Check for typos |
| `Both --fc and --card are required` | Single card mode needs both flags supplied together |
