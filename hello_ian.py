#!/usr/bin/env python3
"""
Simple test program to verify the Programs Ian created folder works!
"""

from datetime import datetime

def main():
    print("=" * 50)
    print("Hello, Ian! 👋")
    print("=" * 50)
    print(f"\nCurrent time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"This program is running from: Programs Ian created/")
    print("\n✅ Folder setup successful!")
    print("=" * 50)

if __name__ == "__main__":
    main()
