import os
import logging


def open_run_dialog():
    try:
        os.system("explorer shell:::{2559a1f3-21d7-11d4-bdaf-00c04f60b9f0}")
        return True
    except Exception as e:
        logging.error(f"Error executing open_run_dialog: {e}", exc_info=True)
        return False


open_run_dialog()
