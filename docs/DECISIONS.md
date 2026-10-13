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
| D11 | 2026-10-13 | Reviewer to skrypt `scripts/reviewer-agy.sh` wołający `agy --model claude-sonnet-4-6 --mode plan --sandbox` | swarmboard podaje prompt reviewera na standardowe wejście, a `agy -p` wymaga promptu w argumencie. Skrypt łączy oba sposoby. Tryb `plan` i `--sandbox` dają przegląd bez zmiany plików. |
| D12 | 2026-10-13 | Workery to Claude Code CLI wskazany na API DeepSeek (`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`, `ANTHROPIC_MODEL=deepseek-flash`) | Decyzja właściciela: kod pisze DeepSeek V4.1 Flash. Claude Code daje workerowi edycję plików, uruchamianie testów i `git commit` w worktree. Klucz API wyłącznie przez `env_files`, nigdy w argumencie. |
| D13 | 2026-10-13 | `CLAUDE_CODE_MAX_CONTEXT_TOKENS=1048576` w środowisku workera | Claude Code nie zna modelu `deepseek-flash` i domyślnie zakłada okno 200k. Model ma 1M tokenów, więc bez tej zmiennej sesja kompaktuje się za wcześnie. |
| D14 | 2026-10-13 | Numeracja i wzory praw **z wykładu** („Logika pragmatyczna”, PWr, T1–T14) | Właściciel zdaje ten kurs. Numeracja podręcznikowa różni się od wykładowej: na wykładzie I prawo de Morgana dotyczy `∨`, a I prawo rozdzielności ma postać `((p∨q)∧r) ≡ ((p∧r)∨(q∧r))`. Zgodność z wykładem ma pierwszeństwo. |
| D15 | 2026-10-13 | Główna notacja: `∼`, `≡`, wartości `1`/`0`; notacja `¬`, `↔` tylko obok | Wykład i test pisemny używają `∼` i `≡`. Parser przyjmuje oba zapisy, ale strona pokazuje najpierw wykładowy. |
| D16 | 2026-10-13 | „Prawo zastępowania równ.” to z wykładu `(p ≡ q) ≡ ((p → q) ∧ (q → p))` | Tak definiuje je wykład (T12). Reguła podstawiania formuł do tautologii to osobne, dodatkowe prawo na stronie `/przeksztalcanie`. |
| D17 | 2026-10-13 | Dodatkowe prawa (idempotencja, podstawianie) poza listą T1–T14 | Wykład używa `(q ∨ q) ≡ q` w przykładzie upraszczania. Strona oznacza je jako „prawa dodatkowe”, żeby nie mylić numeracji T1–T14. |
| D18 | 2026-10-13 | Strony kursu `/wstep`, `/formuly`, `/tautologie`, `/przeksztalcanie`, `/kpn` odwzorowują kolejność slajdów wykładu 1 | Student przechodzi materiał w kolejności wykładu. Strona `/prawa` zostaje jako ściągawka z 14 prawami. |
| D19 | 2026-10-13 | Reviewer próbuje modeli po kolei: `claude-sonnet-4-6`, potem `gemini-3.8-flash-high` (oba przez `agy`) | Antigravity ma osobne okna limitu dla „Claude/GPT” i „Gemini”. Gdy jedno się kończy, przegląd idzie dalej drugim modelem. Reviewer zawsze pochodzi z innego modelu niż wykonawca (DeepSeek). |
| D20 | 2026-10-13 | Limit WIP kolumny `review` podniesiony do 30 | Limit Antigravity na modele Claude wyczerpał się po 6 przeglądach (reset po ~4,5 h). Karty mają czekać w `review` na przegląd, a rój ma dalej pisać kod. Przeglądy wznawiamy po odnowieniu limitu (`sb review <ID>`). |
| D21 | 2026-10-13 | Wrapper reviewera dodaje do promptu zasady oszczędzania limitu (maks. 40 linii, tylko karta i diff) | Każdy przegląd zużywa okno 5-godzinne. Krótsza odpowiedź i węższy zakres czytania pozwalają wykonać więcej przeglądów w jednym oknie. |
