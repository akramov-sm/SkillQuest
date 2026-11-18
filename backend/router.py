import re


class Router:
    def __init__(self):
        self._routes = []

    def add(self, method, pattern, handler):
        regex = re.compile("^" + re.sub(r"\{(\w+)\}", r"(?P<\1>\\d{1,15})", pattern) + "/?$")
        self._routes.append((method, regex, handler))

    def route(self, method, pattern):
        def deco(fn):
            self.add(method, pattern, fn)
            return fn
        return deco

    def match(self, method, path):
        """Returns (handler, params) | ('method_not_allowed', None) | (None, None)."""
        path_matched = False
        for m, regex, handler in self._routes:
            hit = regex.match(path)
            if hit:
                path_matched = True
                if m == method:
                    return handler, {k: int(v) for k, v in hit.groupdict().items()}
        return ("method_not_allowed", None) if path_matched else (None, None)
