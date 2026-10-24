# Backtest run 2: pre-registration

Written 21 October 2026, after run 1 (`backtest/reports/run1.md`) and before any monthly UN
Comtrade values or any 2016-18 data were pulled. Committed before the pulls. Run 1's rules,
cases, reference dates and placebos carry over unless stated here.

Run 2 answers the two questions run 1 left open:

- **A.** Does a monthly onward check bring leads forward, and what does it cost in extra
  leads elsewhere?
- **B.** How often does the run 1 rule fire on ordinary trade, in years with no war?

## Part A: monthly onward check

**Corridors.** The seven with monthly UN Comtrade data after 2019: the Kyrgyz Republic,
Armenia, Kazakhstan, Georgia, Turkey, Uzbekistan and Azerbaijan. The UAE (monthly data stop
at 2019) and Tajikistan (none) keep the annual check only.

**Data.** Each corridor's monthly exports of the nine codes to Russia (partner 643, flow X,
headline records only), January 2019 to the latest month available. Each month counts from
the date UN Comtrade first released it (its data availability service). A month counts as
reported when UN Comtrade holds a monthly dataset for that corridor and month; within a
reported month, a code with no record counts as zero.

**Monthly onward signal,** at the radar run at the end of month A:

1. L is the latest month first released by the end of A. L must be January 2022 or later.
2. The window is the 12 months ending at L. Months in it not yet released at A, or not
   reported, count as zero.
3. The baseline is the average reported month in 2019-21, times 12. A corridor with fewer
   than 12 reported baseline months has no monthly signal.
4. The signal is on when the window sum is at least 2x the baseline and at least USD 100,000.

**Onward signal in run 2:** the annual signal (run 1's rule, release dates) or the monthly
signal. Run 2 can therefore only find a lead at the same time as run 1 or earlier, and it can
find more leads; the placebos measure that cost.

**Unchanged from run 1:** the UK signal (HMRC month M counts from the end of month M + 2),
the lead, the hit rule, the eight tests in `backtest/data/test_plan.csv`, their reference
dates, and placebos P1 to P3.

**Reported:** each test's outcome and lead time against run 1; placebo counts against run 1;
the number of the 81 series that are ever a lead, against run 1's.

**Known in advance:** Kazakhstan's and Georgia's 2022 and 2023 months show first release dates
in 2024 and 2026, which look like later replacements. They are used as they stand, so those
two corridors' monthly signals can only come late.

## Part B: peacetime placebo

The run 1 rule, moved three years earlier:

- Baseline: 2016-18. Radar runs: the end of each month from January 2019 to December 2021
  (36 runs).
- UK signal: HMRC monthly exports, the same thresholds and publication lag.
- Onward signal: the corridor's annual exports of the code to Russia in the latest year
  available, 2019 or later, counted from its first release date, at least 2x its 2016-18
  average and at least USD 100,000.
- Same nine corridors and nine codes.

**Compared with:** the first 36 war-time runs under run 1's rule (January 2022 to December
2024), in which 18 of the 81 series were a lead at least once (known from run 1).

**Reading:** the peacetime count estimates how many leads ordinary trade produces with no
diversion going on. 2019-21 is not a clean control: it holds the pandemic's swings in trade,
and sanctions on Russia from 2014 were already in force [Certain]. So it is an indication,
not a measured false alarm rate.

## Shared caveats

- Baseline years are treated as available at every run. Some show first release dates after
  the runs that use them (for example Kazakhstan's 2021 data, shown as first released in May
  2023); these look like replacements of data first published earlier [Likely].
- Values are today's, after revisions [Certain].
- Nothing else is run in run 2. Any further analysis gets a new run number.

A rise in exports is a lead, not evidence of a breach.

Contains public sector information licensed under the Open Government Licence v3.0.
