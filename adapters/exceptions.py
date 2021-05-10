
class SanitizerNotFound(Exception):
    def __init__(self, sanitizer_name):
        self.message = f'Sanitizer "{sanitizer_name}" does not found'
        super().__init__(self.message)

    def __str__(self):
        return self.message


class ArticleNotFound(Exception):
    pass
