# Gimle Deck

Gimle Deck turns a directory of authored HTML slides into a self-contained HTML
deck or a verified PDF. It owns manifest validation, named content variants,
themes, appendix placement, asset embedding, page numbering, optional Google
Analytics, and verified Chrome rendering. Slide content, brand assets, and
publication policy remain in the deck project.

## Install

Gimle Deck requires Python 3.9 or newer. From a clone of this repository:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/gimle-deck --help
```

Python 3.9–3.10 install the small `tomli` compatibility dependency. PDF output
also requires Chrome or Chromium; `pdfinfo` and `pdffonts` add artifact checks
when available.

## Run it against another repository

The project path is independent of the current directory. From a clone of this
repository, point `--project` at any directory containing a compatible
`deck.toml`:

```bash
.venv/bin/gimle-deck --project ../my-deck check
.venv/bin/gimle-deck --project ../my-deck list
.venv/bin/gimle-deck --project ../my-deck \
  build --variant public --format html --analytics \
  --output ../my-deck/build/public.html
.venv/bin/gimle-deck --project ../my-deck \
  build --variant public --format pdf \
  --output ../my-deck/build/public.pdf
```

The target project's manifest chooses its content variants and default theme;
the compiler does not carry project-specific slides or branding.

## Try the included example

```bash
.venv/bin/gimle-deck --project examples/basic check
.venv/bin/gimle-deck --project examples/basic build --format html
.venv/bin/gimle-deck --project examples/basic \
  build --variant public --theme minimal --format html
```

The reference project demonstrates a title, large statement, split code layout,
ordered sequence, embedded image, comparison, artifact summary, close, generated
appendix divider, reference table, archived source, two variants, and two themes.
Its default output is `examples/basic/basic_deck.html`. Non-default variants and
themes are added to automatic filenames so one build cannot silently overwrite
another.

## Authoring slides

### Required HTML contract

Every slide source is a UTF-8 HTML fragment with exactly one outer `section`.
That section must include the `slide` class:

```html
<section class="slide">
  <h2>One clear claim</h2>
  <p>Only the support that claim needs.</p>
</section>
```

The source must not contain a full HTML document, HTML comments, or an element
with the `num` class. The compiler owns the document template, generated
appendix divider, and final page numbers. Nested sections are allowed inside the
outer slide.

### Recommended slide anatomy

Use the outer class list to name the layout, then keep the children semantic and
shallow. Themes can style the same anatomy differently:

```html
<section class="slide split">
  <div class="copy">
    <p class="kicker">Short context</p>
    <h2>The takeaway belongs in the heading</h2>
    <p>Use body copy for evidence or consequence.</p>
  </div>
  <figure>
    <img src="{{asset:observation.jpg}}" alt="What the image shows">
    <figcaption>Why the image matters.</figcaption>
  </figure>
</section>
```

Prefer one claim and one composition per slide. Keep presentation rules in the
theme stylesheet rather than inline styles, give meaningful images alternative
text, and keep selection logic in `deck.toml` rather than `data-*` attributes.
Every declared slide also gets a same-named notes file. See
[`docs/slide-authoring.md`](docs/slide-authoring.md) for layout patterns,
ownership boundaries, and a pre-build checklist.

## Project contract

A deck project is a directory containing `deck.toml`. Every configured path is
relative to that directory and may not escape it.

```toml
[deck]
title = "Example"
default_variant = "full"
slides_dir = "slides"
notes_dir = "notes"
assets_dir = "assets"
default_theme = "default"
output_basename = "example_deck"

[themes.default]
template = "themes/default/template.html"
stylesheet = "themes/default/deck.css"

[themes.minimal]
template = "themes/minimal/template.html"
stylesheet = "themes/minimal/deck.css"

[web]
google_analytics_id = "G-ABC123"

[variants]
full = "Complete deck"
public = "Public narrative"

[[slides]]
slug = "title"

[[slides]]
slug = "private_detail"
variants = ["full"]

[[slides]]
slug = "supporting_detail"
variants = ["full"]
placement = "appendix"

[[slides]]
slug = "old_treatment"
archived = true
```

Each active or archived slug needs a matching `slides/<slug>.html`; notes are
required by default at `notes/<slug>.md`. A slide source must contain exactly
one outer `<section class="slide">`.

### Themes

A theme is a named template-and-stylesheet pair. `default_theme` is optional and
defaults to the theme named `default`. A template must contain `{{css}}` and
`{{slides}}`; `{{title}}` is replaced when present. Select another declared
theme with `build --theme NAME`.

Projects using the original `deck.template` and `deck.stylesheet` settings are
also supported. That pair becomes the project's implicit default theme.

### Assets

Slides and CSS support two placeholders:

- `{{include:name.svg}}` inserts a UTF-8 text asset directly.
- `{{asset:name.png}}` inserts a base64 data URI.

Other local `url(...)` references in the stylesheet are embedded automatically,
resolved relative to the stylesheet first and then the project root for legacy
projects.

### Variants and appendices

The reserved `all` variant includes every active slide while still excluding
archived material. Appendix slides are moved after the main narrative, with a
generated divider only when the selected variant contains appendix material.

### Google Analytics

Google Analytics is optional and opt-in. Configure a GA4 measurement ID in
`[web].google_analytics_id`, then pass `--analytics` to an HTML build:

```bash
gimle-deck --project path/to/deck build --format html --analytics
```

Without `--analytics`, HTML contains no tracking even when an ID is configured.
If the setting is absent or blank, `--analytics` is a no-op. PDF builds never
include analytics.

## Development

```bash
python3 -m unittest discover -s tests -p "test_*.py"
black --check src tests
mypy src/gimle_deck
```

## License

Gimle Deck is available under the [MIT License](LICENSE).
