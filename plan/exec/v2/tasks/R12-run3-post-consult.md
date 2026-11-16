# R12: consult on the blog post about run 3 (read-only)

You are the consultant. You change no file and run no git command that changes state.
Answer in under 500 words.

## What to read

1. The draft: `plan/exec/v2/launch/post-run-3.md` (everything below the line `---` is the
   post; the maintainer will post it under their own name on Hashnode and dev.to).
2. The checked result: `plan/exec/v2/study/RESULT-run-3.md`.
3. The registration: `plan/exec/v2/study/PREREGISTRATION-run-3.md`.
4. The first post, for voice: `plan/exec/v2/launch/hashnode-post-1.md`.

## The question

Is this text safe and worth posting as it stands? The decision to make is: post this
version, post it with named changes, or do not post a run 3 article at all (the two reader
replies in `plan/exec/v2/launch/devto-reply-2.md` and `hashnode-reply-1.md` already carry
the result).

## My leaning

Post it with small changes at most. My doubts, in order:

1. The first paragraph gives 15 of 16 and 2 of 16 before any limit. A reader judge asked
   for the result in the first 60 words; a strict reader may call it a headline number
   without its caveat.
2. The sentence about the code retry ("It tests the whole system with the recovery handed
   to code, and it does not isolate what the model decides.") is the only reason given for
   not running the variant a reader asked for.
3. "I tried that idea at the empty lookup": the reader's idea was about the error text of a
   wrong tool call ("unknown SKU"); I applied it one step later, at the empty lookup.
4. "A trial passes when the order ends with the right stock note and no refund." It is my
   plain-words summary of `order-desk-empty-message/check.py`.
5. The section on the two errata uses "the trial run" for the smoke run.

## What I need from you

- Every sentence that claims more than `RESULT-run-3.md` supports, quoted, with a
  replacement.
- Every number that does not match the files.
- Your answer to the question, in one line, and whether you disagree with my leaning.
- Anything a hostile but fair reader on Hacker News would attack first.
