"""Reads the IQM Resonance token from the environment variable IQM_TOKEN into memory. Never prints it.
(This package copy replaces the original, which read a local keychain item; nothing else in the IQM scripts changed.)"""
import os
def token():
    t = os.environ.get("IQM_TOKEN", "").strip()
    if len(t) < 10: raise SystemExit("set IQM_TOKEN")
    return t
def scrub(s, t):
    """Removes the token and any 12+ character prefix of it from a string."""
    if t:
        s = s.replace(t, "<token>")
        for n in range(len(t) - 1, 11, -1): s = s.replace(t[:n], "<token-start>")
    return s
