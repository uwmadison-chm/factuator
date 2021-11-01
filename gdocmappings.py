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
                self.do_not_convert = data['do_not_convert']
                self.file_to_id = data['do_not_convert']

        else:
            self.title_to_id = {}
            self.id_to_title = {}
            self.do_not_convert = []
            self.file_to_id = {}

    def save(self):
        data = {
            'title_to_id': self.title_to_id,
            'id_to_title': self.id_to_title,
            'do_not_convert': self.do_not_convert,
            'file_to_id': self.file_to_id,
        }

        with open(self.path, 'w') as f:
            json.dump(data, f)

    def add(self, title, document_id):
        self.title_to_id[title] = document_id
        self.id_to_title[document_id] = title
        self.save()
