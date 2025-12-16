import asyncio
from typing import TypedDict, Annotated

from google import genai
from langchain_core.messages import HumanMessage, SystemMessage
from sentence_transformers import SentenceTransformer

import app.ExtractEntity as ee
import json
import os
from langgraph.graph import StateGraph, START, END, add_messages
from langchain_neo4j import Neo4jGraph
from difflib import SequenceMatcher

import app.TreeByModel as tbm
import re

from dotenv import load_dotenv


neo4j_graph = None
model = SentenceTransformer('all-MiniLM-L6-v2')
gemini_api_key = ""

sentence = []
elenco_triple = []


class State(TypedDict, total=False):
    text_user: list
    tree: list
    entities: list
    question: bool
    sentence: list
    query: str
    params: dict


def itera_e_analizza(nodo, entities):
    if nodo['text'] in entities:
        nodo['isEntity'] = "true"
    else:
        nodo['isEntity'] = "false"

    if 'isEntity' in nodo:
        chiavi_ordinate = ['text', 'lemma', 'pos', 'dep', 'isEntity']

        if 'children' in nodo:
            chiavi_ordinate.append('children')

        chiavi_esistenti = list(nodo.keys())

        for chiave in chiavi_esistenti:
            if chiave not in chiavi_ordinate:
                chiavi_ordinate.append(chiave)

        nodo_ordinato = {k: nodo[k] for k in chiavi_ordinate if k in nodo}
        nodo.clear()
        nodo.update(nodo_ordinato)

    if 'children' in nodo and nodo['children']:
        for figlio in nodo['children']:
            itera_e_analizza(figlio, entities)


def set_sentence(sent):
    global sentence
    sentence = [sent]
    asyncio.run(run_graph())
    return elenco_triple

def run_pipeline(neograph, api_key, _frase_):
    global neo4j_graph
    neo4j_graph = neograph
    global gemini_api_key
    gemini_api_key = api_key
    return set_sentence(_frase_)


async def init(state: State):
    return {"sentence": sentence}


async def generateTree(state: State):
    msg = state["sentence"][-1].content
    tree = await asyncio.to_thread(tbm.genera_triple, [msg], gemini_api_key)
    return {"tree": tree}


async def generateEntities(state: State):
    msg = state["sentence"][-1].content
    entities = await asyncio.to_thread(ee.extract_entity, [msg])
    return {"entities": entities}


def combineResults(state: State):
    tree = state["tree"]
    entities = state["entities"]

    if tree:
        root_node = tree[0]
        itera_e_analizza(root_node, entities)

    json_finale = json.dumps(tree, indent=2)


async def createGraphSentence(state: State):
    text_user = [state["sentence"][-1].content]
    tree = state["tree"]
    mapping = {
        "chi?": "SUBJECT",  # chi compie l'azione
        "a chi?": "TARGET",  # destinatario dell'azione
        "con chi?": "ASSOCIATED_WITH",  # relazione di collaborazione
        "per chi?": "BENEFITS",  # azione fatta per qualcuno
        "cosa?": "OBJECT",  # oggetto dell'azione
        "con cosa?": "USES",  # strumento usato
        "di cosa?": "ABOUT",  # argomento o contenuto
        "dove?": "LOCATED_IN",  # luogo
        "da dove?": "ORIGINATES_FROM",  # provenienza
        "verso dove?": "DIRECTED_TO",  # destinazione
        "quando?": "OCCURS_AT",  # tempo puntuale
        "per quanto tempo?": "DURATION",  # durata
        "da quando?": "STARTS_AT",  # inizio
        "fino a quando?": "ENDS_AT",  # fine
        "come?": "MANNER",  # modo d'azione
        "in quale maniera?": "MANNER",  # sinonimo di "come?"
        "perché?": "CAUSES",  # causa o motivazione
        "a quale scopo?": "AIMS_TO",  # scopo intenzionale
        "per quale motivo?": "MOTIVATED_BY",  # motivazione più generica
        "quanto?": "AMOUNT",  # quantità
        "quante volte?": "FREQUENCY",  # frequenza
        "in quali condizioni?": "UNDER_CONDITIONS",  # condizioni generali
        "in quale situazione?": "CONTEXT",  # contesto specifico
        "sotto quali circostanze?": "CIRCUMSTANCES"  # situazione straordinaria
    }

    for f, t in zip(text_user, tree):
        clean_output = re.sub(r"^```json\s*|\s*```$", "", t.strip(), flags=re.DOTALL)

        data = json.loads(clean_output)

        # Costruzione delle triple
        triple = []

        for item in data:
            soggetto = item["soggetto"]
            verbo = item["verbo"]
            if verbo == "":
                verbo = "UNKNOWN"
            risposte = item.get("risposte", {})
            if risposte:  # se ci sono risposte
                for domanda, risposta in risposte.items():
                    triple.append((soggetto, verbo, risposta, mapping.get(domanda)))
            else:  # se non ci sono risposte
                triple.append((soggetto, verbo, "UNKNOWN", "UNKNOWN"))  # oppure "" / "OBJECT" come default

        # Stampa del risultato
        for tr in triple:
            print(tr)

        global elenco_triple
        elenco_triple = triple

    return {"tree": triple}


