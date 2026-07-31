"""Tests de conformité légale des barèmes (Art. L.412-1, Art. L.415-5).

Source : brochure LCGB « Délégations du personnel », édition 10/2023,
reprenant le Code du travail luxembourgeois.

Ces tests servent de pièce justificative de conformité — ils sont
rédigés pour être lisibles par un auditeur non-développeur.
"""

import pytest
from app.models.organization import Organization


# ═══════════════════════════════════════════════════════════════════
# required_titulaires — Art. L.412-1 (brochure LCGB 10/2023)
# ═══════════════════════════════════════════════════════════════════

TITULAIRES_TRANCHES = [
    # (effectif_min, effectif_max, attendu)
    (15, 25, 1),
    (26, 50, 2),
    (51, 75, 3),
    (76, 100, 4),
    (101, 200, 5),
    (201, 300, 6),
    (301, 400, 7),
    (401, 500, 8),
    (501, 600, 9),
    (601, 700, 10),
    (701, 800, 11),
    (801, 900, 12),
    (901, 1000, 13),
    (1001, 1100, 14),
    (1101, 1500, 15),
    (1501, 1900, 16),
    (1901, 2300, 17),
    (2301, 2700, 18),
    (2701, 3100, 19),
    (3101, 3500, 20),
    (3501, 3900, 21),
    (3901, 4300, 22),
    (4301, 4700, 23),
    (4701, 5100, 24),
    (5101, 5500, 25),
]


def _build_titulaires_cases():
    """Construit les cas de test : borne inférieure ET borne supérieure de chaque tranche."""
    cases = []
    for low, high, expected in TITULAIRES_TRANCHES:
        cases.append((low, expected, f"tranche {low}-{high}, borne basse ({low})"))
        cases.append((high, expected, f"tranche {low}-{high}, borne haute ({high})"))
    return cases


TITULAIRES_AU_DELA_5500 = [
    # n=5500 n'est pas « au-delà », il tombe dans la 25e tranche 5101-5500
    # Au-delà : +1 titulaire par tranche ENTIÈRE de 500 (arrondi INFÉRIEUR).
    (5500, 25, "seuil exact — 5500 salariés, dernière tranche standard"),
    (5501, 25, "5501 salariés, tranche incomplète → 0 tranche entière de 500 → 25"),
    (5999, 25, "5999 salariés, 499 dans la première tranche de 500 → pas une tranche entière"),
    (6000, 26, "6000 salariés, 1 tranche entière de 500 → 25 + 1 = 26"),
    (6001, 26, "6001 salariés, 1 tranche entière de 500 → 25 + 1 = 26"),
    (6500, 27, "6500 salariés, 2 tranches entières de 500 → 25 + 2 = 27"),
]


class TestRequiredTitulaires:
    """Vérifie le nombre de délégués titulaires requis selon l'Art. L.412-1.

    Source : brochure LCGB « Délégations du personnel », édition 10/2023,
    tableau p. 5-6, reprenant les art. L.412-1 et suivants du Code du travail.
    """

    @pytest.mark.parametrize(
        "n,expected,description",
        _build_titulaires_cases(),
    )
    def test_tranche_couverture_bornes(self, n, expected, description):
        """Chaque tranche légale : les DEUX bornes retournent le bon nombre de titulaires."""
        org = Organization(employee_count=n)
        assert org.required_titulaires == expected, (
            f"{description}: attendu {expected}, obtenu {org.required_titulaires}"
        )

    @pytest.mark.parametrize(
        "n,expected,description",
        TITULAIRES_AU_DELA_5500,
    )
    def test_au_dela_5500_tranche_entiere(self, n, expected, description):
        """Au-delà de 5500 : +1 par tranche ENTIÈRE de 500 (arrondi inférieur).

        Texte officiel : « 1 membre titulaire supplémentaire par tranche
        ENTIÈRE de 500 salariés, lorsque l'effectif des salariés excède 5.500. »
        """
        org = Organization(employee_count=n)
        assert org.required_titulaires == expected, (
            f"{description}: attendu {expected}, obtenu {org.required_titulaires}"
        )


# ═══════════════════════════════════════════════════════════════════
# weekly_credit_hours — Art. L.415-5 (brochure LCGB 10/2023, p. 14)
# ═══════════════════════════════════════════════════════════════════

# Table < 150 salariés : formule (40 × n) / 500, arrondi arithmétique
HEURES_MOINS_150 = [
    (15, 1),
    (20, 2),
    (40, 3),
    (60, 5),
    (80, 6),
    (100, 8),
    (120, 10),
    (140, 11),
    (149, 12),
]

# Table 150–249 salariés : formule (40 × n) / 250, arrondi arithmétique
HEURES_150_A_249 = [
    (150, 24),
    (160, 26),
    (180, 29),
    (200, 32),
    (220, 35),
    (240, 38),
    (249, 40),
]

# À partir de 250 salariés : délégués libérés, pas de crédit horaire
HEURES_250_PLUS = [250, 500, 5000]


