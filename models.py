"""models.py: Various data models used in discgolfmetrix.com API."""

__author__ = "Jakub Wroniecki"
__copyright__ = "Copyright 2022, Jakub Wroniecki, see LICENSE.txt for details."

import datetime
from typing import Dict, List, Tuple, Optional, Generator, Callable, Type, TypeVar, Any
import itertools
from dataclasses import dataclass, field, asdict


@dataclass
class Player:
    id: int
    name: str

    pdga_id: int = None
    pdga_rating: int = None

    default_category: str = "OPEN"

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
    sum_tuple: Tuple[int, int] 
    diff: int
    points: int = 0
    scores: List[Score] = field(default_factory=list)
    comment: str = None
    selected: bool = False
    place: int = 0
    dqf: bool = False
    dns: bool = False
    
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
    playoff_result: int = 0
    rating: Optional[int] = None
    dnf: int= 0
    

    @property
    def sum(self):
        return sum(s.result for s in self.scores)

    @property
    def diff(self):
        return sum(s.diff for s in self.scores)

    @property
    def rating_or_zero(self):
        return self.rating or 0

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

    rating_par: int = None
    rating_propagators: int = 0
    rating_per_stroke: float = 0

    use_default_category: bool = False

    @property
    def par(self):
        return sum(tr.par for tr in self.tracks)

    @property
    def ranking(self) -> List[Tuple[str, RankingList]]:
        if len(self.sub) > 0:
            results = itertools.chain(*(s.results for s in self.sub))
        else:
            results = self.results

        results = list(results)
        playoff_results = { r.player.id: r.playoff_result for r in results }


        if self.use_default_category:
            classes = itertools.groupby(sorted(results, key=lambda r: r.player.default_category),
                                                 lambda r: r.player.default_category)
        else:                        
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
                                     sum_tuple=(sum(r.sum for r in player_results), playoff_results.get(player.id, 0)),
                                     sum=sum(r.sum for r in player_results),
                                     diff=sum(r.submitted_diff for r in player_results),
                                     scores=list(itertools.chain(*(r.scores for r in player_results)))
                                     )
                for pr in player_results:
                    if pr.dnf==1:
                        entry.dqf=True
                    if pr.dnf==2:
                        entry.dqf=True
                        entry.dns=True
                        
                if not entry.dqf: #not a DQF result according to metrix        
                    if len(player_results) < len(self.sub): # too few rounds entered
                        entry.dqf = True #DNF
                    elif any(len(pr.scores) < len(self.tracks) for pr in player_results):
                        entry.dqf = True # too few holes
                
                entries.append(entry)

            entries = list(sorted(entries, key=lambda e: e.sum_tuple if not e.dqf else (1e12, 1e12)))
            place = 1
            count = 1
            previous_sum = entries[0].sum_tuple
            for e in entries:

                if e.sum_tuple > previous_sum:
                    place = count
                    previous_sum = e.sum_tuple
                e.place = place
                rl.entries.append((place, e))
                count = count + 1

            #print("Yielding class", class_name, "with", len(rl.entries), "entries")
            yield class_name, rl
