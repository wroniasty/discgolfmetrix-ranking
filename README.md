## DiscGolfMetrix rankings

This utility generates disc golf rankings based on competition results retrieved from discgolfmetrix.com.

### Zimowy Puchar DGW

Żeby wygenerować nowy ranking w stylu Zimowej Ligi DGW:
 - zainstaluj w miarę nową wersję Pythona,
 - sklonuj to repozytorium,
 - zainstaluj wymagane biblioteki z ``requirements.txt``,
 - dodaj nową pozycję do pliku "config.yaml" pod kluczem **leagues** (np. DGW2024),
 - w polu "competition_ids" podaj identyfikatory zawodów, które mają być brane pod uwagę podczas generowania rankingu (pamiętaj by dodać główny identyfikator zawodów, a nie identyfikatory poszczególnych rund),
 - uruchom polecenie ``python3 main.py -l <dodany klucz, np DGW2024>``,
 - jeżeli polecenie uruchomi się pomyślnie - w aktualnym katalogu powstanie plik DGW2024.ranking.html.

#### Wyjściowy plik HTML

Wygenerowany plik jest dość duży. Jego rozmiar rośnie liniowo wraz z liczbą zawodników i zawodów składających się na ranking (plik z sezonu 2021/22 ma około 1.2MB). Jego zaletą jest prawie całkowita przenośność - można go zapisać na dysku, przesłać mailem, lub umieścić na dowolnej stronie www i powinien się otworzyć bez żadnych dodatkowych wymagań.