async def createEntityAndRelationWithTree(state: State):
    text_user = [state["sentence"][-1].content]
    entities = state["entities"]
    tree = state["tree"]
    if isinstance(state["sentence"][-1], HumanMessage):
        agent = "User"
        type_message = "SENTENCE"
    elif isinstance(state["sentence"][-1], SystemMessage):
        agent = "System"
        type_message = "SENTENCE"
    else:
        agent = "System"
        type_message = "INTERPRETATION"

    f = text_user[-1]
    e = entities[-1]

    # Calcola embedding per ogni entità menzionata nella frase
    entities_with_embeddings = []
    for ent in e:
        document_embedding = model.encode(ent).tolist()
        entities_with_embeddings.append({
            "name": ent,
            "embedding": document_embedding
        })

    # Cicla sulle triple (soggetto, verbo, oggetto)
    # for trip_set in tree:
    obj_entities = []
    for s, v, o, a in tree:

        if o is None:
            continue

        # Calcola anche l'embedding per l'action (verbo)
        action_embedding = model.encode(v).tolist()
        extracted = ee.extract_entity([o])
        if extracted and isinstance(extracted[0], list):
            extracted = [item for sublist in extracted for item in sublist]
        obj_entities.append({
            "object": o,
            "entities": extracted
        })

    query = f"""
            CALL apoc.cypher.doIt(
          'MERGE (sent:' + $type_message + ' {{text: $sentence}})
          RETURN sent',{{type_message: $type_message, sentence: $sentence}}) YIELD value
    WITH value.sent AS sent, $entities AS ents, $trip as trips, $obj_entities as obj_entities,
         $threshold AS threshold, $action_embedding AS action_embedding
    // --- ENTITÀ DELLA FRASE ---
    UNWIND ents AS ent
        MERGE (e:ENTITY {{name: ent.name}})
        MERGE (emb:ENTITY:EMBEDDING {{id: ent.name + "_embedding"}})
        SET emb.embedding = ent.embedding
        MERGE (sent)-[r1:REFERS_TO]->(e)
        ON CREATE SET r1.count = 1
        ON MATCH SET r1.count = r1.count + 1
        MERGE (e)-[r2:HAS_EMBEDDING]->(emb)
        ON CREATE SET r2.count = 1
        ON MATCH SET r2.count = r2.count + 1
    WITH collect(e) AS entities, trips, threshold, action_embedding, sent, obj_entities
    // --- STRUTTURA SVO ---
    UNWIND trips AS trip
    MERGE (subj:ENTITY {{name: trip[0]}})
    MERGE (action:ACTION {{name: trip[1]}})
    MERGE (obj:COMPLEMENTS {{name: trip[2]}})
    // --- EMBEDDING DELL’ACTION ---
    MERGE (aemb:ACTION:EMBEDDING {{id: trip[1] + "_embedding"}})
    SET aemb.embedding = action_embedding
    MERGE (ag:AGENT {{name: $agent}})
    MERGE (ag)-[r3:WRITES]->(sent)
    ON CREATE SET r3.count = 1
    ON MATCH SET r3.count = r3.count + 1
    MERGE (action)-[r4:HAS_EMBEDDING]->(aemb)
    ON CREATE SET r4.count = 1
    ON MATCH SET r4.count = r4.count + 1
    MERGE (subj)-[r5:ACTS]->(action)
    ON CREATE SET r5.count = 1
    ON MATCH SET r5.count = r5.count + 1
    WITH action, trip, obj, obj_entities
    CALL apoc.merge.relationship(action,trip[3],{{}},{{}},obj) YIELD rel
    SET rel.count = coalesce(rel.count,0) + 1
    WITH obj_entities
    UNWIND $obj_entities AS obj_map
    MERGE (ob:COMPLEMENTS {{name: obj_map.object}})
    WITH obj_map, ob
    UNWIND obj_map.entities AS entita
    MERGE (e:ENTITY {{name: entita}})
    MERGE (ob)-[r6:CONTAINS]->(e)
    ON CREATE SET r6.count = 1
    ON MATCH SET r6.count = r6.count + 1
    RETURN ob
    """


    params = {
        "sentence": f,
        "entities": entities_with_embeddings,
        "trip": tree,
        "action_embedding": action_embedding,
        "threshold": 0.8,
        "agent": agent,
        "obj_entities": obj_entities,
        "type_message": type_message
    }

    return {"query": query, "params": params}


