import os
import json

class GDocMappings:
    def __init__(self, path):
        self.path = path
        if os.path.exists(path):
            with open(path) as json_file:
                data = json.load(json_file)
                self.title_to_id = data['title_to_id']
                self.id_to_title = data['id_to_title']
                self.ids_that_link_to_id = data['ids_that_link_to_id']
                self.do_not_convert = data['do_not_convert']
                self.file_to_id = data['file_to_id']

        else:
            self.title_to_id = {}
            self.id_to_title = {}
            self.ids_that_link_to_id = {}
            self.do_not_convert = []
            self.file_to_id = {}

    def save(self):
        data = {
            'title_to_id': self.title_to_id,
            'id_to_title': self.id_to_title,
            'ids_that_link_to_id': self.ids_that_link_to_id,
            'do_not_convert': self.do_not_convert,
            'file_to_id': self.file_to_id,
        }

        with open(self.path, 'w') as f:
            json.dump(data, f)

    def add(self, title, document_id):
        title = self.normalize(title)
        self.title_to_id[title] = document_id
        self.id_to_title[document_id] = title
        self.save()

    
    def normalize(self, title):
        # NOTE: Probably more stuff here
        return title.replace("_", " ")

    def get_id_for_title(self, title):
        title = self.normalize(title)
        if title in self.title_to_id:
            return self.title_to_id[title]
        else:
            return None
