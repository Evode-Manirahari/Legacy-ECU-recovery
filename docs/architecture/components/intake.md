# Component: Intake

**Status:** built — `src/ecu_recovery/intake.py`, `binary/`, `models.py`

## 1. Position in the architecture

The first box after `Firmware image`, and the only component that touches raw
bytes before anything interprets them as code. Both branches — CVE/sink mapping
and binary analysis — begin from its output.

It is **not** an analyser. It does not disassemble, does not identify functions,
and does not guess what the firmware does. It establishes what the image *is*,
so that everything downstream is analysing the right bytes at the right
addresses.

## 2. Responsibility

Turn an untrusted file into an identified, fingerprinted artifact with a stated
architecture and load address.

The load address is the part that matters most and is easiest to underrate. Every
address in every downstream result — every sink, every source, every path — is
meaningless if the image was mapped at the wrong base. Intake owns that decision
and owns being explicit when it cannot make it.

**Firmware is data here and is never executed.**

## 3. Inputs

- A firmware image file.
- Operator-supplied processor/architecture selection.
- Operator-supplied load address, where known.

## 4. Outputs

- Content fingerprints (SHA-256, SHA-1, MD5) identifying exactly which bytes
  were analysed.
- Size, entropy profile, fill-byte statistics, repeated-block structure.
- The declared architecture and load address, marked as *stated by an operator*
  rather than *determined by analysis*.
- A refusal, when the image cannot be identified well enough to analyse.

## 5. Permitted dependencies

**None.** Intake is a leaf. It calls no other component in this architecture.

It must not call Binary analysis, must not consult the CVE branch, and must not
call the sidecar. An architecture guess produced by a model, arriving here and
then presented downstream as an established fact, would corrupt every address in
every later result — with no marker that a guess was involved.

## 6. Verification and testing

- Fingerprints are reproducible for identical bytes and differ for any change.
- Entropy, fill-byte and repeated-block statistics are checked against
  synthetic images with known structure.
- Architecture is never inferred silently: a test asserts that an unspecified
  processor produces a refusal or an explicitly-unknown marker, never a default.
- No execution path exists for image bytes.
- The declared load address appears in downstream address arithmetic, and a
  change to it changes downstream addresses.
