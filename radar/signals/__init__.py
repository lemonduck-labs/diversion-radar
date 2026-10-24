"""Research on three more public signals for the radar (radar/signals/RESEARCH.md).

- S1 (price.py): the price per kilogram of UK exports to a corridor, against the other
  eight corridors, drifting outside a fixed band.
- S2 (codeshift.py): UK exports of one code to a corridor falling while the other list codes
  in the same heading rise to make up for it.
- S3 (displacement.py): UK exports to Russia falling while UK exports of the same code to a
  corridor rise by a share of that fall.

The rules, thresholds and success criteria were fixed in RESEARCH.md (entry S0) before any of
them was computed. These are research signals, not part of the live radar: nothing here
changes a lead or a watch item.

A rise in exports is a lead, not evidence of a breach.
Contains public sector information licensed under the Open Government Licence v3.0.
"""
