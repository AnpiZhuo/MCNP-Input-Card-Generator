"""
generator — MCNP Input Card Generation Engine

This package provides the core engine for parsing, validating, and generating
MCNP input decks. It includes:
  - inp_parser:     Parses raw MCNP INP text into a structured Deck object
  - inp_generator:  Serializes a Deck object back into valid MCNP INP text
  - validator:      Checks a Deck for semantic consistency and correctness
"""
