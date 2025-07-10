"""
A configuration class for all the arguments which we will need,
.
Current CLI args include:
 - "--hidden
"""
import argparse

class Configs:
    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="Configuration for CLI arguments",
                    epilog= """
        Example usage:
        python cli.py --hidden
        This will run the CLI in hidden mode, suppressing certain outputs.
        """,
            formatter_class=argparse.RawDescriptionHelpFormatter
            )
    def add_arguments(self) -> argparse.ArgumentParser:
        self.parser.add_argument(
            "--hidden",
            action="store_true",
            help="Enable hidden mode for the CLI, which suppresses certain outputs."
        )
        # Add more arguments as needed
        return self.parser