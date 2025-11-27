from dataclasses import dataclass, field
from typing import Dict, List, Optional
import logging

from models import RankingEntry, Competition, Player
from metrix import MetrixAPI
import jinja2
import os, os.path

DEF_CATS= {"OPEN", "WOMEN", "MASTERS", "JUNIOR"}
SCORING= {"dgpt100" : [100,85,75,69,64,60,57,54,52,50,48,46,44,42,40,38,36,34,32,30,29,28,27,26,25,24,23,22,21,20,19,18,17,16,15,14,13,12,11,10,9,8,7,6,5,4,3,2,2,2]}

"""main.py: Generator rankingu Zimowej Ligi DGW."""

__author__ = "Jakub Wroniecki"
__copyright__ = "Copyright 2022, Jakub Wroniecki, see LICENSE.txt for details."


def polish_rounding(num):
    return (int(num*2)+1)//2

class ZimowyDGW:

    @dataclass
    class DGWEntry:
        player: Player
        results: Dict[int, RankingEntry] = field(default_factory=dict)
        sum: int = 0
        place: int = None

        def best(self, count):
            for s in self.results.values():
                s.selected = False
            selected = sorted(self.results.values(), key=lambda r: 1 if r.dqf else -r.points)[:count]
            for s in selected:
                s.selected = True
            self.sum = sum(1 if s.dqf else s.points for s in selected)
            return self.sum

        def __hash__(self):
            return hash(self.player)

    def __init__(self, competition_ids: List[int], title='', categories= DEF_CATS, api: Optional[MetrixAPI] = None, scoring="proportional",cache_file=None,ignore_holes=None):
        self.competition_ids = competition_ids
        
        self.entries = {}
        self.rankings = {}
        for cat in categories:
            self.entries[cat]={}
            self.rankings[cat]={}
        self.entries_sorted: Dict[str, List[ZimowyDGW.DGWEntry]] = {}

        self.scoring=scoring
        self.open_cat=list(categories.keys())[0]
        
        self.competitions: List[Competition] = []

        self.errors: List[str] = []
        self.title = title

        self.cache_file = cache_file

        self.api = api or MetrixAPI(cache_file=self.cache_file)

        self.ignore_holes=ignore_holes

    def reload(self) -> List[Competition]:
        api = self.api
        data: List[Competition] = []

        for competition_id in self.competition_ids:
            if self.ignore_holes and competition_id in self.ignore_holes:
                data.append(api.results(competition_id,self.ignore_holes[competition_id]))
            else:
                data.append(api.results(competition_id))
                
        for competition in data:
            self.competitions.append(competition)
            rankings = {}
            for class_name, ranking in competition.ranking:
                class_name = class_name.upper()
                if class_name not in self.rankings:
                    #print("Class not in rankings",class_name,self.rankings.keys())
                    if "MASTER" in class_name:
                        real_class_name = "MASTERS"
                    elif "WOMEN" in class_name:
                        real_class_name = "WOMEN"
                    elif "JUNIOR" in class_name:
                        real_class_name = "JUNIOR"
                    else:
                        real_class_name = "OPEN"
                else: #class_name in rankings
                    real_class_name = class_name
                    
                self.rankings[real_class_name] = ranking

            #print("self.rankings.keys", list(self.rankings.keys()),"self.open_cat",self.open_cat,SCORING[self.scoring])

            if self.open_cat not in self.rankings:
                continue

            if self.scoring=="proportional":
                #LuOpen = len(list(e for e in rankings["OPEN"].entries if not e[1].dqf)) # moglibyśmy nie liczyć DNFów
                LuOpen = len(list(e for e in self.rankings[self.open_cat].entries)) #  liczymy DNFy do liczby graczy


                for class_name, ranking in self.rankings.items():
                    Lu = len(list(e for e in ranking.entries))# if not e[1].dqf)) # liczymy DNF do LU
                    if Lu < 3:
                        filler_ranking = self.rankings[self.open_cat].entries[:]
                        filler_ranking.extend(ranking.entries)

                    for entry in ranking.entries:
                        dgw_entry: ZimowyDGW.DGWEntry = self.entries[class_name].get(entry[1].player, self.DGWEntry(player=entry[1].player))
                        if entry[1].dqf:
                            entry[1].points = 1
                            entry[1].comment = "DNF = 1 pkt"
                        elif Lu >= 3:
                            points = polish_rounding((Lu-entry[0]+1)*(100/Lu))
                            entry[1].points = points
                            entry[1].comment = f"{entry[0]} na {Lu} = ({Lu}-{entry[0]}+1)*(100/{Lu}) = ({Lu - entry[0] +1}*{(100/Lu):0.3f})"
                        else:
                            M = 1
                            for m, re in self.rankings[self.open_cat].entries:
                                if re.sum < entry[1].sum:
                                    M = M + 1
                                else:
                                    break
                            entry[1].comment = f"(OPEN) {M} na {LuOpen+1} = ({LuOpen + 1}-{entry[0]}+1)*(100/{Lu}) = ({LuOpen + 1 - entry[0]+1}*{(100/(LuOpen+1)):0.2f}) "
                            entry[1].points =polish_rounding( max((LuOpen + 1 - M + 1)*(100/(LuOpen+1)),1))
                        dgw_entry.results[competition.id] = entry[1]
                        self.entries[class_name][entry[1].player] = dgw_entry
            else: # we'll search for scoring table in scoring
                score_table=SCORING[self.scoring]
                for class_name, ranking in self.rankings.items():
                    for entry in ranking.entries:
                        dgw_entry: ZimowyDGW.DGWEntry = self.entries[class_name].get(entry[1].player, self.DGWEntry(player=entry[1].player))
                        if entry[1].dqf:
                            entry[1].points = 1
                            entry[1].comment = "DNF = 1 pkt"
                        else:
                            if entry[0]<len(score_table):
                                points = score_table[entry[0]-1]
                            else: #outside of defined range
                                points=1
                            entry[1].points = points
                            entry[1].comment = f" miejsce {entry[0]} "
                        dgw_entry.results[competition.id] = entry[1]
                        self.entries[class_name][entry[1].player] = dgw_entry
                            
        for class_name, entries in self.entries.items():
            logging.info(f"Generating ranking: {class_name}")
            self.entries_sorted[class_name] = list(sorted(entries.values(), key=lambda e: -e.best(7)))
            place = 0
            count = 1
            previous_points = 1e24
            for e in self.entries_sorted[class_name]:
                if e.sum < previous_points:
                    place = count
                    previous_points = e.sum
                e.place = place
                count = count + 1

        return data

    def render_ranking(self, filename: str):
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.realpath(__file__))),
                                 trim_blocks=True, lstrip_blocks=True)
        template = env.get_template("dgw.template.html")
        html_file = f'{filename}'
        logging.info(f"Generating HTML -> {html_file}.")
        all_results = []
        for c in self.competitions:
            if c.sub != []:
                for s in c.sub:
                    all_results.extend(s.results)
            else: #single round competition
                all_results.extend(c.results)
        all_results = list(sorted(all_results, key=lambda r: r.rating or 0, reverse=True))
        #print(all_results)
        logging.info(f"Results: {len(all_results)}")
        top_results = all_results[:50]
        with open(f'{html_file}', 'w', encoding='utf-8') as f:
            f.write(template.render(data=self, ratings=self.api.cache['ratings'], top_rounds=top_results))

    def render_rating(self, filename: str):
        env = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(os.path.realpath(__file__))),
                                 trim_blocks=True, lstrip_blocks=True)
        template = env.get_template("dgw.rating.template.html")
        html_file = f'{filename}'
        logging.info(f"Generating HTML -> {html_file}.")
        all_results = []
        for c in self.competitions:
            if c.sub != []:
                for s in c.sub:
                    all_results.extend(s.results)
            else: #single round
                all_results.extend(c.results)
        all_results = list(sorted(all_results, key=lambda r: r.rating or 0, reverse=True))
        logging.info(f"Results: {len(all_results)}")
        top_results = all_results[:50]
        with open(f'{html_file}', 'w', encoding='utf-8') as f:
            f.write(template.render(data=self, ratings=self.api.cache['ratings'], top_rounds=top_results))


class DgwHtmlHandler(logging.StreamHandler):

    def __init__(self, dgw: ZimowyDGW):
        super().__init__()
        self.dgw = dgw

    def emit(self, record: logging.LogRecord):
        self.dgw.errors.append(self.format(record))
