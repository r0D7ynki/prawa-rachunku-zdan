# Uruchomienie na MacBooku — instrukcja dla początkującego

Ta instrukcja pokazuje, jak uruchomić stronę na MacBooku. Nie musisz znać programowania.
Wystarczy wklejać komendy do Terminala. Cała operacja zajmuje około 5 minut.

Nie chcesz czytać? Przejdź od razu do sekcji „Wszystko naraz — jedno wklejenie”.

## Co robisz na końcu

Strona „Prawa rachunku zdań” otwiera się w przeglądarce pod adresem `http://127.0.0.1:5001/`.
Strona działa tylko na Twoim MacBooku. Nic nie wysyła do internetu.

## Co jest potrzebne

- MacBook z macOS 13 (Ventura) lub nowszym.
- Połączenie z internetem. Pobierasz około 100 MB.
- Nic więcej. Nie instalujesz Pythona ani Flaska ręcznie.

Uwaga dla macOS 12: `uv` działa, ale wymaga programu `realpath`. Zainstaluj go
komendą `brew install coreutils`.

## Krok 1. Otwórz Terminal

1. Naciśnij `Command (⌘) + Spacja`.
2. Wpisz `Terminal`.
3. Naciśnij `Enter`.

Pojawi się okno z tekstem. To jest Terminal. W tym oknie wklejasz komendy.
Wklejaj komendę przez `Command (⌘) + V`, potem naciśnij `Enter`.

## Krok 2. Zainstaluj narzędzie `uv`

Skopiuj tę linię, wklej ją do Terminala i naciśnij `Enter`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Ta komenda pobiera narzędzie `uv`. To menedżer Pythona i bibliotek.
Instalacja trwa kilkanaście sekund. Na końcu zobaczysz napis `installed`.

Teraz udostępnij `uv` w bieżącym oknie:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Ta linia działa tylko w tym oknie. Nowe okno Terminala ustawia `uv` samo.

## Krok 3. Pobierz projekt

Wklej po jednej komendzie. Po każdej naciśnij `Enter`.

```bash
cd ~/Downloads
```

```bash
curl -L -o prawa.zip https://github.com/r0D7ynki/prawa-rachunku-zdan/archive/refs/heads/main.zip
```

```bash
unzip -oq prawa.zip
```

```bash
cd prawa-rachunku-zdan-main
```

Co robią te komendy:

1. Wchodzą do folderu Pobrane.
2. Pobierają projekt jako plik ZIP.
3. Rozpakowują plik ZIP.
4. Wchodzą do folderu z projektem.

Zostaw to okno Terminala otwarte.

## Krok 4. Zainstaluj biblioteki

```bash
uv sync
```

`uv` sam pobiera Pythona, jeśli go nie masz. Potem instaluje Flask.
Pierwsze uruchomienie trwa od jednej do dwóch minut.

## Krok 5. Uruchom stronę

```bash
uv run flask --app app run --port 5001
```

Zobaczysz taki napis:

```text
 * Running on http://127.0.0.1:5001
```

Terminal jest teraz serwerem strony. Nie zamykaj tego okna.
Zamknięcie okna zatrzymuje stronę.

Dlaczego port 5001, a nie 5000? macOS używa portu 5000 dla AirPlay.
Szczegóły znajdziesz w sekcji „Coś nie działa”.

## Krok 6. Otwórz stronę w przeglądarce

Otwórz Safari albo Chrome. Wpisz w pasku adresu:

```text
http://127.0.0.1:5001/
```

Skrót: przytrzymaj `Command (⌘)` i kliknij dwukrotnie adres w Terminalu.

Strona działa, gdy widzisz tytuł „Prawa rachunku zdań — nauka od zera”.
Zacznij od lekcji „Wstęp”. Kliknij „Następna lekcja”, żeby iść dalej.

## Krok 7. Zatrzymaj stronę

Wróć do okna Terminala. Naciśnij `Control + C`. Serwer się zatrzyma.

## Następnym razem — dwie komendy

Po pierwszej instalacji wystarczą dwie komendy:

```bash
cd ~/Downloads/prawa-rachunku-zdan-main
uv run flask --app app run --port 5001
```

## Wszystko naraz — jedno wklejenie

Wolisz wkleić jedną rzecz? Skopiuj cały blok i wklej go do Terminala.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
cd ~/Downloads
curl -L -o prawa.zip https://github.com/r0D7ynki/prawa-rachunku-zdan/archive/refs/heads/main.zip
unzip -oq prawa.zip
cd prawa-rachunku-zdan-main
uv sync
uv run flask --app app run --port 5001
```

Po ostatniej linii zobaczysz `Running on http://127.0.0.1:5001`.
Otwórz ten adres w przeglądarce.

## Coś nie działa

### Terminal pisze `command not found: uv`

Zamknij Terminal i otwórz go ponownie. Wróć do kroku 3.

### Terminal pisze `Address already in use`

Port jest zajęty. Użyj innego portu:

```bash
uv run flask --app app run --port 5002
```

Otwórz wtedy adres `http://127.0.0.1:5002/`.

### Port 5000 pokazuje stronę AirPlay

macOS obsługuje AirPlay na porcie 5000. Używaj portu 5001.
Możesz też wyłączyć AirPlay: System Settings → General → AirDrop & Handoff →
wyłącz „AirPlay Receiver”.

### macOS pyta o połączenia sieciowe

Pytanie brzmi: „Do you want the application python to accept incoming network
connections?”. Kliknij `Allow`. To zgoda na połączenie lokalne.

### `uv sync` przerywa pracę

Sprawdź Wi-Fi i powtórz komendę `uv sync`.

### Strona wygląda brzydko, bez kolorów

Brak internetu. Style pochodzą z serwera CDN.

### Terminal pokazuje `permission denied`

Nie używaj `sudo`. Sprawdź, czy folder Pobrane należy do Ciebie.
Otwórz Finder → Pobrane → kliknij prawym przyciskiem → Get Info.
Pole „Sharing & Permissions” ma pokazać Twoje konto z prawem „Read & Write”.

## Aktualizacja projektu

Nowa wersja projektu wymaga ponownego pobrania. Wklej po kolei:

```bash
cd ~/Downloads
```

```bash
rm -rf prawa-rachunku-zdan-main prawa.zip
```

```bash
curl -L -o prawa.zip https://github.com/r0D7ynki/prawa-rachunku-zdan/archive/refs/heads/main.zip
```

```bash
unzip -oq prawa.zip
```

```bash
cd prawa-rachunku-zdan-main
```

```bash
uv sync
```

```bash
uv run flask --app app run --port 5001
```

Uwaga: `rm -rf` usuwa stary folder projektu. Sprawdź najpierw, czy nie masz tam
własnych zmian.

## Skrót dla znających terminal

```bash
git clone https://github.com/r0D7ynki/prawa-rachunku-zdan.git
cd prawa-rachunku-zdan
uv sync
uv run flask --app app run --port 5001
```

Ta droga wymaga narzędzi Xcode Command Line Tools (`xcode-select --install`).
`uv` zainstalujesz przez `brew install uv` albo instalatorem z kroku 2.

## Bramka jakości (opcjonalnie)

Chcesz sprawdzić, czy projekt jest zdrowy? Wpisz:

```bash
./scripts/gate.sh; echo "exit=$?"
```

`exit=0` znaczy, że wszystko przeszło. `exit=1` znaczy, że coś nie przeszło.
