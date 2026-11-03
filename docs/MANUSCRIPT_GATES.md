# What checks the two documents, and what those checks do not see

This is the apparatus the manuscript is built under. It was written in the Supporting
Information, where a reader of the chemistry has no use for it, and it is kept here because the
failures it records are real and were paid for.

The Supporting Information keeps every statement about the *reach of the work*. What moved here
is the description of the machinery: how the checks are implemented, which of them once failed
silently, and what they still cannot see. Nothing a reader needs in order to judge the
measurements left that document.

## The pointer checker, and the three faults it has had

A pointer between the manuscript and its Supporting Information resolves through `xr` against the
other document's own labels; none is hand-typed. What makes a wrong pointer *fail* is not the
build. The build runs `pdflatex` under `-interaction=nonstopmode` with its output discarded, so an
unresolved reference does not stop the compile: the page is produced with `??` on it. The failure
comes from a separate checker that counts undefined references in the log, and that checker is
only as good as its pattern and its list.

Three faults, each closed:

1. Its pattern once required a numeric page number, so it matched nothing in a document whose
   pages are numbered S1, S2 and onward. An unresolved pointer reached page S10 that way.
2. It was not among the checks the test suite ran, which is how a manuscript shipped a pointer
   printing `??` through a green suite.
3. It did not look at font classes. It now refuses a Type 3 font in either compiled document.

## Three things the build checker still does not see

- It counts overfull horizontal boxes, so a table that overruns its text block **vertically**
  passes. One did, and its page folio printed on top of a data cell.
- It compares the digest of every source against what the build recorded. That catches an edit
  and says nothing about whether the numbers in that source are right, which is a different
  checker's job.
- It reads the compiled log, not the rendered page. A fault in the geometry falls outside it,
  where a fault in the references does not.
