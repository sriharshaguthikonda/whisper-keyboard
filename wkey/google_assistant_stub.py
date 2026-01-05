"""Stub for google_assistant module since the embedded API is deprecated"""

import logging

async def google_assistant(transcript):
    """
    Stub function for Google Assistant since the embedded API is deprecated.
    This logs the command instead of executing it.
    """
    logging.info(f"Google Assistant command (not executed due to deprecated API): {transcript}")
    print(f"Google Assistant command would be: {transcript}")
    return f"Would execute: {transcript}"
