from typing import List, Tuple, Callable, Type, TypeVar, Iterable
REntry = TypeVar('REntry')


def enumerate_ranking(ranking_list: Iterable[Type[REntry]], key: Callable[[REntry], int])\
        -> List[Tuple[int, Type[REntry]]]:
    p = 0
    c = 0
    v = -1e21
    for entry in sorted(ranking_list, key=key):
        c = c + 1
        if key(entry) > v:
            p = c
        yield p, entry
