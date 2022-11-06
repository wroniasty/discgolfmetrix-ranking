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


## License

MIT License

Copyright (c) 2022 Jakub Wroniecki

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
``
