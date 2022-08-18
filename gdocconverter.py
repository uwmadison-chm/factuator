import mwparserfromhell
import logging
import re
import time
import tempfile
import socket
import os

from enum import Enum

FONT_SIZE_DEFAULT = 11
FONT_SIZE_TABLE = 8

class NodeResponseKind(Enum):
    NONE = 1
    BULLET = 2

class BulletKind(Enum):
    NORMAL = 1
    NUMERIC = 2

class NodeResponse:
    def __init__(self):
        self.kind = NodeResponseKind.NONE
        self.is_bold = False
        self.is_italic = False
        self.last_was_heading = False
        self.font_size = FONT_SIZE_DEFAULT

    def is_bullet(self):
        return self.kind == NodeResponseKind.BULLET

    def toggle_bold(self):
        self.is_bold = not self.is_bold
        return self

    def toggle_italic(self):
        self.is_italic = not self.is_italic
        return self

    def set_bullet(self, level):
        self.kind = NodeResponseKind.BULLET
        self.bullet_kind = BulletKind.NORMAL
        self.level = level
        return self

    def set_numeric_bullet(self, level):
        self.kind = NodeResponseKind.BULLET
        self.bullet_kind = BulletKind.NUMERIC
        self.level = level
        return self

    def bullet_complete(self):
        self.kind = NodeResponseKind.NONE
        return self

    def __str__(self):
        s = ""
        if self.is_bullet():
            return "* "
        else:
            return "None"


GOOGLE_DOCS_PREFIX = "https://docs.google.com/document/d/"
GOOGLE_DRIVE_PREFIX = "https://drive.google.com/file/d/"


