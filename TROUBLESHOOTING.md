# Troubleshooting Guide

## Segmentation Fault przy starcie pluginu

### Problem
```
Fatal Python error: Segmentation fault
  File "/usr/lib/python3.9/asyncio/events.py", line 786 in <module>
```

### Przyczyna
Konflikt między różnymi wersjami bibliotek Modbus:
- **T-Cap plugin** używa `pyModbusTCP` (działa poprawnie)
- **Sofar-modbus plugin** (lub inny) używa `pymodbus` wersja 3.x
- `pymodbus 3.x` używa `asyncio`, co nie jest kompatybilne z modelem wątkowania Domoticza

### Rozwiązanie

#### Krok 1: Sprawdź wersje zainstalowanych bibliotek

```bash
pip3 list | grep -i modbus
```

Powinieneś zobaczyć coś takiego:
```
minimalmodbus    2.1.1
pyModbusTCP      0.2.0
pymodbus         3.x.x    # <-- To powoduje problem!
```

#### Krok 2: Opcje naprawy

**Opcja A: Downgrade pymodbus do wersji 2.x (zalecane)**

Pymodbus 2.x nie używa asyncio i jest kompatybilny z Domoticzem:

```bash
# Usuń aktualną wersję
sudo pip3 uninstall pymodbus

# Zainstaluj wersję 2.5.3 (ostatnia stabilna bez asyncio)
sudo pip3 install pymodbus==2.5.3
```

**Opcja B: Użyj osobnych środowisk wirtualnych**

Jeśli potrzebujesz różnych wersji dla różnych pluginów:

```bash
# Dla każdego pluginu stwórz osobne venv
python3 -m venv /opt/domoticz/userdata/plugins/T-Cap/venv
python3 -m venv /opt/domoticz/userdata/plugins/Sofar-modbus/venv

# Instaluj odpowiednie zależności w każdym venv
```

**Opcja C: Wyłącz konfliktujący plugin**

Jeśli nie potrzebujesz Sofar-modbus:

```bash
# Wyłącz plugin w Domoticz
# Lub usuń/przenieś katalog pluginu
mv /opt/domoticz/userdata/plugins/Sofar-modbus /opt/domoticz/userdata/plugins/Sofar-modbus.disabled
```

#### Krok 3: Zrestartuj Domoticz

```bash
sudo systemctl restart domoticz
```

#### Krok 4: Sprawdź logi

```bash
tail -f /opt/domoticz/domoticz.log | grep -i "t-cap\|sofar\|modbus"
```

### Weryfikacja poprawności

Po naprawie powinieneś zobaczyć w logach:

```
T-Cap: Initialized version 0.9
T-Cap: TCP Modbus configured: 10.0.20.6:502
T-Cap: Loading sensors and settings from config.yaml
T-Cap: Panasonic-IntesisBox-Modbus plugin start
```

**BEZ** błędów segmentation fault.

### Dlaczego to się stało?

- Domoticz uruchamia pluginy w osobnych wątkach (threads)
- Python asyncio ma problemy z inicjalizacją w środowisku wielowątkowym
- Starsze wersje pymodbus (2.x) nie używały asyncio → działały
- Nowsze wersje pymodbus (3.x+) używają asyncio → crash

### Zalecenia

1. **Dla T-Cap plugin**: Używaj `pyModbusTCP` (już tak jest)
2. **Dla innych pluginów**: Sprawdź czy mogą używać `pyModbusTCP` zamiast `pymodbus 3.x`
3. **Ogólnie**: W środowisku Domoticz unikaj bibliotek wymagających asyncio

## Dodatkowe problemy

### Plugin nie łączy się z urządzeniem

Sprawdź:
1. Adres IP i port w konfiguracji pluginu
2. Czy urządzenie odpowiada: `telnet 10.0.20.6 502`
3. Timeout w konfiguracji (zwiększ jeśli potrzeba)

### Urządzenia nie są tworzone

Sprawdź:
1. Czy plik `config.yaml` istnieje w katalogu pluginu
2. Czy plik ma poprawną składnię YAML
3. Logi Domoticza pod kątem błędów parsowania

### Błędy "Update failure"

To normalne przy przejściowych problemach sieciowych. Plugin automatycznie:
- Powtarza operacje (retry with backoff)
- Exponential backoff: 0.5s → 1s → 2s
- Maksymalnie 3 próby

Jeśli występują często:
1. Zwiększ timeout w konfiguracji
2. Sprawdź stabilność sieci
3. Sprawdź obciążenie urządzenia Modbus
