class LogStream:
    def __init__(self, log_browser):
        self.log_browser = log_browser

    def write(self, data):
        self.log_browser.append(data)
