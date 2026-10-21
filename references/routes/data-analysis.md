# Data analysis route

Use for exploring, transforming, interpreting, or reporting structured data. Inputs: original files or connected source, the question/metrics, grain and time range if known, definitions, and available analysis tools.

1. Inspect provenance, schema, grain, freshness, missingness, duplicates, units, joins, and coverage before interpreting. Preserve the original input unchanged and work on a separate copy; report material quality limits.
2. Define transformations, exclusions, assumptions, formulas, and method. Prefer reproducible queries, scripts, or documented spreadsheet formulas; retain enough steps to rerun the analysis.
3. Reconcile totals and samples against the source, check formulas/calculations, and test whether conclusions survive relevant limitations. Present evidence, hypothesis, and inference distinctly; cite source URLs and dates for external evidence.

Quality means another person can trace the result to the input and repeat the method, with uncertainty and caveats visible. Never fabricate data or fill gaps silently. If data or analysis tools are unavailable, request the missing input or deliver a clearly labeled analysis plan; do not claim calculations were performed.
