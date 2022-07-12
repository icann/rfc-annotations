# About the annotations/ directory

This directory and all of its subdirectories are scanned for annotation files.

Annotation file names have the pattern `rfc<nr>.*` where `<nr>` is the number of the RFC that the annotation applies to. All files that don't match that naming pattern are ignored.

If you want a subdirectory and all of its subdirectories to be ignored when scanning, add a `.ignore` file (the file content does not matter) to that directory.

## Format of the Annotation Files

An annotation file is a UTF-8 encoded text file.

All lines that contain a single `#`, or start with a `# ` (note the space after the hash character) are treated as comments.
All lines that start with `#` and a letter are used for metadata. Those currently defined are:

* `#A <AuthorName>` specifies the author of the annotation
* `#C <Caption>` specifies the caption that appears at the top of the annotation when displayed in an RFC
* `#L <LineNumber>` specifies the referenced line of the RFC
* `#S <Section>`  specifies the referenced section of the RFC
* `#T <Type>`  specifies the type of the annotation; this should only be set by the tool itself when creating annotations

Only one of `#L ` and `#S ` can be used in an annotation.
Specifying `#L 1` is the equivalent of not including either a `#L ` or a `#S ` specification,
and indicates that the annotation is "global" and should appear after the automatically-generated
global annotations.

The first line that does not contain a comment or metadata is the beginning of the annotation content.
If this first line starts with an allowed HTML tag, the rest of the annotation is assumed to be HTML.
This is typically done with a `<div>` tag, but it could be any of the tags listed below.
If the first non-comment, non-metadata line does not start with an HTML tag, the rest of the annotation is treated as plain, pre-formatted text.

The HTML tags that you use are currently:

- `<a>`
- `<b>`
- `<br>`
- `<code>`
- `<div>`
- `<hr>`
- `<i>`
- `<li>`
- `<ol>`
- `<p>`
- `<pre>`
- `<span>`
- `<style>`
- `<svg>`
- `<ul>`

Within SVG, you can currently use:

- `<circle>`
- `<g>`
- `<path>`
- `<polygon>`
- `<text>`

See the `html-restrictions.json` file in the `program/` folder for more technical detail on what can be used in HTML-formatted annotations.

The HTML in annotations should be well-formed.
However, the annotation collector will make best guesses about closing unterminated `<p>` and `<div>` elements.
To see which annotations need these guesses applied to them, use `RFC_HTML_WARNINGS="YES"` when running
`make annotations`.

If you start an HTML-formatted annotation with a `<div>` element, and that `<div>` element has an `id` attribute,
you can refer to that annotation in other annotations using the `id`.

## References to RFCs

Annotations will often refer to RFCs, some of which will be be the processed RFCs, others that will be external.
You can reference RFCs as `@@RFC<Number>@@`, and the annotation creator will turn this into a local reference if possible,
or a reference to the RFC at the RFC Editor's site if it is not an annotated RFC.
This can be used in both HTML-formatted and plain text annotations.
