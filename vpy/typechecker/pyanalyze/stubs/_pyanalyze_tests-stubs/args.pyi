from typing import Tuple

from typing_extensions import TypedDict, Unpack

class TD(TypedDict):
    x: int
    y: str

def f(*args: Unpack[Tuple[int, str]]) -> None: ...
def g(**kwargs: Unpack[TD]) -> None: ...
def h(*args: int) -> None: ...
def i(**kwargs: str) -> None: ...
