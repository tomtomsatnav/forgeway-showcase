class Library:
    def __init__(self, resources, prompts):
        self.resources = list(resources)
        self.prompts = list(prompts)

    def handle(self, request):
        """Answer a resources/* or prompts/* request with a complete JSON-RPC response."""
        raise NotImplementedError("list and read resources, list and render prompts")
