# Podsumowanie Prac nad Projektem StatsMods Tarkov (MVP)

## Cel Główny Projektu

Stworzenie aplikacji webowej (MVP) do śledzenia i wyświetlania szczegółowych statystyk z rajdów w grze Escape from Tarkov, wykorzystując dane przesyłane przez mod serwerowy SPT (`mod.js`) i tłumaczenia z pliku `pl.json`.

---

## Dotychczasowe Osiągnięcia i Kluczowe Elementy

### Mod Serwerowy (`mod.js`)

- Bazowano na stabilnej wersji istniejącego moda.
- Wprowadzono minimalne modyfikacje (HTTP zamiast HTTPS, obsługa logowania).
- Mod przechwytuje zdarzenia rozpoczęcia i zakończenia rajdu, zbierając pełne dane profilu gracza w formacie JSON.
- Dane JSON są wysyłane na dedykowane endpointy API serwera Flask.

### Aplikacja Backendowa Flask (`mvp.app.py`)

#### Strategia Przechowywania Danych

- Całkowita rezygnacja z CSV.
- Dane przechowywane wyłącznie w plikach JSON.

#### Zapis Pełnych Danych Rajdów

- Endpointy `/api/raid/start` i `/api/raid/end` odbierają dane JSON z moda.
- Dane zapisywane jako osobne pliki w strukturze:
- Możliwość ignorowania zapisu dla wybranych graczy (lista `IGNORED_PLAYER_NICKNAMES`).

#### Dynamiczne Przetwarzanie Danych

- Funkcja `get_or_refresh_data_cache()`:
- Skanuje katalogi z plikami `_end.json`.
- Buduje cache:
  - `all_raids_summary`: skrócone podsumowania wszystkich rajdów.
  - `players_summary`: statystyki zagregowane per gracz (K/D, SR itp.).

#### Obsługa Szablonów HTML

- Endpointy `/`, `/players`, `/player/<nickname>`:
- Zasilane z `RAID_DATA_CACHE`.
- Korzystają z szablonów Jinja2: `index.html`, `gracze.html`, `profil.html`.

- Strona profilu:
- Sekcje **Umiejętności** i **Osiągnięcia** wypełniane z ostatniego pliku JSON danego gracza.

#### API dla Modala "Szczegóły Rajdu"

- Endpoint `/api/raid_json_details?path=<relative_path>`:
- Parsuje dane z pełnego JSON-a:
  - Ofiary, zabójca, SessionCounters, zdrowie, umiejętności, zadania, osiągnięcia, przedmioty.
- Zwraca obiekt JSON z gotowymi danymi do modala.

#### Tłumaczenia

- Aplikacja ładuje słownik tłumaczeń z `translate/pl.json`.

#### Funkcje Pomocnicze

- Formatowanie dat, czasów, XP, dystansów.
- Parsowanie struktur JSON.

---

## Szablony HTML

### `profil.html`

- Skrypt JS dostosowany do `/api/raid_json_details`.
- Używa `data-jsonpath-relative` do wskazania konkretnego rajdu.

### `index.html`, `gracze.html`

- Dane pochodzą z `RAID_DATA_CACHE`.

---

## Aktualny Status

- Aplikacja poprawnie zapisuje dane rajdów jako JSON.
- Strony główne i profil gracza działają na danych z cache.
- Modal "Szczegóły Rajdu" działa poprawnie i wczytuje dane bezpośrednio z JSON.
- Błąd _"Object reference not set to an instance of an object"_ rozwiązany przez użycie stabilnej wersji `mod.js`.
- **Problem z rozjeżdżaniem się CSV został wyeliminowany przez całkowitą rezygnację z CSV jako głównego nośnika danych na rzecz plików JSON.**

## 🖼️ Zrzuty ekranu (StatsMod)

Poniżej zrzuty ekranu z działania moda oraz interfejsu:

| Podgląd
|--------
| ![Zrzut 1](https://raw.githubusercontent.com/kybeq/StatsModSPTarkov/main/produkt/Zrzut%20ekranu%202025-05-04%20161620.png)
| ![Zrzut 2](https://raw.githubusercontent.com/kybeq/StatsModSPTarkov/main/produkt/Zrzut%20ekranu%202025-05-04%20161702.png)
| ![Zrzut 3](https://raw.githubusercontent.com/kybeq/StatsModSPTarkov/main/produkt/Zrzut%20ekranu%202025-05-04%20161718.png)
| ![Zrzut 4](https://raw.githubusercontent.com/kybeq/StatsModSPTarkov/main/produkt/Zrzut%20ekranu%202025-05-04%20161727.png)

## 🚀 Jak uruchomić

```bash
# Zainstaluj zależności
pip install flask

# Uruchom aplikację
python app.py
```
