# Log-signals study: the first registration ended before any run

**What this note says.** The first registration of the log-signals study ended on 19 November
2026, before either of its two stages ran. One sentence in it is false, and the registration's
own rule says that kind of sentence cannot be corrected. No result exists under that text.

## The registration

- File: `plan/exec/v2/study/logsignals/PREREGISTRATION.md` on branch `v2/phase0`.
- Commit: `ea3b762e3975fd80bf98e6d9e7d9b75ce6d71b98`, pushed on 19 November 2026.
- The text stays in the history at that commit, unchanged.

## The false sentence

General limit 3, which the registration prints with the result of each half:

> Many sessions carry no user id, and no repository shows two identified users. Repository and
> person cannot be told apart.

What the data shows, counted from the signal side alone (no outcome value was read): in the
first reported half no repository shows two or more identified user ids; in the second, some
do. How many is not printed, because beside the other printed counts it would bound the
number of user ids in a single repository.

The sentence is true of the first half and false of the second. The registration's own figures
already showed it: it prints 35 distinct user ids in the second half and 32 repositories, and
35 ids cannot sit one per repository in 32 repositories.

## Who wrote it and who found it

The maintainer is one person; agents did the work under the maintainer's approval. The
orchestrating agent wrote the sentence. Two review rounds by other agents and a read-only
consultant agent (a second model) read the text before it was registered, and none of them
caught it. The consultant caught it on 19 November 2026, while it reviewed the implementation
record that the registration asks for. One reviewing agent, working on the same record at the
same time, reported the same contradiction.

## Why this ends the registration

Step 3 of the registration lists what cannot be corrected, and the limits are on that list:
"Changing one of them ends this registration: that is published as a short note under
`docs/results/`, and no run happens under this text." This is that note.

Running the first half alone was not an option. The limit is printed with both halves, so a
page for the first half would already have carried a sentence that is false as a general
statement. The registration also fixes in advance that the second half runs after the first
whenever the first meets its conditions.

## What had been done, and what had not

- **Not done.** Stage 1 and stage 2 never ran on the real tables. No program and no person put
  a signal value beside an outcome value of the same session, in either half.
- **Done before the registration.** Two count programs, one per side, as the registration
  lists under "What was looked at".
- **Done after the registration, all on 19 November 2026.**
  - The code was built and compared with a second implementation on simulated data.
  - Two programs wrote the two private tables, one side each.
  - A third program counted the signal side alone: the registered check figures, the model
    names per repository and the possible weight of each block definition.
  - After the consultant's finding, the orchestrating agent counted the user ids per repository
    with a short script.
  - An audit then recounted every sentence of the registration that can be recounted from the
    signal table, with two separately written programs. They agree with each other on all 59
    sentences. 58 match the registration, and the one that does not is the sentence above. The
    audit gives the same counts as the short script.

## Other faults the audit found in the text

None of these changes a number the study would have printed. Faults 2 and 4 are in sentences
of the printed limits.

1. "About 73% of the sessions sit at 0% or at 100%." That is the first half (307 of 423).
   Over both halves it is 598 of 855, about 70%.
2. "Inside many repositories the outcome takes few distinct values, and ties carry much of the
   weight." No count stands behind this sentence.
3. The section "Why there is no test" points "those seven cases" at a passage that names three,
   and the text calls one simulated case applicable in one place and not applicable in
   another.
4. "Repository and person cannot be told apart", the second sentence of limit 3, is too strong
   where a repository shows several user ids.

## What happens next

A replacement registration is written before any pairing:
`plan/exec/v2/study/logsignals/PREREGISTRATION-2.md` on branch `v2/phase0`. It is a new
registration, not an amendment.

- **The same:** the question, the population, the two measures, the floors, the numbers printed
  with a result, the headline sentence, the yardstick table, the README sentence and the dates.
- **Not word for word the same; the main differences:** the limits and the facts of each half;
  two readings inside the third block definition that the first text left open; two failure
  reports, which are specified more fully; the order of work, which is rewritten around code
  that already exists; and one more privacy leftover that is accepted and stated (printed
  numbers can show the size of a block that carries no weight).

This is a summary. The replacement lists every difference from the first text as old words and new words, and
everything counted so far. The code that exists was built under the first text; the
replacement says so and says how it is reused. No stage runs before the replacement and a new
implementation record are pushed.
