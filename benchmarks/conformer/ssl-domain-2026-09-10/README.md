# SSL/domain conformer component benchmark

This sanitized result records the deterministic portion of the 10 September 2026 test. It contains no production media, OCR text, transcripts, private paths or credentials.

The retrieval runner made **zero agent calls**. Its visual requests were a manually authored benchmark fixture. The result therefore measures what the screen matcher can do after it receives a requested visual; it does not measure automatic beat creation.

The useful result is narrow:

- 11 of 13 script visuals appeared in the top three;
- all six explicit healthy/expired/on/off contrast probes ranked the correct state first;
- the finished host edit preserved 93.1% of normalized canonical-script tokens exactly, but was not an exact reading.

This is a component-level partial pass. It does not validate raw host take selection, long-recording boundaries, automatic semantic planning or Final Cut export.

Validate the record independently:

```bash
video-conformer validate-benchmark benchmarks/conformer/ssl-domain-2026-09-10/summary.json
```
