import logging

GOOGLE_DOCS_PREFIX = "https://docs.google.com/document/d/"

class GDocLinks:
    def __init__(self, driver):
        self.driver = driver
        self.mappings = driver.mappings


    def check_links(self, doc_id):
        """
        Updates any links with "wiki://" or "mother://" prefixes
        if they exist in the driver's mappings to the resulting doc ID
        """
        logging.info(f"Re-linking inside doc {doc_id}")
        document = self.driver.get_document(doc_id)

        content = document['body']['content']
        requests = []

        # Now we walk the AST looking for links
        # Links are stored as 'link' properties inside the 'textStyle'
        # properties of 'textRun' elements.
        def check_for_link(element, start_index, end_index):
            if not 'link' in element:
                return False

            link = element['link']
            url = link['url']

            if url.startswith("mother://") or \
                    url.startswith("wiki://"):
                # Check in mappings for something with that title
                _, title = url.split("://", 2)
                if "File:" in title or "Media:" in title:
                    # TODO: bring that file over, probably store in mappings separately as well
                    logging.info(f"Hit file {title}, TODO")
                if title in self.mappings.title_to_id:
                    doc_url = GOOGLE_DOCS_PREFIX + self.mappings.title_to_id[title]
                    request = self.fix_link(start_index, end_index, doc_url)
                    requests.append(request)

        for item in content:
            self.driver.traverse(check_for_link, item, 0, 0)

        # Because indexes and content aren't changing through these edits,
        # we can send them as a batch in any order, hooray
        if requests:
            logging.info(f"Found {len(requests)} links in need of updating, sending batch")
            self.driver.batch_update(doc_id, requests)


    def fix_link(self, start_index, end_index, url):
        return {
            "updateTextStyle": {
                "textStyle": {
                    "link": {
                        "url": url
                    }
                },
                "range": {
                    "startIndex": start_index,
                    "endIndex": end_index
                },
                "fields": "link"
            }
        }

