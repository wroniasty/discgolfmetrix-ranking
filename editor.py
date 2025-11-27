import textual
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Tree, DataTable, Button, ContentSwitcher, Footer, Log, Input, \
    Static, Label, TabbedContent, TabPane, RichLog, Select
from textual.containers import Vertical, Horizontal, Container
from textual.screen import ModalScreen
from textual.widgets.tree import TreeNode

from textual.logging import TextualHandler

import logging
import logging.handlers

import yaml
import pdga

import models
from metrix import MetrixAPI


class ConfirmModal(ModalScreen[bool | None]):
    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel"),
    ]

    DEFAULT_CSS = """
    ConfirmModal {
        align: center middle;
    }

    ConfirmModal > Container {
        width: auto;
        height: auto;
        border: thick $background 80%;
        background: $surface;
    }

    ConfirmModal > Container > Label {
        width: 100%;
        content-align-horizontal: center;
        margin-top: 1;
    }
    
    ConfirmModal > Container > Horizontal {
        width: auto;
        height: auto;
    }
    
    ConfirmModal > Container > Horizontal > Button {
        margin: 2 4;
    }
        
    """

    def __init__(self, question, cancel=False, **kwargs):
        self._question = question
        self._cancel = cancel
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        with Container():
            yield Label(self._question)
            with Horizontal():
                yield Button("Yes", id="yes")
                yield Button("No", id="no")
                if self._cancel:
                    yield Button("Cancel", id="cancel")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "yes":
            self.dismiss(True)
        elif event.button.id == "no":
            self.dismiss(False)
        elif event.button.id == "cancel":
            self.dismiss(None)
        event.stop()


class PlayerInputModal(ModalScreen[models.Player]):

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel"),
    ]

    DEFAULT_CSS = """
    PlayerInputModal {
        align: center middle;
    }

    PlayerInputModal > Container {
        width: auto;
        height: auto;
        border: thick $background 80%;
    }

    PlayerInputModal > Container > Input {
        width: 60;
    }

    PlayerInputModal > Container > Horizontal {
        width: auto;
        height: auto;
    }
    
    PlayerInputModal > Container > Horizontal > Button {
        margin: 2 4;
    }
    
    """

    def __init__(self, player, **kwargs):
        self._player = player
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(self._player.name)
            yield Label("PDGA ID")
            yield Input(id="data_pdga_id", value=f"{self._player.pdga_id or ''}", type="integer")
            yield Label("PDGA rating")
            yield Input(id="data_pdga_rating", value=f"{self._player.pdga_rating or ''}", type="integer")
            with Horizontal():
                yield Button("Submit", id="submit", variant="success")
                yield Button("Cancel", id="cancel", variant="error")
            #yield Button("Fetch from PDGA", id="fetch")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "submit":
            self._player.pdga_id = int(self.query_one("Input#data_pdga_id").value or 0)
            self._player.pdga_rating = int(self.query_one("Input#data_pdga_rating").value or 0)
            self.dismiss(self._player)
        elif event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "fetch":
            pass
            #self.action_fetch()
        event.stop()

    def on_input_submitted(self, event: Input.Submitted):
        event.stop()