class GDocConverter:
    """
    Generic converter class, called by GDocExporter

    Uses most of the same APIs

    `file_prefix` is used to store image and other files in a 
    public-internet-accessible location so the Google Docs API can read them 
    from `http_prefix`
    """

    def __init__(self, driver, wiki, wiki_prefix, docs, mappings, file_prefix, http_prefix):
        self.driver = driver
        self.wiki = wiki
        self.wiki_prefix = wiki_prefix
        self.docs = docs
        self.mappings = mappings
        self.file_prefix = file_prefix
        self.http_prefix = http_prefix


    def convert(self, page, doc_id, debug=False):
        """
        Convert content from a given `page` into a google document at `doc_id`.

        Passing `debug=True` will run requests one at a time, so you can see 
        the document getting created from the "bottom up" and debug API errors
        """

        self.doc_id = doc_id

        # If we were really fancy, we would try to do merging of content.
        # But we're just going to brute force override old content.
        self.clear_document()

        # Note that the Google Docs API recommends that you "create
        # backwards" because of the indexes changing on edits.
        # So we insert everything at index 1 and then flip the order of operations
        requests = []

        requests += self.insert_heading_text(1, page.name + "\n", level='TITLE') 
        requests += self.insert_link(1, "Original wiki location\n\n", self.wiki_prefix + str(page.name)) 

        oldtext = page.text()
        requests.extend(self.wiki_markup_to_requests(oldtext))

        requests = list(reversed(requests))
        flat_requests = []
        for x in requests:
            if isinstance(x, list):
                flat_requests.extend(x)
            else:
                flat_requests.append(x)

        self.driver.batch_update(self.doc_id, flat_requests, debug=debug)


    def wiki_markup_to_requests(self, markup, start_index=1, status=None):
        """
        Turn Mediawiki markup into a series of Google Docs API requests.

        Note that it mutates requests in place because the `node_to_requests`
        function returns stateful NodeResponse. Better way would be to combine
        requests into that state object, but that's hard and confusing so
        I'm leaving this as is for now.

        `start_index` is usually 1, where we are inserting into the doc,
        because we're going in reverse. But sometimes inside tables we might
        need to insert at a different specific index.
        """
        requests = []
        p = mwparserfromhell.parse(self.cleanup_markup(markup))
        nodes = list(p.nodes)
        if not status:
            status = NodeResponse()

        # Now just loop over the nodes, accumulating the last status
        for node in nodes:
            status = self.node_to_requests(node, requests, status, start_index=start_index)

        return requests


    def cleanup_markup(self, text):
        """
        Initial pass to cleanup the mediawiki linefeeds and stuff that we don't
        want to even have in the parse.

        Mostly tries to remove extra line feeds in between text; mediawiki 
        does not break there when displaying (impedance mismatch between docs 
        and html whitespace)
        """
        text = re.sub(r"(\w) *\n *(\w)", r"\1 \2", text)
        # Cleaning up space around headings
        text = re.sub("=\n{2,}", "=\n", text)
        text = re.sub("\n{2,}=", "\n=", text)
        text = re.sub("\n{2,}", "\n\n", text)
        text = re.sub("__NOTOC__\n*", "", text)
        return text


    def node_to_text(self, node):
        """
        Turn a mwparserfromhell node into plaintext.

        NOTE: Again, this makes us losing formatting inside (if there is any), 
        and is probably doing the wrong thing for some kinds of content
        """

        if node is None:
            return ''
        
        return str(node)


    def is_image(self, name):
        return name.endswith(".jpg") or name.endswith(".png") or name.endswith(".gif")


    def node_to_requests(self, node, requests, status, start_index=1):
        if isinstance(node, mwparserfromhell.nodes.comment.Comment):
            logging.debug(f"Skipping comment: {str(node)}")

        elif isinstance(node, mwparserfromhell.nodes.text.Text):
            text = self.node_to_text(node)

            if text == '' or not text:
                # Don't insert anything
                return status
            if status and status.is_bullet():
                # TODO: insert_bullet_text is way too happy at inserting bullets
                requests.append(self.insert_bullet_text(start_index, status, str(node)))
                # requests.append(self.insert_text(start_index, text, status))
                status = status.bullet_complete()
            else:
                requests.append(self.insert_text(start_index, text, status))

        elif isinstance(node, mwparserfromhell.nodes.heading.Heading): 
            original_text = str(node)
            stripped = original_text.lstrip('=')
            level = "HEADING_" + str(len(original_text) - len(stripped))
            text = re.sub("(^=+|=+$)", "", original_text, 2)
            text = re.sub("'{2,}", "", text)
            text = text.strip()
            requests.append(self.insert_heading_text(start_index, text, level))

        elif isinstance(node, mwparserfromhell.nodes.wikilink.Wikilink):
            if node.title is None:
                raise "Unclear what to do with a wikilink that has no title destination"
            else:
                title = self.node_to_text(node.title)
                # Strip off front colon that makes it go straight to the file/category
                title = title.strip(":")

            doc_id = self.mappings.get_id_for_title(title)
            if doc_id:
                url = GOOGLE_DOCS_PREFIX + doc_id + "/edit"
            else:
                url = "wiki://" + title

            text = self.node_to_text(node.text).strip()
            if not text:
                text = title

            if "File:" in title or "Media:" in title:
                # Mediawiki lets you insert thumbnails of PDFs, let's not bother with that
                if "thumb" in text and self.is_image(title):
                    thumb_params = text.split("|")
                    additional_text = "\n"
                    if len(thumb_params) > 0:
                        # NOTE: This is probably not the right way to choose what part of the parameters are the caption
                        caption = thumb_params[-1]
                        if not caption == "thumb" and not "px" in caption:
                            additional_text = "\n" + caption

                    image = self.wiki.pages[title]
                    escaped_title = title.replace(" ", "_")
                    uri = self.http_prefix + "/" + escaped_title
                    filename = self.file_prefix + "/" + escaped_title
                    if 'baldi' in socket.gethostname():
                        with open(filename, 'wb') as fd:
                            image.download(fd)
                    else:
                        _, tempfilename = tempfile.mkstemp()
                        with open(tempfilename, 'wb') as fd:
                            image.download(fd)
                            cmd = f"chmod 664 '{tempfilename}'"
                            os.system(cmd)
                            cmd = f"scp '{tempfilename}' baldi:'{filename}'"
                            os.system(cmd)
                        os.system(f"rm {tempfilename}")

                    # TODO: Consider extracting width from thumb_params and passing along?
                    logging.info(f"Trying to insert image at url: {uri}")
                    # TODO: Disable when image truncation is "solved"
                    # requests.append(self.insert_image(start_index, uri))
                    requests.append(self.insert_text(start_index, "IMAGE PENDING"))

                    requests.append(self.insert_text(start_index, additional_text))

                elif title in self.mappings.file_to_id:
                    url = GOOGLE_DRIVE_PREFIX + self.mappings.file_to_id[title]
                    requests.append(self.insert_link(start_index, text, url))

                else:
                    # Insert link to file that we'll fix up in a second pass
                    url = "wiki://" + title
                    requests.append(self.insert_link(start_index, text, url))
            else:
                requests.append(self.insert_link(start_index, text, url))

        elif isinstance(node, mwparserfromhell.nodes.external_link.ExternalLink):
            text = self.node_to_text(node.title).strip()
            url = self.node_to_text(node.url)
            if text == "":
                text = url
            requests.append(self.insert_link(start_index, text, url))

        elif isinstance(node, mwparserfromhell.nodes.tag.Tag): 
            if node.wiki_markup == '*':
                return status.set_bullet(level=1) 
            elif node.wiki_markup == '**':
                return status.set_bullet(level=2) 
            elif node.wiki_markup == '***':
                return status.set_bullet(level=3) 
            elif node.wiki_markup == '****':
                return status.set_bullet(level=4) 
            elif node.wiki_markup == '*****':
                return status.set_bullet(level=5) 
            elif node.wiki_markup == '******':
                return status.set_bullet(level=6) 
            elif node.wiki_markup == '#':
                return status.set_numeric_bullet(level=1) 
            elif node.wiki_markup == '##':
                return status.set_numeric_bullet(level=2) 
            elif node.wiki_markup == '###':
                return status.set_numeric_bullet(level=3) 
            elif node.wiki_markup == '####':
                return status.set_numeric_bullet(level=4) 
            elif node.wiki_markup == '#####':
                return status.set_numeric_bullet(level=5) 
            elif node.wiki_markup == '######':
                return status.set_numeric_bullet(level=6) 
            elif node.wiki_markup == '{|':
                requests.append(self.insert_table(start_index, node))
            elif node.wiki_markup is None:
                text = str(node)
                logging.info(f"No markup in tag? Likely raw html: {text}")
                # TODO: Clean up various kinds of html?
                # There's at least:
                # <nowiki /> (often used to escape bullets, can maybe just drop the tag?)
                # <gallery /> ex: CHM Communications and Branding Style Guide
                # <blockquote />
                # <u />
                # <pre />
                # <syntaxhighlight /> ex: FreeSurfer Setup
                # <code />
                # <sup />
                # <s />
                if text == "<br>":
                    requests.append(self.insert_text(start_index, "\n"))
                else:
                    # TODO: better HTML stripping from a library would be smart
                    text = re.sub('<[^<]+?>', '', text)
                    requests.append(self.insert_text(start_index, text, status))

            elif "''" in str(node.wiki_markup):
                def toggle():
                    if node.wiki_markup == "'''''":
                        status.toggle_bold()
                        status.toggle_italic()
                    elif node.wiki_markup == "'''":
                        status.toggle_bold()
                    elif node.wiki_markup == "''":
                        status.toggle_italic()

                clean = re.sub("'{2,}", "", str(node))
                toggle()
                requests.append(self.insert_text(start_index, clean, status))
                toggle()

            elif "---" in str(node.wiki_markup):
                logging.info(f"Skipping horizontal rule")
            else:
                logging.warning(f"Got unknown Tag node with markup {node.wiki_markup}, skipping")

        elif isinstance(node, mwparserfromhell.nodes.html_entity.HTMLEntity): 
            # Just output the Unicode version of whatever this is
            text = node.normalize()
            if text:
                requests.append(self.insert_text(start_index, text))

        elif isinstance(node, mwparserfromhell.nodes.template.Template): 
            template_name = node.name.strip() 
            requests.append(self.insert_text(start_index, f"<template for {template_name} goes here>"))
            logging.info(f"Skipping template")

        else:
            cls = str(node.__class__)
            logging.warning(f"Got node with class {cls}, skipping")

        return status


    def clear_document(self):
        idxend = self.get_last_index()
        if idxend <= 2:
            # Doc already empty
            return
        self.driver.batch_update(self.doc_id, [{
            'deleteContentRange': {
                'range': {
                    'startIndex': 1,
                    'endIndex': idxend-1,
                }
            }}])


    def insert_text(self, idx, text, status=None):
        """
        Create text.
        """

        if text == "" or not text:
            return []

        insert_text = {
            'insertText': {
                'location': {
                    'index': idx,
                },
                'text': text
            }
        }

        is_bold = False
        is_italic = False
        if status:
            is_bold = status.is_bold
            is_italic = status.is_italic

        pt = FONT_SIZE_DEFAULT
        if status:
            pt = status.font_size

        update_text = {
            'updateTextStyle': {
                'range': {
                    'startIndex': idx,
                    'endIndex': idx + len(text)
                },
                'textStyle': {
                    'bold': is_bold,
                    'italic': is_italic,
                    'fontSize': {
                        'magnitude': pt,
                        'unit': 'PT'
                    },
                },
                'fields': 'bold, italic, fontSize'
            }
        }

        return [[insert_text, update_text]]


    def insert_heading_text(self, idx, text, level='HEADING_1'):
        """
        Create a heading in the document.

        Levels are here: https://developers.google.com/docs/api/reference/rest/v1/documents?hl=en#NamedStyleType
        """

        if text == "" or not text:
            return []

        return [[{
                'insertText': {
                    'location': {
                        'index': idx,
                    },
                    'text': text
                }
            },
            {
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': idx,
                        'endIndex':  idx + len(text)
                    },
                    'paragraphStyle': {
                        'namedStyleType': level,
                    },
                    'fields': 'namedStyleType'
                }
            },
            # This is real dumb, but if we don't insert a paragraph and force 
            # it to NORMAL, the stuff preceding this header in the document 
            # will get header-tized when the requests are all reversed and 
            # batched up. It leads to a really dumb extra blank paragraph that 
            # gets the formatting, but I can't find a good way around that
            {
                'insertText': {
                    'location': {
                        'index': idx,
                    },
                    'text': "\n"
                }
            },
            {
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': idx,
                        'endIndex':  idx
                    },
                    'paragraphStyle': {
                        'namedStyleType': 'NORMAL_TEXT',
                    },
                    'fields': 'namedStyleType'
                }
            },
            ]]


    def insert_bullet_text(self, idx, status, text):
        """
        Create bullets in the document.

        I couldn't figure out how to do this without completely
        bulletting everything in the doc, so I stole the idea from
        https://stackoverflow.com/questions/65330602/how-do-i-indent-a-bulleted-list-with-the-google-docs-api
        to do a really dumb set of insertions and deletions
        """

        if text == "" or not text:
            return []

        if status.bullet_kind == BulletKind.NUMERIC:
            bullet_preset = 'NUMBERED_DECIMAL_ALPHA_ROMAN_PARENS'
        else:
            bullet_preset = 'BULLET_DISC_CIRCLE_SQUARE'

        bullet_text = ("\t" * (status.level - 1)) + text

        return [[
            { 'insertText': {
                'location': {
                    'index': idx,
                },
                'text': f"\n"
            }},
            { 'createParagraphBullets': {
                    'range': {
                        'startIndex': idx+1,
                        'endIndex':  idx+1
                    },
                    'bulletPreset': bullet_preset,
            }},
            { 'insertText': {
                'location': {
                    'index': idx+1,
                },
                'text': bullet_text
            }},
            { 'deleteContentRange': {
                    'range': {
                        'startIndex': idx + len(bullet_text),
                        'endIndex':  idx + len(bullet_text) + 1
                    },
            }},
            ]]


    def insert_image(self, idx, uri):
        """
        Insert image accessible at the given URI.
        """

        return [[
            {
                'insertInlineImage': {
                    'location': {
                        'index': idx,
                    },
                    'uri': uri,
                    'objectSize': {
                        'width': {
                            'magnitude': 200,
                            'unit': 'PT'
                        }
                    }
                }
            }
        ]]


    def insert_link(self, idx, text, url):
        """
        Insert hyperlink with given text and URL.
        """

        if text == "" or not text:
            return []

        return [[
            {
                'insertText': {
                    'location': {
                        'index': idx,
                    },
                    'text': text
                }
            },
            {
                "updateTextStyle": {
                    "textStyle": {
                        "link": {
                            "url": url
                        }
                    },
                    "range": {
                        "startIndex": idx,
                        "endIndex": idx + len(text)
                    },
                    "fields": "link"
                }
            }
        ]]


    def insert_table(self, idx, markup):
        """
        Create table, given the raw mediawiki markup
        """

        rows = markup.contents.split("|-")
        # Not sure how header exclamations in wikitable markup are escaped?
        # Here we're just going to eat whether a row is a header and not try
        # to format it at all
        rows[0] = rows[0].replace("!", "|")
        # NOTE: Naive split on "|" breaks on tables with links that use |,
        # so the ^|\n here is a bad hack to get by those
        split_rows = [re.split(r"(?:^|\n)\|", r)[1:] for r in rows]
        max_columns = max([len(r) for r in split_rows])
        if max_columns == 0:
            logging.warning(f"Hit table with no columns? Skipping")
            return self.insert_text(idx, "[Table failed to convert]")

        def table_index_of_cell(i, j):
            # Complicated math to find index location of a given cell 
            # in the crazy google docs json tree counting system, yuck
            return (3 + i + max_columns * i * 2) + (j + 1) * 2

        # For some reason we have to tweak this, you would think it would be 
        # just the same as the table index of the last cell, but it's not
        end_of_font_range = table_index_of_cell(len(split_rows), max_columns) - max_columns * 2

        requests = [
            { 'insertTable': {
                'location': { 'index': idx, },
                'rows': len(rows),
                'columns': max_columns }},
            { 'updateTextStyle': {
                'range': {
                    'startIndex': 1,
                    'endIndex': end_of_font_range
                },
                'textStyle': {
                    'fontSize': {
                        'magnitude': FONT_SIZE_TABLE,
                        'unit': 'PT'
                    },
                },
                'fields': 'fontSize'
            }}
            ]

        all_cell_requests = []

        for i, row in enumerate(split_rows):
            for j, cell in enumerate(row):
                text = cell.strip()
                if text:
                    index = table_index_of_cell(i, j)

                    # Now we parse the cell's content and convert that, too, 
                    # because it could have links and what not
                    table_status = NodeResponse()
                    table_status.font_size = 9
                    cell = self.wiki_markup_to_requests(text, index, status=table_status)
                    all_cell_requests.extend(cell)

                    # TODO: Links not getting output here???

        requests.extend(reversed(all_cell_requests))

        # Remember, we have to wrap the list of actions in another list
        # so it doesn't get reversed, we've already set it up to happen
        # exactly in the order we want
        return [requests]


    def get_content(self):
        return self.driver.get_document(self.doc_id).get('body').get('content')


    def get_last_index(self):
        content = self.get_content()
        last = content[-1]
        return last['endIndex']


    def get_text_range(self, match_text):
        """
        Find `match_text` and return its start and end index.
        """

        data = self.get_content()

        for d in data:
            para = d.get('paragraph')
            if para is None:
                continue
            else:
                elements = para.get('elements')
                for e in elements:
                    if e.get('textRun'):
                        content = e.get('textRun').get('content')
                        if match_text in content:
                            # Do we want to adjust to WHERE in content, or just return the whole run?
                            idx = e.get('startIndex')
                            inxend = e.get('endIndex')
                            return idx, endIdx

        return None, None

