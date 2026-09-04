# Slide authoring

This guide describes the small contract Gimle Deck enforces and the conventions
used by the reference project. The contract is intentionally narrow: projects
remain free to invent their own semantic layout classes and visual system.

## Required source boundary

Each file under the configured `slides_dir` represents one slide. It must:

- be a UTF-8 HTML fragment, not a complete document;
- contain exactly one outer `section` element;
- include `slide` in that outer section's quoted `class` attribute;
- contain no HTML comments; and
- contain no element with the `num` class.

The smallest valid source is:

```html
<section class="slide">
  <h2>A complete thought</h2>
</section>
```

Nested sections are valid because only the single outer section defines the
page boundary:

```html
<section class="slide comparison">
  <h2>The conclusion the comparison supports</h2>
  <div class="compare">
    <section>
      <h3>First case</h3>
      <p>Evidence for the first case.</p>
    </section>
    <section>
      <h3>Second case</h3>
      <p>Evidence for the second case.</p>
    </section>
  </div>
</section>
```

## Compiler-owned markup

The compiler owns structure that depends on the selected variant:

- the surrounding document from the selected theme template;
- the generated appendix divider;
- contiguous page numbers after cuts are applied;
- optional internal review labels requested with `--tags`; and
- asset substitution and local URL embedding.

Do not author `.num` page markers. Do not copy an appendix divider into
`slides/`. If the source owns either one, numbering or conditional structure can
silently disagree with the finished deck, so the compiler rejects authored page
markers and reserves the divider slug.

## Project-owned markup

The project owns everything that communicates the slide:

- the claim, evidence, labels, links, and accessible alternative text;
- semantic layout classes such as `title`, `split`, `sequence`, or `reference`;
- figures, tables, lists, code, and nested sections inside the slide boundary;
- the matching editorial notes file; and
- the slide's order, variant membership, placement, and archive state in
  `deck.toml`.

Keep the source semantic. Put typography, spacing, color, and positioning in the
theme stylesheet. Avoid inline `style` attributes unless a genuinely unique
value belongs to the content rather than the design system.

## Recommended anatomy

The class names below are conventions, not compiler keywords. The reference
themes implement all of them.

### Title

Keep the opening sparse: identity, title, and one line of orientation.

```html
<section class="slide title">
  {{include:mark.svg}}
  <p class="kicker">What this deck is</p>
  <h1>The question or proposition</h1>
  <p class="lede">One sentence that establishes scope.</p>
</section>
```

### Statement

Use a statement slide for one transition or organizing idea.

```html
<section class="slide statement">
  <p class="kicker">Context</p>
  <h2>The complete claim goes here.</h2>
  <p class="support">A consequence or qualification, if the claim needs one.</p>
</section>
```

### Split text and visual

Use a split only when the figure carries evidence or meaning that the copy
cannot carry alone.

```html
<section class="slide split">
  <div class="copy">
    <h2>The figure's takeaway</h2>
    <p>Interpret the figure instead of merely naming it.</p>
  </div>
  <figure>
    <img src="{{asset:result.png}}" alt="Concise description">
    <figcaption>Scope, method, or source.</figcaption>
  </figure>
</section>
```

### Sequence

Use an ordered list only when the content is genuinely sequential.

```html
<section class="slide sequence">
  <h2>The process reaches a specific outcome.</h2>
  <ol>
    <li><strong>Observe</strong><span>Collect the signal.</span></li>
    <li><strong>Test</strong><span>Challenge the explanation.</span></li>
    <li><strong>Decide</strong><span>Act on what survives.</span></li>
  </ol>
</section>
```

### Reference table

Tables work best for exact mappings. Keep the takeaway in the heading and the
cells short enough to scan.

```html
<section class="slide reference">
  <h2>Each source has one resolution path.</h2>
  <table>
    <thead><tr><th>Source</th><th>Result</th></tr></thead>
    <tbody>
      <tr><td>Text asset</td><td>Inline markup</td></tr>
      <tr><td>Binary asset</td><td>Data URI</td></tr>
    </tbody>
  </table>
</section>
```

## Assets

Asset names resolve inside the configured `assets_dir` and may not escape it.

- `{{include:name.svg}}` inserts a UTF-8 text file directly into the source.
- `{{asset:image.png}}` produces a base64 data URI.
- Relative `url(...)` references in theme CSS are embedded from the
  stylesheet's directory, with the project root as a compatibility fallback.

Use `include` when the inserted text should become part of the DOM. Use `asset`
for images and other binary media. In either case, give meaningful images an
`alt` attribute in the authored markup.

## Notes and manifest entries

With `require_notes = true`, every active and archived slide needs a matching
`notes/<slug>.md`. Notes are never included in the output; use them for intent,
provenance, caveats, and revision rationale.

Declare the same slug in `deck.toml`:

```toml
[[slides]]
slug = "result"
variants = ["full", "public"]

[[slides]]
slug = "method"
variants = ["full"]
placement = "appendix"

[[slides]]
slug = "old_result"
archived = true
```

Avoid audience or archive metadata in the HTML. Keeping selection in one
manifest prevents internal deck names from leaking into published source.

## Theme responsibilities

The template provides the HTML document and must contain `{{css}}` and
`{{slides}}`. `{{title}}` is optional. The stylesheet should define:

- explicit slide width and height;
- a matching zero-margin `@page` size for PDF output;
- `break-after: page` on `.slide`;
- print color adjustment when backgrounds carry meaning;
- stable typography and asset URLs; and
- every semantic layout class used by the project's slides.

Themes should not depend on a particular variant. A slide selected under any
theme should remain legible even when its preferred layout is not available;
the reference project's minimal theme demonstrates that fallback discipline.

## Pre-build checklist

- One outer `<section class="slide ...">` per source file.
- One claim or communication job per slide.
- No authored `.num`, appendix divider, HTML comments, or full document shell.
- No unresolved `{{include:...}}` or `{{asset:...}}` placeholders.
- Every image has useful alternative text; every visible URL is a real link.
- Every slug has a manifest entry and, when required, a notes file.
- All layout classes exist in every selectable theme.
- Titles and body copy fit without clipping or unintended wrapping.
- `gimle-deck check` passes before HTML or PDF is built.
- Every final slide is inspected after rendering.
