# 🧠 Flask Stats Collector for SPT-AKI

Aplikacja backendowa oparta na **Flask**, służąca do odbierania i analizowania danych JSON generowanych przez **mod do gry SPT-AKI**.

## 🔧 Obecna funkcjonalność

- Odbieranie plików `.json` zawierających dane z rozgrywek
- Ręczne wgrywanie plików do folderu `debug_logs/` z rajdów w plikach `.json` w debug_logs w mod StatsMods
- Parsowanie i wstępna obróbka danych

## 📦 Struktura projektu


## 🧩 Mod: StatsMod

- Znajduje się w folderze `StatsMod`
- Wgrywany do: `SPT/user/mods/StatsMod`
- Automatycznie zapisuje dane z rajdów w plikach `.json` w debug_logs
- W przyszłości będzie wysyłał dane do serwera Flask (automatyczny `POST`)

## 🖼️ Zrzuty ekranu (StatsMod)

Poniżej zrzuty ekranu z działania moda oraz interfejsu:

| Podgląd | Opis |
|--------|------|
| ![screen1](./StatsModSPTarkov/Zrzut%20ekranu%202025-05-04%20161620.png) | Przykładowy ekran rajdu |
| ![screen2](./StatsModSPTarkov/Zrzut%20ekranu%202025-05-04%20161702.png) | Szczegółowe statystyki gracza |
| ![screen3](./StatsModSPTarkov/Zrzut%20ekranu%202025-05-04%20161718.png) | Statystyki wyciągnięte z rajdu |
| ![screen4](./StatsModSPTarkov/Zrzut%20ekranu%202025-05-04%20161727.png) | Interfejs moda z przykładowym zapisem |

## 🔮 Planowane funkcje

- Automatyczne wysyłanie danych z `StatsMod` do backendu (`POST`)
- API REST + prosty frontend HTML do przeglądania statystyk
- Wyszukiwanie po dacie, ID rajdu, uzbrojeniu, frakcji itd.
- Eksport danych do CSV
- Generowanie wykresów (np. kill ratio, czas przeżycia)

## 🚀 Jak uruchomić

```bash
# Zainstaluj zależności
pip install flask

# Uruchom aplikację
python app.py
