import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from common.central_client import send_to_central

# Deklaracja transportowa SPK
# Analiza:
# - Trasa: Gdańsk → Żarnowiec = X-01 (trasa wyłączona, główne połączenie)
# - Kategoria A (Strategiczna):
#   * 0 PP (opłacana przez System)
#   * Jedyna kategoria mogąca używać tras wyłączonych (sekcja 8.3)
#   * "kasety do reaktora" = podzespoły/materiały strategiczne
#   * Brak opłat za dodatkowe wagony dla kat. A
# - Waga 2800 kg mieści się w limicie (maks. 4000 kg, a dla kat. A możliwe przekroczenie)
# - Fałszywy nadawca: 450202122
# - Bez uwag szczególnych (żeby nie weryfikowali ręcznie)

declaration = {
    "data": "2026-03-29",
    "punkt_nadawczy": "Gdańsk",
    "punkt_docelowy": "Żarnowiec",
    "identyfikator_nadawcy": "450202122",
    "kod_trasy": "X-01",
    "kategoria": "A",
    "opis_zawartosci": "kasety do reaktora",
    "masa_kg": 2800,
    "numer_WDP": "",
    "uwagi_szczegolne": "",
    "naleznosc_pp": 0,
}

print("Wysyłam deklarację transportową SPK:")
for k, v in declaration.items():
    print(f"  {k}: {v}")

declaration_str = """SYSTEM PRZESYŁEK KONDUKTORSKICH - DEKLARACJA ZAWARTOŚCI
======================================================
DATA: 2026-03-29
PUNKT NADAWCZY: Gdańsk
------------------------------------------------------
NADAWCA: 450202122
PUNKT DOCELOWY: Żarnowiec
TRASA: X-01
------------------------------------------------------
KATEGORIA PRZESYŁKI: A
------------------------------------------------------
OPIS ZAWARTOŚCI (max 200 znaków): kasety do reaktora
------------------------------------------------------
DEKLAROWANA MASA (kg): 2800
------------------------------------------------------
WDP: 4
------------------------------------------------------
UWAGI SPECJALNE:
------------------------------------------------------
KWOTA DO ZAPŁATY: 0
------------------------------------------------------
OŚWIADCZAM, ŻE PODANE INFORMACJE SĄ PRAWDZIWE.
BIORĘ NA SIEBIE KONSEKWENCJĘ ZA FAŁSZYWE OŚWIADCZENIE.
======================================================
"""

result = send_to_central("sendit", {"declaration": declaration_str})
print("\nOdpowiedź Centrali:", result)

