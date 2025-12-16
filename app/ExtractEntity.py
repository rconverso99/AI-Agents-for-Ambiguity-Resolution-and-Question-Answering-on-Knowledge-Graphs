import spacy

# Carica il modello italiano
nlp = spacy.load("it_core_news_sm")

def extract_entity(frasi):
    entita_testo = []

    for frase in frasi:
        doc = nlp(frase)

        # Ottieni tutte le entità (nomi propri, luoghi, ecc.)
        entita_frase = []
        for ent in doc.ents:
            entita_frase.append(ent.text)


        # Estrai tutti i sostantivi (NOUN) che NON sono sottostringhe di un'entità

        for token in doc:
            if token.pos_ == "NOUN":
                # Controlla se il token NON è parte di un'entità già estratta
                if not any(token.text in ent for ent in entita_frase):
                    entita_frase.append(token.text)

        entita_testo.append(entita_frase)

    return entita_testo


def extract_entityLongText(text: str) -> str:

    righe = [r.strip() for r in text.split('.') if r.strip()]

    i = 1
    entities = ""
    for riga in righe:
        ent = extract_entity([riga])[0]
        entities = entities + str(i) + ". " + ", ".join(ent) + "\n"
        i += 1

    #print("\n", entities)
    return entities







if __name__ == '__main__':
    frasi = ["Io Ieri sera, con grande emozione, ho raccontato a Marco la storia della mia famiglia in biblioteca, con l’aiuto di un vecchio libro di legno, per fargli capire l’importanza delle sue origini."]

    a = extract_entity(frasi)
    print(a)
