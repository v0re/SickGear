from ..util import FeedParserDict as FeedParserDict
from typing import Any

class Namespace:
    supported_namespaces: Any = ...
    def _start_cc_license(self, attrs_d: Any) -> None: ...
    def _start_creativecommons_license(self, attrs_d: Any) -> None: ...
    _start_creativeCommons_license: Any = ...
    def _end_creativecommons_license(self) -> None: ...
    _end_creativeCommons_license: Any = ...