class PlayersWidget(DataTable):
    BINDINGS = [
        Binding("f3", "fetch()", "Fetch from PDGA"),
        Binding("f4", "edit()", "Edit player"),
        Binding("f5", "clear()", "Clear player"),
        Binding("f8", "delete()", "Delete player"),
        Binding("f6", "sort()", "Sort"),
        Binding("space", "set_category()", "Set category"),
    ]

    # DEFAULT_CSS = """
    #     Screen {
    #     }
    #
    #     #data_input {
    #     }
    #     """


    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.edited_cell = None
        self.edited_player = None

        self.add_column("Metrix ID", key="id")
        self.add_column("Name", key="name")
        self.add_column("PDGA ID", key="pdga_id")
        self.add_column("PDGA Rating", key="pdga_rating")
        self.add_column("Default Category", key="default_category")

        self.players = {}

    def add_player(self, player: models.Player):
        self.players[self.add_row(player.id, player.name, player.pdga_id, player.pdga_rating, player.default_category)] = player

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted):
        table = self
        self.edited_player = table.players[event.cell_key.row_key]
        self.edited_cell = event.cell_key

    def action_set_category(self):
        categories = self.app.config.get("dgw", {}).get("default_categories", ["OPEN"])
        self.edited_player.default_category = categories[(categories.index(self.edited_player.default_category) + 1) % len(categories)]
        self.update_current_row()

    def action_sort(self, event: DataTable.CellHighlighted):
        pass

    def action_edit(self):
        self.app.push_screen(PlayerInputModal(player=self.edited_player),
                             lambda v: self.update_current_row(v) if v is not None else None)

    def update_current_row(self, player=None):
        player = player or self.edited_player
        table = self
        table.update_cell(self.edited_cell.row_key, "pdga_id", player.pdga_id)
        table.update_cell(self.edited_cell.row_key, "pdga_rating", player.pdga_rating)
        table.update_cell(self.edited_cell.row_key, "default_category", player.default_category)

    def action_fetch(self):
        table = self

        rating = 0
        if not (self.edited_player.pdga_id or 0 > 0):
            pdga_id, rating = pdga.search_player(self.edited_player.name)
            if pdga_id is not None:
                self.edited_player.pdga_id = pdga_id
                self.edited_player.pdga_rating = rating
                self.update_current_row()
                self.app.notify(f"Fetched PDGA ID {pdga_id} rating {rating} for {self.edited_player}")
            else:
                self.edited_player.pdga_id = 0
                self.edited_player.pdga_rating = 0
                self.update_current_row()
                self.app.notify(f"PDGA ID not found for {self.edited_player.name}")

        if self.edited_player.pdga_id > 0 and rating == 0:
            rating, name = pdga.get_player_rating(self.edited_player.pdga_id)
            if rating is not None:
                self.edited_player.pdga_rating = rating
                self.update_current_row()
                self.app.notify(f"Fetched PDGA rating {rating} for {self.edited_player}")
            else:
                self.edited_player.pdga_rating = 0
                self.update_current_row()
                table.update_cell(self.edited_cell.row_key, "pdga_rating", 0)
                self.app.notify(f"PDGA rating not found for {self.edited_player.pdga_id}")


class RatingsWidget(DataTable):
    BINDINGS = [
        Binding("f3", "compute()", "Compute ratings"),
        Binding("f8", "clear()", "Clear ratings"),
    ]

    # DEFAULT_CSS = """
    #     Screen {
    #     }
    #
    #     #data_input {
    #     }
    #     """


    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.edited_cell = None

        self.add_column("ID", key="id")
        self.add_column("Name", key="name")
        self.add_column("Par rating", key="par_rating")
        self.add_column("Per stroke", key="per_stroke")
        self.add_column("Propagators", key="propagators")

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted):
        self.edited_cell = event.cell_key

    def action_clear(self):
        comp_id = self.get_cell(self.edited_cell.row_key, "id")
        self.app.push_screen(ConfirmModal(f"Clear ratings for {comp_id}?"), self.clear_on_confirm)

    def clear_on_confirm(self, clear: bool):
        if clear:
            comp_id = self.get_cell(self.edited_cell.row_key, "id")
            comp = self.app.api.sub_competitions.get(comp_id)
            if comp is not None:
                comp.rating_par = None
                comp.rating_per_stroke = None
                comp.rating_propagators = None
                for r in comp.results:
                    r.rating = None
                self.update_cell(self.edited_cell.row_key, "par_rating", "[red]NA[/]")
                self.update_cell(self.edited_cell.row_key, "per_stroke", 0)
                self.update_cell(self.edited_cell.row_key, "propagators", 0)
                self.app.notify(f"Cleared ratings for {comp.name}")

    def action_compute(self):
        comp_id = self.get_cell(self.edited_cell.row_key, "id")
        self.app.push_screen(ConfirmModal(f"Compute ratings for {comp_id}?"), self.compute_on_confirm)

    def compute_on_confirm(self, compute: bool):
        import rating
        if compute:
            comp_id = self.get_cell(self.edited_cell.row_key, "id")
            comp = self.app.api.sub_competitions.get(comp_id)
            if comp is not None:
                player_lookup = {
                    player.id: player.pdga_rating for player in self.app.api.players.values() if
                    (player.pdga_rating or 0) > 0
                }
                rating.calculate_round_rating(comp, player_lookup,
                                              plotting=True,
                                              outlier_fraction=self.app.config.get("rating", {}).get("outlier_fraction", 0.25),
                                              prop_min_rating=self.app.config.get("rating", {}).get("prop_min_rating", 500))
                self.update_cell(self.edited_cell.row_key, "par_rating", comp.rating_par)
                self.update_cell(self.edited_cell.row_key, "per_stroke", comp.rating_per_stroke)
                self.update_cell(self.edited_cell.row_key, "propagators", comp.rating_propagators)
                self.app.notify(f"Computed ratings for {comp.name}")


