import logging
import re
from apiclient.http import MediaFileUpload
from apiclient.errors import HttpError

GOOGLE_DOCS_PREFIX = "https://docs.google.com/document/d/"
GOOGLE_DRIVE_PREFIX = "https://drive.google.com/file/d/"

class GDocLinks:
    def __init__(self, wiki, driver, file_prefix, folder_id):
        """
        Needs a mwclient wiki connection, a GDocDriver, a file_prefix where we 
        can stash files, the mappings so we can save what links to what and 
        what file IDs represent what wiki files, and the folder_id in Drive to 
        store new files
        """
        self.wiki = wiki
        self.driver = driver
        self.file_prefix = file_prefix
        self.mappings = driver.mappings
        self.folder_id = folder_id


    def check_links(self, doc_id):
        """
        Updates any links with "wiki://" prefixes if they exist in the 
        driver's mappings to the resulting doc or file ID
        """
        logging.info(f"Re-linking inside doc {doc_id}")
        try:
            document = self.driver.get_document(doc_id)
        except HttpError as e:
            logging.warning(f"HttpError when trying to read doc {doc_id}: {e}")
            return

        content = document['body']['content']
        requests = []

        doc_id_regex = re.compile('docs.google.com/document/d/([^/]{40,})', re.IGNORECASE)
        category_regex = re.compile(r'[^a-zA-Z0-9.!@$%&*()/]', re.IGNORECASE)

        # Now we walk the AST looking for links
        # Links are stored as 'link' properties inside the 'textStyle'
        # properties of 'textRun' elements.
        def check_for_link(element, start_index, end_index):
            if not 'link' in element:
                return False

            link = element['link']
            if 'url' in link:
                url = link['url']
            else:
                return False

            if url.startswith("wiki://"):
                # Check in mappings for something with that title
                _, title = url.split("://", 2)
                if "File:" in title or "Media:" in title:
                    # Regularize the title
                    title = title.strip(":")
                    title = title.replace("Media:", "File:")

                    if title in self.mappings.file_to_id:
                        file_url = GOOGLE_DRIVE_PREFIX + self.mappings.file_to_id[title]
                    else:
                        # Bring that file over, store in mappings separately as well
                        filename = self.file_prefix + "/" + title
                        wiki_file = self.wiki.pages[title]
                        with open(filename, 'wb') as fd:
                            wiki_file.download(fd)

                        file_metadata = {
                            'name': title.replace("File:", ""),
                            'mimeType': '*/*',
                            'parents': [self.folder_id],
                        }
                        media = MediaFileUpload(filename,
                            mimetype='*/*',
                            resumable=True)

                        result = self.driver.drive.files().create(
                                body=file_metadata,
                                media_body=media,
                                supportsAllDrives=True,
                                fields='id').execute()
                        file_id = result.get('id')

                        self.mappings.file_to_id[title] = file_id
                        file_url = GOOGLE_DRIVE_PREFIX + file_id

                    logging.info(f"Linking {title} to {file_id}")
                    request = self.fix_link(start_index, end_index, file_url)
                    requests.append(request)

                elif "Category:" in title:
                    _, category = url.split("Category:", 2)
                    category = category.strip()
                    category = category_regex.sub("-", category)
                    self.driver.add_tag(doc_id, category)

                elif title in self.mappings.title_to_id:
                    doc_url = GOOGLE_DOCS_PREFIX + self.mappings.title_to_id[title]
                    request = self.fix_link(start_index, end_index, doc_url)
                    requests.append(request)

            else:
                match = doc_id_regex.search(url)
                if match:
                    # Track this link in our mappings
                    link_doc_id = match.group(1)
                    if not link_doc_id in self.mappings.ids_that_link_to_id:
                        self.mappings.ids_that_link_to_id[link_doc_id] = []

                    if not doc_id in self.mappings.ids_that_link_to_id[link_doc_id]:
                        self.mappings.ids_that_link_to_id[link_doc_id].append(doc_id)

        for item in content:
            self.driver.traverse(check_for_link, item, 0, 0)

        # Because indexes and content aren't changing through these edits,
        # we can send them as a batch in any order, hooray
        if requests:
            logging.info(f"Found {len(requests)} links in need of updating, sending batch")
            self.driver.batch_update(doc_id, requests)
            self.mappings.save()


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

