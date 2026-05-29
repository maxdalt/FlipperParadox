#!/usr/bin/env python3
"""
Paradox RFID Generator
----------------------
Two modes of operation:

1) Single card — supply FC and CARD directly on the command line:
       python3 paradox_rfid_generator.py --fc 22 --card 31352 [output_dir]

2) CSV batch — supply a CSV file with FC and CARD columns:
       python3 paradox_rfid_generator.py <input.csv> [output_dir]

Arguments:
    --fc        Facility Code (1-255)
    --card      Card ID (1-65535)
    input.csv   CSV file with FC and CARD columns (headers required)
    output_dir  Directory for .rfid files (default: current directory /
                same directory as the CSV)

CSV format example:
    FC,CARD
    22,31352
    7,6286
    209,63321
"""

import csv
import os
import sys


# ── Paradox CRC & encoding logic ─────────────────────────────────────────────

def _reflect(val, bits):
    result = 0
    for _ in range(bits):
        result = (result << 1) | (val & 1)
        val >>= 1
    return result


def _crc8(data, poly, init, ref_in, ref_out, xor_out):
    crc = init
    for byte in data:
        if ref_in:
            byte = _reflect(byte, 8)
        for _ in range(8):
            if (crc ^ byte) & 0x80:
                crc = ((crc << 1) ^ poly) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
            byte = (byte << 1) & 0xFF
    if ref_out:
        crc = _reflect(crc, 8)
    return crc ^ xor_out


def _calculate_checksum(fc, card_id):
    """CRC-8 (poly=0x31, init=0x00, refIn=True, refOut=True, xorOut=0x06)"""
    card_hi = (card_id >> 8) & 0xFF
    card_lo = card_id & 0xFF
    arr = bytearray([0, 0, fc, card_hi, card_lo])

    arr_bits = []
    for b in arr:
        for i in range(7, -1, -1):
            arr_bits.append((b >> i) & 1)

    manchester_bits = [0, 0, 0, 0]
    for i in range(6, 40):
        bit = arr_bits[i]
        manchester_bits += [1, 0] if bit == 1 else [0, 1]

    manchester_bytes = bytearray(9)
    for i, b in enumerate(manchester_bits):
        byte_idx = i // 8
        bit_idx = 7 - (i % 8)
        manchester_bytes[byte_idx] |= (b << bit_idx)

    return _crc8(manchester_bytes, 0x31, 0x00, True, True, 0x06)


def _set_bit(data, index, bit):
    byte_idx = index // 8
    bit_idx = 7 - (index % 8)
    if bit:
        data[byte_idx] |= (1 << bit_idx)
    else:
        data[byte_idx] &= ~(1 << bit_idx)


def build_decoded_data(fc, card_id):
    """
    Build the 6-byte Paradox decoded data blob.

    Bit layout:
      bits  0-9  : leading zeros
      bits 10-17 : facility code (FC)
      bits 18-33 : card ID
      bits 34-41 : CRC
      bits 42-43 : trailing stop bits (always 1,1)
      bits 44-47 : padding zeros
    """
    decoded = bytearray(6)
    crc = _calculate_checksum(fc, card_id)

    for i in range(8):
        _set_bit(decoded, 10 + i, (fc >> (7 - i)) & 1)
    for i in range(16):
        _set_bit(decoded, 18 + i, (card_id >> (15 - i)) & 1)
    for i in range(8):
        _set_bit(decoded, 34 + i, (crc >> (7 - i)) & 1)

    # Trailing stop bits — always 1,1 in the Paradox protocol frame
    _set_bit(decoded, 42, 1)
    _set_bit(decoded, 43, 1)

    hex_str = ' '.join(f'{b:02X}' for b in decoded)
    return crc, hex_str


# ── File I/O ──────────────────────────────────────────────────────────────────

def write_rfid_file(path, hex_str):
    """Write a Flipper Zero compatible .rfid file."""
    content = (
        "Filetype: Flipper RFID key\n"
        "Version: 1\n"
        "Key type: Paradox\n"
        f"Data: {hex_str}\n"
    )
    with open(path, 'w') as f:
        f.write(content)


