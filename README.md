# factuator

A Python bot to help maintain fancier features of the MOTHER wiki at CHM.

## Requirements

    python3 -m virtualenv .venv
    source .venv/bin/activate
    pip3 install -r requirements.txt

## Examples

Factuator can be loud, just add `-v` for info messages or `-vv` for debug logging.

Currently, it warns you if it's actually updating things, and it tries to only 
post changes if things are different.

### Update study pages

Update all `{{Study}}` infobox templates on Category:Study pages.

    python3 factuator.py --study

### Media links

Replace all `[[:File:Name.pdf]]` and `[[File:Name.pdf]]` style links with 
`[[Media:Name.pdf]]` to make them link directly to the file.

On a page:

    python3 factuator.py --medialinks-page User:Myname

On multiple pages:

    python3 factuator.py --medialinks-page "Page 1" --medialinks-page "Page Title 2"

On all pages in a category:

    python3 factuator.py --medialinks-category "Self Report Measure"
