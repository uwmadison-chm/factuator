import mwparserfromhell
import logging
import re

from enum import Enum

class NodeResponseKind(Enum):
    NONE = 1
    BULLET = 2

class NodeResponse:
    def __init__(self, is_bullet=False, level=0):
        if is_bullet:
            self.kind = NodeResponseKind.BULLET
            self.level = level
        else:
            self.kind = NodeResponseKind.NONE

    def is_bullet(self):
        return self.kind == NodeResponseKind.BULLET


MOTHER_WIKI_PREFIX = "https://wiki.keck.waisman.wisc.edu/wikis/mother/index.php/"
GOOGLE_DOCS_PREFIX = "https://docs.google.com/document/d/"


class GDocConverter:
    """
    Generic converter class, called by GDocExporter

    Uses most of the same APIs
    """

    def __init__(self, mother, docs, mappings):
        self.mother = mother
        self.docs = docs
        self.mappings = mappings


    def convert(self, page, doc_id):
        """
        Convert a given page into a google document.
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
        requests += self.insert_link(1, "Original wiki location\n", MOTHER_WIKI_PREFIX + str(page.name)) 

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
            result = self.node_to_requests(node, requests, last)
            last = result

        requests = list(reversed(requests))
        flat_requests = []
        for x in requests:
            if isinstance(x, list):
                flat_requests.extend(x)
            else:
                flat_requests.append(x)

        self.batch_update(flat_requests)


    def node_to_text(self, node):
        # NOTE: Again, we're losing formatting inside if there is any, and probably doing the wrong thing for some kinds of content
        return str(node)


    def node_to_requests(self, node, requests, last):
        # TODO: convert this all to isinstance checks
        cls = str(node.__class__)
        if 'Text' in cls:
            if last.is_bullet():
                # TODO: Bullet/indent level? How?
                # https://developers.google.com/docs/api/how-tos/lists
                # TODO: insert_bullet_text is way too happy at inserting bullets
                # requests.append(self.insert_bullet_text(1, str(node)))
                requests.append(self.insert_text(1, str(node)))
            else:
                requests.append(self.insert_text(1, str(node)))

        elif 'Heading' in cls: 
            original_text = str(node)
            stripped = original_text.lstrip('=')
            level = "HEADING_" + str(len(original_text) - len(stripped))
            text = re.sub("(^=+|=+$)", "", original_text, 2)
            requests.append(self.insert_heading_text(1, text, level))
            # requests.append(self.insert_text(1, text))

        elif 'Wikilink' in cls:
            title = str(node.title)
            if title in self.mappings.title_to_id:
                url = GOOGLE_DOCS_PREFIX + self.mappings.title_to_id[title] + "/edit"
            else:
                url = "mother://" + title
            if node.text:
                text = self.node_to_text(node.text)
            else:
                text = title
            requests.append(self.insert_link(1, text, url))

        elif 'ExternalLink' in cls:
            # NOTE: Here we're losing any formatting inside the link
            requests.append(self.insert_link(1, self.node_to_text(node.title), self.node_to_text(node.url)))

        elif 'Tag' in cls: 
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
            elif node.wiki_markup == '{|':
                requests.append(self.insert_text(1, "<table goes here>"))
            else:
                logging.warning(f"Got unknown Tag node with markup {node.wiki_markup}, skipping")

        elif 'Table' in cls: 
            requests.append(self.insert_text(1, "<table? goes here>"))
            logging.info(f"Skipping table, ohhhhh boy")

        elif 'Template' in cls: 
            template_name = node.name.strip() 
            requests.append(self.insert_text(1, f"<template for {template_name} goes here>"))
            logging.info(f"Skipping template, probably deal with these after tables are working")

        else:
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


    def batch_update(self, requests):
        """
        Batch update the document with the given requests.
        """

        return self.docs.documents().batchUpdate(
            documentId=self.doc_id, body={'requests': requests}).execute()

        return result


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


    def insert_link(self, idx, text, url):
        """
        Insert hyperlink with given text and URL.
        """

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