def process_single(fc, card_id, output_dir):
    """Generate a single .rfid file from command-line FC and CARD arguments."""
    os.makedirs(output_dir, exist_ok=True)

    if not (1 <= fc <= 255):
        print(f"ERROR: FC {fc} out of range (must be 1-255)")
        sys.exit(1)
    if not (1 <= card_id <= 65535):
        print(f"ERROR: Card ID {card_id} out of range (must be 1-65535)")
        sys.exit(1)

    crc, hex_str = build_decoded_data(fc, card_id)
    rfid_filename = f"{fc}_{card_id}.rfid"
    rfid_path = os.path.join(output_dir, rfid_filename)
    write_rfid_file(rfid_path, hex_str)

    print(f"Paradox RFID Generator - Single Card Mode")
    print(f"  FC:         {fc}")
    print(f"  Card ID:    {card_id}")
    print(f"  CRC:        {crc} (0x{crc:02X})")
    print(f"  Data:       {hex_str}")
    print(f"  Output:     {rfid_path}")
    print(f"\nDone.")


def process_csv(input_path, output_dir):
    """
    Read the input CSV, calculate hex data for each row, write updated CSV
    and individual .rfid files.
    """
    os.makedirs(output_dir, exist_ok=True)

    # Read all rows first — utf-8-sig strips the Excel BOM if present
    with open(input_path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        if not fieldnames or 'FC' not in fieldnames or 'CARD' not in fieldnames:
            print("ERROR: CSV must have 'FC' and 'CARD' column headers.")
            sys.exit(1)

        rows = list(reader)

    # Add HEX column if not already present
    output_fieldnames = list(fieldnames)
    if 'HEX' not in output_fieldnames:
        output_fieldnames.append('HEX')

    updated_rows = []
    rfid_count = 0
    errors = 0

    print(f"\nProcessing {len(rows)} rows...\n")
    print(f"{'#':<5} {'FC':<6} {'CARD':<8} {'CRC':<5} {'HEX Data':<20} Status")
    print("-" * 70)

    for idx, row in enumerate(rows, 1):
        try:
            fc = int(row['FC'])
            card_id = int(row['CARD'])

            if not (1 <= fc <= 255):
                raise ValueError(f"FC {fc} out of range (1-255)")
            if not (1 <= card_id <= 65535):
                raise ValueError(f"Card ID {card_id} out of range (1-65535)")

            crc, hex_str = build_decoded_data(fc, card_id)
            row['HEX'] = hex_str
            updated_rows.append(row)

            rfid_filename = f"{fc}_{card_id}.rfid"
            rfid_path = os.path.join(output_dir, rfid_filename)
            write_rfid_file(rfid_path, hex_str)
            rfid_count += 1

            print(f"{idx:<5} {fc:<6} {card_id:<8} {crc:<5} {hex_str:<20} OK -> {rfid_filename}")

        except (ValueError, KeyError) as e:
            print(f"{idx:<5} {row.get('FC','?'):<6} {row.get('CARD','?'):<8} {'':5} {'':20} ERROR: {e}")
            row['HEX'] = 'ERROR'
            updated_rows.append(row)
            errors += 1

    # Write updated CSV (overwrites original with HEX column appended)
    with open(input_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=output_fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)

    print(f"\nDone.")
    print(f"  CSV updated:    {input_path}")
    print(f"  .rfid files:    {rfid_count} written to '{output_dir}'")
    if errors:
        print(f"  Errors:         {errors} row(s) skipped")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]

    # ── Single card mode: --fc <n> --card <n> [output_dir] ───────────────────
    if '--fc' in args or '--card' in args:
        if '--fc' not in args or '--card' not in args:
            print("ERROR: Both --fc and --card are required for single card mode.")
            print("  Example: python3 paradox_rfid_generator.py --fc 22 --card 31352")
            sys.exit(1)

        try:
            fc_idx   = args.index('--fc')
            card_idx = args.index('--card')
            fc      = int(args[fc_idx + 1])
            card_id = int(args[card_idx + 1])
        except (IndexError, ValueError):
            print("ERROR: --fc and --card must be followed by integer values.")
            sys.exit(1)

        # Any remaining arg that isn't a flag or flag value is the output dir
        flag_positions = {fc_idx, fc_idx + 1, card_idx, card_idx + 1}
        extras = [a for i, a in enumerate(args) if i not in flag_positions]
        output_dir = extras[0] if extras else os.getcwd()

        process_single(fc, card_id, output_dir)

    # ── CSV batch mode: <input.csv> [output_dir] ─────────────────────────────
    elif len(args) >= 1:
        input_path = args[0]

        if not os.path.isfile(input_path):
            print(f"ERROR: File not found: {input_path}")
            sys.exit(1)

        output_dir = args[1] if len(args) >= 2 else os.path.dirname(os.path.abspath(input_path))

        print(f"Paradox RFID Generator - CSV Batch Mode")
        print(f"  Input CSV:  {input_path}")
        print(f"  Output dir: {output_dir}")

        process_csv(input_path, output_dir)

    else:
        print(__doc__)
        sys.exit(1)


if __name__ == '__main__':
    main()
