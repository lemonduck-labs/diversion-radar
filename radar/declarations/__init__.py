"""The radar's restricted layer: what a deployment inside government would run on export
declarations, which the public data cannot show. Designed here and run on synthetic records
only; see README.md.

- schema.py: the record, field by field, against HMRC's CDS export data elements.
- scope.py: the corridors, codes, shown routes and windows the layer looks at.
- generate.py: a seeded synthetic world with injected patterns and look-alikes as ground truth.
- signals.py: one detector per pattern, citing the red flags it implements; questions, never findings.
- cases.py: signals grouped into cases, and the link graph.
- evaluate.py: precision and recall against the ground truth, on synthetic data only.
- export.py: the data files for the workspace page (scripts/build_declarations.py writes them).

SYNTHETIC. A rise in exports is a lead, not evidence of a breach.
"""
