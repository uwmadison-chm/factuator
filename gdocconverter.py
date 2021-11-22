import mwparserfromhell
import logging
import re
import time

from enum import Enum

class NodeResponseKind(Enum):
    NONE = 1
    BULLET = 2

class BulletKind(Enum):
    NORMAL = 1
    NUMERIC = 2

class NodeResponse:
    def __init__(self, is_bullet=False, is_numeric_bullet=False, level=0):
        if is_bullet:
            self.kind = NodeResponseKind.BULLET
            self.bullet_kind = BulletKind.NORMAL
            self.level = level
        elif is_numeric_bullet:
            self.kind = NodeResponseKind.BULLET
            self.bullet_kind = BulletKind.NUMERIC
            self.level = level
        else:
            self.kind = NodeResponseKind.NONE

    def is_bullet(self):
        return self.kind == NodeResponseKind.BULLET

    def __str__(self):
        if self.is_bullet():
            return "Bullet"
        else:
            return "None"


GOOGLE_DOCS_PREFIX = "https://docs.google.com/document/d/"


class GDocConverter:
    """
    Generic converter class, called by GDocExporter

    Uses most of the same APIs

    `file_prefix` is used to store image and other files in a 
    public-internet-accessible location so the Google Docs API can read them 
    from `http_prefix`
    """

    def __init__(self, wiki, wiki_prefix, docs, mappings, file_prefix, http_prefix):
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

        oldtext = page.text()
        p = mwparserfromhell.parse(oldtext)

        # If we were really fancy, we would try to do merging of content.
        # But we're just going to brute force override old content.
        self.clear_document()

        # Note that the Google Docs API recommends that you "create
        # backwards" because of the indexes changing on edits.
        # So we insert everything at index 1 and then flip the order of operations
        # Except this won't work for bullets or other operations that do more than one thing?
        # Or will it because of nested lists???? yarrrrrr
        requests = []

        nodes = list(p.nodes)
        last = NodeResponse()

        requests += self.insert_heading_text(1, page.name + "\n", level='TITLE') 
        requests += self.insert_link(1, "Original wiki location\n", self.wiki_prefix + str(page.name)) 

        #### TESTING CODE, adds fake content
        # requests += self.insert_text(1, "Should be normal\n") 
        # requests += self.insert_text(1, "Continuing normal\n") 
        # requests += self.insert_heading_text(1, "Should be heading 1\n", level='HEADING_1') 
        # requests += self.insert_text(1, "Intro to this normal\n") 
        # requests += self.insert_heading_text(1, "Should be heading 2\n", level='HEADING_2') 
        # requests += self.insert_text(1, "Should be normal, again\n") 

        for node in nodes:
            # NOTE: It's going to get way funkier if we need to maintain AST context,
            # but so far the only thing that requires context are bullets, which show up
            # as a Tag with markup '*' and then the following text is a bullet
            logging.debug(f"Converting node {node} with status {last}")
            result = self.node_to_requests(node, requests, last)
            last = result

        requests = list(reversed(requests))
        flat_requests = []
        for x in requests:
            if isinstance(x, list):
                flat_requests.extend(x)
            else:
                flat_requests.append(x)

        self.batch_update(flat_requests, debug=debug)


    def node_to_text(self, node):
        # NOTE: Again, we're losing formatting inside if there is any, and 
        # probably doing the wrong thing for some kinds of content
        if node is None:
            return ''
        reduce_newlines = re.sub("\n{2,}", "\n", str(node))
        remove_toc = re.sub("__NOTOC__\n*", "", reduce_newlines)
        return remove_toc

    def is_image(self, name):
        return name.endswith(".jpg") or name.endswith(".png") or name.endswith(".gif")

    def node_to_requests(self, node, requests, last):
        if isinstance(node, mwparserfromhell.nodes.comment.Comment):
            logging.debug(f"Skipping comment: {str(node)}")

        elif isinstance(node, mwparserfromhell.nodes.text.Text):
            text = self.node_to_text(node)

            # Try to remove extra line feeds in between text;
            # mediawiki does not break there when displaying
            # (impedance mismatch between docs and html whitespace)
            text = re.sub(r"(.|\s)\n(.|\s)", r"\1\2", text)
            if text == '' or not text:
                # Don't insert anything
                return NodeResponse()
            # TODO: Probably want to trim extra newlines here
            if last and last.is_bullet():
                # TODO: Bullet/indent level? How?
                # https://developers.google.com/docs/api/how-tos/lists
                # TODO: insert_bullet_text is way too happy at inserting bullets
                # requests.append(self.insert_bullet_text(1, str(node)))
                requests.append(self.insert_text(1, text))
            else:
                requests.append(self.insert_text(1, text))

        elif isinstance(node, mwparserfromhell.nodes.heading.Heading): 
            original_text = str(node)
            stripped = original_text.lstrip('=')
            level = "HEADING_" + str(len(original_text) - len(stripped))
            text = re.sub("(^=+|=+$)", "", original_text, 2)
            text = re.sub("'{2,}", "", text)
            text = text.strip()
            requests.append(self.insert_heading_text(1, text, level))

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
                    uri = self.http_prefix + "/" + title
                    filename = self.file_prefix + "/" + title
                    with open(filename, 'wb') as fd:
                        image.download(fd)

                    # TODO: Consider extracting width from thumb_params and passing along?
                    logging.info(f"Trying to insert image at url: {uri}")
                    requests.append(self.insert_image(1, uri))
                    requests.append(self.insert_text(1, additional_text))
                else:
                    # Insert link to file that we'll fix up in a second pass
                    url = "wiki://" + title
            else:
                requests.append(self.insert_link(1, text, url))

        elif isinstance(node, mwparserfromhell.nodes.external_link.ExternalLink):
            text = self.node_to_text(node.title).strip()
            url = self.node_to_text(node.url)
            if text == "":
                text = url
            requests.append(self.insert_link(1, text, url))

        elif isinstance(node, mwparserfromhell.nodes.tag.Tag): 
            if node.wiki_markup == '*':
                return NodeResponse(is_bullet=True, level=1) 
            elif node.wiki_markup == '**':
                return NodeResponse(is_bullet=True, level=2) 
            elif node.wiki_markup == '***':
                return NodeResponse(is_bullet=True, level=3) 
            elif node.wiki_markup == '****':
                return NodeResponse(is_bullet=True, level=4) 
            elif node.wiki_markup == '*****':
                return NodeResponse(is_bullet=True, level=5) 
            elif node.wiki_markup == '******':
                return NodeResponse(is_bullet=True, level=6) 
            elif node.wiki_markup == '#':
                return NodeResponse(is_numeric_bullet=True, level=1) 
            elif node.wiki_markup == '##':
                return NodeResponse(is_numeric_bullet=True, level=2) 
            elif node.wiki_markup == '###':
                return NodeResponse(is_numeric_bullet=True, level=3) 
            elif node.wiki_markup == '####':
                return NodeResponse(is_numeric_bullet=True, level=4) 
            elif node.wiki_markup == '#####':
                return NodeResponse(is_numeric_bullet=True, level=5) 
            elif node.wiki_markup == '######':
                return NodeResponse(is_numeric_bullet=True, level=6) 
            elif node.wiki_markup == '{|':
                logging.info(f"Skipping table")
                requests.append(self.insert_text(1, "<table goes here>"))
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
                    requests.append(self.insert_text(1, "\n"))
                else:
                    requests.append(self.insert_text(1, text))
            elif "'" in str(node.wiki_markup):
                logging.info(f"Skipping bold/italic")
            elif "---" in str(node.wiki_markup):
                logging.info(f"Skipping horizontal rule")
            else:
                logging.warning(f"Got unknown Tag node with markup {node.wiki_markup}, skipping")

        elif isinstance(node, mwparserfromhell.nodes.html_entity.HTMLEntity): 
            # Just output the Unicode version and hope that works?
            text = node.normalize()
            if text:
                requests.append(self.insert_text(1, text))

        elif isinstance(node, mwparserfromhell.nodes.template.Template): 
            template_name = node.name.strip() 
            requests.append(self.insert_text(1, f"<template for {template_name} goes here>"))
            logging.info(f"Skipping template, probably deal with these after tables are working?")

        else:
            cls = str(node.__class__)
            logging.warning(f"Got node with class {cls}, skipping")

        return NodeResponse()


    def clear_document(self):
        idxend = self.get_last_index()
        if idxend <= 2:
            # Doc already empty
            return
        self.batch_update([{
            'deleteContentRange': {
                'range': {
                    'startIndex': 1,
                    'endIndex': idxend-1,
                }
            }}])


    def batch_update(self, requests, debug=False):
        """
        Batch update the document with the given requests.

        If debug is passed, do each request one at a time.
        """
        
        if debug:
            for r in requests:
                try:
                    self.docs.documents().batchUpdate(
                        documentId=self.doc_id, body={'requests': [r]}).execute()
                except BaseException as e:
                    print(f"Unexpected {e}, {type(e)} with request {r}")
                    raise
                time.sleep(0.1)

        else:
            return self.docs.documents().batchUpdate(
                documentId=self.doc_id, body={'requests': requests}).execute()


    def format_text(self, idx, idxend, is_bold, is_italic, is_underline):
        """
        Format the text at certain indexes with various options

        TODO: Just an example, not actually in use because of how the wiki markup works,
                may need to do a second pass with get_text_range to catch this stuff fully? Yargh
        """
        return [{
            'updateTextStyle': {
                'range': {
                    'startIndex': idx,
                    'endIndex': idxend
                },
                'textStyle': {
                    'bold': is_bold,
                    'italic': is_italic,
                    'underline': is_underline
                },
                'fields': 'bold, italic'
            }}]

        return req


    def insert_text(self, idx, text):
        """
        Create text.
        """

        if text == "" or not text:
            return []

        return [[{
            'insertText': {
                'location': {
                    'index': idx,
                },
                'text': text
            }}, {
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
            }]]


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
            }}, {
                'updateParagraphStyle': {
                    'range': {
                        'startIndex': idx,
                        'endIndex':  idx # + len(text) # we don't extend because this gets the line we want correctly (maybe)
                    },
                    'paragraphStyle': {
                        'namedStyleType': level,
                    },
                    'fields': 'namedStyleType'
                }
            }]]


    def insert_bullet_text(self, idx, text, numbered=False):
        """
        Create bullets in the document.
        """

        if text == "" or not text:
            return []

        if numbered:
            bullet_preset = 'BULLET_DECIMAL_ALPHA_ROMAN_PARENS'
        else:
            bullet_preset = 'BULLET_DISC_CIRCLE_SQUARE'

        return [[{
            'insertText': {
                'location': {
                    'index': idx,
                },
                'text': text
            }}, {
                'createParagraphBullets': {
                    'range': {
                        'startIndex': idx,
                        'endIndex':  idx + len(text)
                    },
                    'bulletPreset': bullet_preset,
                }
            }]]


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



    def get_document(self):
        return self.docs.documents().get(documentId=self.doc_id).execute()

    def get_content(self):
        return self.get_document().get('body').get('content')


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