class CompetitionsTree(Tree):
    BINDINGS = [
        Binding("f8", "clear()", "Clear cached data"),
        Binding("f4", "edit()", "Toggle playoff result"),
        Binding("f7", "remove()", "Remove competition from cache"),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.selected_node: TreeNode = None
        self.selected_comp = None

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted):
        self.selected_node = event.node

    def action_edit(self):
        if isinstance(self.selected_node.data, models.CompetitionResult):
            r: models.CompetitionResult = self.selected_node.data
            r.playoff_result = (r.playoff_result or 0) + 1 if r.playoff_result < 10 else 0
            self.selected_node.label = f"{self.selected_node.label.split('playoff=')[0]}playoff={r.playoff_result}"
            
            if r.competition.id not in self.app.api.cache['playoffs']:
                self.app.api.cache['playoffs'][r.competition.id] = {}            
            self.app.api.cache['playoffs'][r.competition.id][r.player.id] = r.playoff_result

            self.app.notify(f"Toggled playoff result for {r.player.name} to {r.playoff_result}")

    def action_clear(self):
        self.app.push_screen(ConfirmModal(f"Clear cached data?"), self.clear_on_confirm)

    def clear_on_confirm(self, clear: bool):
        if clear:
            self.app.api.cache['competitions'] = {}
            self.app.api.competitions = {}
            self.app.api.save_cache()
            self.app.api.load_cache()
            self.app.repopulate()
            self.app.notify(f"Cleared cached data.")

