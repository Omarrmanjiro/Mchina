from data.cities import cities
#Graph representation of the cities and their connections with distances
graph = {
    "Casablanca": [
        ("Rabat", 90),
        ("Marrakech", 240)
    ],

    "Rabat": [
        ("Casablanca", 90),
        ("Kenitra", 40),
        ("Fes", 210)
    ],

    "Kenitra": [
        ("Rabat", 40),
        ("Tangier", 200)
    ],

    "Tangier": [
        ("Kenitra", 200),
        ("Tetouan", 60)
    ],

    "Tetouan": [
        ("Tangier", 60)
    ],

    "Fes": [
        ("Rabat", 210),
        ("Oujda", 330),
        ("Marrakech", 530)
    ],

    "Oujda": [
        ("Fes", 330)
    ],

    "Marrakech": [
        ("Casablanca", 240),
        ("Fes", 530),
        ("Agadir", 250)
    ],

    "Agadir": [
        ("Marrakech", 250)
    ]
}