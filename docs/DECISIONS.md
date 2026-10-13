# Rejestr decyzji

Wpis: numer, data, decyzja, powód. Nowy wpis na końcu.

| # | Data | Decyzja | Powód |
|---|---|---|---|
| D1 | 2026-10-13 | Stos: Flask + Bootstrap 5 z CDN, bez kroku budowania frontendu | Trzy agenty piszą kod równolegle. Brak `npm` i `node_modules` usuwa całą klasę konfliktów i awarii bramki. Wybór właściciela: „python + flask + bootstrap”. |
| D2 | 2026-10-13 | Silnik logiki w Pythonie, ten sam kod obsługuje strony i API | Jedno źródło prawdy. Testy `pytest` sprawdzają logikę bez przeglądarki, więc bramka QA roju jest szybka i pewna. |
| D3 | 2026-10-13 | `app/__init__.py` sam znajduje widoki w `app/blueprints/` | Karty nie edytują wspólnego pliku, więc równoległa praca nie daje konfliktów scalenia. |
| D4 | 2026-10-13 | `laws.py` sam znajduje treść w `app/logic/laws_data/` | Treść 14 praw dzielimy na pliki. Trzy karty piszą treść równolegle, każda w swoim pliku. |
| D5 | 2026-10-13 | Odnośniki w menu jako zwykłe ścieżki, nie `url_for` | Strona nie zwraca błędu 500, gdy widok jeszcze nie istnieje. Karty wchodzą niezależnie. |
| D6 | 2026-10-13 | Partiale `_truth_table.html`, `_gates.html`, `_sets.html`, `_steps.html` istnieją od początku jako zaślepki | Strona praw może ich używać, zanim karty komponentów się scalą. |
| D7 | 2026-10-13 | Limit rozmiaru karty dla modelu `deepseek`: `L` (domyślnie `M`) | Karty `L` są potrzebne, a reviewer Claude sprawdza każdą kartę niezależnie. DoR wymaga wtedy pełnej listy plików i kryteriów sprawdzalnych testem. |
| D8 | 2026-10-13 | Reviewer: `agy -p --model claude-sonnet-4-6` (Antigravity), wykonawca: `deepseek-flash` | Decyzja właściciela. Reviewer zawsze innym modelem niż wykonawca karty. |
| D9 | 2026-10-13 | Bez skanera `gitleaks` w bramce QA (`secret_scan: auto`) | `gitleaks` nie jest zainstalowany. Brak narzędzia pomija skan z ostrzeżeniem, nie blokuje roju. Nie dodajemy zależności bez decyzji właściciela. |
| D10 | 2026-10-13 | Wersja strony tylko po polsku | Materiał na studia w języku polskim. Słowniki i18n to zakres poza tym projektem. |
