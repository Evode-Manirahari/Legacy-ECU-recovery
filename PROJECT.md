# Automotive Firmware Reachability Engine

> A tool that tells automotive security teams which vulnerabilities in their ECU
> firmware are actually reachable, not just present.

## Problem

An ECU firmware image contains vendored components — network stacks, parsers,
crypto libraries, RTOS pieces — and those components have known CVEs. A
composition scanner will produce a list. On a real image the list is long.

The list answers **presence**. The team has to answer something else: which of
these can an attacker actually reach?

Most cannot. A defect in a code path that no external input ever drives is not
an attack. A defect one function call from a UDS service handler is. The two look
identical in a CVE list and could not be more different in a release decision,
and today the work of telling them apart is done by hand — an engineer with
Ghidra open, tracing whether anything from CAN, UDS, DoIP or OTA can reach the
vulnerable function.

That work is slow, it is repeated for every image and every release, and it is
the work this system automates.

The bet:

> Deterministic binary analysis can decide reachability from an automotive attack
> surface to a known vulnerable sink, with evidence a security engineer can
> check, often enough to change how remediation is prioritised.

## Target user

An automotive product security or vulnerability management team — at an OEM, a
tier-1 supplier, or a firm doing security assessment for them. Someone who
already has the CVE list and has to decide what it means.

The discovery question:

> Show me the last firmware release where you had a CVE list and had to decide,
> by hand, which entries actually mattered.

Then measure what consumed the time, what evidence convinced them, where they
gave up and shipped a judgement call, and what they did when they could not tell.

## What the product does

Given a firmware image, it identifies the vulnerable sinks that known CVEs map
to, identifies the automotive entry points an attacker can influence, and decides
deterministically whether a path connects them — returning `REACHABLE`,
`NOT_REACHABLE`, or `INCONCLUSIVE`, with an Evidence Pack supporting the verdict.

See [docs/architecture/](docs/architecture/) for the system design, which is the
source of truth.

## First technical goal

> Given one supported ECU firmware image, a known vulnerable function, and an
> identified automotive entry point, determine deterministically whether a valid
> path exists from the source to the vulnerable sink, and output the evidence
> supporting that verdict.

One image, one sink, one source, one verdict, one Evidence Pack. Not the whole
system.

## What makes the answer trustworthy

**The decision is deterministic.** Same firmware, same verdict, every time. A
language model assists with interpretation and labelling and is architecturally
prevented from deciding: remove every model annotation and the verdicts must not
change.

**The evidence is the product.** A verdict without its chain is a claim. A team
acting on `NOT_REACHABLE` is deprioritising a real defect, and they need to see
the reasoning, not trust a black box.

**The system prefers admitting it does not know.** `INCONCLUSIVE` is a designed
outcome, not a degraded one. A wrong `NOT_REACHABLE` is the only error whose cost
is paid entirely by whoever trusted the answer, and it is treated as
release-blocking.

**No confidence percentages on verdicts.** The Evidence Pack states what was
established and what was assumed. A number would let a reader average across
findings whose missing pieces are not comparable.

## Secondary use case: legacy ECU recovery

The same machinery answers a question engineers pay for today: *what does this
undocumented function actually do?*

Legacy embedded software routinely outlives its source repository, compiler
toolchain, design documents, symbols, test suite, and original engineering team,
while the controller still matters — in vehicles, industrial equipment, and
discontinued products. An engineer holding an authorised firmware image and
partial manuals can spend days establishing the processor, memory layout,
function inventory and behaviour by hand.

Call graphs, cross-references, decompilation, hidden ground truth and an
evidence-first report with explicit `known` / `inferred` / `unknown` distinctions
are what that work needs, and they are the same components the reachability
engine is built on. Users include ECU remanufacturers, automotive electronics
specialists, embedded reverse engineers, engineering consultancies, suppliers
maintaining discontinued products, and motorsport and classic-car electronics
teams.

This capability is built and is kept. It is a use case, not the identity of the
product, and it is not what the roadmap is organised around.

## Non-goals

The system reads firmware and reports reachability with evidence. It does not:

- generate, weaponise, or execute exploits;
- flash, modify, or control vehicles or hardware;
- certify or guarantee regulatory compliance;
- reconstruct source code, or produce replacement firmware;
- decompile an ECU with a language model.

Only firmware the operator is authorised to possess and inspect is analysed, and
firmware is treated as data and never executed by the intake path.

## How the work is organised

Development follows an explicit dependency graph
([docs/MASTER_SPEC.md](docs/MASTER_SPEC.md)); an edge means the prerequisite was
verified. Architecture is documented before or alongside implementation, and
component boundaries are contracts rather than conventions — see
[docs/architecture/components/](docs/architecture/components/).

Benchmarking is CI and development infrastructure and does not appear in the
runtime architecture. Metrics, including the false-unreachable release blocker,
are in [EVALS.md](EVALS.md).
