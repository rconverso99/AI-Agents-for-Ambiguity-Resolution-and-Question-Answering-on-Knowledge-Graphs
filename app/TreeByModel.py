from google import genai


# Configura la chiave API
def genera_triple(frasi, apikey):
    tree = []
    for frase in frasi:

        system_message = (
            f"""Ti verranno fornite delle frasi in italiano, il tuo compito sarà quello di generare una struttura semantica che rappresenti le informazioni chiave di una frase.
            Regola: Se il campo è null non lo riportare. Se nella frase non è presente il verbo o il soggetto inserisci lo stesso il campo ma con una stringa vuota.
            Gli unici tag consentiti sono:
            [{{
          "soggetto": null,
          "verbo": null,
          "risposte": {{
            "chi?": null,
            "a chi?": null,
            "con chi?": null,
            "per chi?": null,
            "cosa?": null,
            "con cosa?": null,
            "di cosa?": null,
            "dove?": null,
            "da dove?": null,
            "verso dove?": null,
            "quando?": null,
            "per quanto tempo?": null,
            "da quando?": null,
            "fino a quando?": null,
            "come?": null,
            "in quale maniera?": null,
            "perché?": null,
            "a quale scopo?": null,
            "per quale motivo?": null,
            "quanto?": null,
            "quante volte?": null,
            "in quali condizioni?": null,
            "in quale situazione?": null,
            "sotto quali circostanze?": null
            }}
            }}]
            Esempio:
            Frase: Riccardo mangia una mela, dopo Riccardo va a correre nel parco che è chiuso dal 2019.
            Struttura: [{{'soggetto': 'Riccardo', 'verbo': 'mangiare', 'risposte': {{['cosa?': 'mela']}}}}
            {{'soggetto': 'Riccardo', 'verbo': 'andare a correre', 'risposte': {{['quando?': 'dopo'], ['dove?': 'parco']}}
            {{'soggetto': 'parco', 'verbo': 'essere chiuso', 'risposte': {{['da quando?': 'dal 2019']}}
            }}]
            Frase: Francesco.
            Struttura: [{{'soggetto': 'Francesco', 'verbo': '', 'risposte': {{}}}}]
            \n\n
            Frase:{frase}
            \n
            Struttura:
            """
        )
        client = genai.Client(api_key=apikey)
        result = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[system_message]
        )
        new_text = result.text
        tree.append(new_text)

    return tree


if __name__ == '__main__':
    frasi = ["Antonio mangia una mela"]
    tree = genera_triple(frasi)
    print(tree)