async def executeQuery(state: State):
    query = state["query"]
    params = state["params"]
    neo4j_graph.query(query, params=params)
    query_delte_unknown = """MATCH (j)
                            WHERE j.name = "UNKNOWN" OR j.id = "UNKNOWN_embedding"
                            DETACH DELETE j"""
    neo4j_graph.query(query_delte_unknown)

    print("Inserita a DB frase:", f)


graph_builder = StateGraph(State)
graph_builder.add_node("init", init)
graph_builder.add_node("generateTree", generateTree)
graph_builder.add_node("generateEntities", generateEntities)
graph_builder.add_node('createGraphSentence', createGraphSentence)
graph_builder.add_node('createEntityAndRelationWithTree', createEntityAndRelationWithTree)
graph_builder.add_node('executeQuery', executeQuery)

graph_builder.add_edge(START, "init")
graph_builder.add_edge("init", "generateTree")
graph_builder.add_edge("init", "generateEntities")
graph_builder.add_edge("generateTree", "createGraphSentence")
graph_builder.add_edge('generateEntities', 'createGraphSentence')
graph_builder.add_edge('createGraphSentence', 'createEntityAndRelationWithTree')
graph_builder.add_edge('createEntityAndRelationWithTree', 'executeQuery')

graph = graph_builder.compile()

try:
    img_bytes = graph.get_graph().draw_mermaid_png()  # salva su file
    with open("update_graph_schema.png", "wb") as f:
        f.write(img_bytes)
except Exception as e:
    (
        print("⚠️ Errore durante il salvataggio:", e))


async def run_graph():
    # Stato iniziale vuoto
    initial_state = {}

    # Opzionale: puoi abilitare il tracciamento LangSmith se vuoi
    config = {
        # "configurable": {"thread_id": "some_id"},  # se vuoi abilitare il tracciamento
    }

    # Esegui il grafo (passando lo stato iniziale e il config)
    final_state = await graph.ainvoke(initial_state, config=config)



if __name__ == '__main__':
    frase = HumanMessage(content="Giulia ha consegnato la tesi al professore prima di partire per Londra, dove inizierà uno stage in una grande azienda tecnologica")
    set_sentence(frase)
