# redact-tools

Simple tools for working with file redaction. Just one for now: `flatten_pdf`

## `flatten_pdf`

Render a PDF into an image and then convert back to PDF. This guarantees
that redacted PDFs are truly redacted: text layers, hidden text, metadata,
and annotations are all gone.

Requires [uv](https://docs.astral.sh/uv/); dependencies install automatically.

```sh
./flatten_pdf.py input.pdf              # writes input.flattened.pdf
./flatten_pdf.py input.pdf -o out.pdf --dpi 300
./flatten_pdf.py input.pdf --bw         # 1-bit, smallest (text-only docs)
```

Pages are stored as lossless PNG or JPEG, whichever is smaller (default
600 dpi).

Output is (intentionally) not searchable or selectable. All text is
rasterized. The script verifies the output has no extractable text.
