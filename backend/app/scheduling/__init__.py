"""Scheduling module: availability helpers, booking/cancel service, schedule reads.

The pure availability logic lives in ``availability.py`` so booking rules are
testable without a database and reusable by the priority-aware engine introduced
in later phases.
"""
