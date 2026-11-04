class Server:
    def __init__(self, supported_versions, capabilities, name, version):
        self.supported_versions = list(supported_versions)  # preferred first
        self.capabilities = capabilities
        self.name = name
        self.version = version
        self.client_info = None
        self.client_capabilities = None
        self.ready = False

    def handle(self, message):
        """Answer one decoded JSON-RPC message: a response dict, or None for a notification."""
        raise NotImplementedError(
            "track the lifecycle: initialize, then the initialized notification"
        )
