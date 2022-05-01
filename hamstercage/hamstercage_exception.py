class HamstercageException(Exception):
    """
    An application runtime error that leads to exiting the application
    """

    def __init__(self, msg, exit_code=1):
        super().__init__(msg)
        self.exit_code = exit_code
