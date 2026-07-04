#!/usr/bin/env python3
"""
Fetches unread replies from Instantly unibox and appends to .tmp/raw_signals.json.
PHASE 5 STUB — gracefully skips if INSTANTLY_API_KEY is not set.
Input:  Instantly API
Output: .tmp/raw_signals.json (appended)
"""

import os
import sys

from dotenv import load_dotenv
load_dotenv()


def main():
    api_key = os.getenv("INSTANTLY_API_KEY")
    if not api_key:
        print("0 new replies (INSTANTLY_API_KEY not set — skipping)")
        return

    # Phase 5: full Instantly unibox implementation
    print("0 new replies (Instantly integration coming in Phase 5)")


if __name__ == "__main__":
    main()