class TestWeeklyCreditHours:
    """Vérifie le crédit d'heures hebdomadaire selon l'Art. L.415-5.

    Source : brochure LCGB « Délégations du personnel », édition 10/2023,
    tableau p. 14, reprenant l'art. L.415-5 du Code du travail.
    """

    @pytest.mark.parametrize("n,expected", HEURES_MOINS_150)
    def test_moins_de_150_salaries(self, n, expected):
        """Entreprises < 150 salariés : crédit = (40 × n) / 500."""
        org = Organization(employee_count=n)
        assert org.weekly_credit_hours == expected, (
            f"n={n}: attendu {expected}h, obtenu {org.weekly_credit_hours}h"
        )

    @pytest.mark.parametrize("n,expected", HEURES_150_A_249)
    def test_150_a_249_salaries(self, n, expected):
        """Entreprises 150–249 salariés : crédit = (40 × n) / 250."""
        org = Organization(employee_count=n)
        assert org.weekly_credit_hours == expected, (
            f"n={n}: attendu {expected}h, obtenu {org.weekly_credit_hours}h"
        )

    def test_transition_149_vers_150(self):
        """149 salariés → 12h (formule /500), 150 salariés → 24h (formule /250).

        Le saut est voulu par la loi : à 150 salariés, le dénominateur
        change de 500 à 250, doublant le crédit. Ce test documente
        explicitement cette discontinuité légale.
        """
        org_149 = Organization(employee_count=149)
        org_150 = Organization(employee_count=150)
        assert org_149.weekly_credit_hours == 12
        assert org_150.weekly_credit_hours == 24

    @pytest.mark.parametrize("n", HEURES_250_PLUS)
    def test_250_et_plus_delegues_liberes(self, n):
        """À partir de 250 salariés : délégués libérés → crédit horaire None.

        Art. L.415-5(2) : pas de crédit d'heures pour les délégués
        libérés à temps plein.
        """
        org = Organization(employee_count=n)
        assert org.weekly_credit_hours is None, (
            f"n={n}: attendu None (délégués libérés), obtenu {org.weekly_credit_hours}"
        )


# ═══════════════════════════════════════════════════════════════════
# Arrondi légal — Art. L.415-5 (brochure LCGB 10/2023, p. 14)
# ═══════════════════════════════════════════════════════════════════

class TestArrondiLegal:
    """Documente le comportement de l'arrondi arithmétique obligatoire.

    La loi (Art. L.415-5) impose : « les fractions d'heure égales ou
    supérieures à la demie sont arrondies à l'unité supérieure, les
    fractions inférieures à la demie à l'unité inférieure. »

    Python utilise banker's rounding (arrondi au pair) : round(2.5)=2,
    round(3.5)=4. Le code compense par un +0.001 qui décale les valeurs
    juste au-dessus du seuil .5 sans affecter les autres fractions.
    """

    def test_arrondi_arithmetique_fraction_basse(self):
        """Fraction < 0.5 : arrondi inférieur.

        La loi arrondit correctement → round(1.49) = 1, round(1.49+0.001) = 1.
        Le +0.001 ne fausse PAS l'arrondi des fractions inférieures.
        """
        # n=17 : (40*17)/500 = 1.36 → 1h
        org = Organization(employee_count=17)
        assert org.weekly_credit_hours == 1

    def test_arrondi_arithmetique_fraction_haute(self):
        """Fraction ≥ 0.5 : arrondi supérieur.

        La loi arrondit correctement → round(1.6) = 2, round(1.6+0.001) = 2.
        Le +0.001 ne fausse PAS l'arrondi des fractions non-ambiguës.
        """
        # n=23 : (40*23)/500 = 1.84 → 2h
        org = Organization(employee_count=23)
        assert org.weekly_credit_hours == 2

    def test_demo_banker_rounding_probleme(self):
        """Démontre pourquoi le +0.001 est nécessaire.

        Sans le +0.001, Python utiliserait banker's rounding : round(2.5)=2
        alors que la loi exige 3. Ce test ne teste PAS le code directement
        mais documente le besoin du workaround dans organization.py:round(h+0.001).
        """
        # Vérification : si jamais quelqu'un retire le +0.001, ce test
        # documente que Python a un comportement d'arrondi non conforme.
        # round(2.5) en banker's rounding = 2, pas 3.
        assert round(2.5) == 2, (
            "Python utilise banker's rounding : round(2.5)=2. "
            "Le code utilise round(h+0.001) pour contourner cela."
        )
        # round(2.5 + 0.001) = round(2.501) = 3, conforme à la loi.
        assert round(2.5 + 0.001) == 3, (
            "Le workaround round(h+0.001) corrige l'arrondi banquier : attendu 3."
        )

    def test_formule_produit_aucune_valeur_exacte_demie(self):
        """Vérification structurelle : les formules (40*n)/500 et (40*n)/250
        ne produisent jamais une valeur exactement .5 pour n entier.

        Cela signifie qu'en pratique le +0.001 n'est jamais sollicité pour
        corriger un vrai cas ambigu, mais il sert de filet de sécurité
        contre les imprécisions flottantes et les futures modifications.
        """
        # (40*n)/500 = 0.08*n. 0.08*n ≡ 0.5 mod 1 → n ≡ 6.25 mod 12.5 → n non entier.
        # (40*n)/250 = 0.16*n. 0.16*n ≡ 0.5 mod 1 → n ≡ 3.125 mod 6.25 → n non entier.
        for n in range(15, 249):
            h_brut = (40 * n) / (500 if n < 150 else 250)
            reste = h_brut - int(h_brut)
            # Aucune valeur ne devrait être exactement 0.5 à 3 décimales près
            assert abs(reste - 0.5) > 0.001, (
                f"n={n} produit un crédit brut de {h_brut} dont la fraction "
                f"est proche de 0.5. Le +0.001 serait nécessaire pour cet effectif."
            )
