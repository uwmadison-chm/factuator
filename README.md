# factuator

A Python bot to help maintain fancier features of the MOTHER wiki at CHM.

## Requirements

    pip3 install mwclient mwparserfromhell coloredlogs

## Examples

### Media links

Replace all `[[:File:Name.pdf]]` and `[[File:Name.pdf]]` style links with 
`[[Media:Name.pdf` to make them link directly to the file.

On a page:

    python3 factuator.py --medialinks-page User:Myname

On multiple pages:

    python3 factuator.py --medialinks-page "Page 1" --medialinks-page "Page Title 2"

On all pages in a category:

    python3 factuator.py --medialinks-category "Self Report Measure"
