from typing import List, Dict
from scipy import stats
from matplotlib import pylab
from metrix import MetrixAPI
from models import CompetitionResult, Competition
import logging

"""rating.py: Kalkulator ratingu Zimowej Ligi DGW."""

__author__ = "Bartosz Wilczynski"
__copyright__ = "Copyright 2024, Bartosz Wilczynski, see LICENSE.txt for details."


def calculate_round_rating(competition: Competition, player_lookup: Dict[int, int], plotting=False,
                           outlier_fraction=0.25, prop_min_rating=500):
    scores = []
    ratings = []
    logging.info(f"Processing round {competition.name} #{competition.id} par {competition.par}")

    par = competition.par
    propagators_count = 0
    for result in competition.results:
        if result.player.id in player_lookup:
            pl_rating = player_lookup[result.player.id]
            pl_score = par + result.diff
            if pl_rating > prop_min_rating:
                scores.append(pl_score)
                ratings.append(pl_rating)
                propagators_count += 1

    logging.info(f"Available propagators {propagators_count} of {len(competition.results)}")
    if propagators_count < 3:
        logging.warning(f"Too few propagators for {competition.name} #{competition.id} - skipping.")
        return

    # first approx fit
    lr = stats.linregress(ratings, scores)
    predictions = [(lr.intercept + lr.slope * rating) for rating in ratings]
    residuals = [(prediction - score) ** 2 for (prediction, score) in zip(predictions, scores)]
    rating_calc = lambda x: int(x / lr.slope - lr.intercept / lr.slope)
    logging.info(f"Round par score {rating_calc(par)} diff per stroke {-1 / lr.slope} r-val {lr.rvalue}")

    # compute the outliers
    num_outliers = int(outlier_fraction * len(residuals))
    outlier_thr = sorted(residuals)[-num_outliers]
    new_rats, new_scs = [], []
    for r, s, p, rs in zip(ratings, scores, predictions, residuals):
        if rs > outlier_thr:
            logging.debug(f"outlier {r} {s} {p} {rs}")
        else:
            new_rats.append(r)
            new_scs.append(s)

    # second - improved fit
    lr_new = stats.linregress(new_rats, new_scs)
    new_preds = [(lr_new.intercept + lr_new.slope * rating) for rating in new_rats]
    residuals = [(prediction - score) ** 2 for (prediction, score) in zip(new_preds, new_scs)]
    rating_calc_new = lambda x: int(x / lr_new.slope - lr_new.intercept / lr_new.slope)

    logging.info(
        f"Robust round par score {rating_calc_new(par)} diff per stroke {-1 / lr_new.slope} r-val {lr_new.rvalue}")

    competition.rating_par = rating_calc_new(par)
    competition.rating_propagators = propagators_count
    competition.rating_per_stroke = -1 / lr_new.slope

    # apply the robust ranking to the players' results
    for result in competition.results:
        pl_score = par + result.diff
        if result.player.id in player_lookup:
            pl_rating = player_lookup[result.player.id]
        else:
            pl_rating = "NA"

        if pl_score == 999:
            result.rating = None
        else:
            result.rating = rating_calc_new(pl_score)

        logging.debug(f"{result.player.name} rating  {pl_rating} diff {result.diff} par {par} score {pl_score} "
                      f"round rating {rating_calc(pl_score)} robust rating {result.rating}")

    if plotting:
        # full fit plots
        title = " ".join(competition.name.split("&rarr;")[-2:])
        pylab.figure()
        pylab.plot(ratings, scores, "k.", label="fitted scores")
        pylab.plot([rating_calc(max(scores) + 2), rating_calc(min(scores) - 2)], [max(scores) + 2, min(scores) - 2],
                   "b-", label="fitted trend")
        pylab.plot([rating_calc(par)], [par], "ro", label="par rating=%d (+/-%d)" % (rating_calc(par), -1 / lr.slope))
        pylab.legend()
        pylab.title(f"{title}", fontsize=10)
        pylab.savefig(f"round-{competition.parent.id}-{competition.id}.png")

        # robust fit plots
        pylab.figure()
        pylab.plot(new_rats, new_scs, "k.", label="robust fitted scores")
        pylab.plot([rating_calc_new(max(new_scs) + 1), rating_calc_new(min(new_scs) - 1)],
                   [max(new_scs) + 1, min(new_scs) - 1], "b-", label="fitted trend")
        pylab.plot([rating_calc_new(par)], [par], "ro",
                   label="par rating=%d (+/-%d)" % (rating_calc_new(par), -1 / lr_new.slope))
        pylab.legend()
        pylab.title(f"{title} (robust)", fontsize=10)
        pylab.savefig(f"round-{competition.parent.id}-{competition.id}-robust.png")

# if __name__ == "__main__":
#     import os
#     import os.path
#     import time
#     from pprint import pprint
#     import yaml
#
#     api = MetrixAPI(cache_file=os.path.join(os.path.dirname(__file__), "results.cache.pkl"))
#     config = yaml.load(open("config.yaml", 'r'), Loader=yaml.CLoader)
#     for i in [2806560]:
#         api.results(i)
#
#     for c in api.competitions.values():
#         for s in c.sub:
#             calculate_round_rating(api, s, plotting=True, outlier_fraction=0.25, prop_min_rating=500)
#             for r in s.results:
#                 print(r.player.name, r.rating, r.diff, r.sum)
#
#     # OUTLIER_PERC = 0.25
#     # PROP_RATING = 500
#     #
#     # for comp in api.competitions.values():
#     #     for round in comp.sub:
#     #         calculate_round_rating(api, round, plotting=True, outlier_fraction=0.25, prop_min_rating=500)
#
#     api.save_cache()
