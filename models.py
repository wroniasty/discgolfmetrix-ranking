"""models.py: Various data models used in discgolfmetrix.com API."""

__author__      = "Jakub Wroniecki"
__copyright__   = "Copyright 2022, Jakub Wroniecki, see LICENSE.txt for details."

import datetime
from typing import Dict, List, Tuple, Optional, Generator, Callable, Type, TypeVar, Any
import itertools
from dataclasses import dataclass, field, asdict


@dataclass
class Player:
    id: int
    name: str

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return self.id == other.id


@dataclass
class Course:
    id: int
    name: str


@dataclass
class Score:
    result: int
    diff: int

@dataclass
class RankingEntry:
    player: Player
    competition: 'Competition'
    sum: int
    diff: int
    points: int = 0
    scores: List[Score] = field(default_factory=list)
    comment: str = None
    selected: bool = False
    place: int = 0
    dqf: bool = False

    @property
    def calculated_sum(self):
        return sum(s.result for s in self.scores)

    @property
    def calculated_diff(self):
        return sum(s.diff for s in self.scores)

@dataclass
class RankingList:
    name: str
    entries: List[Tuple[int, RankingEntry]] = field(default_factory=list)

@dataclass
class CompetitionResult:
    player: Player
    competition: 'Competition'
    class_name: str
    scores: List[Score] = field(default_factory=list)
    order_number: int = None
    submitted_sum: int = None
    submitted_diff: int = None
    valid: bool = True

    @property
    def sum(self):
        return sum(s.result for s in self.scores)

    @property
    def diff(self):
        return sum(s.diff for s in self.scores)

    def __iadd__(self, other: 'CompetitionResult'):
        self.submitted_sum += other.submitted_sum
        self.submitted_diff += other.submitted_diff
        self.scores += other.scores
        return self

@dataclass
class Track:
    number: int
    par: int
    number_alt: str = None


@dataclass
class Competition:
    id: int
    name: str = None
    date: datetime.datetime = field(default_factory=datetime.datetime.now)

    sub: List['Competition'] = field(default_factory=list)
    course: Course = None
    parent: 'Competition' = None

    tracks: List[Track] = field(default_factory=list)
    results: List[CompetitionResult] = field(default_factory=list)

    @property
    def par(self):
        return sum(tr.par for tr in self.tracks)

    @property
    def ranking(self) -> List[Tuple[str, RankingList]]:
        if len(self.sub) > 0:
            results = itertools.chain(*(s.results for s in self.sub))
        else:
            results = self.results

        classes = itertools.groupby(sorted(results, key=lambda r: r.class_name),
                                    lambda r: r.class_name)
        ranked_players = set()
        for class_name, class_results in classes:
            class_results = list(class_results)
            by_player = itertools.groupby(sorted(class_results, key=lambda r: r.player.id),
                                          lambda r: r.player)
            rl = RankingList(name=class_name)
            entries = []

            for player, player_results in by_player:
                ranked_players.add(player)
                player_results = list(player_results)
                entry = RankingEntry(player=player,
                                     competition=self,
                                     sum=sum(r.sum for r in player_results),
                                     diff=sum(r.submitted_diff for r in player_results),
                                     scores=list(itertools.chain(*(r.scores for r in player_results)))
                                     )
                if len(player_results) < len(self.sub):
                    entry.dqf = True
                elif any(len(pr.scores) < len(self.tracks) for pr in player_results):
                    entry.dqf = True
                else:
                    entry.dqf = any(not r.valid for r in player_results)
                entries.append(entry)

            entries = list(sorted(entries, key=lambda e: e.sum if not e.dqf else 1e12))
            place = 1
            count = 1
            previous_sum = entries[0].sum
            for e in entries:
                if e.sum > previous_sum:
                    place = count
                    previous_sum = e.sum
                e.place = place
                rl.entries.append((place, e))
                count = count + 1

            yield class_name, rl