class DGWWidget(Container):

    def __init__(self, api, config, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.api = api
        self.config = config

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Select.from_values(self.config['leagues'].keys(), id="league")
            yield Button("Generate ranking", id="generate")

    @textual.on(Button.Pressed, "#generate")
    def generate(self, event: Button.Pressed):
        league = self.query_one("Select#league").value
        self.app.push_screen(ConfirmModal(f"Generate ranking for {league}?"), self.generate_on_confirm)

    def generate_on_confirm(self, generate: bool):
        if generate:
            from dgw import ZimowyDGW, DgwHtmlHandler
            import rating
            league_id = self.query_one("Select#league").value
            league = self.config['leagues'].get(league_id)
            dgw = ZimowyDGW(league.get('competition_ids'), league.get('title'), api=self.api)
            logger = logging.getLogger()
            handler = DgwHtmlHandler(dgw)
            logger.addHandler(handler)
            dgw.reload()
            player_lookup = {
                player.id: player.pdga_rating for player in dgw.api.players.values() if (player.pdga_rating or 0) > 0
            }
            for comp in dgw.api.competitions.values():
                for sub_comp in comp.sub:
                    if any(r.rating is not None for r in sub_comp.results):
                        logging.warning(f"Skipping calculating ratings for {comp.name}, already in cache.")
                    else:
                        rating.calculate_round_rating(sub_comp, player_lookup, plotting=True,
                                                      outlier_fraction=self.config.get("rating", {}).get("outlier_fraction",
                                                                                                    0.25),
                                                      prop_min_rating=self.config.get("rating", {}).get("prop_min_rating",
                                                                                                   500))

            logger.removeHandler(handler)
            html_file = f'{league_id}.ranking.html'
            dgw.render_ranking(f'{html_file}')
            self.app.notify(f"Ranking generated for {league_id} in {html_file}.")
            self.app.repopulate()

            # self.app.push_screen(ConfirmModal(f"Generate ranking for {league}?"), self.generate_on_confirm)
            # self.app.notify(f"Generating ranking for {league}...")
            # self.app.api.generate_ranking(league)
            # self.app.notify(f"Ranking generated for {league}.")

class LogWidgetHandler(logging.Handler):
    """A Logging handler for Textual apps."""

    def __init__(self, widget: RichLog) -> None:
        super().__init__()
        self._widget = widget

    def emit(self, record: logging.LogRecord) -> None:
        """Invoked by logging."""
        message = self.format(record)
        self._widget.write(message)


class CacheEditorApp(App):
    CSS_PATH = "editor.tcss"
    BINDINGS = [
        Binding("f12", "repopulate()", "Repopulate", show=False),
        Binding("f2", "save()", "Save"),
        # Binding("f5", "switch_content('players')", "Players"),
        # Binding("f6", "switch_content('competitions')", "Competitions"),
        # Binding("f7", "switch_content('ratings')", "Ratings"),
        # Binding("f9", "switch_content('log')", "Log", show=False),
    ]

    def __init__(self, args):
        super().__init__()
        self.args = args
        self.api = MetrixAPI(cache_file=args.cache_file)
        try:
            self.config = yaml.load(open(args.config, 'r'), Loader=yaml.CLoader)
        except IOError as e:
            logging.exception(f"Loading config file '{args.config}' failed.")
            raise SystemExit(1)

    def repopulate(self):
        player_table = self.query_one("DataTable#players")
        player_table.clear()
        #self._log = self.query_one("Log")

        tree = self.query_one(CompetitionsTree)
        tree.root.remove_children()
        tree.clear()

        league_comp_ids = { c_id: l_id for l_id, l in self.config['leagues'].items() for c_id in l['competition_ids'] }
        logging.info(league_comp_ids)
        for c_id in self.api.cache['competitions']:
            logging.info(f"Competition {c_id}")
            c = self.api.results(c_id)
            league_id = league_comp_ids.get(c.id)
            c_node = tree.root.add(f"{league_id} {c.name}", data=c)
            logging.info(f"Competition {c_id} : {c.name}")
            for c_sub in c.sub:
                r_node = c_node.add(c_sub.name, data=c_sub)
                logging.info(f"SubCompetition {c_sub.id} : {c_sub.name} [{c_sub.parent.id}]")
                for i, r in enumerate(sorted(c_sub.results, key=lambda r: r.sum)):
                    r_node.add_leaf(f"{i+1:2}. {r.player.name} {'[red]+' if r.diff > 0 else '[green]'}{r.diff}[/] ({r.sum}) rating=[yellow]{r.rating}[/yellow] playoff={r.playoff_result}", data=r)
            tree.root.expand()

        for p in sorted(set(self.api.players.values()), key=lambda p: p.name):
            player_table.add_player(p)

        logging.info(f"Players: {len(self.api.cache['players'])}")

        ratings: DataTable = self.query_one("DataTable#ratings")
        ratings.clear()
        for c in sorted(self.api.competitions.values(), key=lambda c: c.name):
            for c_sub in c.sub:
                calculated = self.api.cache['ratings'].get(c_sub.id, None)
                rating_par = self.api.cache['ratings_info'].get(c_sub.id, {}).get("rating_par", None)
                propagators = self.api.cache['ratings_info'].get(c_sub.id, {}).get("rating_propagators", None)
                rating_per_stroke = self.api.cache['ratings_info'].get(c_sub.id, {}).get("rating_per_stroke", None)
                ratings.add_row(c_sub.id, " ".join(c_sub.name.split("&rarr;")),
                                "[red]NA[/]" if calculated is None else f"[green]{rating_par}[/]", rating_per_stroke, propagators)

    def on_mount(self) -> None:
        self.repopulate()

    def compose(self) -> ComposeResult:
        with TabbedContent(id="content", initial="players"):
            with TabPane("Players", id="players"):
                yield PlayersWidget(id="players")
            with TabPane("Competitions", id="competitions"):
                yield CompetitionsTree("Competitions", id="competitions")
            with TabPane("Ratings", id="ratings"):
                yield RatingsWidget(id="ratings")
            # with TabPane("DGW", id="dgw"):
            #     yield DGWWidget(self.api, self.config, id="dgw")
            with TabPane("Log", id="log"):
                log = RichLog(id="llog")
                logging.basicConfig(level=logging.INFO, handlers=[LogWidgetHandler(widget=log)])
                yield log

        yield Footer()

    # def action_switch_content(self, content_id: str):
    #     cs = self.query_one("ContentSwitcher")
    #     cs.current = content_id

    # def on_button_pressed(self, event: Button.Pressed):
    #     self.query_one("ContentSwitcher").current = event.button.id

    @textual.on(TabbedContent.TabActivated, "#content")
    def tab_activated(self, event: TabbedContent.TabActivated):
        event.pane.children[0].focus()
        #event.tab.children[0].focus()

    def action_quit(self) -> None:
        self.push_screen(ConfirmModal("Save before quitting?", cancel=True), self.save_on_quit )

    def save_on_quit(self, save: bool):
        if save:
            self.action_save()
        if save is not None:
            self.exit()

    def action_save(self):
        self.api.save_cache()
        self.notify(f"Cache saved [{self.api._cache_file}]")
        logging.info(f"Cache saved [{self.api._cache_file}]")


    def action_repopulate(self):
        self.api.load_cache()
        self.push_screen(ConfirmModal("Save and repopulate widgets?"), self.repopulate_on_confirm)

    def repopulate_on_confirm(self, repopulate: bool):
        if repopulate:
            self.api.save_cache()
            self.api.load_cache()
            self.repopulate()
            self.notify(f"Cache saved and reloaded [{self.api._cache_file}]")
            logging.info(f"Cache reloaded [{self.api._cache_file}]")


def main(args):
    app = CacheEditorApp(args)
    app.run()


if __name__ == "__main__":
    import argparse
    import os

    argparser = argparse.ArgumentParser()
    argparser.add_argument('--config', '-c', type=str,
                           default=os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                'config.yaml'))
    argparser.add_argument('--cache-file', type=str,
                           default=os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                'results.cache.pkl')
                           )
    main(argparser.parse_args())
